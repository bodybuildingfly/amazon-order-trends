import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.api.services.price_service import get_amazon_price

class TestPriceService(unittest.TestCase):
    @patch('backend.api.services.price_service.requests.get')
    def test_get_amazon_price_success(self, mock_get):
        # Mock HTML content
        html_content = """
        <html>
            <div id="productTitle">Test Product</div>
            <span class="a-price">
                <span class="a-offscreen">$19.99</span>
            </span>
        </html>
        """
        mock_response = MagicMock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        price, title, currency = get_amazon_price("http://example.com")
        self.assertEqual(price, 19.99)
        self.assertEqual(title, "Test Product")
        self.assertEqual(currency, "USD")

    @patch('backend.api.services.price_service.requests.get')
    def test_get_amazon_price_fraction(self, mock_get):
        # Mock HTML content with whole/fraction
        html_content = """
        <html>
            <div id="productTitle">Test Product</div>
            <span class="a-price-whole">1,234<span class="a-price-decimal">.</span></span>
            <span class="a-price-fraction">56</span>
        </html>
        """
        mock_response = MagicMock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Note: my code prefers .a-offscreen if available. Here it's not.
        price, title, currency = get_amazon_price("http://example.com")
        self.assertEqual(price, 1234.56)

    @patch('backend.api.services.price_service.requests.get')
    def test_get_amazon_price_meta_fallback(self, mock_get):
        # Mock HTML content with meta title
        html_content = """
        <html>
            <meta name="title" content="Meta Title Product">
            <span class="a-price"><span class="a-offscreen">$10.00</span></span>
        </html>
        """
        mock_response = MagicMock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        price, title, currency = get_amazon_price("http://example.com")
        self.assertEqual(title, "Meta Title Product")
        self.assertEqual(price, 10.00)

    @patch('backend.api.services.price_service.requests.get')
    def test_get_amazon_price_captcha(self, mock_get):
        # Mock CAPTCHA page
        html_content = """
        <html>
            <title>Robot Check</title>
        </html>
        """
        mock_response = MagicMock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        price, title, currency = get_amazon_price("http://example.com")
        self.assertIsNone(price)
        self.assertIsNone(title)

    @patch('backend.api.services.price_service.requests.get')
    def test_get_amazon_price_fail(self, mock_get):
        mock_get.side_effect = Exception("Network Error")
        price, title, currency = get_amazon_price("http://example.com")
        self.assertIsNone(price)
        self.assertIsNone(title)
        self.assertIsNone(currency)

if __name__ == '__main__':
    unittest.main()
