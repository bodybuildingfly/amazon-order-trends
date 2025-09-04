import requests
from datetime import datetime
from flask import current_app

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
        current_app.logger.info(f"Sending Discord notification to {webhook_url[:30]}...")
        response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        current_app.logger.info(f"Successfully sent Discord notification.")
    except requests.exceptions.RequestException as e:
        # Log the exception and the response body if available
        error_message = f"Failed to send Discord notification: {e}"
        if e.response is not None:
            error_message += f"\nResponse Status Code: {e.response.status_code}"
            error_message += f"\nResponse Body: {e.response.text}"
        current_app.logger.error(error_message)
