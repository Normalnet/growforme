"""
Inventory API Endpoints
"""

import os
from flask import Blueprint, request, jsonify
from app.models import db, Warehouse, InventoryItem
from app.schemas import WarehouseResponse, InventorySyncRequest, InventorySyncResponse
from app.services.inventory import InventorySyncService
from config import Config
import logging

logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

# Initialize inventory sync service
_sync_service = None

def get_sync_service():
    global _sync_service
    if _sync_service is None:
        api_url = os.getenv('INPUT_ACQUISITION_API_URL', 'https://api.input-acquisition.com')
        api_key = os.getenv('INPUT_ACQUISITION_API_KEY', 'dev-key')
        _sync_service = InventorySyncService(api_url, api_key)
    return _sync_service

# ============================================================================
# Warehouse Endpoints
# ============================================================================

@inventory_bp.route('/warehouses', methods=['GET'])
def list_warehouses():
    """List all warehouses"""
    try:
        warehouses = Warehouse.query.all()
        return jsonify([{
            'id': w.id,
            'name': w.name,
            'region': w.region,
            'district': w.district,
            'latitude': w.latitude,
            'longitude': w.longitude,
            'current_stock': w.current_stock,
            'capacity': w.capacity
        } for w in warehouses]), 200
    except Exception as e:
        logger.error(f"Error listing warehouses: {str(e)}")
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/warehouses', methods=['POST'])
def create_warehouse():
    """Create a new warehouse"""
    try:
        data = request.get_json()
        
        warehouse = Warehouse(
            name=data['name'],
            location=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            region=data['region'],
            district=data['district'],
            capacity=data['capacity']
        )
        
        db.session.add(warehouse)
        db.session.commit()
        
        return jsonify({
            'id': warehouse.id,
            'name': warehouse.name,
            'message': 'Warehouse created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating warehouse: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/warehouses/<warehouse_id>', methods=['GET'])
def get_warehouse(warehouse_id):
    """Get warehouse details"""
    try:
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'error': 'Warehouse not found'}), 404
        
        return jsonify({
            'id': warehouse.id,
            'name': warehouse.name,
            'location': warehouse.location,
            'region': warehouse.region,
            'district': warehouse.district,
            'latitude': warehouse.latitude,
            'longitude': warehouse.longitude,
            'current_stock': warehouse.current_stock,
            'capacity': warehouse.capacity
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting warehouse: {str(e)}")
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/warehouses/<warehouse_id>/inventory', methods=['GET'])
def get_warehouse_inventory(warehouse_id):
    """Get inventory items for a warehouse"""
    try:
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'error': 'Warehouse not found'}), 404
        
        items = InventoryItem.query.filter_by(warehouse_id=warehouse_id).all()
        
        return jsonify({
            'warehouse_id': warehouse_id,
            'total_items': len(items),
            'items': [{
                'id': item.id,
                'sku': item.sku,
                'product_name': item.product_name,
                'input_type': item.input_type.value,
                'quantity': item.quantity,
                'unit': item.unit,
                'batch_number': item.batch_number
            } for item in items]
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting warehouse inventory: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Inventory Sync Endpoints
# ============================================================================

@inventory_bp.route('/sync/<warehouse_id>', methods=['POST'])
def sync_inventory(warehouse_id):
    """Sync inventory with Input Acquisition API"""
    try:
        sync_service = get_sync_service()
        result = sync_service.sync_warehouse_inventory(warehouse_id)
        
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error syncing inventory: {str(e)}")
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/warehouses/<warehouse_id>/reorder-levels', methods=['GET'])
def check_reorder_levels(warehouse_id):
    """Check items below reorder levels"""
    try:
        sync_service = get_sync_service()
        items = sync_service.check_reorder_levels(warehouse_id)
        
        return jsonify({
            'warehouse_id': warehouse_id,
            'items_below_reorder': len(items),
            'items': items
        }), 200
    
    except Exception as e:
        logger.error(f"Error checking reorder levels: {str(e)}")
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/warehouses/<warehouse_id>/check-availability', methods=['POST'])
def check_stock_availability(warehouse_id):
    """Check if stock is available"""
    try:
        data = request.get_json()
        sku = data.get('sku')
        quantity = data.get('quantity')
        
        sync_service = get_sync_service()
        result = sync_service.estimate_stock_availability(warehouse_id, sku, quantity)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# Health Check
# ============================================================================

@inventory_bp.route('/health', methods=['GET'])
def inventory_health():
    """Health check for inventory service"""
    try:
        warehouse_count = Warehouse.query.count()
        return jsonify({
            'service': 'inventory',
            'status': 'healthy',
            'warehouses': warehouse_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
