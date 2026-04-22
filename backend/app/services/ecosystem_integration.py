"""
Ecosystem Integration Service
==============================
Manages state-driven handshakes with the rest of the GrowForMe ecosystem:

  ┌─────────────────────────┐     GET /inventory/available
  │  Input Acquisition API  │◄────────────────────────────  Verify stock before dispatch
  └─────────────────────────┘

  ┌─────────────────────────┐     GET /farmer/{id}/eligibility
  │   Credit Scoring API    │◄────────────────────────────  Only eligible farmers receive inputs
  └─────────────────────────┘

  ┌─────────────────────────┐     POST /dispatch/route (inbound)
  │  This Distribution API  │◄────────────────────────────  Triggers routing logic
  └─────────────────────────┘

  ┌─────────────────────────┐     PUSH /delivery/status (outbound)
  │   Monitoring Project    │◄────────────────────────────  Notify monitoring so growth tracking starts
  └─────────────────────────┘

When DATA_SOURCE=mock, all calls return realistic dummy responses so
the full pipeline can be tested without live API credentials.

When DATA_SOURCE=growforme_api, set GROWFORME_API_URL and GROWFORME_API_KEY
in .env and the calls will hit the real GrowForMe endpoints.
"""

import logging
import requests
from datetime import datetime, timedelta, timezone
from flask import current_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input Acquisition Service
# ---------------------------------------------------------------------------

class InputAcquisitionService:
    """
    Handshake with Input Acquisition API.
    You only distribute what has been sourced.

    Real endpoint:  GET  {GROWFORME_API_URL}/inventory/available
    """

    def __init__(self):
        self.base_url = current_app.config.get('GROWFORME_API_URL', '')
        self.api_key = current_app.config.get('GROWFORME_API_KEY', '')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def check_inventory_availability(self, warehouse_id, order_items):
        """
        Verify that every item in *order_items* is available in the warehouse.

        Args:
            warehouse_id (str): Warehouse UUID
            order_items (list): List of dicts with keys: sku, quantity

        Returns:
            dict: {available: bool, items: [...], timestamp: str}
        """
        if current_app.config.get('DATA_SOURCE', 'mock') == 'mock':
            return self._mock_inventory_check(warehouse_id, order_items)

        try:
            payload = {
                'warehouse_id': warehouse_id,
                'items': [
                    {'sku': item.get('sku'), 'quantity': item.get('quantity')}
                    for item in order_items
                ],
            }
            response = requests.post(
                f'{self.base_url}/inventory/available',
                json=payload,
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error('InputAcquisitionService error: %s', exc)
            return {
                'available': False,
                'error': str(exc),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }

    # ------------------------------------------------------------------
    def _mock_inventory_check(self, warehouse_id, order_items):
        items_status = []
        all_available = True

        # Input-type labels for realistic mock output
        type_labels = {
            'seeds': 'Certified seed stock',
            'fertilizer_basal': 'Basal fertilizer stock',
            'fertilizer_top_dressing': 'Top-dressing fertilizer stock',
            'mechanization': 'Equipment inventory',
            'chemical': 'Agro-chemical stock',
        }

        for item in order_items:
            available_qty = item.get('quantity', 0) + 200
            label = type_labels.get(item.get('input_type', ''), 'Input stock')
            items_status.append({
                'sku': item.get('sku', 'UNKNOWN'),
                'product_name': item.get('product_name', ''),
                'input_type': item.get('input_type', 'other'),
                'stock_label': label,
                'requested': item.get('quantity', 0),
                'available': available_qty,
                'status': 'sufficient',
            })

        return {
            'available': all_available,
            'warehouse_id': warehouse_id,
            'items': items_status,
            'source': 'mock_input_acquisition_api',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Credit Scoring Service
# ---------------------------------------------------------------------------

class CreditScoringService:
    """
    Handshake with Credit Scoring API.
    Ensures inputs are only released to farmers who passed the risk assessment.

    Real endpoint:  GET  {GROWFORME_API_URL}/farmer/{id}/eligibility
    """

    def __init__(self):
        self.base_url = current_app.config.get('GROWFORME_API_URL', '')
        self.api_key = current_app.config.get('GROWFORME_API_KEY', '')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def check_farmer_eligibility(self, farmer_id, order_amount=None):
        """
        Check whether the farmer is eligible to receive inputs.

        Args:
            farmer_id (str): Farmer UUID
            order_amount (float, optional): Order value for credit-limit check

        Returns:
            dict: {eligible, credit_score, risk_level, max_credit_limit, reason, ...}
        """
        if current_app.config.get('DATA_SOURCE', 'mock') == 'mock':
            return self._mock_eligibility(farmer_id, order_amount)

        try:
            params = {}
            if order_amount is not None:
                params['order_amount'] = order_amount

            response = requests.get(
                f'{self.base_url}/farmer/{farmer_id}/eligibility',
                headers=self.headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error('CreditScoringService error: %s', exc)
            return {
                'eligible': False,
                'error': str(exc),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }

    # ------------------------------------------------------------------
    def _mock_eligibility(self, farmer_id, order_amount):
        now = datetime.now(timezone.utc)
        return {
            'farmer_id': farmer_id,
            'eligible': True,
            'credit_score': 724,
            'risk_level': 'LOW',
            'max_credit_limit': 50000.0,
            'order_amount': order_amount,
            'within_limit': True,
            'reason': 'Good repayment history; credit score above threshold.',
            'source': 'mock_credit_scoring_api',
            'checked_at': now.isoformat(),
            'expires_at': (now + timedelta(hours=24)).isoformat(),
        }


# ---------------------------------------------------------------------------
# Monitoring Service
# ---------------------------------------------------------------------------

class MonitoringService:
    """
    Push delivery status to the GrowForMe Monitoring Project.
    Once inputs arrive, the monitoring team can begin tracking crop growth.

    Real endpoint:  POST  {GROWFORME_API_URL}/delivery/status
    """

    def __init__(self):
        self.base_url = current_app.config.get('GROWFORME_API_URL', '')
        self.api_key = current_app.config.get('GROWFORME_API_KEY', '')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    # Valid status values that the Monitoring project understands
    STATUS_MAP = {
        'DISPATCHED': 'inputs_dispatched',
        'IN_TRANSIT': 'inputs_in_transit',
        'DELIVERED': 'inputs_delivered',       # triggers growth tracking
        'FAILED': 'delivery_failed',
        'HIGH_RISK': 'delivery_flagged_high_risk',
    }

    def push_delivery_status(self, delivery_id, status, metadata=None):
        """
        Push a status event to the Monitoring project.

        Args:
            delivery_id (str): Delivery UUID
            status (str): One of the STATUS_MAP keys
            metadata (dict, optional): Additional context (farmer_id, GPS, risk_level …)

        Returns:
            dict: confirmation payload
        """
        if current_app.config.get('DATA_SOURCE', 'mock') == 'mock':
            return self._mock_push(delivery_id, status, metadata)

        try:
            payload = {
                'delivery_id': delivery_id,
                'status': self.STATUS_MAP.get(status, status.lower()),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metadata': metadata or {},
            }
            response = requests.post(
                f'{self.base_url}/delivery/status',
                json=payload,
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error('MonitoringService push error: %s', exc)
            return {
                'pushed': False,
                'error': str(exc),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }

    # ------------------------------------------------------------------
    def _mock_push(self, delivery_id, status, metadata):
        return {
            'pushed': True,
            'delivery_id': delivery_id,
            'status': status,
            'monitoring_team_notified': True,
            'growth_tracking_initiated': (status == 'DELIVERED'),
            'source': 'mock_monitoring_api',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
