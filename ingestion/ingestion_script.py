# ingestion/ingestion_script.py
import os
import sys
import logging
import re
import base64
import hashlib
import time
import argparse
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.fernet import Fernet
from amazonorders.session import AmazonSession
from amazonorders.orders import AmazonOrders
from amazonorders.transactions import AmazonTransactions
from amazonorders.exception import AmazonOrdersError
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor, init_pool as init_db_pool

# Use a named logger for better context
logger = logging.getLogger(__name__)

# --- Global Fernet instance for Encryption/Decryption ---
fernet = None

def initialize_fernet():
    """Initializes the global Fernet instance using the encryption key."""
    global fernet
    if fernet:
        return
    logger.info("Initializing Fernet for decryption...")
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set in the environment variables.")
    key_digest = hashlib.sha256(encryption_key.encode('utf-8')).digest()
    derived_key = base64.urlsafe_b64encode(key_digest)
    fernet = Fernet(derived_key)

def decrypt_value(encrypted_bytes):
    """Decrypts a byte string using the global Fernet instance."""
    if not isinstance(encrypted_bytes, bytes):
        raise TypeError("Encrypted value must be in bytes format for decryption.")
    return fernet.decrypt(encrypted_bytes).decode('utf-8')

def get_settings():
    """Fetches, validates, and decrypts settings for the admin user."""
    logger.info("Fetching settings for ingestion script...")
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        admin_user = cur.fetchone()
        if not admin_user:
            raise ValueError("Critical: No admin user found in the database.")
        admin_user_id = admin_user[0]
        
        cur.execute(
            "SELECT amazon_email, amazon_password_encrypted, amazon_otp_secret_key FROM user_settings WHERE user_id = %s",
            (admin_user_id,)
        )
        settings_row = cur.fetchone()

    if not settings_row:
        raise ValueError("Settings not found for the admin user. Please save settings on the Settings page.")
    
    amazon_email, encrypted_password, amazon_otp_secret_key = settings_row

    if not amazon_email:
        raise ValueError("Amazon Email is not configured in settings.")
    if not encrypted_password:
        raise ValueError("Amazon Password is not configured in settings.")

    decrypted_password = decrypt_value(bytes(encrypted_password))
    
    settings = {
        'AMAZON_EMAIL': amazon_email,
        'AMAZON_PASSWORD': decrypted_password,
        'AMAZON_OTP_SECRET_KEY': amazon_otp_secret_key or None
    }
    
    logger.info("Successfully loaded and decrypted settings for ingestion.")
    return settings

def extract_asin(url):
    """Extracts the ASIN from an Amazon product URL."""
    if not url: return None
    match = re.search(r'/(dp|gp/product)/(\w{10})', url)
    return match.group(2) if match else None

def fetch_order_with_retries(order_num, amazon_orders_instance):
    """Fetches a single order with retry logic."""
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    for attempt in range(MAX_RETRIES):
        try:
            return amazon_orders_instance.get_order(order_id=order_num)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} for order {order_num} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All retries failed for order {order_num}.")
                return e

def main(manual_days_override=None):
    """Main generator function to run the ingestion process and yield progress."""
    try:
        initialize_fernet()
        settings = get_settings()
        
        days_to_fetch = 0
        
        if manual_days_override is not None:
            days_to_fetch = manual_days_override
            yield "status", f"Manual override: Fetching last {days_to_fetch} days."
        else:
            with get_db_cursor() as cur:
                cur.execute("SELECT MAX(order_placed_date) FROM orders")
                last_order_date = cur.fetchone()[0]
            if last_order_date:
                days_to_fetch = (date.today() - last_order_date).days
                yield "status", f"Incremental update: Fetching last {days_to_fetch} days."
            else:
                days_to_fetch = 60
                yield "status", f"Initial import: Fetching last {days_to_fetch} days."

        if days_to_fetch <= 0:
            yield "status", "All orders are up to date."
            yield "done", True
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
            yield "status", "No new orders found."
            session.logout()
            yield "done", True
            return
        
        total_orders = len(order_numbers)
        yield "status", f"Found {total_orders} unique orders to process."
        yield "progress", {"value": 0, "max": total_orders}

        amazon_orders = AmazonOrders(session)
        processed_count = 0
        MAX_CONCURRENT_REQUESTS = 5

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            future_to_order_num = {
                executor.submit(fetch_order_with_retries, order_num, amazon_orders): order_num
                for order_num in order_numbers
            }

            with get_db_cursor(commit=True) as cur:
                for future in as_completed(future_to_order_num):
                    order_number = future_to_order_num[future]
                    try:
                        order = future.result()

                        if isinstance(order, Exception):
                            logger.error(f"Skipping order {order_number} due to fetch error: {order}")
                            continue
                        
                        if not order or not order.items:
                            logger.warning(f"Skipping order {order_number} as it has no items.")
                            continue

                        cur.execute("""
                            INSERT INTO orders (order_id, order_placed_date, grand_total, subscription_discount, recipient_name)
                            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (order_id) DO NOTHING;
                        """, (
                            order.order_number, order.order_placed_date, order.grand_total,
                            order.subscription_discount, order.recipient.name if order.recipient else None
                        ))

                        for item in order.items:
                            asin = extract_asin(item.link)
                            is_sns = getattr(item, 'is_subscribe_and_save', False)
                            quantity = item.quantity if item.quantity is not None else 1
                            
                            cur.execute("""
                                INSERT INTO items (order_id, asin, full_title, link, quantity, price_per_unit, is_subscribe_and_save)
                                VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING;
                            """, (
                                order.order_number, asin, item.title,
                                f"https://www.amazon.com{item.link}" if item.link else None,
                                quantity, item.price, is_sns
                            ))
                    except Exception as e:
                        logger.error(f"Failed to process and save order {order_number}: {e}", exc_info=True)
                    finally:
                        processed_count += 1
                        yield "progress", {"value": processed_count, "max": total_orders}

        session.logout()
        yield "status", "Ingestion complete."
        yield "done", True

    except Exception as e:
        logger.error(f"An error occurred during ingestion: {e}", exc_info=True)
        yield "error", str(e)
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Run the Amazon order ingestion script.")
    parser.add_argument('--days', type=int, help="Number of days of order history to fetch.")
    args = parser.parse_args()

    def console_progress_callback(event_type, data):
        print(f"[{event_type.upper()}] {data}")

    try:
        init_db_pool()
        for event_type, data in main(manual_days_override=args.days):
             console_progress_callback(event_type, data)
    except Exception as e:
        print(f"\nA critical error occurred: {e}")

