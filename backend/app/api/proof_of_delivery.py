"""
Proof of Delivery API Endpoints
"""

from flask import Blueprint, request, jsonify, current_app
from app.models import db, ProofOfDelivery, Delivery
from app.services.proof_of_delivery import ProofOfDeliveryService
import logging
import os

logger = logging.getLogger(__name__)

pod_bp = Blueprint('proof_of_delivery', __name__, url_prefix='/proof-of-delivery')

# Initialize PoD service
def get_pod_service():
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    return ProofOfDeliveryService(upload_folder=upload_folder)

# ============================================================================
# Proof of Delivery Endpoints
# ============================================================================

@pod_bp.route('/<delivery_id>', methods=['POST'])
def create_pod(delivery_id):
    """Create proof of delivery"""
    try:
        # Get JSON data and files
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Initialize PoD service
        pod_service = get_pod_service()
        
        # Create PoD
        pod_id = pod_service.create_proof_of_delivery(delivery_id, data)
        
        if not pod_id:
            return jsonify({'error': 'Failed to create proof of delivery'}), 400
        
        return jsonify({
            'pod_id': pod_id,
            'delivery_id': delivery_id,
            'message': 'Proof of delivery created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating PoD: {str(e)}")
        return jsonify({'error': str(e)}), 400

@pod_bp.route('/<pod_id>', methods=['GET'])
def get_pod(pod_id):
    """Get proof of delivery details"""
    try:
        pod_service = get_pod_service()
        
        # Get from database
        pod = ProofOfDelivery.query.get(pod_id)
        if not pod:
            return jsonify({'error': 'Proof of delivery not found'}), 404
        
        pod_data = {
            'id': pod.id,
            'delivery_id': pod.delivery_id,
            'farmer_name': pod.farmer_name,
            'farmer_phone': pod.farmer_phone,
            'delivery_condition': pod.delivery_condition,
            'notes': pod.notes,
            'location': {
                'latitude': pod.location_latitude,
                'longitude': pod.location_longitude,
                'accuracy_meters': pod.accuracy_meters
            },
            'signature_path': pod.signature_stored_path,
            'photo_paths': pod.photo_evidence or [],
            'items_verified': pod.items_verified,
            'device_id': pod.device_id,
            'verified': pod.verified,
            'verified_by': pod.verified_by,
            'verified_at': pod.verified_at.isoformat() if pod.verified_at else None,
            'sms_alert_sent': pod.sms_alert_sent,
            'sms_sent_at': pod.sms_sent_at.isoformat() if pod.sms_sent_at else None,
            'captured_at': pod.captured_at.isoformat() if pod.captured_at else None
        }
        
        return jsonify(pod_data), 200
    
    except Exception as e:
        logger.error(f"Error getting PoD: {str(e)}")
        return jsonify({'error': str(e)}), 500

@pod_bp.route('/<pod_id>/verify', methods=['PUT'])
def verify_pod(pod_id):
    """Verify proof of delivery"""
    try:
        data = request.get_json()
        verified_by = data.get('verified_by', 'system')
        
        pod_service = get_pod_service()
        result = pod_service.verify_pod(pod_id, verified_by)
        
        if not result:
            return jsonify({'error': 'Proof of delivery not found'}), 404
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error verifying PoD: {str(e)}")
        return jsonify({'error': str(e)}), 400

@pod_bp.route('/delivery/<delivery_id>', methods=['GET'])
def get_delivery_pod(delivery_id):
    """Get PoD for a delivery"""
    try:
        pod = ProofOfDelivery.query.filter_by(delivery_id=delivery_id).first()
        
        if not pod:
            return jsonify({'error': 'No proof of delivery found for this delivery'}), 404
        
        pod_service = get_pod_service()
        pod_data = pod_service.get_delivery_pod(delivery_id)
        
        return jsonify(pod_data), 200
    
    except Exception as e:
        logger.error(f"Error getting delivery PoD: {str(e)}")
        return jsonify({'error': str(e)}), 500

@pod_bp.route('', methods=['GET'])
def list_pods():
    """List all proofs of delivery"""
    try:
        delivery_id = request.args.get('delivery_id')
        verified = request.args.get('verified')
        
        query = ProofOfDelivery.query
        
        if delivery_id:
            query = query.filter_by(delivery_id=delivery_id)
        if verified is not None:
            verified_bool = verified.lower() == 'true'
            query = query.filter_by(verified=verified_bool)
        
        pods = query.all()
        
        return jsonify({
            'total': len(pods),
            'pods': [{
                'id': p.id,
                'delivery_id': p.delivery_id,
                'farmer_name': p.farmer_name,
                'delivery_condition': p.delivery_condition,
                'verified': p.verified,
                'sms_alert_sent': p.sms_alert_sent,
                'captured_at': p.captured_at.isoformat() if p.captured_at else None
            } for p in pods]
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing PoDs: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# File Upload/Download Endpoints
# ============================================================================

@pod_bp.route('/<pod_id>/signature', methods=['GET'])
def get_signature(pod_id):
    """Get signature image for PoD"""
    try:
        pod = ProofOfDelivery.query.get(pod_id)
        if not pod or not pod.signature_stored_path:
            return jsonify({'error': 'Signature not found'}), 404
        
        signature_path = pod.signature_stored_path
        
        if not os.path.exists(signature_path):
            return jsonify({'error': 'Signature file not found'}), 404
        
        with open(signature_path, 'rb') as f:
            signature_data = f.read()
        
        return {
            'signature': signature_data,
            'content_type': 'image/png'
        }, 200, {'Content-Type': 'image/png'}
    
    except Exception as e:
        logger.error(f"Error getting signature: {str(e)}")
        return jsonify({'error': str(e)}), 500

@pod_bp.route('/<pod_id>/photos', methods=['GET'])
def get_photos(pod_id):
    """Get photos for PoD"""
    try:
        pod = ProofOfDelivery.query.get(pod_id)
        if not pod or not pod.photo_evidence:
            return jsonify({'error': 'Photos not found'}), 404
        
        photos = []
        
        for photo_path in pod.photo_evidence:
            if os.path.exists(photo_path):
                photos.append({
                    'path': photo_path,
                    'filename': os.path.basename(photo_path)
                })
        
        return jsonify({
            'pod_id': pod_id,
            'total_photos': len(photos),
            'photos': photos
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting photos: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Analytics Endpoints
# ============================================================================

@pod_bp.route('/analytics/summary', methods=['GET'])
def pod_analytics_summary():
    """Get PoD analytics summary"""
    try:
        total_pods = ProofOfDelivery.query.count()
        verified_pods = ProofOfDelivery.query.filter_by(verified=True).count()
        sms_sent_pods = ProofOfDelivery.query.filter_by(sms_alert_sent=True).count()
        
        condition_stats = {}
        for pod in ProofOfDelivery.query.all():
            condition = pod.delivery_condition or 'unknown'
            condition_stats[condition] = condition_stats.get(condition, 0) + 1
        
        return jsonify({
            'total_pods': total_pods,
            'verified_pods': verified_pods,
            'sms_sent_pods': sms_sent_pods,
            'verification_rate': (verified_pods / total_pods * 100) if total_pods > 0 else 0,
            'condition_distribution': condition_stats
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting PoD analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500
