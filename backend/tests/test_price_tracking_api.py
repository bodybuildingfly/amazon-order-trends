import sys
from unittest.mock import MagicMock, patch

# Mock dependencies that might cause issues or are not needed for this test
sys.modules['amazonorders'] = MagicMock()
sys.modules['amazonorders.session'] = MagicMock()
sys.modules['amazonorders.orders'] = MagicMock()
sys.modules['amazonorders.transactions'] = MagicMock()
sys.modules['amazonorders.exception'] = MagicMock()


import unittest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

# We need to import the blueprint.
# Since we mocked price_service, the import in price_tracking.py should be fine.
# However, price_tracking.py imports get_db_cursor from backend.shared.db
# We will patch get_db_cursor where it is used.

from backend.api.routes.price_tracking import price_tracking_bp

class TestPriceTrackingAPI(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['JWT_SECRET_KEY'] = 'test-secret'
        self.jwt = JWTManager(self.app)
        self.app.register_blueprint(price_tracking_bp)
        self.client = self.app.test_client()

    @patch('backend.api.routes.price_tracking.get_db_cursor')
    def test_update_item_name(self, mock_get_db_cursor):
        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the UPDATE query returning the updated row
        # returning id, name, current_price, currency, asin, url, last_checked
        mock_cursor.fetchone.return_value = (
            1,
            "New Name",
            100.0,
            "$",
            "ASIN123",
            "http://url.com",
            "2023-01-01T00:00:00"
        )
        # We also need description for dict conversion if the code uses it.
        mock_cursor.description = [
            ('id',), ('name',), ('current_price',), ('currency',), ('asin',), ('url',), ('last_checked',)
        ]

        # We need a valid JWT token
        with self.app.app_context():
            token = create_access_token(identity='1')
            headers = {'Authorization': f'Bearer {token}'}

        # Perform PUT request
        response = self.client.put(
            '/api/tracked-items/1',
            json={'name': 'New Name'},
            headers=headers
        )

        # Assertions
        if response.status_code != 200:
            print(f"DEBUG Response: {response.json}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], 'New Name')

        # Verify SQL execution
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        self.assertIn("UPDATE tracked_items", sql)
        self.assertIn("SET name = %s", sql)
        self.assertIn("WHERE id = %s AND user_id = %s", sql)

    @patch('backend.api.routes.price_tracking.get_db_cursor')
    def test_update_item_name_missing_name(self, mock_get_db_cursor):
         with self.app.app_context():
            token = create_access_token(identity='1')
            headers = {'Authorization': f'Bearer {token}'}

         response = self.client.put(
            '/api/tracked-items/1',
            json={}, # Missing name
            headers=headers
        )
         self.assertEqual(response.status_code, 400)

    @patch('backend.api.routes.price_tracking.get_db_cursor')
    def test_get_tracked_items_includes_normal_price(self, mock_get_db_cursor):
        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the SELECT query returning one item with normal_price
        # id, asin, url, name, current_price, currency, last_checked, notification_threshold_type, notification_threshold_value, is_custom_name, normal_price
        mock_cursor.fetchall.return_value = [
            (
                1, "ASIN123", "http://url.com", "Product Name", 100.0, "$", "2023-01-01T00:00:00",
                "percent", 10, False, 120.0
            )
        ]

        # We need description for dict conversion
        mock_cursor.description = [
            ('id',), ('asin',), ('url',), ('name',), ('current_price',), ('currency',),
            ('last_checked',), ('notification_threshold_type',), ('notification_threshold_value',),
            ('is_custom_name',), ('normal_price',)
        ]

        # We need a valid JWT token
        with self.app.app_context():
            token = create_access_token(identity='1')
            headers = {'Authorization': f'Bearer {token}'}

        # Perform GET request
        response = self.client.get(
            '/api/tracked-items',
            headers=headers
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['normal_price'], 120.0)

        # Verify SQL execution
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        self.assertIn("SELECT price", sql)
        self.assertIn("ORDER BY COUNT(*) DESC, MIN(recorded_at) ASC", sql)
        self.assertIn("as normal_price", sql)

if __name__ == '__main__':
    unittest.main()
