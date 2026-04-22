"""
test_geofencing.py — Unit tests for geofence validation and anomaly detection.

Run:
    pytest tests/test_geofencing.py -v
"""

import importlib.util
import os
import sys

import pytest

# Load anomaly_detection.py directly — bypasses app/__init__.py → SQLAlchemy chain
_BASE = os.path.join(os.path.dirname(__file__), '..', 'backend')
_spec = importlib.util.spec_from_file_location(
    'anomaly_detection',
    os.path.join(_BASE, 'app', 'services', 'anomaly_detection.py'),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GeofenceValidator = _mod.GeofenceValidator
AnomalyDetector = _mod.AnomalyDetector


FARM_LAT = 5.6037
FARM_LON = -0.1870


class TestGeofenceValidator:

    def test_within_geofence_low_risk(self):
        result = GeofenceValidator().validate(FARM_LAT, FARM_LON, FARM_LAT, FARM_LON)
        assert result['is_within_geofence'] is True
        assert result['risk_level'] == 'LOW'
        assert result['deviation_meters'] == pytest.approx(0.0, abs=1.0)

    def test_just_outside_geofence_medium_risk(self):
        # ~55 m north — just outside 50 m radius
        result = GeofenceValidator().validate(FARM_LAT, FARM_LON, FARM_LAT + 0.0005, FARM_LON)
        assert result['is_within_geofence'] is False
        assert result['risk_level'] == 'MEDIUM'

    def test_far_outside_geofence_high_risk(self):
        # ~1 km away — well above 200 m HIGH threshold
        result = GeofenceValidator().validate(FARM_LAT, FARM_LON, FARM_LAT + 0.009, FARM_LON)
        assert result['risk_level'] == 'HIGH'
        assert 'POTENTIAL_DIVERSION' in [f['code'] for f in result.get('flags', [])]

    def test_custom_radius_respected(self):
        # 30 m away — within 50 m default, outside 20 m custom
        v = GeofenceValidator(geofence_radius_meters=20)
        result_tight = v.validate(FARM_LAT, FARM_LON, FARM_LAT + 0.00027, FARM_LON)
        assert result_tight['is_within_geofence'] is False

    def test_flags_present_when_outside(self):
        result = GeofenceValidator().validate(FARM_LAT, FARM_LON, FARM_LAT + 0.01, FARM_LON)
        assert len(result.get('flags', [])) > 0

    def test_flags_empty_when_inside(self):
        result = GeofenceValidator().validate(FARM_LAT, FARM_LON, FARM_LAT, FARM_LON)
        assert result.get('flags', []) == []


class TestAnomalyDetector:

    def _base_pod(self, **kwargs):
        base = {
            'location_latitude': FARM_LAT,
            'location_longitude': FARM_LON,
            'signature_data': 'data:image/png;base64,ABC123',
            'photos': ['photo1.jpg'],
            'items_verified': {'item-1': True, 'item-2': True},
        }
        base.update(kwargs)
        return base

    def test_all_good_is_low_risk(self):
        farmer = {'latitude': FARM_LAT, 'longitude': FARM_LON}
        result = AnomalyDetector().assess(farmer, self._base_pod())
        assert result['risk_level'] == 'LOW'

    def test_missing_signature_raises_risk(self):
        farmer = {'latitude': FARM_LAT, 'longitude': FARM_LON}
        pod = self._base_pod(signature_data=None)
        result = AnomalyDetector().assess(farmer, pod)
        assert result['risk_score'] > 0

    def test_gps_far_away_flags_diversion(self):
        farmer = {'latitude': FARM_LAT, 'longitude': FARM_LON}
        pod = self._base_pod(
            location_latitude=FARM_LAT + 0.01,
            location_longitude=FARM_LON + 0.01,
        )
        result = AnomalyDetector().assess(farmer, pod)
        assert result['risk_level'] in ('MEDIUM', 'HIGH')

    def test_risk_score_is_bounded(self):
        farmer = {'latitude': FARM_LAT, 'longitude': FARM_LON}
        result = AnomalyDetector().assess(farmer, self._base_pod())
        assert 0 <= result['risk_score'] <= 100
