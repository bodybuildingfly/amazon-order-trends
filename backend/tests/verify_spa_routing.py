import sys
from unittest.mock import MagicMock
import tempfile
import shutil
import os
import unittest
from unittest.mock import patch
from backend.api import create_app

# Mock amazonorders modules before importing app
sys.modules['amazonorders'] = MagicMock()
sys.modules['amazonorders.session'] = MagicMock()
sys.modules['amazonorders.orders'] = MagicMock()
sys.modules['amazonorders.transactions'] = MagicMock()
sys.modules['amazonorders.exception'] = MagicMock()

class TestSPARoutingRealFS(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory to simulate frontend/build
        self.test_dir = tempfile.mkdtemp()
        self.build_dir = os.path.join(self.test_dir, 'frontend', 'build')
        os.makedirs(self.build_dir)

        # Create index.html
        with open(os.path.join(self.build_dir, 'index.html'), 'w') as f:
            f.write("<html>Index</html>")

        # Create a static asset
        self.static_asset_dir = os.path.join(self.build_dir, 'static', 'js')
        os.makedirs(self.static_asset_dir)
        with open(os.path.join(self.static_asset_dir, 'main.js'), 'w') as f:
            f.write("console.log('main');")

        # Create a directory that matches the route name to simulate conflict
        self.conflict_dir = os.path.join(self.build_dir, 'price-tracking')
        os.makedirs(self.conflict_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('backend.api.init_pool')
    @patch('backend.api.initialize_fernet')
    @patch('backend.api.scheduler.init_app')
    def test_routing(self, mock_scheduler, mock_fernet, mock_pool):
        original_abspath = os.path.abspath

        def side_effect_abspath(path):
            if 'frontend/build' in path:
                return self.build_dir
            return original_abspath(path)

        with patch('backend.api.os.path.abspath', side_effect=side_effect_abspath):
            with patch.dict(os.environ, {'FLASK_ENV': 'production', 'SCHEDULER_AUTOSTART': 'False'}):
                app = create_app()
                client = app.test_client()

                # Test 1: Root
                resp = client.get('/')
                print(f"GET / : {resp.status_code}")
                self.assertEqual(resp.status_code, 200)
                self.assertIn(b"Index", resp.data)

                # Test 2: Asset
                resp = client.get('/static/js/main.js')
                print(f"GET /static/js/main.js : {resp.status_code}")
                self.assertEqual(resp.status_code, 200)

                # Test 3: SPA Route (Should now succeed despite directory conflict)
                resp = client.get('/price-tracking')
                print(f"GET /price-tracking : {resp.status_code}")
                self.assertEqual(resp.status_code, 200)
                self.assertIn(b"Index", resp.data)

if __name__ == '__main__':
    unittest.main()
