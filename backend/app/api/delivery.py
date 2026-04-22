"""
Delivery API Endpoints
"""

from flask import Blueprint, request, jsonify
from app.models import db, Delivery, Order, DeliveryStatus, FieldAgent, Route
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

delivery_bp = Blueprint('delivery', __name__, url_prefix='/deliveries')

# ============================================================================
# Delivery Management Endpoints
# ============================================================================

@delivery_bp.route('', methods=['GET'])
def list_deliveries():
    """List deployments"""
    try:
        status = request.args.get('status')
        route_id = request.args.get('route_id')
        agent_id = request.args.get('agent_id')
        
        query = Delivery.query
        
        if status:
            query = query.filter_by(status=status)
        if route_id:
            query = query.filter_by(route_id=route_id)
        if agent_id:
            query = query.filter_by(field_agent_id=agent_id)
        
        deliveries = query.all()
        
        return jsonify({
            'total': len(deliveries),
            'deliveries': [{
                'id': d.id,
                'delivery_number': d.delivery_number,
                'order_id': d.order_id,
                'route_id': d.route_id,
                'field_agent_id': d.field_agent_id,
                'status': d.status.value,
                'scheduled_date': d.scheduled_date.isoformat() if d.scheduled_date else None,
                'delivery_date': d.delivery_date.isoformat() if d.delivery_date else None
            } for d in deliveries]
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing deliveries: {str(e)}")
        return jsonify({'error': str(e)}), 500

@delivery_bp.route('', methods=['POST'])
def create_delivery():
    """Create a new delivery"""
    try:
        data = request.get_json()
        
        # Validate order
        order = Order.query.get(data['order_id'])
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Create delivery
        delivery_number = f"DEL-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        
        delivery = Delivery(
            delivery_number=delivery_number,
            order_id=data['order_id'],
            route_id=data.get('route_id'),
            field_agent_id=data.get('field_agent_id'),
            status=DeliveryStatus.ASSIGNED,
            scheduled_date=data.get('scheduled_date'),
            delivery_notes=data.get('delivery_notes')
        )
        
        db.session.add(delivery)
        db.session.commit()
        
        return jsonify({
            'id': delivery.id,
            'delivery_number': delivery.delivery_number,
            'status': delivery.status.value,
            'message': 'Delivery created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating delivery: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    """Get delivery details"""
    try:
        delivery = Delivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'error': 'Delivery not found'}), 404
        
        return jsonify({
            'id': delivery.id,
            'delivery_number': delivery.delivery_number,
            'order_id': delivery.order_id,
            'route_id': delivery.route_id,
            'field_agent_id': delivery.field_agent_id,
            'status': delivery.status.value,
            'scheduled_date': delivery.scheduled_date.isoformat() if delivery.scheduled_date else None,
            'delivery_date': delivery.delivery_date.isoformat() if delivery.delivery_date else None,
            'actual_arrival_time': delivery.actual_arrival_time.isoformat() if delivery.actual_arrival_time else None,
            'actual_departure_time': delivery.actual_departure_time.isoformat() if delivery.actual_departure_time else None,
            'delivery_notes': delivery.delivery_notes
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting delivery: {str(e)}")
        return jsonify({'error': str(e)}), 500

@delivery_bp.route('/<delivery_id>/assign-agent', methods=['PUT'])
def assign_delivery_agent(delivery_id):
    """Assign field agent to delivery"""
    try:
        delivery = Delivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'error': 'Delivery not found'}), 404
        
        data = request.get_json()
        agent_id = data.get('field_agent_id')
        
        # Validate agent
        agent = FieldAgent.query.get(agent_id)
        if not agent:
            return jsonify({'error': 'Field agent not found'}), 404
        
        delivery.field_agent_id = agent_id
        delivery.status = DeliveryStatus.ASSIGNED
        db.session.commit()
        
        return jsonify({
            'delivery_id': delivery.id,
            'field_agent_id': agent_id,
            'message': 'Agent assigned successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error assigning agent: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/<delivery_id>/start', methods=['PUT'])
def start_delivery(delivery_id):
    """Mark delivery as started"""
    try:
        delivery = Delivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'error': 'Delivery not found'}), 404
        
        delivery.status = DeliveryStatus.IN_TRANSIT
        delivery.actual_arrival_time = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'delivery_id': delivery.id,
            'status': delivery.status.value,
            'message': 'Delivery started'
        }), 200
    
    except Exception as e:
        logger.error(f"Error starting delivery: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/<delivery_id>/complete', methods=['PUT'])
def complete_delivery(delivery_id):
    """Mark delivery as completed"""
    try:
        delivery = Delivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'error': 'Delivery not found'}), 404
        
        data = request.get_json()
        
        delivery.status = DeliveryStatus.COMPLETED
        delivery.delivery_date = datetime.utcnow()
        delivery.actual_departure_time = datetime.utcnow()
        delivery.delivery_notes = data.get('notes')
        
        db.session.commit()
        
        return jsonify({
            'delivery_id': delivery.id,
            'status': delivery.status.value,
            'message': 'Delivery completed'
        }), 200
    
    except Exception as e:
        logger.error(f"Error completing delivery: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/<delivery_id>/fail', methods=['PUT'])
def fail_delivery(delivery_id):
    """Mark delivery as failed"""
    try:
        delivery = Delivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'error': 'Delivery not found'}), 404
        
        data = request.get_json()
        
        delivery.status = DeliveryStatus.FAILED
        delivery.failure_reason = data.get('failure_reason')
        
        db.session.commit()
        
        return jsonify({
            'delivery_id': delivery.id,
            'status': delivery.status.value,
            'failure_reason': delivery.failure_reason,
            'message': 'Delivery marked as failed'
        }), 200
    
    except Exception as e:
        logger.error(f"Error failing delivery: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================================================
# Field Agent Endpoints
# ============================================================================

@delivery_bp.route('/agents', methods=['GET'])
def list_field_agents():
    """List field agents"""
    try:
        district = request.args.get('district')
        
        query = FieldAgent.query.filter_by(is_active=True)
        
        if district:
            query = query.filter_by(assigned_district=district)
        
        agents = query.all()
        
        return jsonify({
            'total': len(agents),
            'agents': [{
                'id': a.id,
                'name': a.name,
                'phone_number': a.phone_number,
                'employee_id': a.employee_id,
                'assigned_district': a.assigned_district,
                'assigned_region': a.assigned_region,
                'vehicle_number': a.vehicle_number,
                'vehicle_capacity_kg': a.vehicle_capacity_kg
            } for a in agents]
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        return jsonify({'error': str(e)}), 500

@delivery_bp.route('/agents', methods=['POST'])
def create_field_agent():
    """Create a new field agent"""
    try:
        data = request.get_json()
        
        agent = FieldAgent(
            name=data['name'],
            phone_number=data['phone_number'],
            email=data.get('email'),
            employee_id=data.get('employee_id'),
            assigned_district=data['assigned_district'],
            assigned_region=data['assigned_region'],
            vehicle_number=data.get('vehicle_number'),
            vehicle_capacity_kg=data.get('vehicle_capacity_kg'),
            is_active=True
        )
        
        db.session.add(agent)
        db.session.commit()
        
        return jsonify({
            'id': agent.id,
            'name': agent.name,
            'message': 'Field agent created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/agents/<agent_id>', methods=['GET'])
def get_field_agent(agent_id):
    """Get field agent details"""
    try:
        agent = FieldAgent.query.get(agent_id)
        if not agent:
            return jsonify({'error': 'Field agent not found'}), 404
        
        return jsonify({
            'id': agent.id,
            'name': agent.name,
            'phone_number': agent.phone_number,
            'email': agent.email,
            'employee_id': agent.employee_id,
            'assigned_district': agent.assigned_district,
            'assigned_region': agent.assigned_region,
            'vehicle_number': agent.vehicle_number,
            'vehicle_capacity_kg': agent.vehicle_capacity_kg,
            'is_active': agent.is_active
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting agent: {str(e)}")
        return jsonify({'error': str(e)}), 500
