# api/app.py
import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add the project root to the Python path to allow importing from 'shared'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor

app = Flask(__name__)
CORS(app) # Allow cross-origin requests for development

@app.route("/api/products")
def get_products():
    """Returns a list of unique products (ASIN and short title)."""
    try:
        with get_db_cursor() as cur:
            # DISTINCT ON ensures we get one entry per ASIN, ordering by date to get the most recent title
            cur.execute("""
                SELECT DISTINCT ON (asin) asin, short_title
                FROM items
                WHERE asin IS NOT NULL AND short_title IS NOT NULL
                ORDER BY asin, order_id DESC;
            """)
            products = [{"asin": row[0], "short_title": row[1]} for row in cur.fetchall()]
        return jsonify(products)
    except Exception as e:
        app.logger.error(f"Failed to fetch products: {e}")
        return jsonify({"error": "Failed to fetch products"}), 500

@app.route("/api/trends/<string:asin>")
def get_price_trends(asin):
    """Returns a time-series of price history for a given ASIN."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT o.order_placed_date, i.price_per_unit
                FROM items i
                JOIN orders o ON i.order_id = o.order_id
                WHERE i.asin = %s
                ORDER BY o.order_placed_date ASC;
            """, (asin,))
            trends = [{"date": row[0].isoformat(), "price": float(row[1])} for row in cur.fetchall()]
        return jsonify(trends)
    except Exception as e:
        app.logger.error(f"Failed to fetch trends for ASIN {asin}: {e}")
        return jsonify({"error": "Failed to fetch price trends"}), 500

@app.route("/api/items")
def get_all_items():
    """Provides a paginated, sortable, and filterable list of all items."""
    # --- Pagination ---
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit

    # --- Sorting ---
    sort_by = request.args.get('sortBy', 'order_placed_date')
    sort_order = request.args.get('sortOrder', 'desc').upper()
    # Whitelist valid sort columns to prevent SQL injection
    valid_sort_columns = {'short_title', 'full_title', 'asin', 'price_per_unit', 'order_placed_date'}
    if sort_by not in valid_sort_columns or sort_order not in ['ASC', 'DESC']:
        sort_by = 'order_placed_date'
        sort_order = 'DESC'
    
    # --- Filtering ---
    filter_asin = request.args.get('filter[asin]')
    filter_title = request.args.get('filter[short_title]')

    # --- Query Building ---
    query = """
        SELECT i.short_title, i.full_title, i.asin, i.price_per_unit, o.order_placed_date
        FROM items i
        JOIN orders o ON i.order_id = o.order_id
    """
    count_query = "SELECT COUNT(*) FROM items i JOIN orders o ON i.order_id = o.order_id"
    where_clauses = []
    params = []

    if filter_asin:
        where_clauses.append("i.asin = %s")
        params.append(filter_asin)
    if filter_title:
        where_clauses.append("i.short_title ILIKE %s")
        params.append(f"%{filter_title}%")

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        count_query += " WHERE " + " AND ".join(where_clauses)

    query += f" ORDER BY {sort_by} {sort_order} LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    try:
        with get_db_cursor() as cur:
            cur.execute(count_query, params[:-2]) # Exclude limit and offset for count
            total_items = cur.fetchone()[0]
            
            cur.execute(query, params)
            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]

        return jsonify({
            "data": items,
            "total": total_items,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        app.logger.error(f"Failed to fetch items: {e}")
        return jsonify({"error": "Failed to fetch items"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

