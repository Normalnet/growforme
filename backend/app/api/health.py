"""
Health Check API Endpoints
"""

from flask import Blueprint, jsonify
from app.models import db, Warehouse, Farmer, Order, Batch, Route, Delivery, ProofOfDelivery
import logging

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

# ============================================================================
# System Health Checks
# ============================================================================

@health_bp.route('/health', methods=['GET'])
def health_check():
    """System health check"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        db_status = 'healthy'
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = 'unhealthy'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat()
    }), 200

@health_bp.route('/status', methods=['GET'])
def system_status():
    """Get system status with metrics"""
    try:
        metrics = {
            'warehouses': Warehouse.query.count(),
            'farmers': Farmer.query.count(),
            'orders': Order.query.count(),
            'batches': Batch.query.count(),
            'routes': Route.query.count(),
            'deliveries': Delivery.query.count(),
            'proofs_of_delivery': ProofOfDelivery.query.count()
        }
        
        # Get order status breakdown
        from app.models import OrderStatus
        order_breakdown = {}
        for status in OrderStatus:
            order_breakdown[status.value] = Order.query.filter_by(status=status).count()
        
        return jsonify({
            'status': 'operational',
            'metrics': metrics,
            'orders_by_status': order_breakdown,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@health_bp.route('/version', methods=['GET'])
def get_version():
    """Get API version"""
    return jsonify({
        'service': 'SmartTechBuddy Input Distribution',
        'version': '1.0.0',
        'status': 'operational'
    }), 200
