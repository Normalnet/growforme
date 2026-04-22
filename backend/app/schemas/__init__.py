from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ============================================================================
# Enum Schemas
# ============================================================================

class InputTypeSchema(str, Enum):
    SEEDS = "seeds"
    FERTILIZER = "fertilizer"
    TOOLS = "tools"
    OTHER = "other"

class OrderStatusSchema(str, Enum):
    PENDING = "pending"
    BATCHED = "batched"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"

# ============================================================================
# Warehouse Schemas
# ============================================================================

class WarehouseBase(BaseModel):
    name: str
    location: str
    latitude: float
    longitude: float
    region: str
    district: str
    capacity: int

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region: Optional[str] = None
    district: Optional[str] = None
    capacity: Optional[int] = None

class WarehouseResponse(WarehouseBase):
    id: str
    current_stock: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# Farmer Schemas
# ============================================================================

class FarmerBase(BaseModel):
    name: str
    phone_number: str
    email: Optional[str] = None
    location: str
    latitude: float
    longitude: float
    district: str
    farm_size_acres: Optional[float] = None

class FarmerCreate(FarmerBase):
    pass

class FarmerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    farm_size_acres: Optional[float] = None

class FarmerResponse(FarmerBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# Order Schemas
# ============================================================================

class OrderItemBase(BaseModel):
    sku: str
    product_name: str
    input_type: InputTypeSchema
    quantity: int
    unit: str = "kg"
    unit_price: float

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemResponse(OrderItemBase):
    id: str
    total_price: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    farmer_id: str
    warehouse_id: str
    total_amount: float
    requested_delivery_date: Optional[datetime] = None

class OrderCreate(OrderBase):
    order_items: List[OrderItemCreate]

class OrderResponse(OrderBase):
    id: str
    order_number: str
    status: OrderStatusSchema
    batch_id: Optional[str] = None
    order_date: datetime
    requested_delivery_date: Optional[datetime] = None
    order_items: List[OrderItemResponse]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# Batch & Routing Schemas
# ============================================================================

class BatchRequest(BaseModel):
    warehouse_id: str
    orders: List[str]  # List of order IDs to batch

class BatchResponse(BaseModel):
    id: str
    batch_number: str
    warehouse_id: str
    district: str
    region: str
    total_orders: int
    total_weight_kg: float
    total_value: float
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class RouteResponse(BaseModel):
    id: str
    route_number: str
    batch_id: str
    district: str
    total_stops: int
    total_distance_km: float
    estimated_delivery_time_hours: Optional[float]
    total_orders: int
    total_weight_kg: float
    status: str
    optimized_sequence: Optional[List[str]]
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# Delivery & PoD Schemas
# ============================================================================

class DeliveryResponse(BaseModel):
    id: str
    delivery_number: str
    order_id: str
    route_id: Optional[str]
    field_agent_id: Optional[str]
    status: str
    scheduled_date: Optional[datetime]
    delivery_date: Optional[datetime]
    actual_arrival_time: Optional[datetime]
    actual_departure_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProofOfDeliveryCreate(BaseModel):
    farmer_name: str
    farmer_phone: str
    delivery_condition: str
    notes: Optional[str] = None
    location_latitude: float
    location_longitude: float
    accuracy_meters: Optional[float] = None
    device_id: Optional[str] = None
    items_verified: Optional[dict] = None

class ProofOfDeliveryResponse(BaseModel):
    id: str
    delivery_id: str
    farmer_name: str
    farmer_phone: str
    delivery_condition: str
    verified: bool
    sms_alert_sent: bool
    captured_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# Inventory Sync Schemas
# ============================================================================

class InventorySyncRequest(BaseModel):
    warehouse_id: str
    sync_source: str = "input_acquisition_api"

class InventorySyncResponse(BaseModel):
    id: str
    warehouse_id: str
    sync_source: str
    status: str
    items_synced: int
    synced_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# Analytics & Reporting Schemas
# ============================================================================

class DeliveryMetrics(BaseModel):
    total_deliveries: int
    completed_deliveries: int
    failed_deliveries: int
    delivery_success_rate: float
    average_delivery_time_hours: float
    total_distance_covered_km: float

class RoutingMetrics(BaseModel):
    total_orders: int
    total_batches: int
    pending_orders: int
    average_orders_per_batch: float
    average_orders_per_route: float
    total_distance_optimized_km: float
