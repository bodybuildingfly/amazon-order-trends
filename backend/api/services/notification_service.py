import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def send_discord_notification(webhook_url, title, description, color, log_messages):
    """Sends a formatted notification to a Discord webhook."""
    if not webhook_url:
        return

    # Truncate log messages to fit within Discord's description limits (4096 chars)
    log_content = "\n".join(log_messages)
    if len(log_content) > 3800:
        log_content = log_content[:3800] + "\n... (log truncated)"
    
    full_description = description + f"\n\n**Verbose Log:**\n```\n{log_content}\n```"
    
    embed = {
        "title": title,
        "description": full_description,
        "color": color,
        "footer": {
            "text": f"Report generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
    }

    try:
        logger.info(f"Sending Discord notification to {webhook_url[:30]}...")
        response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        logger.info(f"Successfully sent Discord notification.")
    except requests.exceptions.RequestException as e:
        # Log the exception and the response body if available
        error_message = f"Failed to send Discord notification: {e}"
        if e.response is not None:
            error_message += f"\nResponse Status Code: {e.response.status_code}"
            error_message += f"\nResponse Body: {e.response.text}"
        logger.error(error_message)

def send_price_drop_notification(webhook_url, item_name, current_price, previous_price, url, currency="USD"):
    """
    Sends a price drop notification to a Discord webhook.
    """
    if not webhook_url:
        return

    price_change = current_price - previous_price
    price_change_percent = (price_change / previous_price) * 100 if previous_price else 0

    embed = {
        "title": "Price Drop Alert!",
        "description": f"The price of [{item_name}]({url}) has dropped!",
        "color": 5763719,  # Green
        "fields": [
            {
                "name": "Previous Price",
                "value": f"{currency} {previous_price:.2f}",
                "inline": True
            },
            {
                "name": "Current Price",
                "value": f"{currency} {current_price:.2f}",
                "inline": True
            },
            {
                "name": "Change",
                "value": f"{currency} {price_change:.2f} ({price_change_percent:.2f}%)",
                "inline": True
            }
        ],
        "url": url,
        "footer": {
            "text": f"Price Check at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
    }

    try:
        logger.info(f"Sending Price Drop Notification to {webhook_url[:30]}...")
        response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully sent Price Drop Notification.")
        return True
    except requests.exceptions.RequestException as e:
        error_message = f"Failed to send Price Drop Notification: {e}"
        if e.response is not None:
            error_message += f"\nResponse Status Code: {e.response.status_code}"
            error_message += f"\nResponse Body: {e.response.text}"
        logger.error(error_message)
        return False
