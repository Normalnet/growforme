# SmartTechBuddy Input Distribution - Development Instructions

## Project Overview

SmartTechBuddy Input Distribution is a comprehensive logistics management system for the GrowForMe Agro-FinTech ecosystem. It handles last-mile distribution of farm inputs with intelligent routing, real-time inventory sync, and digital proof of delivery.

## Technology Stack

- **Backend**: Flask 3.0.0, PostgreSQL, Redis, Celery
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Algorithms**: TSP optimization (Nearest Neighbor + 2-OPT)
- **APIs**: RESTful architecture with JSON

## Quick Start

### Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

API will run on `http://localhost:5000/api/v1`

### Setup Frontend

```bash
cd frontend/pod-interface
# Open index.html in browser (or use local server)
python -m http.server 8000
```

Access PoD interface at `http://localhost:8000?delivery_id=TEST-001`

## Key Modules

### 1. Routing Engine (`backend/app/services/routing.py`)
- **Purpose**: Optimize delivery routes using TSP algorithms
- **Key Functions**:
  - `nearest_neighbor_tsp()`: Greedy route optimization
  - `two_opt_optimization()`: Local search improvement
  - `estimate_delivery_time()`: Calculate ETA

### 2. Inventory Service (`backend/app/services/inventory.py`)
- **Purpose**: Sync inventory with Input Acquisition API
- **Key Functions**:
  - `sync_warehouse_inventory()`: Fetch external stock levels
  - `check_reorder_levels()`: Monitor thresholds
  - `estimate_stock_availability()`: Verify item availability

### 3. PoD Service (`backend/app/services/proof_of_delivery.py`)
- **Purpose**: Manage digital signatures, photos, SMS alerts
- **Key Functions**:
  - `create_proof_of_delivery()`: Capture PoD data
  - `verify_pod()`: Approve delivery
  - `_send_sms_alert()`: Twilio SMS notification

### 4. Database Models (`backend/app/models/__init__.py`)
- **Core**: Warehouse, Farmer, Order, Batch, Route, Delivery, ProofOfDelivery
- **Enums**: OrderStatus, DeliveryStatus, InputType
- **Relationships**: Order→Batch→Route→Delivery→PoD

### 5. API Endpoints
- **Inventory**: `/inventory/*` - Warehouse & stock management
- **Orders**: `/orders/*` - Order & farmer management
- **Batching**: `/batches/*` - Batch creation & routing
- **Delivery**: `/deliveries/*` - Delivery & agent management
- **PoD**: `/proof-of-delivery/*` - Digital proof of delivery
- **Health**: `/health`, `/status`, `/version` - System monitoring

## Development Workflow

### Adding New Features

1. **Backend**
   - Add models to `backend/app/models/__init__.py` if needed
   - Add service logic to `backend/app/services/`
   - Create API endpoints in `backend/app/api/`
   - Test with Postman or curl

2. **Frontend**
   - Update HTML in `frontend/pod-interface/index.html`
   - Add styles to `frontend/pod-interface/css/styles.css`
   - Add logic to `frontend/pod-interface/js/app.js`

### Environment Setup

```env
# Copy .env.example to .env and configure:
- DATABASE_URL: PostgreSQL connection
- TWILIO_*: SMS gateway
- INPUT_ACQUISITION_API_*: Stock sync API
- UPLOAD_FOLDER: File storage
```

## API Testing Examples

### Create Warehouse
```bash
curl -X POST http://localhost:5000/api/v1/inventory/warehouses \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Central Warehouse",
    "location": "Amritsar",
    "latitude": 31.6295,
    "longitude": 74.8696,
    "region": "Punjab",
    "district": "Amritsar",
    "capacity": 10000
  }'
```

### Create Order
```bash
curl -X POST http://localhost:5000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "farmer-1",
    "warehouse_id": "warehouse-1",
    "total_amount": 5000,
    "items": [{
      "sku": "SEED-001",
      "product_name": "Wheat Seeds",
      "input_type": "SEEDS",
      "quantity": 50,
      "unit": "kg",
      "unit_price": 100
    }]
  }'
```

### Optimize Routes
```bash
curl -X POST http://localhost:5000/api/v1/batches/{batch_id}/optimize-routes \
  -H "Content-Type: application/json"
```

### Submit PoD
```bash
curl -X POST http://localhost:5000/api/v1/proof-of-delivery/{delivery_id} \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_name": "Harjeet Singh",
    "farmer_phone": "+919876543210",
    "delivery_condition": "perfect",
    "location_latitude": 31.6295,
    "location_longitude": 74.8696,
    "signature_data": "data:image/png;base64,...",
    "photos": [],
    "items_verified": {}
  }'
```

## Performance Optimization

### Routing Algorithm
- **Current**: O(n²) Nearest Neighbor + O(n²) 2-OPT per iteration
- **Improvement Achieved**: 15-25% distance reduction
- **Optimal for**: Up to 30 stops per route

### Database
- Add indexes on frequently queried columns
- Use connection pooling
- Implement caching with Redis

### Frontend
- Lazy load images in PoD interface
- Compress signatures to base64
- Use service workers for offline capability

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Database error | Verify PostgreSQL running, check DATABASE_URL |
| Static files 404 | Ensure CSS/JS paths are relative-correct |
| SMS not sent | Check Twilio credentials in .env |
| GPS not working | Use HTTPS, check browser permissions |
| Signature missing | Verify Canvas API support, check browser console |

## Code Standards

### Python
- Follow PEP 8 style guide
- Use type hints for function parameters
- Document with docstrings
- Use logging module

### JavaScript
- Use modern ES6+ syntax
- Add JSDoc comments
- Self-documenting variable names
- Error handling with try-catch

### SQL
- Use prepared statements (SQLAlchemy ORM)
- Index foreign keys
- Normalize database schema

## Deployment

### Docker
```bash
docker-compose up -d
```

### Manual
```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

## Monitoring

- System health: `/health`
- Detailed status: `/status`
- API version: `/version`
- Database: Check order/batch/delivery counts
- Performance: Monitor routing time (should be < 5s)

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [Redis](https://redis.io/documentation)
- [Twilio SMS](https://www.twilio.com/docs/sms)

## Support

For issues or questions:
1. Check README.md for overview
2. Review API documentation
3. Check logs in console/files
4. Test with Postman
5. Verify environment configuration

---

**Version**: 1.0.0  
**Last Updated**: April 16, 2026  
**Maintainers**: Lead Agile Software Engineer
