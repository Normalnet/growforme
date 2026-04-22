"""
conftest.py — shared fixtures for all test modules.

Provides:
  - app / client fixtures for the Flask mock backend
  - sample delivery data used across multiple test files
"""

import sys
import os
import pytest

# Load app_simple directly to avoid triggering app/__init__.py → SQLAlchemy chain
import importlib.util
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    'app_simple',
    os.path.join(ROOT, 'backend', 'app_simple.py'),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
flask_app = _mod.app


@pytest.fixture(scope='session')
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture(scope='session')
def admin_token():
    """Generate a valid admin JWT for testing protected endpoints."""
    from datetime import datetime, timedelta, timezone
    payload = {
        'sub': 'admin-001',
        'email': 'admin@smarttech.com',
        'name': 'Test Admin',
        'role': 'admin',
        'exp': int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp()),
    }
    return _mod._create_token(payload)


@pytest.fixture
def sample_deliveries():
    """10 delivery points spread across two districts (Accra + Kumasi)."""
    return [
        # Accra cluster
        {"delivery_id": "DEL-001", "farmer_id": "F-001", "district": "Accra",
         "latitude": 5.6037, "longitude": -0.1870, "order_amount": 5000},
        {"delivery_id": "DEL-002", "farmer_id": "F-002", "district": "Accra",
         "latitude": 5.5560, "longitude": -0.1969, "order_amount": 3000},
        {"delivery_id": "DEL-003", "farmer_id": "F-003", "district": "Accra",
         "latitude": 5.6358, "longitude": -0.1601, "order_amount": 4500},
        {"delivery_id": "DEL-004", "farmer_id": "F-004", "district": "Accra",
         "latitude": 5.5804, "longitude": -0.1706, "order_amount": 2000},
        {"delivery_id": "DEL-005", "farmer_id": "F-005", "district": "Accra",
         "latitude": 5.6506, "longitude": -0.1869, "order_amount": 6000},
        # Kumasi cluster
        {"delivery_id": "DEL-006", "farmer_id": "F-006", "district": "Kumasi",
         "latitude": 6.6885, "longitude": -1.6244, "order_amount": 7000},
        {"delivery_id": "DEL-007", "farmer_id": "F-007", "district": "Kumasi",
         "latitude": 6.6900, "longitude": -1.6260, "order_amount": 3500},
        {"delivery_id": "DEL-008", "farmer_id": "F-008", "district": "Kumasi",
         "latitude": 6.6850, "longitude": -1.6200, "order_amount": 4000},
        {"delivery_id": "DEL-009", "farmer_id": "F-009", "district": "Kumasi",
         "latitude": 6.6950, "longitude": -1.6300, "order_amount": 2500},
        {"delivery_id": "DEL-010", "farmer_id": "F-010", "district": "Kumasi",
         "latitude": 6.7000, "longitude": -1.6150, "order_amount": 5500},
    ]
