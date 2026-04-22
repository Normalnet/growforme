"""
Inventory Handshake Service
Manages real-time stock level synchronization with Input Acquisition API.
"""

import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
from app.models import (
    db, Warehouse, InventoryItem, InventorySyncLog, InputType
)

logger = logging.getLogger(__name__)

class InventorySyncService:
    """
    Service for synchronizing inventory levels with external systems.
    """
    
    def __init__(self, api_url: str, api_key: str):
        """
        Initialize inventory sync service.
        
        Args:
            api_url: Base URL of Input Acquisition API
            api_key: API key for authentication
        """
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def sync_warehouse_inventory(self, warehouse_id: str) -> Dict:
        """
        Sync inventory levels for a specific warehouse from Input Acquisition API.
        
        Args:
            warehouse_id: ID of warehouse to sync
        
        Returns:
            Dictionary with sync status and results
        """
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return {'success': False, 'error': f'Warehouse {warehouse_id} not found'}
        
        try:
            # Fetch warehouse inventory from Input Acquisition API
            external_inventory = self._fetch_external_inventory(warehouse)
            
            if not external_inventory:
                return {'success': False, 'error': 'Failed to fetch external inventory'}
            
            # Sync items
            sync_result = self._sync_inventory_items(warehouse, external_inventory)
            
            # Log sync
            sync_log = InventorySyncLog(
                warehouse_id=warehouse_id,
                sync_source='input_acquisition_api',
                status='success',
                items_synced=sync_result['items_synced']
            )
            db.session.add(sync_log)
            db.session.commit()
            
            logger.info(f"Synced {sync_result['items_synced']} items for warehouse {warehouse_id}")
            
            return {
                'success': True,
                'warehouse_id': warehouse_id,
                'items_synced': sync_result['items_synced'],
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error syncing inventory for warehouse {warehouse_id}: {str(e)}")
            
            # Log failed sync
            sync_log = InventorySyncLog(
                warehouse_id=warehouse_id,
                sync_source='input_acquisition_api',
                status='failed',
                error_message=str(e)
            )
            db.session.add(sync_log)
            db.session.commit()
            
            return {
                'success': False,
                'warehouse_id': warehouse_id,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _fetch_external_inventory(self, warehouse: Warehouse) -> Optional[List[Dict]]:
        """
        Fetch inventory from Input Acquisition API.
        
        Args:
            warehouse: Warehouse object
        
        Returns:
            List of inventory items from external API
        """
        try:
            endpoint = f"{self.api_url}/warehouses/{warehouse.id}/inventory"
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return None
    
    def _sync_inventory_items(self, warehouse: Warehouse, external_items: List[Dict]) -> Dict:
        """
        Sync external inventory items to local database.
        
        Args:
            warehouse: Warehouse object
            external_items: List of items from external API
        
        Returns:
            Dictionary with sync statistics
        """
        items_synced = 0
        items_updated = 0
        items_created = 0
        
        for item_data in external_items:
            try:
                # Map external item to our InputType
                input_type = self._map_input_type(item_data.get('input_type'))
                
                # Check if item already exists
                existing_item = InventoryItem.query.filter_by(
                    warehouse_id=warehouse.id,
                    sku=item_data['sku']
                ).first()
                
                if existing_item:
                    # Update existing item
                    existing_item.quantity = item_data.get('quantity', 0)
                    existing_item.product_name = item_data.get('product_name')
                    existing_item.input_type = input_type
                    existing_item.batch_number = item_data.get('batch_number')
                    existing_item.expiry_date = item_data.get('expiry_date')
                    items_updated += 1
                else:
                    # Create new item
                    new_item = InventoryItem(
                        warehouse_id=warehouse.id,
                        sku=item_data['sku'],
                        product_name=item_data.get('product_name'),
                        input_type=input_type,
                        quantity=item_data.get('quantity', 0),
                        unit=item_data.get('unit', 'kg'),
                        batch_number=item_data.get('batch_number'),
                        expiry_date=item_data.get('expiry_date')
                    )
                    db.session.add(new_item)
                    items_created += 1
                
                items_synced += 1
            
            except Exception as e:
                logger.warning(f"Failed to sync item {item_data.get('sku')}: {str(e)}")
                continue
        
        # Update warehouse stock
        warehouse.current_stock = sum(
            item.quantity for item in InventoryItem.query.filter_by(
                warehouse_id=warehouse.id
            ).all()
        )
        
        db.session.commit()
        
        return {
            'items_synced': items_synced,
            'items_created': items_created,
            'items_updated': items_updated
        }
    
    @staticmethod
    def _map_input_type(external_type: str) -> InputType:
        """Map external input type to our InputType enum."""
        type_mapping = {
            'seed': InputType.SEEDS,
            'seeds': InputType.SEEDS,
            'fertilizer_basal': InputType.FERTILIZER_BASAL,
            'fertilizer_top_dressing': InputType.FERTILIZER_TOP_DRESSING,
            'fertilizer': InputType.FERTILIZER_BASAL,   # legacy alias
            'mechanization': InputType.MECHANIZATION,
            'chemical': InputType.CHEMICAL,
        }
        return type_mapping.get(str(external_type).lower(), InputType.OTHER)
    
    def check_reorder_levels(self, warehouse_id: str) -> List[Dict]:
        """
        Check inventory items below reorder levels.
        
        Args:
            warehouse_id: Warehouse ID
        
        Returns:
            List of items needing reorder
        """
        items_below_reorder = InventoryItem.query.filter(
            (InventoryItem.warehouse_id == warehouse_id) &
            (InventoryItem.quantity <= InventoryItem.reorder_level)
        ).all()
        
        reorder_items = []
        for item in items_below_reorder:
            reorder_items.append({
                'sku': item.sku,
                'product_name': item.product_name,
                'current_quantity': item.quantity,
                'reorder_level': item.reorder_level,
                'shortfall': item.reorder_level - item.quantity
            })
        
        logger.info(f"Found {len(reorder_items)} items below reorder level in warehouse {warehouse_id}")
        return reorder_items
    
    def estimate_stock_availability(self, warehouse_id: str, sku: str, 
                                   quantity_required: int) -> Dict:
        """
        Check if required quantity is available in warehouse.
        
        Args:
            warehouse_id: Warehouse ID
            sku: Product SKU
            quantity_required: Quantity needed
        
        Returns:
            Dictionary with availability status
        """
        item = InventoryItem.query.filter_by(
            warehouse_id=warehouse_id,
            sku=sku
        ).first()
        
        if not item:
            return {
                'available': False,
                'quantity_available': 0,
                'quantity_required': quantity_required,
                'message': f'SKU {sku} not found in warehouse'
            }
        
        is_available = item.quantity >= quantity_required
        
        return {
            'available': is_available,
            'quantity_available': item.quantity,
            'quantity_required': quantity_required,
            'product_name': item.product_name,
            'message': 'Available' if is_available else f'Only {item.quantity} units available'
        }
