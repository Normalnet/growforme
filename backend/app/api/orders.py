"""
Orders API Endpoints
"""

from flask import Blueprint, request, jsonify
from app.models import db, Order, OrderStatus, Farmer, Warehouse, OrderItem, InputType
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

# ============================================================================
# Order Management Endpoints
# ============================================================================

@orders_bp.route('', methods=['GET'])
def list_orders():
    """List orders with filtering"""
    try:
        status = request.args.get('status')
        farmer_id = request.args.get('farmer_id')
        warehouse_id = request.args.get('warehouse_id')
        
        query = Order.query
        
        if status:
            query = query.filter_by(status=status)
        if farmer_id:
            query = query.filter_by(farmer_id=farmer_id)
        if warehouse_id:
            query = query.filter_by(warehouse_id=warehouse_id)
        
        orders = query.all()
        
        return jsonify({
            'total': len(orders),
            'orders': [{
                'id': o.id,
                'order_number': o.order_number,
                'farmer_id': o.farmer_id,
                'warehouse_id': o.warehouse_id,
                'status': o.status.value,
                'total_amount': o.total_amount,
                'order_date': o.order_date.isoformat() if o.order_date else None,
                'batch_id': o.batch_id
            } for o in orders]
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing orders: {str(e)}")
        return jsonify({'error': str(e)}), 500

@orders_bp.route('', methods=['POST'])
def create_order():
    """Create a new order"""
    try:
        data = request.get_json()
        
        # Validate farmer and warehouse
        farmer = Farmer.query.get(data['farmer_id'])
        warehouse = Warehouse.query.get(data['warehouse_id'])
        
        if not farmer or not warehouse:
            return jsonify({'error': 'Farmer or warehouse not found'}), 404
        
        # Create order
        order_number = f"ORD-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        
        order = Order(
            order_number=order_number,
            farmer_id=data['farmer_id'],
            warehouse_id=data['warehouse_id'],
            total_amount=0,
            status=OrderStatus.PENDING,
            requested_delivery_date=data.get('requested_delivery_date')
        )
        
        # Add order items
        total_amount = 0
        for item_data in data.get('items', []):
            item_total = item_data['quantity'] * item_data['unit_price']
            total_amount += item_total
            
            order_item = OrderItem(
                sku=item_data['sku'],
                product_name=item_data['product_name'],
                input_type=InputType[item_data['input_type'].upper()],
                quantity=item_data['quantity'],
                unit=item_data.get('unit', 'kg'),
                unit_price=item_data['unit_price'],
                total_price=item_total
            )
            order.order_items.append(order_item)
        
        order.total_amount = total_amount
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status.value,
            'total_amount': order.total_amount,
            'message': 'Order created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@orders_bp.route('/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get order details"""
    try:
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({
            'id': order.id,
            'order_number': order.order_number,
            'farmer_id': order.farmer_id,
            'warehouse_id': order.warehouse_id,
            'status': order.status.value,
            'total_amount': order.total_amount,
            'order_date': order.order_date.isoformat() if order.order_date else None,
            'batch_id': order.batch_id,
            'items': [{
                'id': item.id,
                'sku': item.sku,
                'product_name': item.product_name,
                'input_type': item.input_type.value,
                'quantity': item.quantity,
                'unit': item.unit,
                'unit_price': item.unit_price,
                'total_price': item.total_price
            } for item in order.order_items]
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting order: {str(e)}")
        return jsonify({'error': str(e)}), 500

@orders_bp.route('/<order_id>', methods=['PUT'])
def update_order_status(order_id):
    """Update order status"""
    try:
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status:
            order.status = OrderStatus[new_status.upper()]
        
        db.session.commit()
        
        return jsonify({
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status.value,
            'message': 'Order updated successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================================================
# Farmer Endpoints
# ============================================================================

@orders_bp.route('/farmers', methods=['GET'])
def list_farmers():
    """List all farmers"""
    try:
        farmers = Farmer.query.all()
        
        return jsonify({
            'total': len(farmers),
            'farmers': [{
                'id': f.id,
                'name': f.name,
                'phone_number': f.phone_number,
                'district': f.district,
                'farm_size_acres': f.farm_size_acres
            } for f in farmers]
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing farmers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@orders_bp.route('/farmers', methods=['POST'])
def create_farmer():
    """Create a new farmer"""
    try:
        data = request.get_json()
        
        farmer = Farmer(
            name=data['name'],
            phone_number=data['phone_number'],
            email=data.get('email'),
            location=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            district=data['district'],
            farm_size_acres=data.get('farm_size_acres')
        )
        
        db.session.add(farmer)
        db.session.commit()
        
        return jsonify({
            'id': farmer.id,
            'name': farmer.name,
            'message': 'Farmer created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating farmer: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@orders_bp.route('/farmers/<farmer_id>', methods=['GET'])
def get_farmer(farmer_id):
    """Get farmer details"""
    try:
        farmer = Farmer.query.get(farmer_id)
        if not farmer:
            return jsonify({'error': 'Farmer not found'}), 404
        
        return jsonify({
            'id': farmer.id,
            'name': farmer.name,
            'phone_number': farmer.phone_number,
            'email': farmer.email,
            'location': farmer.location,
            'latitude': farmer.latitude,
            'longitude': farmer.longitude,
            'district': farmer.district,
            'farm_size_acres': farmer.farm_size_acres
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting farmer: {str(e)}")
        return jsonify({'error': str(e)}), 500
