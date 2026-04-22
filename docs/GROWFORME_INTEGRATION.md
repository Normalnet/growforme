# GrowForMe Integration Guide

## Overview

SmartTechBuddy Input Distribution is architected to seamlessly integrate with GrowForMe's existing system. The application uses **mock data for development and testing**, and can be switched to **real GrowForMe API** with minimal configuration changes.

---

## Core Input Types Supported

The system manages **5 core input categories**:

| Input Type | Category | Examples |
|-----------|----------|----------|
| **SEEDS** | seeds | Wheat, Rice, Cotton (certified varieties) |
| **FERTILIZER_BASAL** | fertilizer_basal | NPK, DAP, MOP (base application) |
| **FERTILIZER_TOP_DRESSING** | fertilizer_top_dressing | Urea, CAN (secondary application) |
| **MECHANIZATION** | mechanization | Hand hoes, plows, seeders, equipment |
| **CHEMICAL** | chemical | Pesticides, fungicides, herbicides |

---

## Architecture Overview

### Current State (Development with Mock Data)

```
Frontend (port 8000)
    ↓
Backend API (port 5000) - app_simple.py
    ↓
Mock Data Storage (in-memory)
    ├── mock_delivery
    ├── mock_order
    └── mock_items
```

### Future State (Production with GrowForMe Integration)

```
Frontend (port 8000)
    ↓
Backend API (port 5000) - full run.py implementation
    ↓
GrowForMe API Gateway
    ↓
GrowForMe Systems
    ├── Inventory Database
    ├── Farmer Database
    ├── Order Management
    └── Delivery Tracking
```

---

## Configuration

### 1. Development Mode (Using Mock Data)

**Environment Variables:**
```env
# .env file
DATA_SOURCE=mock
DATABASE_URL=sqlite:///smarttech_dev.db
```

**Current Backend:** `backend/app_simple.py`
- Returns hardcoded mock delivery and order data
- Perfect for UI/UX testing
- No external dependencies needed

### 2. Production Mode (GrowForMe Integration)

**Environment Variables:**
```env
# .env file
DATA_SOURCE=growforme_api
GROWFORME_API_URL=https://api.growforme.com/api/v1
GROWFORME_API_KEY=your-api-key-here
GROWFORME_DATABASE_URL=postgresql://user:password@host:5432/growforme_db
```

**Production Backend:** `backend/run.py`
- Full Flask application with SQLAlchemy ORM
- Connects to GrowForMe API endpoints
- Uses real database models

---

## Migration Path: Mock Data → GrowForMe API

### Step 1: Switch Configuration

Update `.env` file:
```bash
# BEFORE (Development)
DATA_SOURCE=mock
DATABASE_URL=sqlite:///smarttech_dev.db

# AFTER (Production)
DATA_SOURCE=growforme_api
GROWFORME_API_URL=https://api.growforme.com/api/v1
GROWFORME_API_KEY=<your-actual-key>
GROWFORME_DATABASE_URL=<growforme-db-connection>
```

### Step 2: Implement GrowForMe Service Layer

Create `backend/app/services/growforme_integration.py`:

```python
import requests
from flask import current_app

class GrowForMeService:
    """Service for integrating with GrowForMe API"""
    
    def __init__(self):
        self.base_url = current_app.config['GROWFORME_API_URL']
        self.api_key = current_app.config['GROWFORME_API_KEY']
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_delivery(self, delivery_id):
        """Fetch delivery from GrowForMe"""
        response = requests.get(
            f"{self.base_url}/deliveries/{delivery_id}",
            headers=self.headers
        )
        return response.json()
    
    def get_order(self, order_id):
        """Fetch order with items from GrowForMe"""
        response = requests.get(
            f"{self.base_url}/orders/{order_id}",
            headers=self.headers
        )
        return response.json()
    
    def create_proof_of_delivery(self, delivery_id, pod_data):
        """Submit PoD to GrowForMe"""
        response = requests.post(
            f"{self.base_url}/proof-of-delivery/{delivery_id}",
            headers=self.headers,
            json=pod_data
        )
        return response.json()
    
    def sync_inventory(self, warehouse_id):
        """Sync inventory from GrowForMe"""
        response = requests.get(
            f"{self.base_url}/inventory/warehouses/{warehouse_id}/sync",
            headers=self.headers
        )
        return response.json()
```

### Step 3: Update API Endpoints

Modify `backend/app_simple.py` or `backend/app/api/*.py` files:

**Before (Mock Data):**
```python
@app.route('/api/v1/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    return jsonify(mock_delivery), 200
```

**After (GrowForMe Integration):**
```python
from app.services.growforme_integration import GrowForMeService

@app.route('/api/v1/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    if current_app.config['DATA_SOURCE'] == 'mock':
        return jsonify(mock_delivery), 200
    else:
        service = GrowForMeService()
        return jsonify(service.get_delivery(delivery_id)), 200
```

### Step 4: Database Migration

**From SQLite (Development):**
```bash
python
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
```

**To PostgreSQL (Production):**
```bash
# Update DATABASE_URL in .env to PostgreSQL
# Run migrations
alembic upgrade head
```

---

## API Endpoints Reference

### Delivery Endpoints

| Endpoint | Method | Purpose | Mock/GrowForMe |
|----------|--------|---------|---|
| `/api/v1/deliveries/{id}` | GET | Get delivery details | ✓ Both |
| `/api/v1/deliveries` | POST | Create delivery | ✓ GrowForMe only |
| `/api/v1/deliveries/{id}/start` | PUT | Start delivery | ✓ GrowForMe only |
| `/api/v1/deliveries/{id}/complete` | PUT | Complete delivery | ✓ GrowForMe only |

### Order Endpoints

| Endpoint | Method | Purpose | Mock/GrowForMe |
|----------|--------|---------|---|
| `/api/v1/orders/{id}` | GET | Get order with items | ✓ Both |
| `/api/v1/orders` | POST | Create order | ✓ GrowForMe only |
| `/api/v1/orders/{id}` | PUT | Update order | ✓ GrowForMe only |

### Proof of Delivery Endpoints

| Endpoint | Method | Purpose | Mock/GrowForMe |
|----------|--------|---------|---|
| `/api/v1/proof-of-delivery/{id}` | POST | Submit PoD | ✓ Both |
| `/api/v1/proof-of-delivery/{id}` | GET | Get PoD details | ✓ GrowForMe only |
| `/api/v1/proof-of-delivery/{id}/verify` | PUT | Verify PoD | ✓ GrowForMe only |

### Inventory Endpoints

| Endpoint | Method | Purpose | Mock/GrowForMe |
|----------|--------|---------|---|
| `/api/v1/inventory/warehouses` | GET | List warehouses | ✓ GrowForMe only |
| `/api/v1/inventory/sync/{id}` | POST | Sync inventory | ✓ GrowForMe only |
| `/api/v1/inventory/warehouses/{id}/check-availability` | POST | Check stock | ✓ GrowForMe only |

---

## Testing the Integration

### 1. Test with Mock Data (Current)

```bash
# Terminal 1: Start backend
.\.venv\Scripts\python.exe backend/app_simple.py

# Terminal 2: Start frontend
cd frontend/pod-interface
python -m http.server 8000

# Browser: Open http://localhost:8000?delivery_id=DEL-001
```

Mock data automatically returns:
- Delivery: DEL-001
- Order: ORD-001 with 5 items (Seeds, Fertilizer, Chemical, Mechanization)

### 2. Test GrowForMe Integration (When Ready)

```bash
# Update .env
DATA_SOURCE=growforme_api
GROWFORME_API_URL=https://api.growforme.com/api/v1
GROWFORME_API_KEY=<your-key>

# Start production backend
python backend/run.py

# Test endpoints
curl -H "Authorization: Bearer YOUR_KEY" \
     http://localhost:5000/api/v1/deliveries/REAL_DELIVERY_ID
```

---

## GrowForMe API Specifications

### Expected Delivery Response Format

```json
{
  "id": "DEL-001",
  "delivery_number": "DEL-2026041601",
  "order_id": "ORD-001",
  "farmer_id": "farmer-123",
  "status": "assigned",
  "warehouse_id": "warehouse-1",
  "agent_id": "agent-5",
  "scheduled_date": "2026-04-22T08:00:00Z",
  "delivery_date": null,
  "delivery_latitude": null,
  "delivery_longitude": null
}
```

### Expected Order Response Format

```json
{
  "id": "ORD-001",
  "order_number": "ORD-2026041601",
  "farmer_id": "farmer-123",
  "warehouse_id": "warehouse-1",
  "status": "batched",
  "total_amount": 6780,
  "items": [
    {
      "id": "item-1",
      "sku": "SEED-001",
      "product_name": "Certified Wheat Seeds Premium",
      "input_type": "seeds",
      "quantity": 50,
      "unit": "kg",
      "unit_price": 100
    },
    {
      "id": "item-2",
      "sku": "FERT-001",
      "product_name": "Basal Fertilizer NPK 10:26:26",
      "input_type": "fertilizer_basal",
      "quantity": 100,
      "unit": "kg",
      "unit_price": 45
    },
    {
      "id": "item-3",
      "sku": "FERT-002",
      "product_name": "Top Dressing Urea",
      "input_type": "fertilizer_top_dressing",
      "quantity": 50,
      "unit": "kg",
      "unit_price": 35
    },
    {
      "id": "item-4",
      "sku": "CHEM-001",
      "product_name": "Fungicide (Carbendazim)",
      "input_type": "chemical",
      "quantity": 10,
      "unit": "liters",
      "unit_price": 250
    },
    {
      "id": "item-5",
      "sku": "MECH-001",
      "product_name": "Hand Hoe (Desi Plow)",
      "input_type": "mechanization",
      "quantity": 2,
      "unit": "pieces",
      "unit_price": 500
    }
  ]
}
```

### Expected PoD Response Format

```json
{
  "pod_id": "POD-1713802800.123",
  "delivery_id": "DEL-001",
  "farmer_name": "Harjeet Singh",
  "farmer_phone": "+919876543210",
  "delivery_condition": "perfect",
  "message": "Proof of delivery created successfully",
  "sms_alert_sent": true,
  "sms_message": "Hello Harjeet Singh, your input delivery has been confirmed...",
  "timestamp": "2026-04-22T16:46:40.123456Z"
}
```

---

## Data Synchronization Strategy

### Real-Time Sync
- **Deliveries**: Sync immediately when status changes
- **Orders**: Sync when new orders are created
- **Inventory**: Sync every 6 hours or on-demand

### Offline Capability
- Store last-synced data locally
- Allow PoD submission with offline signature
- Sync when connectivity restored

### Conflict Resolution
- Latest timestamp wins
- Log all conflicts in `inventory_sync_logs` table
- Alert admin if sync fails > 3 attempts

---

## Troubleshooting

### Issue: "GrowForMe API integration not yet configured"

**Solution**: Ensure `DATA_SOURCE=growforme_api` is set in `.env` and backend is running `run.py`

### Issue: API Key validation failed

**Solution**: Verify `GROWFORME_API_KEY` is correct and has appropriate permissions

### Issue: Database connection refused

**Solution**: Check `GROWFORME_DATABASE_URL` connection string and ensure PostgreSQL is running

### Issue: Data mismatch between mock and real API

**Solution**: Compare responses in browser DevTools console; check API documentation for response format

---

## Security Considerations

1. **API Keys**: Never commit to git, use `.env` file
2. **HTTPS**: Always use HTTPS in production
3. **Authentication**: Add JWT tokens for internal API calls
4. **Data Encryption**: Encrypt sensitive fields (phone numbers, locations)
5. **Rate Limiting**: Implement rate limits on API endpoints
6. **CORS**: Restrict CORS origins to trusted domains

---

## Next Steps

1. ✅ Complete UI/UX testing with mock data
2. ⏳ Obtain GrowForMe API credentials
3. ⏳ Implement GrowForMe service layer
4. ⏳ Set up PostgreSQL database
5. ⏳ Migrate from `app_simple.py` to `run.py`
6. ⏳ Perform end-to-end testing with real data
7. ⏳ Deploy to production

---

**Last Updated**: April 22, 2026  
**Status**: Ready for GrowForMe Integration
