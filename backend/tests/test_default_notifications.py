import sys
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

# Mock dependencies
sys.modules['amazonorders'] = MagicMock()
sys.modules['amazonorders.session'] = MagicMock()
sys.modules['amazonorders.orders'] = MagicMock()
sys.modules['amazonorders.transactions'] = MagicMock()
sys.modules['amazonorders.exception'] = MagicMock()

# Import blueprints
# We need to ensure we can import them. Since we mocked amazonorders, it should be fine.
# We also need to mock backend.shared.db if it does DB connection on import? No, it just defines functions.

from backend.api.routes.settings import settings_bp
from backend.api.routes.price_tracking import price_tracking_bp

class TestDefaultNotifications(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['JWT_SECRET_KEY'] = 'test-secret'
        self.jwt = JWTManager(self.app)
        self.app.register_blueprint(settings_bp)
        self.app.register_blueprint(price_tracking_bp)
        self.client = self.app.test_client()

    @patch('backend.api.routes.settings.get_db_cursor')
    @patch('backend.api.routes.settings.get_fernet')
    def test_save_user_settings_partial_update(self, mock_get_fernet, mock_get_db_cursor):
        # Mock Fernet
        mock_fernet = MagicMock()
        mock_get_fernet.return_value = mock_fernet

        # Mock DB Cursor
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # We need a valid JWT token
        with self.app.app_context():
            token = create_access_token(identity='user-123')
            headers = {'Authorization': f'Bearer {token}'}

        # Payload with just the new settings
        payload = {
            'default_notification_threshold_type': 'absolute',
            'default_notification_threshold_value': 15.50
        }

        response = self.client.post(
            '/api/settings/user',
            json=payload,
            headers=headers
        )

        self.assertEqual(response.status_code, 200)

        # Verify SQL
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        # Check if dynamic SQL constructed correctly
        self.assertIn("INSERT INTO user_settings", sql)
        self.assertIn("default_notification_threshold_type", sql)
        self.assertIn("default_notification_threshold_value", sql)
        # Check if ON CONFLICT DO UPDATE is present
        self.assertIn("ON CONFLICT (user_id) DO UPDATE SET", sql)

        # Verify values passed
        self.assertIn('user-123', params)
        self.assertIn('absolute', params)
        self.assertIn(15.50, params)

        # Verify that other columns like amazon_email are NOT in the query (since we didn't pass them)
        self.assertNotIn("amazon_email", sql)


    @patch('backend.api.routes.price_tracking.get_db_cursor')
    @patch('backend.api.routes.price_tracking.get_amazon_price')
    def test_add_tracked_item_with_defaults(self, mock_get_amazon_price, mock_get_db_cursor):
        # Mock Amazon Price
        mock_get_amazon_price.return_value = (99.99, "Test Product", "USD")

        # Mock DB Cursor
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock fetchone for check existing (return None)
        # Then fetchone for RETURNING clause (return new item)
        mock_cursor.fetchone.side_effect = [
            None, # Check existing
            (1, "Test Product", 99.99, "USD") # RETURNING clause
        ]

        with self.app.app_context():
            token = create_access_token(identity='user-123')
            headers = {'Authorization': f'Bearer {token}'}

        payload = {
            'url': 'http://amazon.com/dp/B00000',
            'notification_threshold_type': 'percent',
            'notification_threshold_value': 10
        }

        response = self.client.post(
            '/api/tracked-items',
            json=payload,
            headers=headers
        )

        self.assertEqual(response.status_code, 201)

        # Verify SQL
        # First call is check existing
        # Second call is INSERT tracked_items
        # Third call is INSERT price_history
        self.assertEqual(mock_cursor.execute.call_count, 3)

        insert_call = mock_cursor.execute.call_args_list[1]
        sql = insert_call[0][0]
        params = insert_call[0][1]

        self.assertIn("INSERT INTO tracked_items", sql)
        self.assertIn("notification_threshold_type", sql)
        self.assertIn("notification_threshold_value", sql)

        self.assertIn('percent', params)
        self.assertIn(10, params)

if __name__ == '__main__':
    unittest.main()
