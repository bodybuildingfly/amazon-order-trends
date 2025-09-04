from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from shared.db import get_db_cursor

items_bp = Blueprint('items_bp', __name__)

@items_bp.route("/api/items")
@jwt_required()
def get_all_items():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit
    sort_by = request.args.get('sortBy', 'order_placed_date')
    sort_order = request.args.get('sortOrder', 'desc').upper()
    filter_text = request.args.get('filterText', '')
    current_user_id = get_jwt_identity()

    valid_sort_columns = {'full_title', 'asin', 'price_per_unit', 'order_placed_date'}
    if sort_by not in valid_sort_columns or sort_order not in ['ASC', 'DESC']:
        sort_by = 'order_placed_date'
        sort_order = 'DESC'

    # Base query components
    query_from = "FROM items i JOIN orders o ON i.order_id = o.order_id"
    # Filter by the current user
    query_where = "WHERE o.user_id = %s"
    params = [current_user_id]

    # Add text filter if provided
    if filter_text:
        query_where += " AND (i.full_title ILIKE %s OR CAST(o.order_placed_date AS TEXT) ILIKE %s)"
        params.extend([f"%{filter_text}%", f"%{filter_text}%"])

    # Construct the final queries
    query = f"""
        SELECT i.full_title, i.link, i.thumbnail_url, i.asin, i.price_per_unit, o.order_placed_date
        {query_from}
        {query_where}
        ORDER BY {sort_by} {sort_order}
        LIMIT %s OFFSET %s
    """
    count_query = f"SELECT COUNT(*) {query_from} {query_where}"

    try:
        with get_db_cursor() as cur:
            # Execute count query
            cur.execute(count_query, params)
            total_items = cur.fetchone()[0]
            
            # Execute data query
            data_params = params + [limit, offset]
            cur.execute(query, data_params)
            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]

        return jsonify({
            "data": items,
            "total": total_items,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        current_app.logger.error(f"Failed to fetch items: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch items"}), 500

@items_bp.route('/api/repeat-items')
@jwt_required()
def get_repeat_items():
    current_user_id = get_jwt_identity()

    # --- Sorting ---
    sort_by = request.args.get('sortBy', 'full_title')
    sort_order = request.args.get('sortOrder', 'asc').upper()
    valid_sort_columns = {
        'full_title', 'price_current', 'date_current', 
        'price_prev_1', 'date_prev_1'
    }
    if sort_by not in valid_sort_columns or sort_order not in ['ASC', 'DESC']:
        sort_by = 'full_title'
        sort_order = 'ASC'

    # --- Filtering ---
    filter_text = request.args.get('filterText', '')
    price_changed_only = request.args.get('priceChangedOnly', 'false').lower() == 'true'

    params = [current_user_id]
    
    # --- Base Query ---
    base_query = """
        WITH RankedItems AS (
            SELECT
                i.asin, i.full_title, i.link, i.thumbnail_url, i.price_per_unit, o.order_placed_date,
                i.is_subscribe_and_save,
                ROW_NUMBER() OVER(PARTITION BY i.asin ORDER BY o.order_placed_date DESC) as rn
            FROM items i
            JOIN orders o ON i.order_id = o.order_id
            WHERE i.asin IS NOT NULL AND o.user_id = %s
        ),
        RepeatItems AS (
            SELECT
                current.asin,
                current.full_title,
                current.link,
                current.thumbnail_url,
                current.is_subscribe_and_save,
                current.price_per_unit AS price_current,
                current.order_placed_date AS date_current,
                p1.price_per_unit AS price_prev_1,
                p1.order_placed_date AS date_prev_1,
                p2.price_per_unit AS price_prev_2,
                p2.order_placed_date AS date_prev_2,
                p3.price_per_unit AS price_prev_3,
                p3.order_placed_date AS date_prev_3
            FROM
                RankedItems current
            LEFT JOIN RankedItems p1 ON current.asin = p1.asin AND p1.rn = 2
            LEFT JOIN RankedItems p2 ON current.asin = p2.asin AND p2.rn = 3
            LEFT JOIN RankedItems p3 ON current.asin = p3.asin AND p3.rn = 4
            WHERE
                current.rn = 1 AND p1.asin IS NOT NULL
        )
        SELECT * FROM RepeatItems
    """

    # --- Dynamic WHERE clauses ---
    where_clauses = []
    if filter_text:
        where_clauses.append("full_title ILIKE %s")
        params.append(f"%{filter_text}%")
    
    if price_changed_only:
        # Ensure prices are not null and are different
        where_clauses.append("(price_current IS NOT NULL AND price_prev_1 IS NOT NULL AND price_current != price_prev_1)")

    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)

    # --- Dynamic ORDER BY clause ---
    base_query += f" ORDER BY {sort_by} {sort_order}"

    try:
        with get_db_cursor() as cur:
            cur.execute(base_query, tuple(params))
            items = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
        return jsonify(items)
    except Exception as e:
        current_app.logger.error(f"Failed to fetch repeat items: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch repeat items."}), 500
