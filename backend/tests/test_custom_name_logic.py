import sys
from unittest.mock import MagicMock, patch, ANY
import unittest
from datetime import datetime
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the function to test
from backend.api.services.price_service import update_all_prices

class TestCustomNameLogic(unittest.TestCase):

    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_custom_name_respected(self, mock_get_price, mock_get_db_cursor):
        """Verify that if is_custom_name is True, the name is NOT updated with scraped title."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock items: (id, url, user_id, type, val, current_name, is_custom_name)
        # Item 1: Custom name "My Custom Item", Scraper returns "Amazon Title"
        mock_cursor.fetchall.side_effect = [
            [(1, 'http://url.com/1', 'user1', 'percent', 10, 'My Custom Item', True)]
        ]

        # Scraper returns: (price, title, currency)
        mock_get_price.return_value = (100.0, "Amazon Title", "$")

        # Mock last entry check (price same, no history update needed)
        mock_cursor.fetchone.return_value = (100.0, datetime.now())

        update_all_prices()

        # Check what was passed to UPDATE
        # Expected: name = "My Custom Item" (the existing name)
        execute_calls = mock_cursor.execute.call_args_list

        found_update = False
        for call_args in execute_calls:
            args = call_args[0]
            query = args[0]
            if "UPDATE tracked_items" in query:
                found_update = True
                params = args[1]
                # Params: (price, title, item_id)
                updated_title = params[1]
                self.assertEqual(updated_title, "My Custom Item", "Should preserve custom name")
                self.assertNotEqual(updated_title, "Amazon Title", "Should NOT use scraped title")

        self.assertTrue(found_update)

    @patch('backend.api.services.price_service.get_db_cursor')
    @patch('backend.api.services.price_service.get_amazon_price')
    def test_automatic_name_update(self, mock_get_price, mock_get_db_cursor):
        """Verify that if is_custom_name is False, the name IS updated with scraped title."""
        mock_cursor = MagicMock()
        mock_get_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Item 1: Auto name "Old Name", Scraper returns "New Amazon Title", is_custom_name=False
        mock_cursor.fetchall.side_effect = [
            [(1, 'http://url.com/1', 'user1', 'percent', 10, 'Old Name', False)]
        ]

        mock_get_price.return_value = (100.0, "New Amazon Title", "$")
        mock_cursor.fetchone.return_value = (100.0, datetime.now())

        update_all_prices()

        execute_calls = mock_cursor.execute.call_args_list
        found_update = False
        for call_args in execute_calls:
            args = call_args[0]
            query = args[0]
            if "UPDATE tracked_items" in query:
                found_update = True
                params = args[1]
                updated_title = params[1]
                self.assertEqual(updated_title, "New Amazon Title", "Should update to scraped title")

        self.assertTrue(found_update)

if __name__ == '__main__':
    unittest.main()
