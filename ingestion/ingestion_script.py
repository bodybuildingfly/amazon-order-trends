# ingestion/ingestion_script.py
import os
import sys
import logging
import re
import base64
import hashlib
import time
import importlib
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from cryptography.fernet import Fernet
import amazonorders.session
import amazonorders.orders
import amazonorders.transactions
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
            """SELECT amazon_email, amazon_password_encrypted, amazon_otp_secret_key,
                      discord_webhook_url, discord_notification_preference
               FROM user_settings WHERE user_id = %s""",
            (user_id,)
        )
        settings_row = cur.fetchone()

    if not settings_row: raise ValueError(f"Settings not found for user {user_id}.")
    
    amazon_email, encrypted_password, amazon_otp_secret_key, webhook_url, notification_pref = settings_row
    
    if not amazon_email or not encrypted_password:
        raise ValueError("Amazon credentials are not fully configured.")

    decrypted_password = decrypt_value(encrypted_password)
    return {
        'AMAZON_EMAIL': amazon_email,
        'AMAZON_PASSWORD': decrypted_password,
        'AMAZON_OTP_SECRET_KEY': amazon_otp_secret_key or None,
        'DISCORD_WEBHOOK_URL': webhook_url,
        'DISCORD_NOTIFICATION_PREFERENCE': notification_pref or 'off'
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
    # Reload the library modules to ensure a clean state for each run.
    # This prevents issues where the library retains state from a previous
    # run in the same long-lived process.
    importlib.reload(amazonorders.session)
    importlib.reload(amazonorders.orders)
    importlib.reload(amazonorders.transactions)
    AmazonSession = amazonorders.session.AmazonSession
    AmazonOrders = amazonorders.orders.AmazonOrders
    AmazonTransactions = amazonorders.transactions.AmazonTransactions

    error_occurred = False
    settings = {}
    session = None

    def yield_and_log(event, message):
        """Yields an event and logs the message."""
        if event == "error":
            nonlocal error_occurred
            error_occurred = True
            logger.error(message)
        else:
            logger.info(message)
        
        yield event, message


    try:
        initialize_fernet()
        settings = get_settings(user_id)
        
        # Wrapper for yielding status and logging it
        def log_status(message):
            yield from yield_and_log("status", message)

        days_to_fetch = 0
        if manual_days_override is not None:
            days_to_fetch = manual_days_override
            yield from log_status(f"Manual override: Fetching orders for the last {days_to_fetch} days.")
        else:
            with get_db_cursor() as cur:
                cur.execute("SELECT MAX(order_placed_date) FROM orders WHERE user_id = %s", (user_id,))
                last_order_date = cur.fetchone()[0]
            if last_order_date:
                days_to_fetch = (date.today() - last_order_date).days
                yield from log_status(f"Incremental update: Fetching orders for the last {days_to_fetch} days.")
            else:
                days_to_fetch = 60
                yield from log_status(f"Initial import: Fetching orders for the last {days_to_fetch} days.")

        if days_to_fetch <= 0:
            yield from log_status("All orders are up to date.")
            return

        yield from log_status(f"Logging into Amazon as {settings['AMAZON_EMAIL']}...")
        session = AmazonSession(
            username=settings['AMAZON_EMAIL'],
            password=settings['AMAZON_PASSWORD'],
            otp_secret_key=settings.get('AMAZON_OTP_SECRET_KEY')
        )
        session.login()
        yield from log_status("Amazon login successful.")

        amazon_transactions = AmazonTransactions(session)
        yield from log_status(f"Fetching transactions for the last {days_to_fetch} days...")
        transactions = amazon_transactions.get_transactions(days=days_to_fetch)
        
        order_numbers = {t.order_number for t in transactions if t.order_number}

        if not order_numbers:
            yield from log_status("No new orders found in the specified date range.")
            return

        yield from log_status(f"Found {len(order_numbers)} orders in the date range. Checking for new orders to import...")
        
        with get_db_cursor() as cur:
            cur.execute("SELECT order_id FROM orders WHERE user_id = %s AND order_id = ANY(%s)", (user_id, list(order_numbers)))
            existing_orders = {row[0] for row in cur.fetchall()}
        
        if existing_orders:
            yield from log_status(f"Found {len(existing_orders)} orders already in the database. Filtering them out.")
            order_numbers.difference_update(existing_orders)

        if not order_numbers:
            yield from log_status("All orders are up to date. No new orders to import.")
            return
        
        total_orders = len(order_numbers)
        yield from yield_and_log("progress", {"value": 0, "max": total_orders})
        yield from log_status(f"Found {total_orders} new orders to process...")

        amazon_orders = AmazonOrders(session)
        processed_count = 0

        def fetch_order_with_retries(order_num):
            """Fetches an order with retry logic."""
            for attempt in range(3):
                try:
                    return amazon_orders.get_order(order_id=order_num)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} for order {order_num} failed: {e}")
                    if attempt < 2: time.sleep(2)
            
            nonlocal error_occurred
            error_occurred = True
            log_msg = f"All retries failed for order {order_num}."
            logger.error(log_msg)
            # This log is not passed up, so it won't be in the webhook. That's acceptable.
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
                                item.link,
                                item.image_link,
                                item.quantity or 1, item.price, is_subscribe_and_save_order
                            ))
                    except Exception as e:
                        yield from yield_and_log("error", f"Failed to process order {order.order_number} in DB: {e}")

        yield from log_status("Successfully processed all fetched orders.")
        yield "done", "Import complete."

    except Exception as e:
        # Use the logging wrapper to capture the exception
        yield from yield_and_log("error", f"An unexpected error occurred during ingestion: {e}")
    finally:
        if session:
            session.logout()
            yield from yield_and_log("status", "Amazon session logged out.")

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
