from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.shared.db import get_db_cursor
from backend.api.services.price_service import get_amazon_price
from datetime import datetime
import re

price_tracking_bp = Blueprint('price_tracking_bp', __name__)

def extract_asin(url):
    """Extracts the ASIN from an Amazon product URL."""
    if not url: return None
    match = re.search(r'/(dp|gp/product)/(\w{10})', url)
    return match.group(2) if match else None

@price_tracking_bp.route("/api/tracked-items", methods=['POST'])
@jwt_required()
def add_tracked_item():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Extract ASIN
    asin = extract_asin(url)

    # Check if already tracked by this user
    with get_db_cursor() as cur:
        # Check by URL or ASIN if available
        if asin:
            cur.execute("SELECT id FROM tracked_items WHERE user_id = %s AND asin = %s", (current_user_id, asin))
        else:
            cur.execute("SELECT id FROM tracked_items WHERE user_id = %s AND url = %s", (current_user_id, url))

        if cur.fetchone():
            return jsonify({"error": "Item already tracked"}), 409

    # Scrape initial price
    price, title, currency = get_amazon_price(url)

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO tracked_items (user_id, asin, url, name, current_price, currency, last_checked)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id, name, current_price, currency
            """, (current_user_id, asin, url, title, price, currency))

            new_item_row = cur.fetchone()
            # Convert row to dict for easy access or just use indices
            # new_item_row: (id, name, current_price, currency)
            item_id = new_item_row[0]
            name = new_item_row[1]
            current_price = new_item_row[2]
            currency_val = new_item_row[3]

            if price is not None:
                cur.execute("""
                    INSERT INTO price_history (tracked_item_id, price)
                    VALUES (%s, %s)
                """, (item_id, price))

        return jsonify({
            "id": item_id,
            "name": name,
            "url": url,
            "asin": asin,
            "current_price": current_price,
            "currency": currency_val,
            "last_checked": datetime.now().isoformat(),
            "message": "Item added successfully"
        }), 201

    except Exception as e:
        current_app.logger.error(f"Failed to add tracked item: {e}")
        return jsonify({"error": "Failed to add item"}), 500

@price_tracking_bp.route("/api/tracked-items", methods=['GET'])
@jwt_required()
def get_tracked_items():
    current_user_id = get_jwt_identity()

    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, asin, url, name, current_price, currency, last_checked
                FROM tracked_items
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (current_user_id,))

            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]

        return jsonify(items)
    except Exception as e:
        current_app.logger.error(f"Failed to fetch tracked items: {e}")
        return jsonify({"error": "Failed to fetch items"}), 500

@price_tracking_bp.route("/api/tracked-items/<item_id>", methods=['GET'])
@jwt_required()
def get_tracked_item_details(item_id):
    current_user_id = get_jwt_identity()

    try:
        with get_db_cursor() as cur:
            # Get item details
            cur.execute("""
                SELECT id, asin, url, name, current_price, currency, last_checked
                FROM tracked_items
                WHERE id = %s AND user_id = %s
            """, (item_id, current_user_id))

            item_row = cur.fetchone()
            if not item_row:
                return jsonify({"error": "Item not found"}), 404

            item = dict(zip([desc[0] for desc in cur.description], item_row))

            # Get price history
            # Aggregate to show only the last price check of each day to reduce noise
            cur.execute("""
                SELECT DISTINCT ON (DATE(recorded_at)) price, recorded_at
                FROM price_history
                WHERE tracked_item_id = %s
                ORDER BY DATE(recorded_at) ASC, recorded_at DESC
            """, (item_id,))

            history = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]

            item['history'] = history

        return jsonify(item)
    except Exception as e:
        current_app.logger.error(f"Failed to fetch item details: {e}")
        return jsonify({"error": "Failed to fetch item details"}), 500

@price_tracking_bp.route("/api/tracked-items/<item_id>", methods=['PUT'])
@jwt_required()
def update_tracked_item(item_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    name = data.get('name')

    if not name or not name.strip():
        return jsonify({"error": "Name is required"}), 400

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("""
                UPDATE tracked_items
                SET name = %s
                WHERE id = %s AND user_id = %s
                RETURNING id, asin, url, name, current_price, currency, last_checked
            """, (name.strip(), item_id, current_user_id))

            item_row = cur.fetchone()
            if not item_row:
                return jsonify({"error": "Item not found"}), 404

            item = dict(zip([desc[0] for desc in cur.description], item_row))

        return jsonify(item)
    except Exception as e:
        current_app.logger.error(f"Failed to update item: {e}")
        return jsonify({"error": "Failed to update item"}), 500

@price_tracking_bp.route("/api/tracked-items/<item_id>", methods=['DELETE'])
@jwt_required()
def delete_tracked_item(item_id):
    current_user_id = get_jwt_identity()

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("""
                DELETE FROM tracked_items
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (item_id, current_user_id))

            if not cur.fetchone():
                return jsonify({"error": "Item not found"}), 404

        return jsonify({"message": "Item deleted successfully"})
    except Exception as e:
        current_app.logger.error(f"Failed to delete item: {e}")
        return jsonify({"error": "Failed to delete item"}), 500
