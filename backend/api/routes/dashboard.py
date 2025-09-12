from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.shared.db import get_db_cursor
import json

dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route('/api/dashboard/summary', methods=['GET'])
@jwt_required()
def get_dashboard_summary():
    current_user_id = get_jwt_identity()

    query = """
    WITH UserOrders AS (
        SELECT 
            order_id,
            grand_total,
            DATE_TRUNC('month', order_placed_date) AS month
        FROM orders
        WHERE user_id = %s
    ),
    MonthlySpending AS (
        SELECT
            month,
            SUM(grand_total) AS total_spending
        FROM UserOrders
        GROUP BY month
        ORDER BY month
    ),
    TotalStats AS (
        SELECT
            SUM(grand_total) AS total_spending,
            COUNT(order_id) AS total_orders
        FROM UserOrders
    )
    SELECT
        (SELECT total_spending FROM TotalStats),
        (SELECT total_orders FROM TotalStats),
        (SELECT json_agg(json_build_object('month', TO_CHAR(month, 'YYYY-MM'), 'total_spending', total_spending)) FROM MonthlySpending)
    """

    try:
        with get_db_cursor() as cur:
            cur.execute(query, (current_user_id,))
            result = cur.fetchone()

        if not result:
            return jsonify({
                "total_spending": 0,
                "total_orders": 0,
                "spending_trend": []
            })

        total_spending, total_orders, spending_trend = result

        # Handle the case where there is no spending trend
        if spending_trend is None:
            spending_trend = []

        return jsonify({
            "total_spending": float(total_spending) if total_spending else 0,
            "total_orders": int(total_orders) if total_orders else 0,
            "spending_trend": spending_trend
        })

    except Exception as e:
        current_app.logger.error(f"Failed to fetch dashboard summary: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch dashboard summary"}), 500
