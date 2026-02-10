import logging
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from datetime import datetime
from backend.shared.db import get_db_cursor
from backend.api.services.notification_service import send_price_drop_notification
import re

logger = logging.getLogger(__name__)

def get_amazon_price(url):
    """
    Scrapes the price of an Amazon product from the given URL.
    Returns a tuple (price, name, currency).
    """
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')

        # Check for CAPTCHA or blocking
        page_title_text = soup.title.string.strip() if soup.title else ""
        if "CAPTCHA" in page_title_text or "Robot Check" in page_title_text:
            logger.warning(f"CAPTCHA detected for URL: {url}")
            return None, None, None

        # 1. Extract Title
        title = None

        # Priority 1: Main product title element
        title_element = soup.select_one('#productTitle')
        if title_element:
            title = title_element.get_text(strip=True)

        # Priority 2: Meta title
        if not title:
            meta_title = soup.select_one('meta[name="title"]')
            if meta_title:
                title = meta_title.get('content')

        # Priority 3: OG Title
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title:
                title = og_title.get('content')

        # Priority 4: H1 (sometimes used on mobile or different layouts)
        if not title:
            h1_title = soup.select_one('h1')
            if h1_title:
                title = h1_title.get_text(strip=True)

        # Priority 5: Fallback to page title, cleaning up "Amazon.com: " prefix/suffix
        if not title:
            if page_title_text:
                # Remove "Amazon.com: " or " : Amazon.com"
                clean_title = page_title_text.replace("Amazon.com: ", "").replace(" : Amazon.com", "").strip()
                if clean_title:
                    title = clean_title

        if not title:
            title = "Unknown Product"
            logger.warning(f"Could not extract title for URL: {url}. Page Title was: {page_title_text}")

        # 2. Extract Price
        # Try multiple selectors for price
        # .a-price .a-offscreen is common for the main price
        price_element = soup.select_one('.a-price .a-offscreen')
        if not price_element:
            price_element = soup.select_one('#priceblock_ourprice')
        if not price_element:
            price_element = soup.select_one('#priceblock_dealprice')
        if not price_element:
            # Sometimes price is in a span with class a-price-whole
            price_whole = soup.select_one('.a-price-whole')
            price_fraction = soup.select_one('.a-price-fraction')
            if price_whole and price_fraction:
                whole = price_whole.get_text(strip=True).rstrip('.')
                fraction = price_fraction.get_text(strip=True)
                price_text = f"{whole}.{fraction}"
            elif price_whole:
                price_text = price_whole.get_text(strip=True)
            else:
                price_text = None
        else:
            price_text = price_element.get_text(strip=True)

        price = None
        currency = '$' # Default

        if price_text:
            # Remove currency symbol and parse float
            # Example: $19.99 -> 19.99
            # Example: 1,234.56 -> 1234.56
            # Remove non-numeric chars except dot
            # But we might have commas.
            # Assuming US locale for Amazon.com
            clean_price_text = re.sub(r'[^\d.]', '', price_text)
            try:
                # If there are multiple dots (e.g. from some weird formatting), handle it?
                # Usually it's fine.
                price = float(clean_price_text)
            except ValueError:
                logger.warning(f"Could not parse price from text: {price_text}")

        if price is None:
            logger.warning(f"Could not find price for URL: {url}")

        return price, title, currency

    except requests.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"Error parsing page {url}: {e}")
        return None, None, None

def update_all_prices():
    """
    Fetches all tracked items from the database and updates their current price.
    This function is intended to be run by the scheduler.
    """
    logger.info("Starting scheduled price update for tracked items...")

    try:
        # Fetch all items first to keep the transaction short
        items = []
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, url, user_id, notification_threshold_type, notification_threshold_value, name, is_custom_name
                FROM tracked_items
            """)
            items = cur.fetchall() # List of tuples

        if not items:
            logger.info("No items to track.")
            return

        for item_data in items:
            item_id = item_data[0]
            url = item_data[1]
            user_id = item_data[2]
            threshold_type = item_data[3]
            threshold_value = item_data[4]
            current_name = item_data[5]
            is_custom_name = item_data[6]

            logger.info(f"Updating price for item {item_id} ({url})...")
            price, title, _ = get_amazon_price(url)

            if is_custom_name and current_name:
                # If name is custom, keep the existing name
                title = current_name
            else:
                # If title was not found, fallback to existing name or "Unknown Product"
                if not title and current_name:
                    title = current_name
                elif not title:
                    title = "Unknown Product"

            if price is not None:
                try:
                    with get_db_cursor(commit=True) as cur:
                        # Fetch last entry before update to check price change
                        cur.execute("""
                            SELECT price, recorded_at
                            FROM price_history
                            WHERE tracked_item_id = %s
                            ORDER BY recorded_at DESC
                            LIMIT 1
                        """, (item_id,))
                        last_entry = cur.fetchone()

                        last_price = float(last_entry[0]) if last_entry else None
                        last_recorded_at = last_entry[1] if last_entry else None

                        # Update current price and last checked timestamp
                        cur.execute("""
                            UPDATE tracked_items
                            SET current_price = %s, last_checked = NOW(), name = COALESCE(%s, name)
                            WHERE id = %s
                        """, (price, title, item_id))

                        should_insert = False
                        if not last_entry:
                            should_insert = True
                        else:
                            if price != last_price:
                                should_insert = True
                            else:
                                # Insert if the last entry was not today
                                if last_recorded_at.date() < datetime.now().date():
                                    should_insert = True

                        if should_insert:
                            cur.execute("""
                                INSERT INTO price_history (tracked_item_id, price)
                                VALUES (%s, %s)
                            """, (item_id, price))
                            logger.info(f"Updated price for item {item_id} to {price} (History added)")
                        else:
                            logger.info(f"Updated price for item {item_id} to {price} (History skipped - same price same day)")

                        # Notification Logic
                        if last_price is not None and price < last_price:
                            should_notify = False
                            price_change = price - last_price
                            price_change_percent = (price_change / last_price) * 100

                            # Check threshold if configured
                            if threshold_value is not None:
                                if threshold_type == 'percent':
                                    if abs(price_change_percent) >= float(threshold_value):
                                        should_notify = True
                                elif threshold_type == 'absolute':
                                    if abs(price_change) >= float(threshold_value):
                                        should_notify = True

                            if should_notify:
                                # Fetch user's webhook URL
                                cur.execute("SELECT price_change_notification_webhook_url FROM user_settings WHERE user_id = %s", (user_id,))
                                settings_row = cur.fetchone()
                                webhook_url = settings_row[0] if settings_row else None

                                if webhook_url:
                                    send_price_drop_notification(
                                        webhook_url,
                                        item_name=title,
                                        current_price=price,
                                        previous_price=last_price,
                                        url=url
                                    )

                except Exception as e:
                    logger.error(f"Failed to update database for item {item_id}: {e}")
            else:
                logger.warning(f"Failed to fetch price for item {item_id}")
                try:
                    with get_db_cursor(commit=True) as cur:
                        cur.execute("""
                            UPDATE tracked_items
                            SET last_checked = NOW()
                            WHERE id = %s
                        """, (item_id,))
                except Exception as e:
                    logger.error(f"Failed to update last_checked for item {item_id}: {e}")

        logger.info("Finished scheduled price update.")

    except Exception as e:
        logger.error(f"Error during price update job: {e}")
