# ingestion/ingestion_script.py
import os
import sys
import logging
import re
import json
import requests
import hashlib
import base64
from datetime import date, timedelta
from cryptography.fernet import Fernet
from amazonorders.session import AmazonSession
from amazonorders.orders import AmazonOrders
from amazonorders.exception import AmazonOrdersError

# Add the project root to the Python path to allow importing from 'shared'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global Fernet instance for Encryption/Decryption ---
fernet = None

def initialize_fernet():
    """Initializes the global Fernet instance using the encryption key."""
    global fernet
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set in the environment variables.")
    
    # Derive a 32-byte key suitable for Fernet
    key_digest = hashlib.sha256(encryption_key.encode('utf-8')).digest()
    derived_key = base64.urlsafe_b64encode(key_digest)
    fernet = Fernet(derived_key)

def decrypt_value(encrypted_value):
    """Decrypts a value using the global Fernet instance."""
    if not fernet:
        initialize_fernet()
    return fernet.decrypt(bytes(encrypted_value)).decode()

def get_settings():
    """Fetches and decrypts settings from the database."""
    settings = {}
    required_keys = ['AMAZON_EMAIL', 'AMAZON_PASSWORD', 'OLLAMA_URL', 'OLLAMA_MODEL']
    
    logging.info("Fetching application settings from the database...")
    with get_db_cursor() as cur:
        cur.execute("SELECT key, value, is_encrypted FROM settings")
        db_settings = cur.fetchall()

    settings_map = {row[0]: (row[1], row[2]) for row in db_settings}

    for key in required_keys:
        if key not in settings_map:
            raise ValueError(f"Required setting '{key}' not found in the database.")
        
        value, is_encrypted = settings_map[key]
        if is_encrypted:
            settings[key] = decrypt_value(value)
        else:
            settings[key] = value

    # Optional key
    if 'AMAZON_OTP_SECRET_KEY' in settings_map:
        settings['AMAZON_OTP_SECRET_KEY'] = settings_map['AMAZON_OTP_SECRET_KEY'][0]
    
    logging.info("Successfully loaded settings.")
    return settings

def extract_asin(url):
    """Extracts the ASIN from an Amazon product URL."""
    if not url:
        return None
    match = re.search(r'/(dp|gp/product)/(\w{10})', url)
    return match.group(2) if match else None

def summarize_titles_bulk(titles, ollama_url, model_name):
    """Summarizes a list of product titles in batches using Ollama."""
    if not titles:
        return {}

    unique_titles = list(dict.fromkeys(titles))
    logging.info(f"Summarizing {len(unique_titles)} unique titles...")
    
    all_summaries = {}
    batch_size = 10
    num_batches = (len(unique_titles) + batch_size - 1) // batch_size
    
    for i in range(num_batches):
        batch_titles = unique_titles[i*batch_size : (i+1)*batch_size]
        logging.info(f"Processing batch {i+1} of {num_batches}...")

        prompt = f"""
        You are an expert product catalog summarizer. Your goal is to create a very short, human-readable summary for each product title provided. The summary must be strictly between 3 and 5 words.

        CRITICAL INSTRUCTIONS:
        1. Your output MUST be a single, valid JSON object.
        2. The JSON object must have a key for EVERY product title from the input list.
        3. The value for each key must be the new, summarized title.

        RULES:
        - Identify Core Product & Brand.
        - Combine and Refine (e.g., "Elmer's Clear Craft Glue").
        - Strictly Exclude sizes, weights, counts, marketing claims, and model numbers.

        Titles to Summarize:
        {json.dumps(batch_titles, indent=2)}
        """

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json"
        }

        try:
            response = requests.post(ollama_url, json=payload, timeout=90)
            response.raise_for_status()
            response_json = json.loads(response.json().get("message", {}).get("content", "{}"))
            all_summaries.update(response_json)
        except (requests.RequestException, json.JSONDecodeError) as e:
            logging.error(f"Failed to summarize batch {i+1}: {e}. Using original titles as fallback for this batch.")
            for title in batch_titles:
                all_summaries[title] = title

    return all_summaries

def main():
    """Main function to run the ingestion process."""
    try:
        settings = get_settings()
        
        # Determine the date range for fetching orders
        with get_db_cursor() as cur:
            cur.execute("SELECT MAX(order_placed_date) FROM orders")
            last_order_date = cur.fetchone()[0]

        if last_order_date:
            start_date = last_order_date + timedelta(days=1)
            logging.info(f"Found existing data. Fetching new orders from {start_date.isoformat()} to today.")
        else:
            start_date = date.today() - timedelta(days=365)
            logging.info("No existing data found. Fetching orders for the last year.")
        
        end_date = date.today()

        if start_date > end_date:
            logging.info("All orders are up to date. No new orders to fetch.")
            return

        # Fetch orders from Amazon
        logging.info(f"Logging into Amazon as {settings['AMAZON_EMAIL']}...")
        session = AmazonSession(
            username=settings['AMAZON_EMAIL'],
            password=settings['AMAZON_PASSWORD'],
            otp_secret_key=settings.get('AMAZON_OTP_SECRET_KEY')
        )
        session.login()
        logging.info("Amazon login successful.")

        amazon_orders = AmazonOrders(session)
        orders = amazon_orders.get_orders(start_date=start_date, end_date=end_date)
        
        order_list = list(orders)
        if not order_list:
            logging.info("No new orders found in the specified date range.")
            session.logout()
            return
            
        logging.info(f"Found {len(order_list)} new orders to process.")

        # Process and store data
        all_item_titles = [item.title for order in order_list for item in order.items]
        summaries = summarize_titles_bulk(all_item_titles, settings['OLLAMA_URL'], settings['OLLAMA_MODEL'])

        logging.info("Inserting new orders and items into the database...")
        with get_db_cursor(commit=True) as cur:
            for order in order_list:
                # Insert order (or do nothing if it already exists)
                cur.execute("""
                    INSERT INTO orders (order_id, order_placed_date, grand_total, subscription_discount, recipient_name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (order_id) DO NOTHING;
                """, (
                    order.order_number,
                    order.order_placed_date,
                    order.grand_total,
                    order.subscription_discount,
                    order.recipient.name if order.recipient else None
                ))
                
                # Insert items for the order
                for item in order.items:
                    asin = extract_asin(item.link)
                    short_title = summaries.get(item.title, item.title)
                    
                    cur.execute("""
                        INSERT INTO items (order_id, asin, full_title, short_title, link, quantity, price_per_unit, is_subscribe_and_save)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        order.order_number,
                        asin,
                        item.title,
                        short_title,
                        f"https://www.amazon.com{item.link}" if item.link else None,
                        item.quantity,
                        item.price,
                        item.is_subscribe_and_save
                    ))
            logging.info("Successfully inserted all new orders and items.")

        session.logout()
        logging.info("Ingestion process completed successfully.")

    except (ValueError, AmazonOrdersError) as e:
        logging.error(f"A configuration or authentication error occurred: {e}")
    except Exception:
        logging.exception("An unexpected error occurred during the ingestion process.")

if __name__ == "__main__":
    main()
