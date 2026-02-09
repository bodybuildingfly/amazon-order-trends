import sys
from unittest.mock import MagicMock

# Mock ALL external dependencies that might be imported by backend.api.__init__
# This is necessary because importing price_service triggers backend.api.__init__
# which imports flask and other dependencies that might not be present in the test environment.
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

class TestPriceTrackingLogic(unittest.TestCase):

    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_price_changed(self, mock_get_price, mock_get_db_cursor):
        """Scenario 1: Price Changed. Expect Insert into history."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock Fetch Items
        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1')]
        ]

        # Mock Fetch Last Price (Logic I added)
        # Assuming query: SELECT price, recorded_at FROM price_history ... LIMIT 1
        # Return an old price that is different from new price
        mock_cursor.fetchone.return_value = (10.0, datetime.now() - timedelta(hours=1))

        # Mock New Price
        mock_get_price.return_value = (20.0, "Test Product", "USD")

        update_all_prices()

        execute_calls = [str(c) for c in mock_cursor.execute.call_args_list]
        self.assertTrue(any("INSERT INTO price_history" in c for c in execute_calls))
        self.assertTrue(any("UPDATE tracked_items" in c for c in execute_calls))

    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_price_same_same_day(self, mock_get_price, mock_get_db_cursor):
        """Scenario 2: Price Same, Same Day. Expect NO Insert into history."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1')]
        ]

        # Last price same as new, recorded just now (same day)
        mock_cursor.fetchone.return_value = (10.0, datetime.now())

        mock_get_price.return_value = (10.0, "Test Product", "USD")

        update_all_prices()

        execute_calls = [str(c) for c in mock_cursor.execute.call_args_list]
        # Should NOT insert
        self.assertFalse(any("INSERT INTO price_history" in c for c in execute_calls))
        # Should UPDATE last_checked
        self.assertTrue(any("UPDATE tracked_items" in c for c in execute_calls))

    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_price_same_different_day(self, mock_get_price, mock_get_db_cursor):
        """Scenario 3: Price Same, Different Day. Expect Insert into history."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1')]
        ]

        # Last price same, recorded yesterday (different day)
        mock_cursor.fetchone.return_value = (10.0, datetime.now() - timedelta(days=1))

        mock_get_price.return_value = (10.0, "Test Product", "USD")

        update_all_prices()

        execute_calls = [str(c) for c in mock_cursor.execute.call_args_list]
        self.assertTrue(any("INSERT INTO price_history" in c for c in execute_calls))
        self.assertTrue(any("UPDATE tracked_items" in c for c in execute_calls))

    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_price_fetch_failure(self, mock_get_price, mock_get_db_cursor):
        """Scenario 4: Price Fetch Failure. Expect UPDATE last_checked."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [('item_1', 'http://example.com/1')]
        ]

        # Price fetch fails (returns None)
        mock_get_price.return_value = (None, None, None)

        update_all_prices()

        execute_calls = [str(c) for c in mock_cursor.execute.call_args_list]

        # Should verify that we updated last_checked
        # This will fail until we implement the fix
        self.assertTrue(any("UPDATE tracked_items" in c and "last_checked = NOW()" in c for c in execute_calls),
                        "Expected UPDATE tracked_items with last_checked = NOW() on failure")

        # Ensure we didn't try to update current_price
        self.assertFalse(any("current_price =" in c for c in execute_calls),
                         "Should not update current_price on failure")

if __name__ == '__main__':
    unittest.main()
