import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.api.services.price_service import get_amazon_price

class TestPriceService(unittest.TestCase):
    @patch('backend.api.services.price_service.UserAgent')
    @patch('requests.get')
    def test_get_amazon_price_success(self, mock_get, mock_ua):
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
        mock_response.url = "http://example.com"
        mock_get.return_value = mock_response

        price, title, currency = get_amazon_price("http://example.com")
        self.assertEqual(price, 19.99)
        self.assertEqual(title, "Test Product")
        self.assertEqual(currency, "$")

    @patch('backend.api.services.price_service.UserAgent')
    @patch('requests.get')
    def test_get_amazon_price_fraction(self, mock_get, mock_ua):
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
        mock_response.url = "http://example.com"
        mock_get.return_value = mock_response

        # Note: my code prefers .a-offscreen if available. Here it's not.
        price, title, currency = get_amazon_price("http://example.com")
        self.assertEqual(price, 1234.56)

    @patch('backend.api.services.price_service.UserAgent')
    @patch('requests.get')
    def test_get_amazon_price_meta_fallback(self, mock_get, mock_ua):
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
        mock_response.url = "http://example.com"
        mock_get.return_value = mock_response

        price, title, currency = get_amazon_price("http://example.com")
        self.assertEqual(title, "Meta Title Product")
        self.assertEqual(price, 10.00)

    @patch('backend.api.services.price_service.UserAgent')
    @patch('requests.get')
    def test_get_amazon_price_captcha(self, mock_get, mock_ua):
        # Mock CAPTCHA page
        html_content = """
        <html>
            <title>Robot Check</title>
        </html>
        """
        mock_response = MagicMock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_response.url = "http://example.com"
        mock_get.return_value = mock_response

        price, title, currency = get_amazon_price("http://example.com")
        self.assertIsNone(price)
        self.assertIsNone(title)

    @patch('backend.api.services.price_service.UserAgent')
    @patch('requests.get')
    def test_get_amazon_price_fail(self, mock_get, mock_ua):
        mock_get.side_effect = Exception("Network Error")
        price, title, currency = get_amazon_price("http://example.com")
        self.assertIsNone(price)
        self.assertIsNone(title)
        self.assertIsNone(currency)

    @patch('backend.api.services.price_service.UserAgent')
    @patch('requests.get')
    def test_get_amazon_price_unavailable_short_url(self, mock_get, mock_ua):
        # Scenario: User tracks a short URL. ASIN is not in short URL.
        # Item is unavailable (no core price).
        # "Similar items" has a price (which we want to IGNORE).

        html_content = """
        <html>
            <div id="productTitle">Miracle Grow Indoor Plant Food</div>
            <div id="availability">
                <span class="a-size-medium a-color-price">Currently unavailable.</span>
            </div>
            <!-- Similar items with price that should be ignored -->
            <div id="similar-items">
                <span class="a-price">
                    <span class="a-offscreen">$8.49</span>
                </span>
            </div>
        </html>
        """
        mock_response = MagicMock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        # Simulate redirect to full URL with ASIN
        mock_response.url = "https://www.amazon.com/dp/B082BPQH6Z?th=1"
        mock_get.return_value = mock_response

        # Short URL
        price, title, currency = get_amazon_price("https://a.co/d/0f4htW3j")

        # Expectation: Price should be None because ASIN should be extracted from response.url,
        # leading to strict checking which fails to find price in unavailable page,
        # correctly ignoring the "Similar items" price.
        self.assertIsNone(price)
        self.assertEqual(title, "Miracle Grow Indoor Plant Food")

if __name__ == '__main__':
    unittest.main()
