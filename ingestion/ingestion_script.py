# ingestion/ingestion_script.py
import os
import sys
import logging
import re
import base64
import hashlib
import time
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.fernet import Fernet
from amazonorders.session import AmazonSession
from amazonorders.orders import AmazonOrders
from amazonorders.transactions import AmazonTransactions
from amazonorders.exception import AmazonOrdersError
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor

# Use a named logger for better context
logger = logging.getLogger(__name__)

# --- Global Fernet instance for Encryption/Decryption ---
fernet = None

def initialize_fernet():
    """Initializes the global Fernet instance using the encryption key."""
    global fernet
    if fernet: return
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    if not encryption_key: raise ValueError("ENCRYPTION_KEY is not set.")
    key_digest = hashlib.sha256(encryption_key.encode('utf-8')).digest()
    derived_key = base64.urlsafe_b64encode(key_digest)
    fernet = Fernet(derived_key)

def decrypt_value(encrypted_bytes):
    """Decrypts a byte string using the global Fernet instance."""
    if not isinstance(encrypted_bytes, (bytes, memoryview)):
        raise TypeError("Encrypted value must be in bytes or memoryview format.")
    return fernet.decrypt(bytes(encrypted_bytes)).decode('utf-8')

def get_settings(user_id):
    """Fetches, validates, and decrypts settings for a given user."""
    logger.info(f"Fetching settings for user_id: {user_id}...")
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT amazon_email, amazon_password_encrypted, amazon_otp_secret_key FROM user_settings WHERE user_id = %s",
            (user_id,)
        )
        settings_row = cur.fetchone()

    if not settings_row: raise ValueError(f"Settings not found for user {user_id}.")
    amazon_email, encrypted_password, amazon_otp_secret_key = settings_row
    if not amazon_email or not encrypted_password: raise ValueError("Amazon credentials are not fully configured.")

    decrypted_password = decrypt_value(encrypted_password)
    return {
        'AMAZON_EMAIL': amazon_email,
        'AMAZON_PASSWORD': decrypted_password,
        'AMAZON_OTP_SECRET_KEY': amazon_otp_secret_key or None
    }

def extract_asin(url):
    """Extracts the ASIN from an Amazon product URL."""
    if not url: return None
    match = re.search(r'/(dp|gp/product)/(\w{10})', url)
    return match.group(2) if match else None

def main(user_id, manual_days_override=None):
    """
    Generator function to run the ingestion process and yield progress events.
    :param user_id: The UUID of the user for whom to run ingestion.
    :param manual_days_override: An integer specifying the number of days to fetch.
    """
    try:
        initialize_fernet()
        settings = get_settings(user_id)
        
        days_to_fetch = 0
        if manual_days_override is not None:
            days_to_fetch = manual_days_override
            yield "status", f"Manual override: Fetching orders for the last {days_to_fetch} days."
        else:
            with get_db_cursor() as cur:
                cur.execute("SELECT MAX(order_placed_date) FROM orders")
                last_order_date = cur.fetchone()[0]
            if last_order_date:
                days_to_fetch = (date.today() - last_order_date).days
                yield "status", f"Incremental update: Fetching orders for the last {days_to_fetch} days."
            else:
                days_to_fetch = 60
                yield "status", f"Initial import: Fetching orders for the last {days_to_fetch} days."

        if days_to_fetch <= 0:
            yield "status", "All orders are up to date."
            return

        yield "status", f"Logging into Amazon as {settings['AMAZON_EMAIL']}..."
        session = AmazonSession(
            username=settings['AMAZON_EMAIL'],
            password=settings['AMAZON_PASSWORD'],
            otp_secret_key=settings.get('AMAZON_OTP_SECRET_KEY')
        )
        session.login()
        yield "status", "Amazon login successful."

        amazon_transactions = AmazonTransactions(session)
        yield "status", f"Fetching transactions for the last {days_to_fetch} days..."
        transactions = amazon_transactions.get_transactions(days=days_to_fetch)
        
        order_numbers = {t.order_number for t in transactions if t.order_number}

        if not order_numbers:
            yield "status", "No new orders found in the specified date range."
            session.logout()
            return
        
        total_orders = len(order_numbers)
        yield "progress", {"value": 0, "max": total_orders}
        yield "status", f"Found {total_orders} unique orders to process..."

        amazon_orders = AmazonOrders(session)
        processed_count = 0

        def fetch_order_with_retries(order_num):
            """Fetches an order with retry logic, following the reference app's direct method."""
            for attempt in range(3):
                try:
                    # --- CORRECTED LOGIC: Use the simple get_order call as per your working application ---
                    return amazon_orders.get_order(order_id=order_num)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} for order {order_num} failed: {e}")
                    if attempt < 2: time.sleep(2)
            logger.error(f"All retries failed for order {order_num}.")
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_order = {executor.submit(fetch_order_with_retries, num): num for num in order_numbers}
            
            with get_db_cursor(commit=True) as cur:
                for future in as_completed(future_to_order):
                    order = future.result()
                    processed_count += 1
                    yield "progress", {"value": processed_count, "max": total_orders}

                    if not order or not order.items: continue

                    try:
                        is_subscribe_and_save_order = order.subscription_discount is not None
                        
                        cur.execute("""
                            INSERT INTO orders (order_id, user_id, order_placed_date, grand_total, subscription_discount, recipient_name)
                            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (order_id) DO NOTHING;
                        """, (order.order_number, user_id, order.order_placed_date, order.grand_total, order.subscription_discount, order.recipient.name if order.recipient else None))

                        for item in order.items:
                            cur.execute("""
                                INSERT INTO items (order_id, asin, full_title, link, thumbnail_url, quantity, price_per_unit, is_subscribe_and_save)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (order_id, full_title, price_per_unit) DO UPDATE SET
                                    is_subscribe_and_save = EXCLUDED.is_subscribe_and_save,
                                    thumbnail_url = EXCLUDED.thumbnail_url;
                            """, (
                                order.order_number, extract_asin(item.link), item.title,
                                f"https://www.amazon.com{item.link}" if item.link else None,
                                item.image_link,
                                item.quantity or 1, item.price, is_subscribe_and_save_order
                            ))
                    except Exception as e:
                        logger.error(f"Failed to process order {order.order_number} in DB: {e}", exc_info=True)

        yield "status", "Successfully processed all fetched orders."
        session.logout()
        yield "status", "Ingestion process completed."
        yield "done", "Import complete."

    except Exception as e:
        logger.error(f"An unexpected error occurred during ingestion: {e}", exc_info=True)
        yield "error", str(e)

# --- Standalone Execution Logic ---
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    
    parser = argparse.ArgumentParser(description="Run the Amazon order ingestion script.")
    parser.add_argument("--days", type=int, help="Number of days of orders to fetch.")
    args = parser.parse_args()

    def console_progress_callback(event, payload):
        if event == "status":
            print(f"STATUS: {payload}")
        elif event == "progress":
            print(f"PROGRESS: {payload['value']}/{payload['max']}")
        elif event == "error":
            print(f"ERROR: {payload}", file=sys.stderr)
        elif event == "done":
            print(f"STATUS: {payload}")

    try:
        # For standalone script execution, we default to the admin user.
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            admin = cursor.fetchone()
            if not admin:
                print("ERROR: No admin user found. Cannot run ingestion.", file=sys.stderr)
                sys.exit(1)
            admin_id = admin[0]
            
        for event, payload in main(user_id=admin_id, manual_days_override=args.days):
             console_progress_callback(event, payload)
    except Exception as e:
        print(f"Script failed with a critical error: {e}", file=sys.stderr)
        sys.exit(1)
