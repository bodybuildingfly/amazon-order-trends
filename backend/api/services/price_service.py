import logging
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from datetime import datetime
from backend.shared.db import get_db_cursor
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

        # 1. Extract Title
        title_element = soup.select_one('#productTitle')
        title = title_element.get_text(strip=True) if title_element else "Unknown Product"

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
        currency = 'USD' # Default

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
            cur.execute("SELECT id, url FROM tracked_items")
            items = cur.fetchall() # List of (id, url)

        if not items:
            logger.info("No items to track.")
            return

        for item_id, url in items:
            logger.info(f"Updating price for item {item_id} ({url})...")
            price, title, _ = get_amazon_price(url)

            if price is not None:
                try:
                    with get_db_cursor(commit=True) as cur:
                        # Update current price and last checked timestamp
                        # Also update title if it was "Unknown Product" before or just to keep it fresh
                        cur.execute("""
                            UPDATE tracked_items
                            SET current_price = %s, last_checked = NOW(), name = COALESCE(name, %s)
                            WHERE id = %s
                        """, (price, title, item_id))

                        # Add to price history
                        cur.execute("""
                            INSERT INTO price_history (tracked_item_id, price)
                            VALUES (%s, %s)
                        """, (item_id, price))
                    logger.info(f"Updated price for item {item_id} to {price}")
                except Exception as e:
                    logger.error(f"Failed to update database for item {item_id}: {e}")
            else:
                logger.warning(f"Failed to fetch price for item {item_id}")

        logger.info("Finished scheduled price update.")

    except Exception as e:
        logger.error(f"Error during price update job: {e}")
