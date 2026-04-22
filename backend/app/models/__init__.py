from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import uuid

db = SQLAlchemy()

class OrderStatus(Enum):
    PENDING = "pending"
    BATCHED = "batched"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"

class DeliveryStatus(Enum):
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    FAILED = "failed"

class InputType(Enum):
    SEEDS = "seeds"  # Certified varieties
    FERTILIZER_BASAL = "fertilizer_basal"
    FERTILIZER_TOP_DRESSING = "fertilizer_top_dressing"
    MECHANIZATION = "mechanization"
    CHEMICAL = "chemical"
    OTHER = "other"

# ============================================================================
# Inventory Models
# ============================================================================

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(500), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    region = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)  # in units
    current_stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    inventory_items = db.relationship('InventoryItem', backref='warehouse', lazy=True, cascade='all, delete-orphan')
    outbound_orders = db.relationship('Order', backref='source_warehouse', lazy=True)
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_id = db.Column(db.String(36), db.ForeignKey('warehouses.id'), nullable=False)
    input_type = db.Column(db.Enum(InputType), nullable=False)
    sku = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50), default='kg')  # kg, packets, units
    reorder_level = db.Column(db.Integer, default=100)
    batch_number = db.Column(db.String(100))
    expiry_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventoryItem {self.product_name}>'

class InventorySyncLog(db.Model):
    __tablename__ = 'inventory_sync_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_id = db.Column(db.String(36), db.ForeignKey('warehouses.id'), nullable=False)
    sync_source = db.Column(db.String(100), default='input_acquisition_api')
    status = db.Column(db.String(50), default='success')  # success, failed, partial
    items_synced = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventorySyncLog {self.warehouse_id} - {self.synced_at}>'

# ============================================================================
# Order & Delivery Models
# ============================================================================

class Farmer(db.Model):
    __tablename__ = 'farmers'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(255))
    location = db.Column(db.String(500), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    district = db.Column(db.String(100), nullable=False)
    farm_size_acres = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    orders = db.relationship('Order', backref='farmer', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Farmer {self.name}>'

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    farmer_id = db.Column(db.String(36), db.ForeignKey('farmers.id'), nullable=False)
    warehouse_id = db.Column(db.String(36), db.ForeignKey('warehouses.id'), nullable=False)
    
    # Order Details
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING)
    
    # Batch Info
    batch_id = db.Column(db.String(36), db.ForeignKey('batches.id'))
    
    # Dates
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    requested_delivery_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    delivery = db.relationship('Delivery', backref='order', uselist=False, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    sku = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    input_type = db.Column(db.Enum(InputType), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit = db.Column(db.String(50), default='kg')
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<OrderItem {self.product_name}>'

# ============================================================================
# Batching & Routing Models
# ============================================================================

class Batch(db.Model):
    __tablename__ = 'batches'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_number = db.Column(db.String(50), unique=True, nullable=False)
    warehouse_id = db.Column(db.String(36), db.ForeignKey('warehouses.id'), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    
    # Batch Metrics
    total_orders = db.Column(db.Integer, default=0)
    total_weight_kg = db.Column(db.Float, default=0)
    total_value = db.Column(db.Float, default=0)
    
    # Batch Status
    status = db.Column(db.String(50), default='pending')  # pending, ready, in_transit, completed
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dispatched_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    orders = db.relationship('Order', backref='batch', lazy=True)
    routes = db.relationship('Route', backref='batch', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Batch {self.batch_number}>'

class Route(db.Model):
    __tablename__ = 'routes'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_number = db.Column(db.String(50), unique=True, nullable=False)
    batch_id = db.Column(db.String(36), db.ForeignKey('batches.id'), nullable=False)
    
    # Route Details
    warehouse_id = db.Column(db.String(36), db.ForeignKey('warehouses.id'))
    district = db.Column(db.String(100), nullable=False)
    
    # Route Metrics
    total_stops = db.Column(db.Integer, default=0)
    total_distance_km = db.Column(db.Float, default=0)
    estimated_delivery_time_hours = db.Column(db.Float)
    total_orders = db.Column(db.Integer, default=0)
    total_weight_kg = db.Column(db.Float, default=0)
    
    # Route Status
    status = db.Column(db.String(50), default='pending')  # pending, active, completed
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Stored optimized route sequence (JSON)
    optimized_sequence = db.Column(db.JSON)  # List of farmer IDs in optimized order
    
    deliveries = db.relationship('Delivery', backref='route', lazy=True)
    
    def __repr__(self):
        return f'<Route {self.route_number}>'

# ============================================================================
# Delivery & PoD Models
# ============================================================================

class Delivery(db.Model):
    __tablename__ = 'deliveries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_number = db.Column(db.String(50), unique=True, nullable=False)
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    route_id = db.Column(db.String(36), db.ForeignKey('routes.id'))
    field_agent_id = db.Column(db.String(36), db.ForeignKey('field_agents.id'))
    
    # Delivery Status
    status = db.Column(db.Enum(DeliveryStatus), default=DeliveryStatus.ASSIGNED)
    
    # Delivery Details
    scheduled_date = db.Column(db.DateTime)
    delivery_date = db.Column(db.DateTime)
    actual_arrival_time = db.Column(db.DateTime)
    actual_departure_time = db.Column(db.DateTime)
    
    # Location tracking
    delivery_latitude = db.Column(db.Float)
    delivery_longitude = db.Column(db.Float)
    delivery_address = db.Column(db.String(500))
    
    # Notes
    delivery_notes = db.Column(db.Text)
    failure_reason = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    proof_of_deliveries = db.relationship('ProofOfDelivery', backref='delivery', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Delivery {self.delivery_number}>'

class ProofOfDelivery(db.Model):
    __tablename__ = 'proof_of_deliveries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id = db.Column(db.String(36), db.ForeignKey('deliveries.id'), nullable=False)
    
    # PoD Details
    farmer_name = db.Column(db.String(255), nullable=False)
    farmer_phone = db.Column(db.String(20), nullable=False)
    signature_data = db.Column(db.LargeBinary)  # Signature image
    signature_stored_path = db.Column(db.String(500))  # Path to stored signature file
    photo_evidence = db.Column(db.JSON)  # List of photo paths
    
    # System Details
    device_id = db.Column(db.String(100))  # Mobile device identifier
    location_latitude = db.Column(db.Float, nullable=False)
    location_longitude = db.Column(db.Float, nullable=False)
    accuracy_meters = db.Column(db.Float)
    
    # Conditions
    delivery_condition = db.Column(db.String(50))  # perfect, minor_damage, major_damage
    items_verified = db.Column(db.JSON)  # JSON list of verified items
    
    # Notes
    notes = db.Column(db.Text)
    
    # Verification
    verified = db.Column(db.Boolean, default=False)
    verified_by = db.Column(db.String(100))
    verified_at = db.Column(db.DateTime)
    
    # Timestamps
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # SMS Alert Sent
    sms_alert_sent = db.Column(db.Boolean, default=False)
    sms_sent_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<ProofOfDelivery {self.delivery_id}>'

class FieldAgent(db.Model):
    __tablename__ = 'field_agents'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(255))
    employee_id = db.Column(db.String(50), unique=True)
    assigned_district = db.Column(db.String(100), nullable=False)
    assigned_region = db.Column(db.String(100), nullable=False)
    vehicle_number = db.Column(db.String(50))
    vehicle_capacity_kg = db.Column(db.Float)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    deliveries = db.relationship('Delivery', backref='field_agent', lazy=True)
    
    def __repr__(self):
        return f'<FieldAgent {self.name}>'


# ============================================================================
# Ecosystem Integration Models
# ============================================================================

class EligibilityCheck(db.Model):
    """
    Cached result from Credit Scoring API.
    Inputs are only released to eligible farmers.
    """
    __tablename__ = 'eligibility_checks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = db.Column(db.String(36), db.ForeignKey('farmers.id'), nullable=False)
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'))

    # Credit Scoring API result
    is_eligible = db.Column(db.Boolean, nullable=False)
    credit_score = db.Column(db.Float)
    risk_level = db.Column(db.String(20))          # LOW / MEDIUM / HIGH
    max_credit_limit = db.Column(db.Float)
    order_amount = db.Column(db.Float)
    within_limit = db.Column(db.Boolean)
    reason = db.Column(db.Text)
    source_api = db.Column(db.String(100), default='credit_scoring_api')

    # Validity window
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    farmer = db.relationship('Farmer', backref='eligibility_checks')

    def __repr__(self):
        return f'<EligibilityCheck farmer={self.farmer_id} eligible={self.is_eligible}>'


class DeliveryRiskAssessment(db.Model):
    """
    Anomaly detection result per delivery.
    Flags GPS deviation, missing PoD evidence, or potential diversion.
    """
    __tablename__ = 'delivery_risk_assessments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id = db.Column(db.String(36), db.ForeignKey('deliveries.id'), nullable=False, unique=True)

    # Geofencing
    expected_latitude = db.Column(db.Float)        # Farmer's registered location
    expected_longitude = db.Column(db.Float)
    actual_latitude = db.Column(db.Float)           # GPS at PoD submission
    actual_longitude = db.Column(db.Float)
    gps_deviation_meters = db.Column(db.Float)
    geofence_radius_meters = db.Column(db.Float, default=50.0)
    is_within_geofence = db.Column(db.Boolean)

    # Risk classification
    risk_level = db.Column(db.String(20))           # LOW / MEDIUM / HIGH
    risk_score = db.Column(db.Integer, default=0)   # 0-100
    anomaly_flags = db.Column(db.JSON)              # List of flag dicts
    requires_review = db.Column(db.Boolean, default=False)
    auto_approved = db.Column(db.Boolean, default=False)

    # Predicted delivery window
    predicted_window_start = db.Column(db.DateTime)
    predicted_window_end = db.Column(db.DateTime)
    prediction_confidence = db.Column(db.String(20))

    assessed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<DeliveryRiskAssessment delivery={self.delivery_id} risk={self.risk_level}>'


class DispatchRecord(db.Model):
    """
    Audit trail for the full dispatch pipeline:
    eligibility → inventory → route optimisation → dispatch → monitoring push.
    """
    __tablename__ = 'dispatch_records'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = db.Column(db.String(36), db.ForeignKey('batches.id'))
    warehouse_id = db.Column(db.String(36), db.ForeignKey('warehouses.id'))

    # Pipeline stages
    dispatch_status = db.Column(db.String(50), default='PENDING')
    # PENDING → ELIGIBILITY_CHECKED → INVENTORY_VERIFIED → ROUTED → DISPATCHED → COMPLETED

    eligibility_check_passed = db.Column(db.Boolean)
    inventory_check_passed = db.Column(db.Boolean)
    route_optimised = db.Column(db.Boolean, default=False)
    monitoring_push_sent = db.Column(db.Boolean, default=False)

    total_orders = db.Column(db.Integer, default=0)
    total_routes = db.Column(db.Integer, default=0)
    ineligible_farmers = db.Column(db.JSON)     # List of farmer IDs blocked
    unavailable_items = db.Column(db.JSON)      # List of SKUs out of stock

    notes = db.Column(db.Text)
    dispatched_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<DispatchRecord batch={self.batch_id} status={self.dispatch_status}>'
