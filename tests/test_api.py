"""
test_api.py — Integration tests for the Flask mock API endpoints.

Run:
    pytest tests/test_api.py -v
"""

import json
import os
import sys

import pytest


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get('/api/v1/health')
        assert r.status_code == 200

    def test_health_status_field(self, client):
        data = r = client.get('/api/v1/health').get_json()
        assert data['status'] == 'healthy'

    def test_health_has_ecosystem_integrations(self, client):
        data = client.get('/api/v1/health').get_json()
        assert 'ecosystem_integrations' in data


class TestDeliveryEndpoints:
    def test_get_delivery(self, client, admin_token):
        r = client.get('/api/v1/deliveries/DEL-001',
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.get_json()
        assert data['id'] == 'DEL-001'

    def test_delivery_includes_farmer_gps(self, client, admin_token):
        data = client.get('/api/v1/deliveries/DEL-001',
                          headers={"Authorization": f"Bearer {admin_token}"}).get_json()
        farmer = data.get('farmer', {})
        assert 'latitude' in farmer
        assert 'longitude' in farmer

    def test_get_order(self, client, admin_token):
        r = client.get('/api/v1/orders/ORD-001',
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['items']) == 5

    def test_order_has_all_input_types(self, client, admin_token):
        data = client.get('/api/v1/orders/ORD-001',
                          headers={"Authorization": f"Bearer {admin_token}"}).get_json()
        types = {item['input_type'] for item in data['items']}
        expected = {'seeds', 'fertilizer_basal', 'fertilizer_top_dressing', 'chemical', 'mechanization'}
        assert types == expected


class TestProofOfDelivery:
    def _valid_pod(self):
        return {
            "farmer_name": "Kofi Yeboah",
            "farmer_phone": "+233241234567",
            "delivery_condition": "perfect",
            "location_latitude": 5.6037,
            "location_longitude": -0.1870,
            "signature_data": "data:image/png;base64,ABC123",
        }

    def test_submit_pod_returns_201(self, client, admin_token):
        r = client.post(
            '/api/v1/proof-of-delivery/DEL-001',
            data=json.dumps(self._valid_pod()),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201

    def test_pod_response_has_pod_id(self, client, admin_token):
        r = client.post(
            '/api/v1/proof-of-delivery/DEL-001',
            data=json.dumps(self._valid_pod()),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.get_json()
        assert data['pod_id'].startswith('POD-')

    def test_pod_low_risk_within_geofence(self, client, admin_token):
        r = client.post(
            '/api/v1/proof-of-delivery/DEL-001',
            data=json.dumps(self._valid_pod()),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ra = r.get_json()['risk_assessment']
        assert ra['risk_level'] == 'LOW'
        assert ra['is_within_geofence'] is True

    def test_pod_high_risk_far_from_farm(self, client, admin_token):
        pod = self._valid_pod()
        pod['location_latitude'] = 30.9010   # ~100 km away
        pod['location_longitude'] = 75.8573
        r = client.post(
            '/api/v1/proof-of-delivery/DEL-001',
            data=json.dumps(pod),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ra = r.get_json()['risk_assessment']
        assert ra['risk_level'] == 'HIGH'
        assert ra['requires_review'] is True

    def test_pod_sms_sent(self, client, admin_token):
        r = client.post(
            '/api/v1/proof-of-delivery/DEL-001',
            data=json.dumps(self._valid_pod()),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.get_json()['sms_alert_sent'] is True



    def test_cluster_returns_201(self, client, sample_deliveries, admin_token):
        r = client.post(
            '/api/v1/batches/regional-cluster',
            data=json.dumps({"deliveries": sample_deliveries}),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201

    def test_all_deliveries_appear_in_batches(self, client, sample_deliveries, admin_token):
        r = client.post(
            '/api/v1/batches/regional-cluster',
            data=json.dumps({"deliveries": sample_deliveries}),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.get_json()
        assert data['total_deliveries'] == len(sample_deliveries)
        total_in_batches = sum(b['size'] for b in data['batches'])
        assert total_in_batches == len(sample_deliveries)

    def test_empty_deliveries_returns_400(self, client, admin_token):
        r = client.post(
            '/api/v1/batches/regional-cluster',
            data=json.dumps({"deliveries": []}),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400

    def test_missing_lat_lon_returns_400(self, client, admin_token):
        r = client.post(
            '/api/v1/batches/regional-cluster',
            data=json.dumps({"deliveries": [{"delivery_id": "X", "farmer_id": "Y"}]}),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400

    def test_algorithm_field_is_kmeans(self, client, sample_deliveries, admin_token):
        r = client.post(
            '/api/v1/batches/regional-cluster',
            data=json.dumps({"deliveries": sample_deliveries}),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert 'kmeans' in r.get_json()['algorithm']


class TestGeofenceEndpoint:
    def test_within_geofence(self, client, admin_token):
        r = client.post(
            '/api/v1/dispatch/geofence-check',
            data=json.dumps({
                "farm_latitude": 31.6295, "farm_longitude": 74.8696,
                "delivery_latitude": 31.6295, "delivery_longitude": 74.8696,
            }),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.get_json()
        assert data['is_within_geofence'] is True
        assert data['risk_level'] == 'LOW'

    def test_high_risk_far_away(self, client, admin_token):
        r = client.post(
            '/api/v1/dispatch/geofence-check',
            data=json.dumps({
                "farm_latitude": 31.6295, "farm_longitude": 74.8696,
                "delivery_latitude": 30.9010, "delivery_longitude": 75.8573,
            }),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.get_json()
        assert data['risk_level'] == 'HIGH'

    def test_missing_fields_returns_400(self, client, admin_token):
        r = client.post(
            '/api/v1/dispatch/geofence-check',
            data=json.dumps({"farm_latitude": 31.6295}),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400


class TestDispatchPipeline:
    def test_eligibility_check(self, client, admin_token):
        r = client.get(
            '/api/v1/dispatch/eligibility-check/farmer-123',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['eligible'] is True
        assert 'credit_score' in data

    def test_dispatch_route_pipeline(self, client, admin_token):
        r = client.post(
            '/api/v1/dispatch/route',
            data=json.dumps({
                "order_ids": ["ORD-001"],
                "warehouse_id": "warehouse-001",
                "district": "Accra",
            }),
            content_type='application/json',
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        data = r.get_json()
        assert data['status'] == 'DISPATCHED'
        assert 'steps' in data

    def test_openapi_spec_returns_200(self, client):
        r = client.get('/api/v1/openapi.json')
        assert r.status_code == 200
        spec = r.get_json()
        assert spec['openapi'] == '3.0.0'
        assert '/batches/regional-cluster' in spec['paths']
