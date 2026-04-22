# System Architecture - SmartTechBuddy Input Distribution

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Mobile/Web Clients                      │
│                    (PoD Interface / Admin)                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   Nginx/LB       │
                    │   (Reverse Proxy)│
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼─────────┐  ┌──────▼──────┐  ┌─────────▼────────┐
│   Flask API     │  │   Flask API  │  │  Flask API       │
│   (Instance 1)  │  │  (Instance 2)│  │  (Instance 3)    │
└───────┬─────────┘  └──────┬──────┘  └─────────┬────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼──────────┐ ┌──────▼──────┐ ┌──────────▼─────┐
│  PostgreSQL DB   │ │  Redis      │ │  Celery Worker │
│  (Primary)       │ │  (Cache)    │ │  (Async Tasks) │
└──────────────────┘ └─────────────┘ └────────────────┘
```

---

## Core Components

### 1. Flask Application Layer

**Location**: `backend/app/__init__.py`

```python
app = create_app()
```

**Features**:
- Application factory pattern
- Blueprint registration
- Database initialization
- CORS enablement

**Key Blueprints**:
- `inventory_bp` - Warehouse & stock management
- `orders_bp` - Order & farmer management
- `batching_bp` - Batch creation & route optimization
- `delivery_bp` - Delivery & field agent management
- `pod_bp` - Proof of delivery
- `health_bp` - System monitoring

---

### 2. Database Layer

**ORM**: SQLAlchemy 2.0  
**Database**: PostgreSQL 12+

#### Entity Relationship Diagram

```
┌─────────────┐
│  Warehouse  │◄─────┐
└─────────────┘      │
                     │
                ┌────┴──────────┐
                │               │
          ┌─────▼─────┐  ┌─────▼──────┐
          │InventoryItem│  │  Order   │──┐
          └───────────┘  └──────────┘  │
                             │         │
                        ┌────▼─────────┤
                        │              │
                   ┌────▼────┐  ┌─────▼──────┐
                   │OrderItem│  │   Batch    │
                   └─────────┘  └─────┬──────┘
                                      │
                                 ┌────▼─────┐
                                 │  Route    │
                                 └────┬─────┘
                                      │
                                 ┌────▼──────────┐
                                 │ Delivery       │───┐
                                 └────┬──────────┘   │
                                      │              │
                              ┌───────▼──────┐      │
                              │FieldAgent    │      │
                              └───────────────┘  ┌──▼─────────────┐
                                                 │ProofOfDelivery │
                                                 └────────────────┘
```

#### Key Models

**Warehouse**
```python
{
  id: UUID,
  name: String,
  location: String,
  latitude/longitude: GeoPoint,
  region/district: String,
  capacity: Integer,
  current_stock: Integer,
}
```

**Order**
```python
{
  id: UUID,
  order_number: String (unique),
  farmer_id: FK,
  warehouse_id: FK,
  batch_id: FK (nullable),
  status: Enum [PENDING, BATCHED, IN_TRANSIT, DELIVERED, FAILED],
  total_amount: Float,
  order_date: DateTime,
  requested_delivery_date: DateTime,
}
```

**Batch**
```python
{
  id: UUID,
  batch_number: String (unique),
  warehouse_id: FK,
  district: String,
  region: String,
  total_orders: Integer,
  total_weight_kg: Float,
  total_value: Float,
  status: String [pending, ready, in_transit, completed],
}
```

**Route**
```python
{
  id: UUID,
  route_number: String (unique),
  batch_id: FK,
  total_stops: Integer,
  total_distance_km: Float,
  estimated_delivery_time_hours: Float,
  optimized_sequence: JSON (List[farmer_id]),
  status: String,
}
```

**ProofOfDelivery**
```python
{
  id: UUID,
  delivery_id: FK,
  farmer_name: String,
  farmer_phone: String,
  signature_stored_path: String,
  photo_evidence: JSON (List[file_path]),
  location_latitude/longitude: Float,
  delivery_condition: String,
  verified: Boolean,
  sms_alert_sent: Boolean,
  captured_at: DateTime,
}
```

---

### 3. Service Layer

#### 3.1 Routing Engine (`services/routing.py`)

**Class**: `RoutingEngine`

```python
class RoutingEngine:
    - haversine_distance(lat1, lon1, lat2, lon2) -> float
    - nearest_neighbor_tsp(warehouse, farmers) -> (sequence, distance)
    - two_opt_optimization(sequence, warehouse) -> (optimized_seq, distance)
    - estimate_delivery_time(distance, stops) -> float
```

**Algorithm Flow**:

```
Input: Warehouse location + List of farmers

Step 1: Nearest Neighbor TSP
  1. Start at warehouse
  2. Repeat until all farmers visited:
     - Find nearest unvisited farmer
     - Visit farmer, add distance
     - Mark farmer as visited
  3. Return to warehouse
  4. Output: Sequence, Total Distance

Step 2: 2-OPT Optimization
  1. Set current_sequence = NN sequence
  2. Set improved = True
  3. While improved AND iterations < max:
     a. Set improved = False
     b. For each segment pair (i, j):
        - Try reversing segment [i+1:j+1]
        - If distance improves:
          * Update sequence
          * Set improved = True
          * Break
  4. Output: Optimized sequence, Optimized distance
```

**Complexity Analysis**:
- Nearest Neighbor: O(n²)
- 2-OPT per iteration: O(n²)
- Total: O(n² × iterations)
- Typical result: 15-25% distance reduction

#### 3.2 Batching Engine (`services/routing.py`)

**Class**: `BatchingEngine`

```python
class BatchingEngine:
    - create_batches_for_district(warehouse_id, district, region) -> List[Batch]
    - generate_routes_for_batch(batch_id) -> List[Route]
    - _split_into_subroutes(warehouse, sequence, distance) -> List[Route]
```

**Workflow**:

```
1. Get pending orders for district
2. Group orders by:
   - Warehouse
   - District
   - Maximum orders per batch (config)
3. For each batch:
   - Calculate total weight & value
   - Create batch record
   - Assign orders to batch
4. For each batch:
   - Get all farmers from orders
   - Apply routing optimization
   - Split into sub-routes if needed
```

#### 3.3 Inventory Sync Service (`services/inventory.py`)

**Class**: `InventorySyncService`

```python
class InventorySyncService:
    - sync_warehouse_inventory(warehouse_id) -> Dict
    - _fetch_external_inventory(warehouse) -> List[Dict]
    - _sync_inventory_items(warehouse, external_items) -> Dict
    - check_reorder_levels(warehouse_id) -> List[Dict]
    - estimate_stock_availability(warehouse_id, sku, quantity) -> Dict
```

**Sync Flow**:

```
Input: Warehouse ID

1. Fetch warehouse from database
2. Call Input Acquisition API:
   GET /warehouses/{warehouse_id}/inventory
3. Process each external item:
   - Check if SKU exists in local DB
   - If exists: Update quantity & metadata
   - If not exists: Create new record
4. Update warehouse total stock
5. Log sync event
6. Send success/error notification
```

#### 3.4 Proof of Delivery Service (`services/proof_of_delivery.py`)

**Class**: `ProofOfDeliveryService`

```python
class ProofOfDeliveryService:
    - create_proof_of_delivery(delivery_id, pod_data) -> str
    - _save_signature(delivery_id, farmer_name, signature_base64) -> str
    - _save_photos(delivery_id, farmer_name, photos_base64) -> List[str]
    - _send_sms_alert(delivery, pod) -> bool
    - verify_pod(pod_id, verified_by) -> Dict
    - get_delivery_pod(delivery_id) -> Dict
```

**PoD Creation Flow**:

```
Input: Delivery ID + PoD Data

1. Validate delivery exists
2. Save signature:
   - Decode base64 image
   - Generate unique filename
   - Store on disk/S3
3. Save photos:
   - For each photo:
     * Decode base64
     * Generate unique filename
     * Store on disk/S3
4. Create PoD record:
   - Store farmer info
   - Store location (GPS)
   - Store file paths
   - Mark items as verified
5. Update delivery status → COMPLETED
6. Send SMS alert:
   - Format message
   - Call Twilio API
   - Update sms_alert_sent flag
7. Return PoD ID
```

---

### 4. API Layer

**Base URL**: `/api/v1`

#### 4.1 Request/Response Flow

```
Client Request
    ↓
Nginx Router
    ↓
Flask Blueprint
    ↓
Pydantic Schema Validation
    ↓
Service Layer (Business Logic)
    ↓
Database Query (SQLAlchemy ORM)
    ↓
PostgreSQL
    ↓
Response JSON
    ↓
Client
```

#### 4.2 Error Handling

```python
try:
    # Validate input (Pydantic)
    # Call service
    # Commit to database
except ValidationError:
    return {"error": "Invalid input"}, 400
except ResourceNotFound:
    return {"error": "Resource not found"}, 404
except DatabaseError:
    return {"error": "Database error"}, 500
except Exception:
    return {"error": "Internal server error"}, 500
```

---

### 5. Frontend Layer

#### 5.1 PoD Interface Architecture

```
┌─────────────────────────────────────────┐
│         HTML (Structure)                 │
│  - Form sections                         │
│  - Input fields                          │
│  - Canvas elements                       │
│  - Hidden data containers               │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         CSS (Presentation)              │
│  - Mobile-responsive grid               │
│  - Flexbox layouts                      │
│  - Media queries                        │
│  - Animations                           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      JavaScript (Interaction)           │
│  - Form handling                        │
│  - Geolocation API                      │
│  - Canvas drawing                       │
│  - Photo upload                         │
│  - API communication                    │
└─────────────────────────────────────────┘
```

#### 5.2 PoD App Class Structure

```javascript
class ProofOfDeliveryApp {
  // Initialization
  - init()
  - setupSignatureCapture()
  - setupEventListeners()
  - generateDeviceId()

  // Data Loading
  - loadDeliveryDetails()
  - loadOrderItems()

  // User Interactions
  - handlePhotoUpload()
  - handleFormSubmit()
  - updateItemVerification()

  // Location & Signatures
  - getLocation()
  - updateMap()
  - removePhoto()

  // Submission
  - validateForm()
  - submitPoD()
  - showError() / showSuccess()
}
```

---

## Data Flow Examples

### Order to Delivery Flow

```
1. CREATE ORDER
   POST /api/v1/orders
   ↓
   Create Order record
   Create OrderItem records
   Status: PENDING
   ↓

2. AUTO-BATCH FOR DISTRICT
   POST /api/v1/batches/auto-batch-district
   ↓
   Get pending orders for district
   Group by warehouse & max capacity
   Create Batch records
   Update Order.status → BATCHED
   ↓

3. OPTIMIZE ROUTES
   POST /api/v1/batches/{batch_id}/optimize-routes
   ↓
   Get farmers from orders
   Apply Nearest Neighbor TSP
   Apply 2-OPT optimization
   Create Route record
   Store optimized_sequence
   ↓

4. ASSIGN AGENTS & CREATE DELIVERIES
   PUT /api/v1/deliveries/{delivery_id}/assign-agent
   ↓
   Assign FieldAgent
   Create Delivery record
   Status: ASSIGNED
   ↓

5. START DELIVERY
   PUT /api/v1/deliveries/{delivery_id}/start
   ↓
   Update Delivery.status → IN_TRANSIT
   Set actual_arrival_time
   ↓

6. COMPLETE WITH POD
   POST /api/v1/proof-of-delivery/{delivery_id}
   ↓
   Save signature & photos
   Create ProofOfDelivery record
   Update Delivery.status → COMPLETED
   Send SMS alert
   ↓

7. VERIFY POD
   PUT /api/v1/proof-of-delivery/{pod_id}/verify
   ↓
   Mark pod.verified = True
   Keep audit trail
```

---

## Configuration & Scaling

### Configuration Hierarchy

```
1. Code Defaults (in config.py)
2. Environment Variables (from .env)
3. Runtime Configuration (Flask app.config)
```

**Tuning Parameters**:

```python
MAX_ORDERS_PER_BATCH = 50        # Orders per batch
MAX_DELIVERY_STOPS_PER_ROUTE = 30 # Stops per route
OPTIMAL_ROUTE_DISTANCE_KM = 100   # Target distance
AVG_SPEED_KMPH = 40               # Rural driving speed
TIME_PER_STOP_MINUTES = 15        # Delivery time per stop
```

### Horizontal Scaling

```
Single Server:
  ┌──────────────┐
  │ App (1 CPU)  │
  │ PostgreSQL   │
  │ Redis        │
  └──────────────┘

Multi-Server:
  ┌──────────────────────────────────┐
  │         Load Balancer            │
  ├──────────┬──────────┬────────────┤
  │  App 1   │  App 2   │   App 3    │
  └──────────┴──────────┴────────────┘
              │
      ┌───────┴───────┐
      │               │
  ┌───▼──────┐   ┌───▼──────┐
  │ PostgreSQL│   │  Redis   │
  │ (Primary) │   │ (Cache)  │
  └──────────┘   └──────────┘
```

---

## Security Architecture

### Authentication & Authorization

```
API Request
    ↓
Headers validation
    ↓
CORS check
    ↓
Rate limiting (optional)
    ↓
SQLAlchemy ORM (SQL injection prevention)
    ↓
Response
```

### Data Protection

- ✅ Environment variables for secrets
- ✅ No hardcoded credentials
- ✅ HTTPS/SSL encryption
- ✅ Database user permissions

---

## Performance Considerations

### Bottlenecks & Solutions

| Bottleneck | Solution |
|-----------|----------|
| Routing calculation | Limit stops per route, cache results |
| Database queries | Add indexes on frequently queried columns |
| File uploads | Use S3/CDN, compress images |
| API response time | Redis caching, database optimization |
| Inventory sync | Background job with Celery |

### Optimization Strategies

1. **Database**: Connection pooling, query optimization, indexes
2. **Caching**: Redis for inventory, routes, session data
3. **API**: Pagination, pagination, response compression
4. **Frontend**: Lazy loading, image compression, service workers
5. **Infrastructure**: Load balancing, horizontal scaling, CDN

---

## Monitoring & Observability

### Metrics to Track

```
- API response time
- Database query time
- Number of active routes
- Order processing time
- PoD submission rate
- SMS delivery rate
- System resource usage (CPU, memory)
```

### Logging Strategy

```
Application logs → Aggregated → Alerts
    ↓
  STDOUT
  Files
  ELK Stack (optional)
```

---

**Last Updated**: April 16, 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✅
