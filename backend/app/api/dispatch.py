"""
Dispatch Pipeline API
======================
Orchestrates the complete input distribution workflow.

Endpoints exposed under /api/v1/dispatch:

  POST /route
    ▸ Full pipeline: eligibility → inventory → batch → optimize → dispatch → notify

  GET  /eligibility-check/<farmer_id>
    ▸ Proxy to Credit Scoring API

  POST /inventory-check
    ▸ Proxy to Input Acquisition API

  POST /monitoring/push
    ▸ Outbound push to Monitoring Project

  GET  /risk-assessment/<delivery_id>
    ▸ Retrieve anomaly detection result

  POST /geofence-check
    ▸ Real-time single-point geofence validation (used by frontend at PoD time)

  GET  /status/<delivery_id>
    ▸ Current dispatch-pipeline status for a delivery
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

dispatch_bp = Blueprint('dispatch', __name__)


# ---------------------------------------------------------------------------
# Helper: lazy import services (avoids circular imports at module load)
# ---------------------------------------------------------------------------

def _credit_service():
    from app.services.ecosystem_integration import CreditScoringService
    return CreditScoringService()

def _inventory_service():
    from app.services.ecosystem_integration import InputAcquisitionService
    return InputAcquisitionService()

def _monitoring_service():
    from app.services.ecosystem_integration import MonitoringService
    return MonitoringService()

def _anomaly_detector():
    from app.services.anomaly_detection import AnomalyDetector
    return AnomalyDetector()

def _delivery_predictor():
    from app.services.anomaly_detection import DeliveryWindowPredictor
    return DeliveryWindowPredictor()

def _geofence_validator():
    from app.services.anomaly_detection import GeofenceValidator
    return GeofenceValidator()


# ===========================================================================
# 1.  ELIGIBILITY CHECK
# ===========================================================================

@dispatch_bp.route('/eligibility-check/<farmer_id>', methods=['GET'])
def check_eligibility(farmer_id):
    """
    Proxy to Credit Scoring API.
    Returns eligibility, credit score, risk level.

    Query params:
      order_amount (float): value of the order to check against credit limit
    """
    order_amount = request.args.get('order_amount', type=float)
    result = _credit_service().check_farmer_eligibility(farmer_id, order_amount)
    status = 200 if result.get('eligible') else 403
    return jsonify(result), status


# ===========================================================================
# 2.  INVENTORY CHECK
# ===========================================================================

@dispatch_bp.route('/inventory-check', methods=['POST'])
def check_inventory():
    """
    Proxy to Input Acquisition API.
    Verifies stock is available before committing to dispatch.

    Body (JSON):
      warehouse_id (str)
      items        (list) – [{sku, quantity, input_type, product_name}, ...]
    """
    data = request.get_json(force=True) or {}
    warehouse_id = data.get('warehouse_id')
    items = data.get('items', [])

    if not warehouse_id:
        return jsonify({'error': 'warehouse_id is required'}), 400

    result = _inventory_service().check_inventory_availability(warehouse_id, items)
    status = 200 if result.get('available') else 409
    return jsonify(result), status


# ===========================================================================
# 3.  MAIN DISPATCH PIPELINE  (POST /dispatch/route)
# ===========================================================================

@dispatch_bp.route('/route', methods=['POST'])
def dispatch_route():
    """
    Main dispatch trigger — orchestrates the full pipeline:

    Step 1 │ Eligibility check   → Credit Scoring API
    Step 2 │ Inventory check     → Input Acquisition API
    Step 3 │ Batch creation      → Group orders by district
    Step 4 │ Route optimisation  → TSP Nearest-Neighbor + 2-OPT
    Step 5 │ Dispatch agents     → Assign field agents
    Step 6 │ Notify monitoring   → Push /delivery/status to Monitoring Project

    Body (JSON):
      warehouse_id   (str, required)
      district       (str, required)
      region         (str, required)
      order_ids      (list, required)   – list of Order UUIDs to dispatch

    Returns: dispatch record with pipeline results for each step.
    """
    data = request.get_json(force=True) or {}

    warehouse_id = data.get('warehouse_id')
    district = data.get('district')
    region = data.get('region')
    order_ids = data.get('order_ids', [])

    # ── Validation ───────────────────────────────────────────────────────
    missing = [f for f, v in [
        ('warehouse_id', warehouse_id),
        ('district', district),
        ('region', region),
    ] if not v]
    if missing:
        return jsonify({'error': f'Missing required fields: {missing}'}), 400
    if not order_ids:
        return jsonify({'error': 'order_ids cannot be empty'}), 400

    pipeline = {
        'pipeline_id': f'DISPATCH-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}',
        'warehouse_id': warehouse_id,
        'district': district,
        'region': region,
        'total_orders': len(order_ids),
        'steps': {},
        'status': 'PENDING',
        'dispatched_at': None,
    }

    ineligible = []
    inventory_issues = []

    # ── Step 1: Eligibility Checks ────────────────────────────────────────
    try:
        from app.models import Order, Farmer
        credit_svc = _credit_service()
        eligibility_results = {}

        for oid in order_ids:
            order = Order.query.get(oid)
            if not order:
                continue
            result = credit_svc.check_farmer_eligibility(
                order.farmer_id, order.total_amount
            )
            eligibility_results[order.farmer_id] = result
            if not result.get('eligible'):
                ineligible.append({
                    'farmer_id': order.farmer_id,
                    'order_id': oid,
                    'reason': result.get('reason', 'Not eligible'),
                    'risk_level': result.get('risk_level'),
                })

        pipeline['steps']['eligibility'] = {
            'passed': len(ineligible) == 0,
            'checked': len(eligibility_results),
            'blocked': len(ineligible),
            'ineligible_farmers': ineligible,
        }
    except Exception as exc:
        logger.exception('Eligibility step failed: %s', exc)
        pipeline['steps']['eligibility'] = {'passed': False, 'error': str(exc)}

    # ── Step 2: Inventory Check ───────────────────────────────────────────
    try:
        from app.models import OrderItem
        all_skus = {}
        for oid in order_ids:
            for item in OrderItem.query.filter_by(order_id=oid).all():
                key = item.sku
                if key in all_skus:
                    all_skus[key]['quantity'] += item.quantity
                else:
                    all_skus[key] = {
                        'sku': item.sku,
                        'product_name': item.product_name,
                        'input_type': item.input_type.value if item.input_type else 'other',
                        'quantity': item.quantity,
                    }

        inv_result = _inventory_service().check_inventory_availability(
            warehouse_id, list(all_skus.values())
        )

        for item_status in inv_result.get('items', []):
            if item_status.get('status') != 'sufficient':
                inventory_issues.append(item_status)

        pipeline['steps']['inventory'] = {
            'passed': inv_result.get('available', False),
            'items_checked': len(all_skus),
            'unavailable_items': inventory_issues,
            'source': inv_result.get('source'),
        }
    except Exception as exc:
        logger.exception('Inventory step failed: %s', exc)
        pipeline['steps']['inventory'] = {'passed': False, 'error': str(exc)}

    # ── Step 3 + 4: Batch & Route Optimisation ────────────────────────────
    try:
        from app.services.routing import BatchingEngine
        from app.models import db, Order, Batch, OrderStatus
        import uuid

        # Create batch
        batch_number = f'BATCH-{uuid.uuid4().hex[:8].upper()}'
        batch = Batch(
            batch_number=batch_number,
            warehouse_id=warehouse_id,
            district=district,
            region=region,
            total_orders=len(order_ids),
            status='ready',
        )
        db.session.add(batch)

        # Link orders to batch
        eligible_order_ids = [
            oid for oid in order_ids
            if oid not in [i['order_id'] for i in ineligible]
        ]
        for oid in eligible_order_ids:
            order = Order.query.get(oid)
            if order:
                order.batch_id = batch.id
                order.status = OrderStatus.BATCHED

        db.session.commit()

        # Optimise routes
        engine = BatchingEngine(current_app.config)
        routes = engine.generate_routes_for_batch(batch.id)

        pipeline['steps']['routing'] = {
            'passed': True,
            'batch_id': batch.id,
            'batch_number': batch_number,
            'routes_created': len(routes),
            'orders_routed': len(eligible_order_ids),
        }
    except Exception as exc:
        logger.exception('Routing step failed: %s', exc)
        pipeline['steps']['routing'] = {'passed': False, 'error': str(exc)}

    # ── Step 5: Dispatch Status ───────────────────────────────────────────
    pipeline['status'] = 'DISPATCHED'
    pipeline['dispatched_at'] = datetime.now(timezone.utc).isoformat()

    # ── Step 6: Push to Monitoring ────────────────────────────────────────
    try:
        monitoring_result = _monitoring_service().push_delivery_status(
            delivery_id=pipeline['pipeline_id'],
            status='DISPATCHED',
            metadata={
                'warehouse_id': warehouse_id,
                'district': district,
                'total_orders': len(order_ids),
                'routes': pipeline['steps'].get('routing', {}).get('routes_created', 0),
            },
        )
        pipeline['steps']['monitoring_push'] = {
            'passed': monitoring_result.get('pushed', False),
            'growth_tracking_initiated': monitoring_result.get('growth_tracking_initiated'),
        }
    except Exception as exc:
        logger.exception('Monitoring push failed: %s', exc)
        pipeline['steps']['monitoring_push'] = {'passed': False, 'error': str(exc)}

    return jsonify(pipeline), 201


# ===========================================================================
# 4.  MONITORING PUSH
# ===========================================================================

@dispatch_bp.route('/monitoring/push', methods=['POST'])
def push_to_monitoring():
    """
    Manually push a delivery status event to the Monitoring Project.

    Body (JSON):
      delivery_id (str)
      status      (str)  – DISPATCHED / IN_TRANSIT / DELIVERED / FAILED / HIGH_RISK
      metadata    (dict, optional)
    """
    data = request.get_json(force=True) or {}
    delivery_id = data.get('delivery_id')
    status = data.get('status')

    if not delivery_id or not status:
        return jsonify({'error': 'delivery_id and status are required'}), 400

    result = _monitoring_service().push_delivery_status(
        delivery_id, status, data.get('metadata')
    )
    return jsonify(result), 200


# ===========================================================================
# 5.  RISK ASSESSMENT (stored result per delivery)
# ===========================================================================

@dispatch_bp.route('/risk-assessment/<delivery_id>', methods=['GET'])
def get_risk_assessment(delivery_id):
    """
    Retrieve the stored anomaly-detection result for a completed delivery.
    """
    try:
        from app.models import DeliveryRiskAssessment
        record = DeliveryRiskAssessment.query.filter_by(
            delivery_id=delivery_id
        ).first()
        if not record:
            return jsonify({'error': 'No risk assessment found for this delivery'}), 404

        return jsonify({
            'delivery_id': delivery_id,
            'risk_level': record.risk_level,
            'risk_score': record.risk_score,
            'is_within_geofence': record.is_within_geofence,
            'gps_deviation_meters': record.gps_deviation_meters,
            'anomaly_flags': record.anomaly_flags,
            'requires_review': record.requires_review,
            'auto_approved': record.auto_approved,
            'assessed_at': record.assessed_at.isoformat() if record.assessed_at else None,
        }), 200
    except Exception as exc:
        logger.exception('Risk assessment retrieval failed: %s', exc)
        return jsonify({'error': str(exc)}), 500


# ===========================================================================
# 6.  REAL-TIME GEOFENCE CHECK  (called from frontend at PoD time)
# ===========================================================================

@dispatch_bp.route('/geofence-check', methods=['POST'])
def geofence_check():
    """
    Validate a single GPS point against a farm location.
    Used by the frontend immediately after GPS capture so the agent
    can see whether they're in the right place before submitting the PoD.

    Body (JSON):
      farm_latitude        (float)
      farm_longitude       (float)
      delivery_latitude    (float)
      delivery_longitude   (float)
      geofence_radius      (float, optional — default 50 m)
    """
    data = request.get_json(force=True) or {}
    required = ['farm_latitude', 'farm_longitude', 'delivery_latitude', 'delivery_longitude']
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400

    radius = data.get('geofence_radius', GEOFENCE_RADIUS_METERS)

    from app.services.anomaly_detection import GeofenceValidator, GEOFENCE_RADIUS_METERS
    validator = GeofenceValidator(geofence_radius_meters=radius)
    result = validator.validate(
        float(data['farm_latitude']),
        float(data['farm_longitude']),
        float(data['delivery_latitude']),
        float(data['delivery_longitude']),
    )
    return jsonify(result), 200


# ===========================================================================
# 7.  DELIVERY WINDOW PREDICTION
# ===========================================================================

@dispatch_bp.route('/predict-window', methods=['POST'])
def predict_delivery_window():
    """
    Predict a delivery time window for route planning.

    Body (JSON):
      distance_km    (float)
      num_stops      (int)
      district_type  (str)  – urban / peri_urban / rural / remote
      scheduled_date (str, optional ISO-8601)
    """
    data = request.get_json(force=True) or {}
    distance_km = data.get('distance_km', 0)
    num_stops = data.get('num_stops', 1)
    district_type = data.get('district_type', 'default')
    scheduled_raw = data.get('scheduled_date')

    scheduled_date = None
    if scheduled_raw:
        try:
            scheduled_date = datetime.fromisoformat(scheduled_raw)
        except ValueError:
            pass

    result = _delivery_predictor().predict(
        distance_km=float(distance_km),
        num_stops=int(num_stops),
        district_type=district_type,
        scheduled_date=scheduled_date,
    )
    return jsonify(result), 200


# ===========================================================================
# 8.  PIPELINE STATUS
# ===========================================================================

@dispatch_bp.route('/status/<delivery_id>', methods=['GET'])
def dispatch_status(delivery_id):
    """
    Returns current pipeline status for a delivery, including latest risk assessment.
    """
    try:
        from app.models import Delivery, DeliveryRiskAssessment, DeliveryStatus

        delivery = Delivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'error': 'Delivery not found'}), 404

        risk = DeliveryRiskAssessment.query.filter_by(delivery_id=delivery_id).first()

        return jsonify({
            'delivery_id': delivery_id,
            'delivery_number': delivery.delivery_number,
            'status': delivery.status.value if delivery.status else None,
            'scheduled_date': delivery.scheduled_date.isoformat() if delivery.scheduled_date else None,
            'risk_assessment': {
                'risk_level': risk.risk_level if risk else None,
                'risk_score': risk.risk_score if risk else None,
                'requires_review': risk.requires_review if risk else None,
            } if risk else None,
        }), 200
    except Exception as exc:
        logger.exception('Status retrieval failed: %s', exc)
        return jsonify({'error': str(exc)}), 500
