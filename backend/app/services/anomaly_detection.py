"""
Anomaly Detection & Geofencing Service
========================================
Implements the Cyber-Physical Verification layer:

  1. GPS Geofencing
     - Every PoD submission is validated against the farmer's registered GPS
     - Deliveries outside the 50 m geofence are flagged MEDIUM or HIGH risk
     - Potential diversion detected when deviation > 200 m

  2. Delivery Risk Assessment
     - Combines geofence check + missing evidence signals into a risk score (0-100)
     - risk_level:  LOW (0-19) | MEDIUM (20-39) | HIGH (40+)
     - HIGH-risk deliveries are quarantined for manual supervisor review

  3. Predictive Delivery Window
     - Simple weighted-regression model using:
         distance, stop count, district type, and day-of-week multipliers
     - Returns a start/end window + confidence level
     - Designed to be replaced with a trained ML model once historical data exists
"""

import math
import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GEOFENCE_RADIUS_METERS = 50     # Within 50 m → LOW risk / accepted
MEDIUM_RISK_THRESHOLD = 200     # 50-200 m   → MEDIUM risk
HIGH_RISK_THRESHOLD = 200       # > 200 m    → HIGH risk / potential diversion


# ---------------------------------------------------------------------------
# Geofence Validator
# ---------------------------------------------------------------------------

class GeofenceValidator:
    """
    Checks whether a delivery GPS coordinate is inside the registered
    farm geofence. Uses the Haversine formula for metre-accurate distances.
    """

    def __init__(self, geofence_radius_meters=GEOFENCE_RADIUS_METERS):
        self.radius = geofence_radius_meters

    def validate(self, farm_lat, farm_lon, delivery_lat, delivery_lon):
        """
        Args:
            farm_lat/farm_lon: Farmer's registered coordinates
            delivery_lat/delivery_lon: Actual GPS at time of PoD

        Returns:
            dict with keys: is_within_geofence, deviation_meters,
                            risk_level, flags, expected_location, actual_location
        """
        deviation = self.haversine_meters(farm_lat, farm_lon, delivery_lat, delivery_lon)
        within = deviation <= self.radius
        risk = self._risk_level(deviation)
        flags = self._build_flags(deviation, within)

        return {
            'is_within_geofence': within,
            'deviation_meters': round(deviation, 2),
            'geofence_radius_meters': self.radius,
            'risk_level': risk,
            'flags': flags,
            'expected_location': {'latitude': farm_lat, 'longitude': farm_lon},
            'actual_location': {'latitude': delivery_lat, 'longitude': delivery_lon},
        }

    @staticmethod
    def haversine_meters(lat1, lon1, lat2, lon2):
        """Great-circle distance between two GPS points, in metres."""
        R = 6_371_000  # Earth radius in metres
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lam = math.radians(lon2 - lon1)
        a = (math.sin(d_phi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _risk_level(deviation_m):
        if deviation_m <= GEOFENCE_RADIUS_METERS:
            return 'LOW'
        if deviation_m <= HIGH_RISK_THRESHOLD:
            return 'MEDIUM'
        return 'HIGH'

    def _build_flags(self, deviation_m, within):
        flags = []
        if not within:
            flags.append({
                'code': 'GPS_DEVIATION',
                'message': (
                    f'Delivery GPS is {deviation_m:.0f} m from the registered farm location '
                    f'(geofence: {self.radius} m).'
                ),
                'severity': self._risk_level(deviation_m),
            })
        if deviation_m > HIGH_RISK_THRESHOLD:
            flags.append({
                'code': 'POTENTIAL_DIVERSION',
                'message': (
                    'Delivery coordinates deviate significantly from the registered farm. '
                    'Possible input diversion — escalate for supervisor review.'
                ),
                'severity': 'HIGH',
            })
        return flags


# ---------------------------------------------------------------------------
# Delivery Window Predictor
# ---------------------------------------------------------------------------

class DeliveryWindowPredictor:
    """
    Predicts a delivery time window using a simple weighted regression approach.

    Variables:
      - Travel time     = distance_km / AVG_SPEED_KMH
      - Stop overhead   = num_stops × STOP_TIME_HOURS
      - District factor = historical baseline for rural/urban area types
      - Day-of-week     = multiplier for market days, weekends, etc.

    The confidence band is ±20 % of the point estimate.

    This is intentionally designed as a *pluggable* model:
    replace predict() with a trained sklearn pipeline once real delivery
    history data is available from GrowForMe's system.
    """

    AVG_SPEED_KMH = 40.0           # Conservative rural speed
    STOP_TIME_HOURS = 15 / 60      # 15 minutes per farm stop

    DISTRICT_BASELINES = {
        'urban': 2.5,
        'peri_urban': 3.5,
        'rural': 5.0,
        'remote': 8.0,
        'default': 4.0,
    }

    # Monday=0 … Sunday=6
    DAY_MULTIPLIERS = {
        0: 1.00,   # Monday   — normal
        1: 1.00,   # Tuesday  — normal
        2: 1.05,   # Wednesday — slight congestion
        3: 1.00,   # Thursday  — normal
        4: 1.15,   # Friday    — market-day delays
        5: 1.30,   # Saturday  — reduced operations
        6: 1.50,   # Sunday    — limited operations
    }

    def predict(self, distance_km, num_stops, district_type='default', scheduled_date=None):
        """
        Returns an estimated delivery window dict.

        Args:
            distance_km (float):   Total route distance
            num_stops (int):       Number of farm drop-offs
            district_type (str):   One of DISTRICT_BASELINES keys
            scheduled_date (datetime, optional): Dispatch date/time (UTC)
        """
        if scheduled_date is None:
            scheduled_date = datetime.now(timezone.utc)

        travel_h = distance_km / self.AVG_SPEED_KMH
        stop_h = num_stops * self.STOP_TIME_HOURS
        baseline_h = self.DISTRICT_BASELINES.get(
            district_type, self.DISTRICT_BASELINES['default']
        )
        day_mult = self.DAY_MULTIPLIERS.get(scheduled_date.weekday(), 1.0)

        estimated_h = (travel_h + stop_h + baseline_h) * day_mult

        window_start = scheduled_date + timedelta(hours=estimated_h * 0.8)
        window_end = scheduled_date + timedelta(hours=estimated_h * 1.2)

        return {
            'estimated_hours': round(estimated_h, 2),
            'window_start': window_start.isoformat(),
            'window_end': window_end.isoformat(),
            'confidence': self._confidence(distance_km, num_stops),
            'model': 'weighted_regression_v1',
            'factors': {
                'travel_hours': round(travel_h, 2),
                'stop_hours': round(stop_h, 2),
                'district_baseline_hours': baseline_h,
                'day_of_week_multiplier': day_mult,
            },
        }

    @staticmethod
    def _confidence(distance_km, num_stops):
        if distance_km < 20 and num_stops <= 5:
            return 'HIGH'
        if distance_km < 50 and num_stops <= 15:
            return 'MEDIUM'
        return 'LOW'


# ---------------------------------------------------------------------------
# Anomaly Detector  (combines all signals)
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Full multi-signal risk assessment for a delivery at PoD time.

    Signals evaluated:
      1. GPS Geofence deviation
      2. Missing digital signature
      3. Missing photo evidence
      4. Partially unverified items
      5. Missing GPS entirely (agent disabled location)

    Risk score bands:
      0–19  → LOW   (auto-approved)
      20–39 → MEDIUM (logged, no block)
      40+   → HIGH  (quarantined, supervisor review required)
    """

    def __init__(self):
        self.geofence = GeofenceValidator()

    def assess(self, farmer_location, pod_data):
        """
        Args:
            farmer_location (dict): {'latitude': float, 'longitude': float}
            pod_data (dict):        Form data from the PoD submission

        Returns:
            dict: risk_level, risk_score, flags, requires_review, auto_approved,
                  geofence_result
        """
        flags = []
        risk_score = 0
        geofence_result = None

        # ── 1. GPS Geofence ──────────────────────────────────────────────
        has_farm_gps = (
            farmer_location.get('latitude') is not None
            and farmer_location.get('longitude') is not None
        )
        has_delivery_gps = (
            pod_data.get('location_latitude') is not None
            and pod_data.get('location_longitude') is not None
        )

        if has_farm_gps and has_delivery_gps:
            geofence_result = self.geofence.validate(
                float(farmer_location['latitude']),
                float(farmer_location['longitude']),
                float(pod_data['location_latitude']),
                float(pod_data['location_longitude']),
            )
            flags.extend(geofence_result['flags'])
            deviation = geofence_result['deviation_meters']
            if deviation > HIGH_RISK_THRESHOLD:
                risk_score += 40
            elif deviation > GEOFENCE_RADIUS_METERS:
                risk_score += 20
        else:
            flags.append({
                'code': 'MISSING_GPS',
                'message': 'GPS coordinates were not captured for this delivery.',
                'severity': 'MEDIUM',
            })
            risk_score += 15

        # ── 2. Missing Signature ─────────────────────────────────────────
        if not pod_data.get('signature_data'):
            flags.append({
                'code': 'MISSING_SIGNATURE',
                'message': 'No digital signature captured at delivery.',
                'severity': 'HIGH',
            })
            risk_score += 30

        # ── 3. Missing Photo Evidence ─────────────────────────────────────
        photos = pod_data.get('photos', [])
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except (json.JSONDecodeError, ValueError):
                photos = []
        if not photos:
            flags.append({
                'code': 'MISSING_PHOTOS',
                'message': 'No photo evidence provided for delivery.',
                'severity': 'MEDIUM',
            })
            risk_score += 15

        # ── 4. Unverified Items ───────────────────────────────────────────
        items_verified = pod_data.get('items_verified', {})
        if isinstance(items_verified, str):
            try:
                items_verified = json.loads(items_verified)
            except (json.JSONDecodeError, ValueError):
                items_verified = {}
        unverified = [k for k, v in items_verified.items() if not v]
        if unverified:
            flags.append({
                'code': 'ITEMS_NOT_VERIFIED',
                'message': f'{len(unverified)} item(s) not confirmed as received by farmer.',
                'severity': 'MEDIUM',
            })
            risk_score += min(len(unverified) * 5, 20)

        # ── Final Classification ──────────────────────────────────────────
        risk_score = min(risk_score, 100)
        if risk_score >= 40:
            risk_level = 'HIGH'
        elif risk_score >= 20:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'flags': flags,
            'geofence_result': geofence_result,
            'requires_review': risk_level == 'HIGH',
            'auto_approved': risk_level == 'LOW',
        }
