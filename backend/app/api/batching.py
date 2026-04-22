"""
Batching & Routing API Endpoints
"""

from flask import Blueprint, request, jsonify, current_app
from app.models import db, Batch, Route, Order, OrderStatus, Warehouse, Farmer
from app.services.routing import BatchingEngine, RoutingEngine
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

batching_bp = Blueprint('batching', __name__, url_prefix='/batches')

# ============================================================================
# Batch Creation Endpoints
# ============================================================================

@batching_bp.route('', methods=['GET'])
def list_batches():
    """List batches"""
    try:
        warehouse_id = request.args.get('warehouse_id')
        district = request.args.get('district')
        status = request.args.get('status')
        
        query = Batch.query
        
        if warehouse_id:
            query = query.filter_by(warehouse_id=warehouse_id)
        if district:
            query = query.filter_by(district=district)
        if status:
            query = query.filter_by(status=status)
        
        batches = query.all()
        
        return jsonify({
            'total': len(batches),
            'batches': [{
                'id': b.id,
                'batch_number': b.batch_number,
                'warehouse_id': b.warehouse_id,
                'district': b.district,
                'region': b.region,
                'total_orders': b.total_orders,
                'total_weight_kg': b.total_weight_kg,
                'total_value': b.total_value,
                'status': b.status,
                'created_at': b.created_at.isoformat() if b.created_at else None
            } for b in batches]
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing batches: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batching_bp.route('', methods=['POST'])
def create_batch():
    """Create a new batch from pending orders"""
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse_id')
        district = data.get('district')
        region = data.get('region')
        order_ids = data.get('order_ids', [])
        
        # Validate warehouse
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'error': 'Warehouse not found'}), 404
        
        # Create batch
        batch_number = f"BATCH-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        
        batch = Batch(
            batch_number=batch_number,
            warehouse_id=warehouse_id,
            district=district,
            region=region,
            status='pending'
        )
        
        # Add orders to batch
        total_weight = 0
        total_value = 0
        
        for order_id in order_ids:
            order = Order.query.get(order_id)
            if order and order.status == OrderStatus.PENDING:
                order.batch_id = batch.id
                order.status = OrderStatus.BATCHED
                
                # Calculate metrics
                for item in order.order_items:
                    total_weight += item.quantity
                total_value += order.total_amount
        
        batch.total_orders = len(order_ids)
        batch.total_weight_kg = total_weight
        batch.total_value = total_value
        
        db.session.add(batch)
        db.session.commit()
        
        return jsonify({
            'id': batch.id,
            'batch_number': batch.batch_number,
            'total_orders': batch.total_orders,
            'total_weight_kg': batch.total_weight_kg,
            'total_value': batch.total_value,
            'message': 'Batch created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating batch: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@batching_bp.route('/<batch_id>', methods=['GET'])
def get_batch(batch_id):
    """Get batch details"""
    try:
        batch = Batch.query.get(batch_id)
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        return jsonify({
            'id': batch.id,
            'batch_number': batch.batch_number,
            'warehouse_id': batch.warehouse_id,
            'district': batch.district,
            'region': batch.region,
            'total_orders': batch.total_orders,
            'total_weight_kg': batch.total_weight_kg,
            'total_value': batch.total_value,
            'status': batch.status,
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'orders': [o.id for o in batch.orders]
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting batch: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Route Generation Endpoints
# ============================================================================

@batching_bp.route('/<batch_id>/routes', methods=['GET'])
def get_batch_routes(batch_id):
    """Get routes for a batch"""
    try:
        routes = Route.query.filter_by(batch_id=batch_id).all()
        
        return jsonify({
            'batch_id': batch_id,
            'total_routes': len(routes),
            'routes': [{
                'id': r.id,
                'route_number': r.route_number,
                'district': r.district,
                'total_stops': r.total_stops,
                'total_distance_km': r.total_distance_km,
                'estimated_delivery_time_hours': r.estimated_delivery_time_hours,
                'status': r.status,
                'created_at': r.created_at.isoformat() if r.created_at else None
            } for r in routes]
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting batch routes: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batching_bp.route('/<batch_id>/optimize-routes', methods=['POST'])
def optimize_batch_routes(batch_id):
    """Generate optimized routes for a batch using TSP algorithm"""
    try:
        batch = Batch.query.get(batch_id)
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        warehouse = Warehouse.query.get(batch.warehouse_id)
        if not warehouse:
            return jsonify({'error': 'Warehouse not found'}), 404
        
        # Initialize routing engine with config
        config = {
            'MAX_DELIVERY_STOPS_PER_ROUTE': current_app.config.get('MAX_DELIVERY_STOPS_PER_ROUTE', 30),
            'OPTIMAL_ROUTE_DISTANCE_KM': current_app.config.get('OPTIMAL_ROUTE_DISTANCE_KM', 100)
        }
        
        routing_engine = RoutingEngine(config)
        batching_engine = BatchingEngine(config)
        
        # Get farmers from batch orders
        farmer_ids = db.session.query(Farmer.id).join(Order).filter(
            Order.batch_id == batch_id
        ).distinct().all()
        
        farmers = Farmer.query.filter(Farmer.id.in_([f[0] for f in farmer_ids])).all()
        
        if not farmers:
            return jsonify({'error': 'No farmers found in batch'}), 400
        
        # Optimize route
        optimized_sequence, total_distance = routing_engine.nearest_neighbor_tsp(
            warehouse, farmers
        )
        
        # Apply 2-OPT optimization
        optimized_sequence, optimized_distance = routing_engine.two_opt_optimization(
            optimized_sequence, warehouse
        )
        
        # Calculate delivery time estimate
        est_delivery_time = routing_engine.estimate_delivery_time(
            optimized_distance, len(optimized_sequence)
        )
        
        # Create route record
        route_number = f"ROUTE-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        
        route = Route(
            route_number=route_number,
            batch_id=batch_id,
            warehouse_id=warehouse.id,
            district=batch.district,
            total_stops=len(optimized_sequence),
            total_distance_km=optimized_distance,
            estimated_delivery_time_hours=est_delivery_time,
            total_orders=batch.total_orders,
            total_weight_kg=batch.total_weight_kg,
            status='pending',
            optimized_sequence=[f.id for f in optimized_sequence]
        )
        
        db.session.add(route)
        db.session.commit()
        
        return jsonify({
            'route_id': route.id,
            'route_number': route.route_number,
            'total_stops': route.total_stops,
            'total_distance_km': round(route.total_distance_km, 2),
            'estimated_delivery_time_hours': round(route.estimated_delivery_time_hours, 2),
            'optimized_sequence': route.optimized_sequence,
            'message': 'Route optimized successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error optimizing routes: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================================================
# Batching Automation Endpoints
# ============================================================================

@batching_bp.route('/auto-batch-district', methods=['POST'])
def auto_batch_by_district():
    """Automatically create and optimize batches for a district"""
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse_id')
        district = data.get('district')
        region = data.get('region')
        
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'error': 'Warehouse not found'}), 404
        
        # Initialize batching engine
        config = {
            'MAX_ORDERS_PER_BATCH': current_app.config.get('MAX_ORDERS_PER_BATCH', 50),
            'MAX_DELIVERY_STOPS_PER_ROUTE': current_app.config.get('MAX_DELIVERY_STOPS_PER_ROUTE', 30),
            'OPTIMAL_ROUTE_DISTANCE_KM': current_app.config.get('OPTIMAL_ROUTE_DISTANCE_KM', 100)
        }
        
        batching_engine = BatchingEngine(config)
        
        # Create batches for district
        batch_configs = batching_engine.create_batches_for_district(
            warehouse_id, district, region
        )
        
        created_batches = []
        
        for batch_config in batch_configs:
            batch_number = f"BATCH-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6].upper()}"
            
            batch = Batch(
                batch_number=batch_number,
                warehouse_id=batch_config['warehouse_id'],
                district=batch_config['district'],
                region=batch_config['region'],
                status='pending',
                total_orders=batch_config['order_count'],
                total_weight_kg=batch_config['total_weight_kg'],
                total_value=batch_config['total_value']
            )
            
            # Assign orders to batch
            for order_id in batch_config['orders']:
                order = Order.query.get(order_id)
                if order:
                    order.batch_id = batch.id
                    order.status = OrderStatus.BATCHED
            
            db.session.add(batch)
            created_batches.append({
                'batch_number': batch.batch_number,
                'orders': len(batch_config['orders'])
            })
        
        db.session.commit()
        
        return jsonify({
            'batches_created': len(created_batches),
            'batches': created_batches,
            'message': f'Created {len(created_batches)} batches for {district}'
        }), 201
    
    except Exception as e:
        logger.error(f"Error auto batching: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
