"""
Simple Mock Backend for Development
Designed to be easily replaced with GrowForMe API integration.

Implements the full ecosystem API surface so the frontend and
integration tests can exercise every pipeline step without needing
live GrowForMe credentials.

Ecosystem endpoints:
  GET  /api/v1/health
  GET  /api/v1/openapi.json            ← Swagger/OpenAPI spec
  GET  /api/v1/deliveries/<id>
  GET  /api/v1/orders/<id>
  POST /api/v1/proof-of-delivery/<id>
  POST /api/v1/batches/regional-cluster ← K-Means regional batching
  GET  /api/v1/dispatch/eligibility-check/<farmer_id>
  POST /api/v1/dispatch/inventory-check
  POST /api/v1/dispatch/route
  POST /api/v1/dispatch/monitoring/push
  POST /api/v1/dispatch/geofence-check
  POST /api/v1/dispatch/predict-window
"""

import hashlib
import hmac
import importlib.util
import json
import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, request
from flask_cors import CORS

# Load batching service directly (bypasses app/__init__.py → SQLAlchemy chain)
_svc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'services', 'batching.py')
_spec = importlib.util.spec_from_file_location('batching', _svc_path)
_batching_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_batching_mod)
RegionalBatchingService = _batching_mod.RegionalBatchingService

app = Flask(__name__)
CORS(app, supports_credentials=True)

DATA_SOURCE = os.getenv('DATA_SOURCE', 'mock')
JWT_SECRET = os.getenv('JWT_SECRET', 'smarttech-dev-jwt-secret-change-in-production')
JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', '8'))

# ============================================================================
# ROLES
#   admin          – full system access, all dashboards
#   warehouse_mgr  – inventory + batching + dispatch
#   field_agent    – their own deliveries + PoD submission
#   supervisor     – review flagged PoDs, read-only on routes
#   farmer         – own orders + delivery status (GrowForMe portal link)
# ============================================================================

ROLE_PERMISSIONS = {
    'admin':         {'dashboard': 'admin',         'scopes': ['*']},
    'warehouse_mgr': {'dashboard': 'warehouse',      'scopes': ['inventory', 'batching', 'dispatch', 'reports']},
    'field_agent':   {'dashboard': 'field_agent',    'scopes': ['deliveries:own', 'pod:submit']},
    'supervisor':    {'dashboard': 'supervisor',     'scopes': ['pod:review', 'deliveries:read', 'routes:read']},
    'farmer':        {'dashboard': 'farmer',         'scopes': ['orders:own', 'deliveries:own']},
}

# Mock user store (in production: query DB with hashed passwords)
# Passwords stored as sha256(password) for demo — use bcrypt in production
def _sha(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

MOCK_USERS = {
    'admin@smarttech.com':    {'id': 'usr-001', 'name': 'Admin User',       'role': 'admin',         'password_hash': _sha('Admin@1234')},
    'warehouse@smarttech.com':{'id': 'usr-002', 'name': 'Adwoa Mensah',     'role': 'warehouse_mgr', 'password_hash': _sha('Warehouse@1234')},
    'agent1@smarttech.com':   {'id': 'usr-003', 'name': 'Kwame Mensah',   'role': 'field_agent',   'password_hash': _sha('Agent@1234')},
    'supervisor@smarttech.com':{'id':'usr-004', 'name': 'Ama Koomson',    'role': 'supervisor',    'password_hash': _sha('Super@1234')},
    'farmer@growforme.com':   {'id': 'usr-005', 'name': 'Kofi Yeboah',    'role': 'farmer',        'password_hash': _sha('Farmer@1234')},
}

# ============================================================================
# MINIMAL JWT  (no external library — stdlib hmac only)
# ============================================================================

import base64

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _create_token(payload: dict) -> str:
    header = _b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
    body   = _b64(json.dumps(payload).encode())
    sig    = _b64(hmac.new(JWT_SECRET.encode(), f'{header}.{body}'.encode(), hashlib.sha256).digest())
    return f'{header}.{body}.{sig}'

def _verify_token(token: str) -> dict | None:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected_sig = _b64(hmac.new(JWT_SECRET.encode(), f'{header}.{body}'.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # Decode body — add padding
        payload = json.loads(base64.urlsafe_b64decode(body + '=='))
        if payload.get('exp', 0) < datetime.now(timezone.utc).timestamp():
            return None
        return payload
    except Exception:
        return None

def _get_token_from_request() -> str | None:
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return request.cookies.get('token')

# ── Auth decorator ────────────────────────────────────────────────────────────

def require_auth(*allowed_roles):
    """Decorator: require a valid JWT and optionally restrict to specific roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _get_token_from_request()
            if not token:
                return jsonify({'error': 'Authentication required', 'code': 'MISSING_TOKEN'}), 401
            payload = _verify_token(token)
            if not payload:
                return jsonify({'error': 'Token invalid or expired', 'code': 'INVALID_TOKEN'}), 401
            if allowed_roles and payload.get('role') not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions', 'code': 'FORBIDDEN',
                                'required_roles': list(allowed_roles),
                                'your_role': payload.get('role')}), 403
            request.current_user = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================================
# MOCK DATA
# ============================================================================

MOCK_FARMER = {
    "id": "farmer-123",
    "name": "Kofi Yeboah",
    "phone_number": "+233501234567",
    "latitude": 5.6037,
    "longitude": -0.1870,
    "district": "Accra",
    "region": "Greater Accra",
    "farm_size_acres": 5.0,
}

mock_delivery = {
    "id": "DEL-001",
    "delivery_number": "DEL-2026041601",
    "order_id": "ORD-001",
    "farmer_id": "farmer-123",
    "farmer": MOCK_FARMER,
    "warehouse_id": "warehouse-001",
    "status": "assigned",
    "scheduled_date": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
}

mock_order = {
    "id": "ORD-001",
    "order_number": "ORD-2026041601",
    "farmer_id": "farmer-123",
    "warehouse_id": "warehouse-001",
    "total_amount": 15750.0,
    "items": [
        {
            "id": "item-1",
            "sku": "SEED-001",
            "product_name": "Certified Wheat Seeds Premium",
            "input_type": "seeds",
            "quantity": 50,
            "unit": "kg",
            "unit_price": 100,
        },
        {
            "id": "item-2",
            "sku": "FERT-001",
            "product_name": "Basal Fertilizer NPK 10:26:26",
            "input_type": "fertilizer_basal",
            "quantity": 100,
            "unit": "kg",
            "unit_price": 45,
        },
        {
            "id": "item-3",
            "sku": "FERT-002",
            "product_name": "Top Dressing Urea 46%",
            "input_type": "fertilizer_top_dressing",
            "quantity": 50,
            "unit": "kg",
            "unit_price": 35,
        },
        {
            "id": "item-4",
            "sku": "CHEM-001",
            "product_name": "Fungicide (Carbendazim 50% WP)",
            "input_type": "chemical",
            "quantity": 10,
            "unit": "liters",
            "unit_price": 250,
        },
        {
            "id": "item-5",
            "sku": "MECH-001",
            "product_name": "Hand Hoe / Desi Plow",
            "input_type": "mechanization",
            "quantity": 2,
            "unit": "pieces",
            "unit_price": 500,
        },
    ],
}


# ============================================================================
# UTILITY — Haversine (metres)
# ============================================================================

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    """
    POST { "email": "...", "password": "..." }
    Returns JWT + role + dashboard path.
    """
    data = request.get_json(force=True) or {}
    email = (data.get('email') or '').lower().strip()
    password = data.get('password') or ''

    user = MOCK_USERS.get(email)
    if not user or user['password_hash'] != _sha(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    role = user['role']
    now = datetime.now(timezone.utc)
    payload = {
        'sub': user['id'],
        'email': email,
        'name': user['name'],
        'role': role,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=JWT_EXPIRY_HOURS)).timestamp()),
    }
    token = _create_token(payload)

    return jsonify({
        'token': token,
        'user': {'id': user['id'], 'name': user['name'], 'email': email, 'role': role},
        'permissions': ROLE_PERMISSIONS[role]['scopes'],
        'dashboard': f"/dashboard/{ROLE_PERMISSIONS[role]['dashboard']}.html",
        'expires_in': JWT_EXPIRY_HOURS * 3600,
    }), 200


@app.route('/api/v1/auth/me', methods=['GET'])
@require_auth()
def me():
    """Return the currently authenticated user's profile."""
    u = request.current_user
    return jsonify({
        'id': u['sub'],
        'email': u['email'],
        'name': u['name'],
        'role': u['role'],
        'permissions': ROLE_PERMISSIONS.get(u['role'], {}).get('scopes', []),
        'dashboard': f"/dashboard/{ROLE_PERMISSIONS.get(u['role'], {}).get('dashboard', 'default')}.html",
    }), 200


@app.route('/api/v1/auth/logout', methods=['POST'])
@require_auth()
def logout():
    """Client should discard the token. Server-side is stateless."""
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/api/v1/auth/users', methods=['GET'])
@require_auth('admin')
def list_users():
    """Admin only — list all users (no password hashes)."""
    users = [
        {'id': u['id'], 'name': u['name'], 'email': email, 'role': u['role']}
        for email, u in MOCK_USERS.items()
    ]
    return jsonify({'users': users, 'total': len(users)}), 200


# ============================================================================
# PERSISTENT MOCK STATE FOR DEMO SESSIONS
# ============================================================================
PERSISTENT_DELIVERIES = [
    {'delivery_id': 'DEL-001', 'farmer': 'Kofi Yeboah', 'district': 'Accra', 'status': 'in_transit', 'eta': '2h 30m', 'pod_submitted': False},
    {'delivery_id': 'DEL-002', 'farmer': 'Abena Osei', 'district': 'Accra', 'status': 'scheduled', 'eta': '4h 00m', 'pod_submitted': False},
    {'delivery_id': 'DEL-003', 'farmer': 'Kwame Adjei (Geofence Test)', 'district': 'Ga West', 'status': 'in_transit', 'eta': '3h 15m', 'pod_submitted': False},
]
PERSISTENT_FLAGGED = []

# ============================================================================
# CORE ENDPOINTS
# ============================================================================

@app.route('/api/v1/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "SmartTechBuddy Input Distribution",
        "version": "1.0.0",
        "data_source": DATA_SOURCE,
        "ecosystem_integrations": {
            "input_acquisition_api": "mock" if DATA_SOURCE == "mock" else "live",
            "credit_scoring_api": "mock" if DATA_SOURCE == "mock" else "live",
            "monitoring_api": "mock" if DATA_SOURCE == "mock" else "live",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/deliveries/<delivery_id>', methods=['GET'])
@require_auth('admin', 'warehouse_mgr', 'field_agent', 'supervisor')
def get_delivery(delivery_id):
    delivery = dict(mock_delivery)
    if delivery_id == "DEL-003":
        delivery["id"] = "DEL-003"
        delivery["delivery_number"] = "DEL-2026041603"
        farmer3 = dict(MOCK_FARMER)
        farmer3["id"] = "farmer-124"
        farmer3["name"] = "Kwame Adjei (Geofence Test)"
        farmer3["latitude"] = 5.764174
        farmer3["longitude"] = -0.219029
        farmer3["district"] = "Ga West"
        delivery["farmer"] = farmer3
    return jsonify(delivery), 200


@app.route('/api/v1/orders/<order_id>', methods=['GET'])
@require_auth('admin', 'warehouse_mgr', 'field_agent', 'supervisor', 'farmer')
def get_order(order_id):
    return jsonify(mock_order), 200


@app.route('/api/v1/proof-of-delivery/<delivery_id>', methods=['POST'])
@require_auth('field_agent', 'admin')
def create_pod(delivery_id):
    """
    Accepts PoD submission, runs anomaly detection, and returns a risk-assessed result.
    In production: saves to DB, calls Twilio SMS, pushes to Monitoring.
    """
    data = request.get_json(force=True) if request.is_json else request.form.to_dict()

    # ── Geofence / Anomaly Detection ────────────────────────────────────
    if delivery_id == "DEL-003":
        farm_lat = 5.764174
        farm_lon = -0.219029
    else:
        farm_lat = MOCK_FARMER['latitude']
        farm_lon = MOCK_FARMER['longitude']
        
    risk_level = 'LOW'
    flags = []
    gps_deviation = None

    try:
        d_lat = float(data.get('location_latitude', 0))
        d_lon = float(data.get('location_longitude', 0))
        gps_deviation = round(_haversine_m(farm_lat, farm_lon, d_lat, d_lon), 2)

        if gps_deviation > 200:
            risk_level = 'HIGH'
            flags.append({
                'code': 'POTENTIAL_DIVERSION',
                'message': f'Delivery is {gps_deviation:.0f} m from registered farm (>200 m threshold).',
                'severity': 'HIGH',
            })
        elif gps_deviation > 50:
            risk_level = 'MEDIUM'
            flags.append({
                'code': 'GPS_DEVIATION',
                'message': f'Delivery GPS is {gps_deviation:.0f} m from farm geofence (50 m radius).',
                'severity': 'MEDIUM',
            })
    except (TypeError, ValueError):
        flags.append({
            'code': 'MISSING_GPS',
            'message': 'GPS coordinates not captured.',
            'severity': 'MEDIUM',
        })
        risk_level = 'MEDIUM'

    # ── Log to console ───────────────────────────────────────────────────
    print(f"\n📦 PROOF OF DELIVERY — {delivery_id}")
    print(f"  Farmer     : {data.get('farmer_name')}")
    print(f"  Phone      : {data.get('farmer_phone')}")
    print(f"  Condition  : {data.get('delivery_condition')}")
    print(f"  GPS        : {data.get('location_latitude')}, {data.get('location_longitude')}")
    print(f"  Deviation  : {gps_deviation} m from registered farm")
    print(f"  Risk Level : {risk_level}")
    print(f"  Flags      : {len(flags)}")
    print(f"  SMS Sent   : {data.get('farmer_phone')}\n")

    pod_id = f"POD-{uuid.uuid4().hex[:8].upper()}"

    # ---- Update Persistent Mock Data ----
    global PERSISTENT_DELIVERIES, PERSISTENT_FLAGGED
    for d in PERSISTENT_DELIVERIES:
        if d['delivery_id'] == delivery_id:
            d['pod_submitted'] = True
            d['status'] = 'delivered'
            break
            
    if risk_level in ['HIGH', 'MEDIUM']:
        PERSISTENT_FLAGGED.append({
            'delivery_id': delivery_id,
            'farmer': data.get('farmer_name', 'Unknown'),
            'risk_level': risk_level,
            'risk_score': 85 if risk_level == 'HIGH' else 50,
            'flags': [f['code'] for f in flags],
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'reviewed': False
        })

    return jsonify({
        "pod_id": pod_id,
        "delivery_id": delivery_id,
        "farmer_name": data.get("farmer_name"),
        "farmer_phone": data.get("farmer_phone"),
        "delivery_condition": data.get("delivery_condition"),
        "message": "Proof of delivery recorded successfully",
        "sms_alert_sent": True,
        "sms_message": (
            f"Hello {data.get('farmer_name')}, your GrowForMe input delivery "
            f"({delivery_id}) has been confirmed. Thank you!"
        ),
        "risk_assessment": {
            "risk_level": risk_level,
            "gps_deviation_meters": gps_deviation,
            "is_within_geofence": (gps_deviation is not None and gps_deviation <= 50),
            "flags": flags,
            "requires_review": risk_level == 'HIGH',
            "auto_approved": risk_level == 'LOW',
        },
        "monitoring_push": {
            "pushed": True,
            "status": "DELIVERED",
            "growth_tracking_initiated": True,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 201


# ============================================================================
# DISPATCH PIPELINE ENDPOINTS
# ============================================================================

@app.route('/api/v1/dispatch/eligibility-check/<farmer_id>', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def eligibility_check(farmer_id):
    """
    Proxy: Credit Scoring API — GET /farmer/{id}/eligibility
    Ensures inputs only go to farmers who passed the risk assessment.
    """
    order_amount = request.args.get('order_amount', type=float)
    now = datetime.now(timezone.utc)
    return jsonify({
        "farmer_id": farmer_id,
        "eligible": True,
        "credit_score": 724,
        "risk_level": "LOW",
        "max_credit_limit": 50000.0,
        "order_amount": order_amount,
        "within_limit": True,
        "reason": "Good repayment history; credit score above threshold.",
        "source": "mock_credit_scoring_api",
        "checked_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
    }), 200


@app.route('/api/v1/dispatch/inventory-check', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def inventory_check():
    """
    Proxy: Input Acquisition API — GET /inventory/available
    You only distribute what has been sourced.
    """
    data = request.get_json(force=True) or {}
    items = data.get('items', [])

    items_status = [{
        "sku": item.get('sku', 'UNKNOWN'),
        "product_name": item.get('product_name', ''),
        "input_type": item.get('input_type', 'other'),
        "requested": item.get('quantity', 0),
        "available": item.get('quantity', 0) + 200,
        "status": "sufficient",
    } for item in items]

    return jsonify({
        "available": True,
        "warehouse_id": data.get('warehouse_id', 'warehouse-001'),
        "items": items_status,
        "source": "mock_input_acquisition_api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/dispatch/route', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def dispatch_route():
    """
    Main dispatch trigger.
    Runs: eligibility → inventory → batch → route-optimise → dispatch → monitoring push.
    """
    data = request.get_json(force=True) or {}
    order_ids = data.get('order_ids', ['ORD-001'])
    now = datetime.now(timezone.utc)

    pipeline_id = f"DISPATCH-{now.strftime('%Y%m%d%H%M%S')}"
    batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
    route_id = f"ROUTE-{uuid.uuid4().hex[:6].upper()}"

    return jsonify({
        "pipeline_id": pipeline_id,
        "warehouse_id": data.get('warehouse_id', 'warehouse-001'),
        "district": data.get('district', 'Accra'),
        "region": data.get('region', 'Greater Accra'),
        "total_orders": len(order_ids),
        "status": "DISPATCHED",
        "dispatched_at": now.isoformat(),
        "steps": {
            "eligibility": {
                "passed": True,
                "checked": len(order_ids),
                "blocked": 0,
                "ineligible_farmers": [],
            },
            "inventory": {
                "passed": True,
                "items_checked": 5,
                "unavailable_items": [],
                "source": "mock_input_acquisition_api",
            },
            "routing": {
                "passed": True,
                "batch_id": batch_id,
                "batch_number": f"BATCH-{now.strftime('%Y%m%d')}-01",
                "routes_created": 1,
                "orders_routed": len(order_ids),
                "route_summary": {
                    "route_id": route_id,
                    "total_stops": len(order_ids),
                    "total_distance_km": 24.5,
                    "estimated_hours": 3.2,
                    "algorithm": "nearest_neighbor_tsp + 2opt",
                    "distance_reduction_pct": 18.4,
                },
            },
            "monitoring_push": {
                "passed": True,
                "growth_tracking_initiated": False,
                "status_pushed": "DISPATCHED",
            },
        },
    }), 201


@app.route('/api/v1/dispatch/monitoring/push', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def monitoring_push():
    """Push delivery status to GrowForMe Monitoring Project."""
    data = request.get_json(force=True) or {}
    return jsonify({
        "pushed": True,
        "delivery_id": data.get('delivery_id'),
        "status": data.get('status'),
        "monitoring_team_notified": True,
        "growth_tracking_initiated": data.get('status') == 'DELIVERED',
        "source": "mock_monitoring_api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/dispatch/geofence-check', methods=['POST'])
@require_auth('field_agent', 'admin', 'supervisor')
def geofence_check():
    """
    Real-time geofence validation.
    Called by the frontend right after GPS capture so the agent knows
    whether they are at the right farm before submitting the PoD.
    """
    data = request.get_json(force=True) or {}
    required = ['farm_latitude', 'farm_longitude', 'delivery_latitude', 'delivery_longitude']
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400

    radius = float(data.get('geofence_radius', 50))
    dev = _haversine_m(
        float(data['farm_latitude']), float(data['farm_longitude']),
        float(data['delivery_latitude']), float(data['delivery_longitude']),
    )
    within = dev <= radius

    if dev > 200:
        risk = 'HIGH'
    elif dev > radius:
        risk = 'MEDIUM'
    else:
        risk = 'LOW'

    flags = []
    if not within:
        flags.append({
            'code': 'GPS_DEVIATION',
            'message': f'You are {dev:.0f} m from the registered farm location.',
            'severity': risk,
        })
    if dev > 200:
        flags.append({
            'code': 'POTENTIAL_DIVERSION',
            'message': 'Significant deviation detected — escalate for review.',
            'severity': 'HIGH',
        })

    return jsonify({
        "is_within_geofence": within,
        "deviation_meters": round(dev, 2),
        "geofence_radius_meters": radius,
        "risk_level": risk,
        "flags": flags,
        "expected_location": {
            "latitude": data['farm_latitude'],
            "longitude": data['farm_longitude'],
        },
        "actual_location": {
            "latitude": data['delivery_latitude'],
            "longitude": data['delivery_longitude'],
        },
    }), 200


@app.route('/api/v1/dispatch/predict-window', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def predict_window():
    """Predict delivery time window for a route."""
    data = request.get_json(force=True) or {}
    distance_km = float(data.get('distance_km', 20))
    num_stops = int(data.get('num_stops', 5))
    district_type = data.get('district_type', 'rural')
    now = datetime.now(timezone.utc)

    baselines = {'urban': 2.5, 'peri_urban': 3.5, 'rural': 5.0, 'remote': 8.0, 'default': 4.0}
    day_mult = {0: 1.0, 1: 1.0, 2: 1.05, 3: 1.0, 4: 1.15, 5: 1.3, 6: 1.5}

    travel_h = distance_km / 40.0
    stop_h = num_stops * 0.25
    baseline_h = baselines.get(district_type, 4.0)
    mult = day_mult.get(now.weekday(), 1.0)
    est_h = (travel_h + stop_h + baseline_h) * mult

    return jsonify({
        "estimated_hours": round(est_h, 2),
        "window_start": (now + timedelta(hours=est_h * 0.8)).isoformat(),
        "window_end": (now + timedelta(hours=est_h * 1.2)).isoformat(),
        "confidence": "HIGH" if distance_km < 20 and num_stops <= 5 else (
            "MEDIUM" if distance_km < 50 else "LOW"
        ),
        "model": "weighted_regression_v1",
        "factors": {
            "travel_hours": round(travel_h, 2),
            "stop_hours": round(stop_h, 2),
            "district_baseline_hours": baseline_h,
            "day_of_week_multiplier": mult,
        },
    }), 200


# ============================================================================
# REGIONAL BATCHING — K-MEANS CLUSTERING
# ============================================================================

@app.route('/api/v1/batches/regional-cluster', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def regional_cluster():
    """
    Groups delivery requests into district-level batches using K-Means clustering.

    Request body:
      {
        "deliveries": [
          {
            "delivery_id": "DEL-001",
            "farmer_id": "farmer-123",
            "district": "Accra",
            "latitude": 5.6037,
            "longitude": -0.1870,
            "order_amount": 5000
          },
          ...
        ],
        "max_batch_size": 15   (optional, default 15)
      }

    Response:
      {
        "total_deliveries": 20,
        "num_batches": 2,
        "algorithm": "kmeans_plusplus",
        "batches": [ { "batch_id": ..., "district": ..., "size": ..., ... } ]
      }
    """
    data = request.get_json(force=True) or {}
    deliveries = data.get('deliveries', [])

    if not deliveries:
        return jsonify({'error': 'No deliveries provided'}), 400

    required_keys = {'delivery_id', 'farmer_id', 'latitude', 'longitude'}
    for i, d in enumerate(deliveries):
        missing = required_keys - set(d.keys())
        if missing:
            return jsonify({'error': f'Delivery at index {i} missing keys: {list(missing)}'}), 400

    max_batch_size = int(data.get('max_batch_size', 15))
    service = RegionalBatchingService(max_batch_size=max_batch_size)

    try:
        batches = service.cluster_from_dicts(deliveries)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

    return jsonify({
        "total_deliveries": len(deliveries),
        "num_batches": len(batches),
        "max_batch_size": max_batch_size,
        "algorithm": "kmeans_plusplus",
        "batches": batches,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 201


# ============================================================================
# OPENAPI / SWAGGER SPEC
# ============================================================================

@app.route('/api/v1/openapi.json', methods=['GET'])
def openapi_spec():
    """Serve machine-readable OpenAPI 3.0 specification for GrowForMe integration."""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "SmartTechBuddy Input Distribution API",
            "version": "1.0.0",
            "description": (
                "Last-mile farm input distribution engine for the GrowForMe Agro-FinTech ecosystem. "
                "Handles inventory handshakes, credit eligibility, regional batching (K-Means), "
                "TSP route optimisation, geofenced proof-of-delivery, and anomaly detection."
            ),
            "contact": {"name": "SmartTechBuddy Team"},
        },
        "servers": [{"url": "http://localhost:5000/api/v1", "description": "Development"}],
        "tags": [
            {"name": "system"},
            {"name": "deliveries"},
            {"name": "batching"},
            {"name": "dispatch"},
            {"name": "proof-of-delivery"},
        ],
        "paths": {
            "/health": {
                "get": {
                    "tags": ["system"],
                    "summary": "Health check",
                    "responses": {"200": {"description": "Service healthy"}},
                }
            },
            "/deliveries/{delivery_id}": {
                "get": {
                    "tags": ["deliveries"],
                    "summary": "Get delivery details",
                    "parameters": [{"name": "delivery_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Delivery object with farmer GPS"}},
                }
            },
            "/proof-of-delivery/{delivery_id}": {
                "post": {
                    "tags": ["proof-of-delivery"],
                    "summary": "Submit proof of delivery",
                    "description": "Requires GPS coordinates, Base64 photo, and digital signature. Runs geofence anomaly detection automatically.",
                    "parameters": [{"name": "delivery_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["farmer_name", "farmer_phone", "location_latitude", "location_longitude", "signature_data"],
                                    "properties": {
                                        "farmer_name": {"type": "string"},
                                        "farmer_phone": {"type": "string"},
                                        "delivery_condition": {"type": "string", "enum": ["perfect", "damaged", "partial"]},
                                        "location_latitude": {"type": "number"},
                                        "location_longitude": {"type": "number"},
                                        "signature_data": {"type": "string", "description": "Base64-encoded PNG"},
                                        "photos": {"type": "array", "items": {"type": "string"}},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "PoD recorded with risk assessment"},
                        "400": {"description": "Missing required fields"},
                    },
                }
            },
            "/batches/regional-cluster": {
                "post": {
                    "tags": ["batching"],
                    "summary": "K-Means regional batching",
                    "description": "Groups delivery requests into district batches using K-Means++ clustering to maximise vehicle capacity.",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["deliveries"],
                                    "properties": {
                                        "deliveries": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["delivery_id", "farmer_id", "latitude", "longitude"],
                                                "properties": {
                                                    "delivery_id": {"type": "string"},
                                                    "farmer_id": {"type": "string"},
                                                    "district": {"type": "string"},
                                                    "latitude": {"type": "number"},
                                                    "longitude": {"type": "number"},
                                                    "order_amount": {"type": "number"},
                                                },
                                            },
                                        },
                                        "max_batch_size": {"type": "integer", "default": 15},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "Batches with centroid and member list"}},
                }
            },
            "/dispatch/eligibility-check/{farmer_id}": {
                "get": {
                    "tags": ["dispatch"],
                    "summary": "Credit Scoring eligibility check",
                    "parameters": [
                        {"name": "farmer_id", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "order_amount", "in": "query", "schema": {"type": "number"}},
                    ],
                    "responses": {"200": {"description": "Eligibility result with credit score"}},
                }
            },
            "/dispatch/inventory-check": {
                "post": {
                    "tags": ["dispatch"],
                    "summary": "Input Acquisition inventory handshake",
                    "responses": {"200": {"description": "Per-SKU availability status"}},
                }
            },
            "/dispatch/route": {
                "post": {
                    "tags": ["dispatch"],
                    "summary": "Full 6-step dispatch pipeline",
                    "description": "Eligibility → Inventory → Batch → TSP Route → Dispatch → Monitoring push.",
                    "responses": {"201": {"description": "Pipeline result with route summary"}},
                }
            },
            "/dispatch/geofence-check": {
                "post": {
                    "tags": ["dispatch"],
                    "summary": "Real-time geofence validation (50 m default radius)",
                    "responses": {"200": {"description": "Risk level and anomaly flags"}},
                }
            },
            "/dispatch/predict-window": {
                "post": {
                    "tags": ["dispatch"],
                    "summary": "Predict delivery time window",
                    "responses": {"200": {"description": "Estimated hours, window start/end, confidence"}},
                }
            },
        },
    }
    return jsonify(spec), 200


# ============================================================================
# USER STORY 1 — INPUT DATA INTEGRATION
#   "As a Distribution Manager, I want to sync with the Input Acquisition
#    Project database so that I can see exactly what seeds and fertilizers
#    are available for dispatch."
# ============================================================================

# Rich mock warehouse inventory (mirrors what the Input Acquisition API returns)
MOCK_WAREHOUSE_INVENTORY = {
    "warehouse-001": [
        {"sku": "SEED-001", "product_name": "Certified Wheat Seeds Premium", "input_type": "seeds",
         "quantity_available": 2500, "unit": "kg", "batch_number": "B2026041",
         "expiry_date": "2026-09-30", "reorder_level": 500, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "AgriSeeds Ghana Ltd", "unit_cost": 98.0},
        {"sku": "SEED-002", "product_name": "Basmati Rice Seed (1121)", "input_type": "seeds",
         "quantity_available": 1800, "unit": "kg", "batch_number": "B2026042",
         "expiry_date": "2026-10-15", "reorder_level": 400, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "AgriSeeds Ghana Ltd", "unit_cost": 120.0},
        {"sku": "FERT-001", "product_name": "Basal Fertilizer NPK 10:26:26", "input_type": "fertilizer_basal",
         "quantity_available": 8000, "unit": "kg", "batch_number": "F2026031",
         "expiry_date": "2027-03-01", "reorder_level": 1000, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "CocoBod Inputs", "unit_cost": 44.5},
        {"sku": "FERT-002", "product_name": "Top Dressing Urea 46%", "input_type": "fertilizer_top_dressing",
         "quantity_available": 420, "unit": "kg", "batch_number": "F2026032",
         "expiry_date": "2027-06-01", "reorder_level": 500, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "CocoBod Inputs", "unit_cost": 34.0},
        {"sku": "FERT-003", "product_name": "DAP (Di-ammonium Phosphate)", "input_type": "fertilizer_basal",
         "quantity_available": 3200, "unit": "kg", "batch_number": "F2026033",
         "expiry_date": "2027-03-15", "reorder_level": 600, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "CocoBod Inputs", "unit_cost": 52.0},
        {"sku": "CHEM-001", "product_name": "Fungicide Carbendazim 50% WP", "input_type": "chemical",
         "quantity_available": 150, "unit": "liters", "batch_number": "C2026011",
         "expiry_date": "2027-01-31", "reorder_level": 50, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "Sidalco Ghana Ltd", "unit_cost": 245.0},
        {"sku": "CHEM-002", "product_name": "Herbicide (Atrazine 50% WP)", "input_type": "chemical",
         "quantity_available": 200, "unit": "liters", "batch_number": "C2026012",
         "expiry_date": "2026-12-31", "reorder_level": 40, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "Syngenta Ghana", "unit_cost": 180.0},
        {"sku": "MECH-001", "product_name": "Hand Hoe / Desi Plow", "input_type": "mechanization",
         "quantity_available": 45, "unit": "pieces", "batch_number": "M2026001",
         "expiry_date": None, "reorder_level": 10, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "B.A. Mensah Tools", "unit_cost": 495.0},
        {"sku": "MECH-002", "product_name": "Knapsack Sprayer 16L", "input_type": "mechanization",
         "quantity_available": 30, "unit": "pieces", "batch_number": "M2026002",
         "expiry_date": None, "reorder_level": 8, "last_synced": "2026-04-22T06:00:00Z",
         "supplier": "Ghana Agro Equipment", "unit_cost": 1250.0},
    ]
}


@app.route('/api/v1/inventory/warehouses/<warehouse_id>/stock', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def get_warehouse_stock(warehouse_id):
    """
    USER STORY 1 — sync with Input Acquisition Project.
    Returns live stock levels for a warehouse. In production, this proxies
    GET {GROWFORME_API_URL}/inventory/warehouse/{id}/items.
    Supports ?input_type= filter and ?low_stock_only=true.
    """
    items = MOCK_WAREHOUSE_INVENTORY.get(warehouse_id, [])

    input_type_filter = request.args.get('input_type')
    low_stock_only = request.args.get('low_stock_only', 'false').lower() == 'true'

    if input_type_filter:
        items = [i for i in items if i['input_type'] == input_type_filter]
    if low_stock_only:
        items = [i for i in items if i['quantity_available'] <= i['reorder_level']]

    # Annotate each item with status
    annotated = []
    for item in items:
        status = 'ok'
        if item['quantity_available'] == 0:
            status = 'out_of_stock'
        elif item['quantity_available'] <= item['reorder_level']:
            status = 'low_stock'
        annotated.append({**item, 'stock_status': status})

    total_value = sum(i['quantity_available'] * i['unit_cost'] for i in items)
    low_stock = [i for i in annotated if i['stock_status'] in ('low_stock', 'out_of_stock')]

    return jsonify({
        "warehouse_id": warehouse_id,
        "source": "mock_input_acquisition_api" if DATA_SOURCE == 'mock' else "growforme_api",
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "total_skus": len(annotated),
        "low_stock_count": len(low_stock),
        "total_inventory_value": round(total_value, 2),
        "items": annotated,
        "low_stock_alerts": [
            {"sku": i['sku'], "product_name": i['product_name'],
             "available": i['quantity_available'], "reorder_level": i['reorder_level'],
             "status": i['stock_status']}
            for i in low_stock
        ],
    }), 200


@app.route('/api/v1/inventory/warehouses/<warehouse_id>/sync', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def trigger_inventory_sync(warehouse_id):
    """
    Trigger a manual re-sync from the Input Acquisition Project.
    In production: calls the GrowForMe Input Acquisition API to pull latest stock.
    """
    items = MOCK_WAREHOUSE_INVENTORY.get(warehouse_id, [])
    # Simulate a sync timestamp update
    now = datetime.now(timezone.utc).isoformat()
    return jsonify({
        "warehouse_id": warehouse_id,
        "sync_status": "success",
        "items_synced": len(items),
        "items_created": 0,
        "items_updated": len(items),
        "source_api": "mock_input_acquisition_api" if DATA_SOURCE == 'mock' else "growforme_api",
        "synced_at": now,
        "next_scheduled_sync": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    }), 200


# ============================================================================
# USER STORY 2 & 3 — REGIONAL BATCHING + WAREHOUSE HANDSHAKE (RELEASE ORDER)
#   "As a Logistics Planner, I want to group orders by district."
#   "As a Warehouse Operator, I want a digital Release Order generated when
#    a distribution task is assigned."
# ============================================================================

# Mock pending orders per district
MOCK_PENDING_ORDERS = [
    {"order_id": "ORD-001", "farmer_id": "farmer-001", "farmer_name": "Kofi Yeboah",
     "district": "Accra", "region": "Greater Accra", "latitude": 5.6037, "longitude": -0.1870,
     "total_amount": 15750, "items": [{"sku": "SEED-001", "qty": 50}, {"sku": "FERT-001", "qty": 100}]},
    {"order_id": "ORD-002", "farmer_id": "farmer-002", "farmer_name": "Abena Osei",
     "district": "Accra", "region": "Greater Accra", "latitude": 5.6150, "longitude": -0.1700,
     "total_amount": 9200, "items": [{"sku": "FERT-002", "qty": 100}, {"sku": "CHEM-001", "qty": 5}]},
    {"order_id": "ORD-003", "farmer_id": "farmer-003", "farmer_name": "Yaw Asare",
     "district": "Accra", "region": "Greater Accra", "latitude": 5.5900, "longitude": -0.2000,
     "total_amount": 11300, "items": [{"sku": "SEED-001", "qty": 30}, {"sku": "MECH-001", "qty": 1}]},
    {"order_id": "ORD-004", "farmer_id": "farmer-004", "farmer_name": "Kwame Appiah",
     "district": "Kumasi", "region": "Ashanti", "latitude": 6.6885, "longitude": -1.6244,
     "total_amount": 18200, "items": [{"sku": "FERT-001", "qty": 200}, {"sku": "FERT-002", "qty": 100}]},
    {"order_id": "ORD-005", "farmer_id": "farmer-005", "farmer_name": "Kojo Owusu",
     "district": "Kumasi", "region": "Ashanti", "latitude": 6.7000, "longitude": -1.6100,
     "total_amount": 7800, "items": [{"sku": "SEED-002", "qty": 50}, {"sku": "CHEM-002", "qty": 3}]},
    {"order_id": "ORD-006", "farmer_id": "farmer-006", "farmer_name": "Akosua Boakye",
     "district": "Kumasi", "region": "Ashanti", "latitude": 6.6700, "longitude": -1.6400,
     "total_amount": 13500, "items": [{"sku": "FERT-003", "qty": 150}, {"sku": "MECH-002", "qty": 2}]},
    {"order_id": "ORD-007", "farmer_id": "farmer-007", "farmer_name": "Adwoa Ofori",
     "district": "Tamale", "region": "Northern", "latitude": 9.4008, "longitude": -0.8393,
     "total_amount": 8500, "items": [{"sku": "SEED-001", "qty": 40}, {"sku": "CHEM-001", "qty": 4}]},
    {"order_id": "ORD-008", "farmer_id": "farmer-008", "farmer_name": "Kwasi Addo",
     "district": "Tamale", "region": "Northern", "latitude": 9.4200, "longitude": -0.8100,
     "total_amount": 10200, "items": [{"sku": "FERT-001", "qty": 120}]},
]


@app.route('/api/v1/batches/by-district', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def orders_by_district():
    """
    USER STORY 2 — list pending orders grouped by district.
    Supports ?district=Accra and ?region=Greater Accra filters.
    """
    district_filter = request.args.get('district')
    region_filter = request.args.get('region')

    orders = MOCK_PENDING_ORDERS
    if district_filter:
        orders = [o for o in orders if o['district'].lower() == district_filter.lower()]
    if region_filter:
        orders = [o for o in orders if o['region'].lower() == region_filter.lower()]

    # Group by district
    grouped = {}
    for order in orders:
        d = order['district']
        if d not in grouped:
            grouped[d] = {'district': d, 'region': order['region'], 'orders': [], 'total_amount': 0}
        grouped[d]['orders'].append(order)
        grouped[d]['total_amount'] += order['total_amount']

    districts = list(grouped.values())
    for dist in districts:
        dist['order_count'] = len(dist['orders'])

    return jsonify({
        "total_pending_orders": len(orders),
        "districts_covered": len(districts),
        "districts": districts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/batches/create-from-district', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def create_batch_from_district():
    """
    USER STORY 2 — create a batch from a district's pending orders.
    Runs K-Means to sub-cluster large districts, then returns batch assignments.
    """
    data = request.get_json(force=True) or {}
    district = data.get('district')
    warehouse_id = data.get('warehouse_id', 'warehouse-001')

    if not district:
        return jsonify({'error': 'district is required'}), 400

    orders = [o for o in MOCK_PENDING_ORDERS if o['district'].lower() == district.lower()]
    if not orders:
        return jsonify({'error': f'No pending orders found for district: {district}'}), 404

    # Feed into K-Means clustering service
    delivery_dicts = [{
        'delivery_id': o['order_id'],
        'farmer_id': o['farmer_id'],
        'district': o['district'],
        'latitude': o['latitude'],
        'longitude': o['longitude'],
        'order_amount': o['total_amount'],
    } for o in orders]

    service = RegionalBatchingService()
    batches = service.cluster_from_dicts(delivery_dicts)

    batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    return jsonify({
        "batch_id": batch_id,
        "warehouse_id": warehouse_id,
        "district": district,
        "total_orders": len(orders),
        "num_sub_batches": len(batches),
        "algorithm": "kmeans_plusplus",
        "batches": batches,
        "status": "created",
        "created_at": now.isoformat(),
    }), 201


@app.route('/api/v1/batches/<batch_id>/release-order', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def generate_release_order(batch_id):
    """
    USER STORY 3 — WAREHOUSE HANDSHAKE / RELEASE ORDER.
    Generates a digital Release Order (RO) when a batch is dispatched.
    Formally moves inventory out of storage in the system of record.
    In production: writes to DB, triggers inventory deduction in Input Acquisition API.
    """
    data = request.get_json(force=True) or {}
    district = data.get('district', 'Accra')
    warehouse_id = data.get('warehouse_id', 'warehouse-001')
    orders = data.get('orders', MOCK_PENDING_ORDERS[:3])

    ro_number = f"RO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)

    # Aggregate items across all orders in the batch
    item_aggregator = {}
    for order in orders:
        for item in order.get('items', []):
            sku = item['sku']
            if sku not in item_aggregator:
                # Look up product details
                all_items = MOCK_WAREHOUSE_INVENTORY.get(warehouse_id, [])
                product = next((i for i in all_items if i['sku'] == sku), {})
                item_aggregator[sku] = {
                    'sku': sku,
                    'product_name': product.get('product_name', sku),
                    'input_type': product.get('input_type', 'other'),
                    'unit': product.get('unit', 'kg'),
                    'unit_cost': product.get('unit_cost', 0),
                    'total_quantity': 0,
                }
            item_aggregator[sku]['total_quantity'] += item.get('qty', 0)

    line_items = list(item_aggregator.values())
    for li in line_items:
        li['total_value'] = round(li['total_quantity'] * li['unit_cost'], 2)

    total_value = sum(li['total_value'] for li in line_items)

    release_order = {
        "release_order_number": ro_number,
        "batch_id": batch_id,
        "warehouse_id": warehouse_id,
        "district": district,
        "status": "issued",
        "issued_by": (request.current_user or {}).get('name', 'System'),
        "issued_at": now.isoformat(),
        "valid_until": (now + timedelta(hours=48)).isoformat(),
        "total_orders": len(orders),
        "line_items": line_items,
        "total_value": round(total_value, 2),
        "inventory_deducted": True,
        "source_api_notified": DATA_SOURCE != 'mock',
        "instructions": [
            "1. Verify each item quantity against physical stock before loading.",
            "2. Field agent must countersign on first delivery.",
            "3. Return this Release Order number with all PoD submissions.",
            "4. Any discrepancy must be reported within 2 hours of dispatch.",
        ],
        "signatures_required": {
            "warehouse_operator": None,
            "field_agent": None,
            "supervisor_approval": total_value > 50000,
        },
    }

    return jsonify(release_order), 201


# ============================================================================
# USER STORY 4 — AUTOMATED SMS ALERTS
#   "As a Farmer, I want an SMS notification when my inputs are
#    'Out for Delivery' so I can prepare for receipt at my farm gate."
# ============================================================================

@app.route('/api/v1/deliveries/<delivery_id>/send-sms', methods=['POST'])
@require_auth('admin', 'warehouse_mgr', 'field_agent')
def send_sms_alert(delivery_id):
    """
    Triggers an SMS to the farmer when the delivery status changes.
    In production: calls Twilio REST API using TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN.
    Supported trigger events:
      - out_for_delivery  → "Your inputs are on the way!"
      - arrived           → "Agent has arrived at your farm gate."
      - delivered         → "Delivery confirmed. Thank you!"
      - failed            → "Delivery could not be completed. Contact us."
    """
    data = request.get_json(force=True) or {}
    event = data.get('event', 'out_for_delivery')
    farmer_name = data.get('farmer_name', MOCK_FARMER['name'])
    farmer_phone = data.get('farmer_phone', MOCK_FARMER['phone_number'])
    agent_name = data.get('agent_name', 'Kwame Mensah')
    eta_minutes = data.get('eta_minutes', 45)

    SMS_TEMPLATES = {
        'out_for_delivery': (
            f"Dear {farmer_name}, your GrowForMe farm inputs ({delivery_id}) are "
            f"OUT FOR DELIVERY. Your field agent {agent_name} will arrive in approx "
            f"{eta_minutes} minutes. Please be available at your farm gate. "
            f"Helpline: 1800-GROWFORME"
        ),
        'arrived': (
            f"Dear {farmer_name}, your GrowForMe field agent {agent_name} has "
            f"ARRIVED at your farm. Please verify and sign for your inputs. "
            f"Delivery ID: {delivery_id}"
        ),
        'delivered': (
            f"Dear {farmer_name}, your GrowForMe input delivery ({delivery_id}) is "
            f"CONFIRMED. Thank you for using GrowForMe. Your inputs are registered "
            f"for growth tracking. Happy farming!"
        ),
        'failed': (
            f"Dear {farmer_name}, we could not complete your delivery ({delivery_id}) "
            f"today. Please contact GrowForMe support at 1800-GROWFORME to reschedule."
        ),
    }

    message_body = SMS_TEMPLATES.get(event, SMS_TEMPLATES['out_for_delivery'])

    # In production: use Twilio
    # from twilio.rest import Client
    # client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
    # msg = client.messages.create(body=message_body, from_=os.getenv('TWILIO_PHONE_NUMBER'), to=farmer_phone)
    # sms_sid = msg.sid

    sms_sid = f"SM{uuid.uuid4().hex[:32].upper()}"  # mock Twilio SID

    print(f"\n📱 SMS ALERT [{event.upper()}]")
    print(f"  To      : {farmer_phone} ({farmer_name})")
    print(f"  Message : {message_body[:80]}…")
    print(f"  SID     : {sms_sid}")

    return jsonify({
        "sms_sent": True,
        "delivery_id": delivery_id,
        "event": event,
        "farmer_phone": farmer_phone,
        "farmer_name": farmer_name,
        "message_preview": message_body[:120] + ('…' if len(message_body) > 120 else ''),
        "full_message": message_body,
        "sms_sid": sms_sid,
        "provider": "twilio_mock" if DATA_SOURCE == 'mock' else "twilio_live",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/deliveries/bulk-sms', methods=['POST'])
@require_auth('admin', 'warehouse_mgr')
def bulk_sms_out_for_delivery():
    """
    Send 'Out for Delivery' SMS to all farmers in a batch at once.
    Called when a driver starts a route.
    """
    data = request.get_json(force=True) or {}
    delivery_ids = data.get('delivery_ids', ['DEL-001'])
    agent_name = data.get('agent_name', 'Kwame Mensah')
    eta_minutes = data.get('eta_minutes', 45)

    results = []
    for did in delivery_ids:
        sms_sid = f"SM{uuid.uuid4().hex[:32].upper()}"
        results.append({
            "delivery_id": did,
            "sms_sent": True,
            "sms_sid": sms_sid,
        })

    return jsonify({
        "total_sent": len(results),
        "event": "out_for_delivery",
        "agent_name": agent_name,
        "estimated_arrival_minutes": eta_minutes,
        "results": results,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }), 200


# ============================================================================
# USER STORY 6 — ANALYTICS DASHBOARD (CEO VIEW)
#   "As the GrowForMe CEO, I want a real-time view of 'Delivered vs. Pending'
#    inputs across all regions."
# ============================================================================

MOCK_ANALYTICS = {
    "summary": {
        "total_orders": 847,
        "delivered": 612,
        "in_transit": 89,
        "pending_dispatch": 103,
        "failed": 43,
        "delivery_rate_pct": 72.3,
        "on_time_rate_pct": 87.4,
    },
    "by_region": [
        {"region": "Greater Accra", "total": 320, "delivered": 241, "in_transit": 38, "pending": 31, "failed": 10},
        {"region": "Ashanti",       "total": 215, "delivered": 162, "in_transit": 22, "pending": 21, "failed": 10},
        {"region": "Eastern",       "total": 180, "delivered": 120, "in_transit": 18, "pending": 32, "failed": 10},
        {"region": "Northern",      "total":  82, "delivered":  56, "in_transit":  8, "pending": 12, "failed":  6},
        {"region": "Central",       "total":  50, "delivered":  33, "in_transit":  3, "pending":  7, "failed":  7},
    ],
    "by_input_type": [
        {"input_type": "Seeds",               "dispatched": 290, "delivered": 241, "pending": 49},
        {"input_type": "Fertilizer (Basal)",  "dispatched": 310, "delivered": 228, "pending": 82},
        {"input_type": "Fertilizer (Top)",    "dispatched": 185, "delivered": 140, "pending": 45},
        {"input_type": "Chemical",            "dispatched":  98, "delivered":  72, "pending": 26},
        {"input_type": "Mechanization",       "dispatched":  42, "delivered":  30, "pending": 12},
    ],
    "weekly_trend": [
        {"week": "Apr 1–7",  "dispatched": 145, "delivered": 128, "failed": 6},
        {"week": "Apr 8–14", "dispatched": 168, "delivered": 149, "failed": 8},
        {"week": "Apr 15–21","dispatched": 192, "delivered": 170, "failed": 11},
        {"week": "Apr 22–28","dispatched": 112, "delivered":  89, "failed": 5},
    ],
    "high_risk_pods": 23,
    "sms_alerts_sent": 1241,
    "avg_delivery_time_hours": 4.7,
}


@app.route('/api/v1/analytics/overview', methods=['GET'])
@require_auth('admin')
def analytics_overview():
    """CEO dashboard — delivered vs pending across all regions."""
    return jsonify({
        **MOCK_ANALYTICS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": DATA_SOURCE,
    }), 200


@app.route('/api/v1/analytics/by-region', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def analytics_by_region():
    """Regional breakdown for logistics planners."""
    region_filter = request.args.get('region')
    data = MOCK_ANALYTICS['by_region']
    if region_filter:
        data = [r for r in data if r['region'].lower() == region_filter.lower()]
    return jsonify({"regions": data, "timestamp": datetime.now(timezone.utc).isoformat()}), 200


@app.route('/api/v1/analytics/by-input-type', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def analytics_by_input_type():
    """Breakdown by seed/fertilizer/chemical/mechanization type."""
    return jsonify({
        "by_input_type": MOCK_ANALYTICS['by_input_type'],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/analytics/weekly-trend', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def analytics_weekly_trend():
    """Weekly dispatch vs delivery trend."""
    return jsonify({
        "weekly_trend": MOCK_ANALYTICS['weekly_trend'],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


# ============================================================================
# USER STORY 7 — INTELLIGENT ROUTING (DRIVER MAP VIEW)
#   "As a Driver, I want a digital map with the most efficient sequence of
#    farm drop-offs to reduce delivery time and fuel costs."
# ============================================================================

# Mock route with sequenced stops for DEL-001's batch
MOCK_ROUTE_STOPS = [
    {"stop_number": 1, "delivery_id": "DEL-001", "farmer_name": "Kofi Yeboah",
     "address": "Osu, Accra", "latitude": 5.6037, "longitude": -0.1870,
     "district": "Accra", "estimated_arrival": "09:30", "distance_from_prev_km": 0,
     "items_summary": "Wheat Seeds 50kg, NPK 100kg", "status": "pending"},
    {"stop_number": 2, "delivery_id": "DEL-002", "farmer_name": "Abena Osei",
     "address": "Cantonments, Accra", "latitude": 5.6150, "longitude": -0.1700,
     "district": "Accra", "estimated_arrival": "10:10", "distance_from_prev_km": 3.2,
     "items_summary": "Urea 100kg, Fungicide 5L", "status": "pending"},
    {"stop_number": 3, "delivery_id": "DEL-003", "farmer_name": "Yaw Asare",
     "address": "East Legon, Accra", "latitude": 5.5900, "longitude": -0.2000,
     "district": "Accra", "estimated_arrival": "11:00", "distance_from_prev_km": 5.8,
     "items_summary": "Wheat Seeds 30kg, Hand Hoe 1 pc", "status": "pending"},
]


@app.route('/api/v1/routes/<route_id>/map', methods=['GET'])
@require_auth('admin', 'warehouse_mgr', 'field_agent')
def get_route_map(route_id):
    """
    USER STORY 7 — optimized delivery sequence for a driver.
    Returns stop sequence + GPS coordinates + ETA + Google Maps deep link per stop.
    """
    warehouse_lat, warehouse_lon = 5.6080, -0.1820  # Central Warehouse

    stops = MOCK_ROUTE_STOPS
    total_distance = sum(s['distance_from_prev_km'] for s in stops)
    total_distance += 6.2  # return to warehouse

    # Build Google Maps directions URL (all stops chained)
    waypoints = '|'.join(f"{s['latitude']},{s['longitude']}" for s in stops[:-1])
    final = stops[-1]
    gmaps_url = (
        f"https://www.google.com/maps/dir/{warehouse_lat},{warehouse_lon}/"
        + '/'.join(f"{s['latitude']},{s['longitude']}" for s in stops)
        + f"/{warehouse_lat},{warehouse_lon}"
    )

    # Per-stop deep link
    enriched_stops = []
    for s in stops:
        enriched_stops.append({
            **s,
            "google_maps_link": f"https://www.google.com/maps?q={s['latitude']},{s['longitude']}",
            "navigate_link": f"https://www.google.com/maps/dir/?api=1&destination={s['latitude']},{s['longitude']}&travelmode=driving",
        })

    return jsonify({
        "route_id": route_id,
        "warehouse": {
            "name": "Central Warehouse — Accra",
            "latitude": warehouse_lat,
            "longitude": warehouse_lon,
            "address": "Industrial Area, Accra, Greater Accra 143001",
        },
        "total_stops": len(stops),
        "total_distance_km": round(total_distance, 1),
        "estimated_duration_hours": round(total_distance / 40 + len(stops) * 0.25, 1),
        "algorithm": "nearest_neighbor_tsp + 2opt",
        "distance_reduction_pct": 18.4,
        "full_route_google_maps": gmaps_url,
        "stops": enriched_stops,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/routes/<route_id>/stops/<int:stop_number>/complete', methods=['POST'])
@require_auth('field_agent', 'admin')
def complete_stop(route_id, stop_number):
    """
    Mark a stop as completed. Triggers SMS 'arrived' alert to next farmer.
    Called by the driver app after each PoD submission.
    """
    data = request.get_json(force=True) or {}
    pod_id = data.get('pod_id', f"POD-{uuid.uuid4().hex[:8].upper()}")
    now = datetime.now(timezone.utc)

    next_stop = next((s for s in MOCK_ROUTE_STOPS if s['stop_number'] == stop_number + 1), None)

    return jsonify({
        "route_id": route_id,
        "stop_completed": stop_number,
        "pod_id": pod_id,
        "completed_at": now.isoformat(),
        "next_stop": next_stop,
        "next_sms_queued": next_stop is not None,
        "next_farmer_notified": next_stop is not None,
    }), 200


# ============================================================================
# ROLE-SPECIFIC DATA ENDPOINTS
# ============================================================================

@app.route('/api/v1/dashboard/admin/stats', methods=['GET'])
@require_auth('admin')
def admin_stats():
    """Admin dashboard — system-wide statistics."""
    return jsonify({
        'total_orders': 128,
        'pending_batches': 5,
        'active_deliveries': 23,
        'pod_pending_review': 7,
        'flagged_high_risk': 3,
        'total_users': len(MOCK_USERS),
        'users_by_role': {role: sum(1 for u in MOCK_USERS.values() if u['role'] == role)
                          for role in ROLE_PERMISSIONS},
        'data_source': DATA_SOURCE,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/dashboard/warehouse/stats', methods=['GET'])
@require_auth('admin', 'warehouse_mgr')
def warehouse_stats():
    """Warehouse manager dashboard — inventory + dispatch status."""
    return jsonify({
        'total_batches_today': 12,
        'routes_optimized': 8,
        'inventory_alerts': 3,
        'items_low_stock': ['SEED-001', 'FERT-002'],
        'dispatch_queue': 14,
        'deliveries_in_transit': 23,
        'data_source': DATA_SOURCE,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/dashboard/field-agent/deliveries', methods=['GET'])
@require_auth('field_agent', 'admin')
def field_agent_deliveries():
    """Field agent dashboard — agent's assigned deliveries."""
    user = request.current_user
    global PERSISTENT_DELIVERIES
    
    # In production: filter by agent_id == user['sub']
    completed = sum(1 for d in PERSISTENT_DELIVERIES if d['status'] == 'delivered')
    pending = len(PERSISTENT_DELIVERIES) - completed
    
    return jsonify({
        'agent_id': user['sub'],
        'agent_name': user['name'],
        'deliveries': PERSISTENT_DELIVERIES,
        'completed_today': completed,
        'pending': pending,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/dashboard/supervisor/flagged', methods=['GET'])
@require_auth('supervisor', 'admin')
def supervisor_flagged():
    """Supervisor dashboard — high-risk PoDs awaiting review."""
    global PERSISTENT_FLAGGED
    default_flags = [
        {'delivery_id': 'DEL-009', 'farmer': 'Kwaku Mensah', 'risk_level': 'HIGH',
         'risk_score': 85, 'flags': ['LOCATION_MISMATCH', 'LATE_DELIVERY'],
         'submitted_at': '2026-04-16T09:22:00Z', 'reviewed': False}
    ]
    
    all_flags = default_flags + [f for f in PERSISTENT_FLAGGED if not f.get('reviewed')]
    return jsonify({
        'flagged_deliveries': all_flags,
        'total_flagged': len(all_flags),
        'reviewed_today': sum(1 for f in PERSISTENT_FLAGGED if f.get('reviewed')),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/v1/dashboard/supervisor/review/<delivery_id>', methods=['POST'])
@require_auth('supervisor', 'admin')
def supervisor_review(delivery_id):
    """Supervisor approves or escalates a flagged PoD."""
    data = request.get_json(force=True) or {}
    action = data.get('action')  # 'approve' | 'escalate' | 'reject'
    notes = data.get('notes', '')
    if action not in ('approve', 'escalate', 'reject'):
        return jsonify({'error': "action must be one of: approve, escalate, reject"}), 400
    reviewer = request.current_user
    return jsonify({
        'delivery_id': delivery_id,
        'action': action,
        'reviewed_by': reviewer['name'],
        'reviewer_id': reviewer['sub'],
        'notes': notes,
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'status': 'review_complete',
    }), 200


@app.route('/api/v1/dashboard/farmer/status', methods=['GET'])
@require_auth('farmer', 'admin')
def farmer_status():
    """Farmer portal — own order + delivery status."""
    user = request.current_user
    # In production: filter by farmer.user_id == user['sub']
    return jsonify({
        'farmer_id': user['sub'],
        'farmer_name': user['name'],
        'orders': [
            {'order_id': 'ORD-001', 'status': 'dispatched', 'total_amount': 5000,
             'items': ['Wheat Seeds (50kg)', 'NPK Fertilizer (2 bags)'],
             'delivery_eta': '2026-04-17T10:00:00Z'},
        ],
        'deliveries': [
            {'delivery_id': 'DEL-001', 'status': 'in_transit',
             'agent_name': 'Kwame Mensah', 'agent_phone': '+233501234567',
             'eta': '2h 30m'},
        ],
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("SmartTechBuddy Input Distribution — Development Server")
    print("=" * 60)
    print("\n✓ Backend API  : http://localhost:5000/api/v1/health")
    print("✓ OpenAPI Spec : http://localhost:5000/api/v1/openapi.json")
    print("✓ PoD Interface: http://localhost:8000?delivery_id=DEL-001")
    print("\nBatching:")
    print("  POST /api/v1/batches/regional-cluster  (K-Means clustering)")
    print("\nDispatch Pipeline:")
    print("  GET  /api/v1/dispatch/eligibility-check/<farmer_id>")
    print("  POST /api/v1/dispatch/inventory-check")
    print("  POST /api/v1/dispatch/route")
    print("  POST /api/v1/dispatch/geofence-check")
    print("  POST /api/v1/dispatch/monitoring/push")
    print("  POST /api/v1/dispatch/predict-window")
    print("\n" + "=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

