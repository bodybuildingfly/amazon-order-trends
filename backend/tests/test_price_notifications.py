import sys
from unittest.mock import MagicMock

# Mock ALL external dependencies that might be imported by backend.api.__init__
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_jwt_extended'] = MagicMock()
sys.modules['flask_apscheduler'] = MagicMock()
sys.modules['werkzeug.security'] = MagicMock()
sys.modules['gevent'] = MagicMock()
sys.modules['psycogreen'] = MagicMock()
sys.modules['psycogreen.gevent'] = MagicMock()
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['fcntl'] = MagicMock()

# Mock dependencies of price_service
sys.modules['requests'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['fake_useragent'] = MagicMock()
sys.modules['lxml'] = MagicMock()
sys.modules['backend.shared.db'] = MagicMock()
sys.modules['backend.api.config'] = MagicMock()
sys.modules['backend.api.extensions'] = MagicMock()
sys.modules['backend.api.helpers'] = MagicMock()
sys.modules['backend.api.helpers.encryption'] = MagicMock()
sys.modules['backend.api.routes'] = MagicMock()
sys.modules['backend.api.routes.auth'] = MagicMock()
sys.modules['backend.api.routes.users'] = MagicMock()
sys.modules['backend.api.routes.settings'] = MagicMock()
sys.modules['backend.api.routes.items'] = MagicMock()
sys.modules['backend.api.routes.ingestion'] = MagicMock()
sys.modules['backend.api.routes.dashboard'] = MagicMock()
sys.modules['backend.api.routes.price_tracking'] = MagicMock()

import unittest
from unittest.mock import patch, call
from datetime import datetime, timedelta
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.api.services.price_service import update_all_prices

class TestPriceNotifications(unittest.TestCase):

    @patch('backend.api.services.price_service.requests.post')
    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_notification_sent_percent(self, mock_get_price, mock_get_db_cursor, mock_post):
        """Test notification sent when price drops by percentage threshold."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock Fetch Items
        # id, url, user_id, notification_threshold_type, notification_threshold_value, name
        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1', 'user_1', 'percent', 10.0, 'Item 1')]
        ]

        # Mock Fetch Last Price
        # Return an old price of 100.0
        mock_cursor.fetchone.side_effect = [
            (100.0, datetime.now() - timedelta(days=1)), # Last price entry
            ('http://webhook.com',), # user settings webhook
        ]

        # Mock New Price: 80.0 (20% drop, > 10% threshold)
        mock_get_price.return_value = (80.0, "Test Product", "USD")

        update_all_prices()

        # Verify requests.post was called
        self.assertTrue(mock_post.called)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'http://webhook.com')
        self.assertEqual(kwargs['json']['current_price'], 80.0)
        self.assertEqual(kwargs['json']['previous_price'], 100.0)
        self.assertEqual(kwargs['json']['price_change_percent'], -20.0)

    @patch('backend.api.services.price_service.requests.post')
    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_notification_not_sent_percent_small_drop(self, mock_get_price, mock_get_db_cursor, mock_post):
        """Test notification NOT sent when price drops by less than percentage threshold."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1', 'user_1', 'percent', 10.0, 'Item 1')]
        ]

        # Old price 100.0
        mock_cursor.fetchone.side_effect = [
            (100.0, datetime.now() - timedelta(days=1)),
        ]

        # New Price: 95.0 (5% drop, < 10% threshold)
        mock_get_price.return_value = (95.0, "Test Product", "USD")

        update_all_prices()

        self.assertFalse(mock_post.called)

    @patch('backend.api.services.price_service.requests.post')
    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_notification_sent_absolute(self, mock_get_price, mock_get_db_cursor, mock_post):
        """Test notification sent when price drops by absolute threshold."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Threshold $5
        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1', 'user_1', 'absolute', 5.0, 'Item 1')]
        ]

        # Old price 100.0
        mock_cursor.fetchone.side_effect = [
            (100.0, datetime.now() - timedelta(days=1)),
            ('http://webhook.com',),
        ]

        # New Price: 90.0 ($10 drop, > $5 threshold)
        mock_get_price.return_value = (90.0, "Test Product", "USD")

        update_all_prices()

        self.assertTrue(mock_post.called)
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['price_change'], -10.0)

    @patch('backend.api.services.price_service.requests.post')
    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_notification_no_webhook(self, mock_get_price, mock_get_db_cursor, mock_post):
        """Test notification NOT sent if user has no webhook configured."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1', 'user_1', 'percent', 10.0, 'Item 1')]
        ]

        mock_cursor.fetchone.side_effect = [
            (100.0, datetime.now() - timedelta(days=1)),
            (None,), # No webhook
        ]

        # New Price: 80.0
        mock_get_price.return_value = (80.0, "Test Product", "USD")

        update_all_prices()

        self.assertFalse(mock_post.called)

if __name__ == '__main__':
    unittest.main()
