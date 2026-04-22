# SmartTechBuddy Input Distribution — Technical Requirements Document

**Version**: 1.0.0
**Date**: April 22, 2026
**Status**: Implemented (Development / Mock Mode)
**Project**: GrowForMe Agro-FinTech Ecosystem — Last-Mile Distribution Module

---

## 1. Project Overview

SmartTechBuddy Input Distribution is the last-mile logistics layer of the GrowForMe Agro-FinTech platform. It manages the movement of farm inputs (seeds, fertilizers, chemicals, mechanization equipment) from regional warehouses to individual farmers, with full digital accountability from dispatch to proof of delivery.

### 1.1 Business Context

GrowForMe provides agricultural credit and procurement services to smallholder farmers across India. Once inputs are purchased via the GrowForMe platform (handled by the companion "Input Acquisition" project), this system takes over to ensure:
- Correct inputs are dispatched from the right warehouse
- Deliveries are batched efficiently by geography
- Farmers receive real-time SMS notifications
- Field agents capture tamper-proof digital proof of delivery
- Leadership has real-time visibility into delivery performance

---

## 2. User Stories & Acceptance Criteria

### US-01 — Input Data Integration
**As a** Distribution Manager,
**I want to** sync with the Input Acquisition Project database,
**So that** I can see exactly what seeds and fertilizers are available for dispatch.

**Acceptance Criteria:**
- System displays live inventory per warehouse (SKU, quantity, reorder level, expiry, supplier)
- Stock status is automatically annotated: `ok`, `low_stock`, `out_of_stock`
- Filters available: by input type, low-stock-only flag
- Manual "Force Sync" triggers a re-fetch from the upstream source
- Last-synced timestamp shown per item

**Endpoints implemented:**
- `GET /api/v1/inventory/warehouses/{warehouse_id}/stock`
- `POST /api/v1/inventory/warehouses/{warehouse_id}/sync`

---

### US-02 — Regional Batching
**As a** Logistics Planner,
**I want to** group orders by district (e.g., Northern Region),
**So that** I can assign them to the correct local delivery partners.

**Acceptance Criteria:**
- Pending orders are automatically grouped by district and region
- K-Means++ clustering further sub-groups large districts into route-sized batches (max 15 stops)
- Planner can filter by district or region
- Each batch shows order count, total value, and estimated area coverage

**Endpoints implemented:**
- `GET /api/v1/batches/by-district`
- `POST /api/v1/batches/create-from-district`
- `POST /api/v1/batches/regional-cluster`

---

### US-03 — Warehouse Handshake (Release Order)
**As a** Warehouse Operator,
**I want** a digital Release Order generated when a distribution task is assigned,
**So that** inventory is formally moved out of storage with a documented trail.

**Acceptance Criteria:**
- Release Order (RO) is generated with a unique `RO-{timestamp}` reference number
- RO contains aggregated line items: SKU, product name, quantity, unit cost, total value
- Mandatory signatures: warehouse operator + field agent (supervisor countersign required if order > ₹50,000)
- RO is valid for 48 hours from generation
- Inventory marked as deducted upon RO generation
- Four mandatory instructions included (handle with care, match serial numbers, obtain farmer signature, report damage)

**Endpoints implemented:**
- `POST /api/v1/batches/{batch_id}/release-order`

---

### US-04 — Automated SMS Alerts
**As a** Farmer,
**I want** an SMS notification when my inputs are "Out for Delivery",
**So that** I can prepare for receipt at my farm gate.

**Acceptance Criteria:**
- SMS sent automatically when delivery status changes to "out for delivery"
- Four message templates: `out_for_delivery`, `arrived`, `delivered`, `failed`
- Per-delivery SMS: sends to individual farmer with agent name and ETA
- Bulk SMS: sends to all farmers on a route simultaneously
- SMS log records status, timestamp, and recipient

**Endpoints implemented:**
- `POST /api/v1/deliveries/{delivery_id}/send-sms`
- `POST /api/v1/deliveries/bulk-sms`

---

### US-05 — Digital Proof of Delivery (PoD)
**As a** Field Agent,
**I want to** capture a digital signature and a photo of the delivered inputs,
**So that** diversion is prevented and accountability is ensured.

**Acceptance Criteria:**
- GPS coordinates captured from device at time of submission
- Geofence check: agent must be within 50 m of registered farm location
- Deviations > 200 m automatically flagged as HIGH risk and queued for supervisor review
- Digital signature captured on canvas (touch/stylus/mouse)
- Photo upload supported (PNG, JPG, JPEG)
- Per-item delivery verification checklist
- Delivery condition recorded: perfect / minor_damage / major_damage / refused
- PoD submission triggers automatic farmer SMS confirmation
- Risk levels: LOW (0–19), MEDIUM (20–39), HIGH (40+ risk score)

**Endpoints implemented:**
- `POST /api/v1/proof-of-delivery/{delivery_id}`
- `POST /api/v1/dispatch/geofence-check`

---

### US-06 — Analytics Dashboard
**As the** GrowForMe CEO,
**I want** a real-time view of "Delivered vs. Pending" inputs across all regions,
**So that** I can monitor operational performance at a glance.

**Acceptance Criteria:**
- KPIs shown: total orders, delivered, in transit, pending dispatch, failed, delivery rate %, on-time rate %
- Breakdown by region (Punjab, Haryana, UP, Rajasthan, Maharashtra)
- Breakdown by input type (Seeds, Fertilizer, Chemical, Mechanization)
- Weekly trend view (4-week rolling window)
- Regional table with colour-coded rate badges (green ≥ 80%, yellow ≥ 60%, red < 60%)
- Supporting metrics: high-risk PoDs count, SMS alerts sent, avg delivery time

**Endpoints implemented:**
- `GET /api/v1/analytics/overview`
- `GET /api/v1/analytics/by-region`
- `GET /api/v1/analytics/by-input-type`
- `GET /api/v1/analytics/weekly-trend`

---

### US-07 — Intelligent Routing
**As a** Driver,
**I want** a digital map with the most efficient sequence of farm drop-offs,
**So that** I can reduce delivery time and fuel costs.

**Acceptance Criteria:**
- Route optimised using Nearest Neighbour TSP + 2-OPT (15–25% distance reduction vs. unoptimised)
- Mobile-optimised display: stop cards with farmer name, address, ETA, distance from previous stop
- Each stop provides: Google Maps deep navigation link, SMS farmer button, PoD submission link, mark-complete button
- "SMS All Farmers" sends bulk out-for-delivery notification in one tap
- Completed stops visually confirmed (green highlight)
- Full route link opens multi-stop Google Maps URL (no API key required)
- Optimised for up to 30 stops per route

**Endpoints implemented:**
- `GET /api/v1/routes/{route_id}/map`
- `POST /api/v1/routes/{route_id}/stops/{stop_number}/complete`

---

## 3. System Architecture

### 3.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Port 8000)                     │
│                                                                 │
│  login/          → Role-aware login, JWT issued at backend      │
│  dashboard/      → 8 role-specific HTML pages (ES modules)      │
│  pod-interface/  → Field agent PoD capture form                 │
│  shared/         → auth.js (JWT helpers), dashboard.css         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / REST JSON
                            │ Bearer Token (JWT)
┌───────────────────────────▼─────────────────────────────────────┐
│                     BACKEND (Port 5000)                         │
│                                                                 │
│  app_simple.py   → Primary development server (Flask 3.0.0)    │
│  app/services/   → Business logic (batching, routing, PoD)     │
│  config.py       → Environment-driven configuration            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ (production target)
┌───────────────────────────▼─────────────────────────────────────┐
│             DATA LAYER (production targets)                     │
│  PostgreSQL    → Persistent data store                          │
│  Redis         → Celery task queue + caching                   │
│  Twilio        → SMS gateway                                    │
│  GrowForMe API → Upstream inventory source                      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Primary server | `app_simple.py` | SQLAlchemy incompatible with Python 3.14.3; mock backend avoids dependency |
| JWT library | stdlib only (hmac + hashlib) | No external JWT library required; self-contained |
| JWT storage | `sessionStorage` | Per-tab isolation; clears on tab close; simpler than cookies for SPA |
| Database (dev) | Mock in-memory dicts | Eliminates DB setup friction during development |
| Database (prod) | PostgreSQL via SQLAlchemy | Full ORM, migrations via Alembic |
| Routing algorithm | Nearest Neighbour TSP + 2-OPT | O(n²) per iteration, suitable for ≤ 30 stops; 15–25% improvement |
| Clustering algorithm | K-Means++ (pure stdlib) | No scipy/sklearn required; runs on any Python 3.x |
| Geofence | Haversine distance | Accurate great-circle distance for GPS validation |
| Maps | Google Maps deep links | No API key required; universally supported on mobile |
| Frontend modules | ES modules (`type="module"`) | Enables shared `auth.js` without a bundler |

---

## 4. Technology Stack

### 4.1 Backend

| Component | Technology | Version |
|---|---|---|
| Web framework | Flask | 3.0.0 |
| CORS | Flask-Cors | 4.0.0 |
| ORM (production) | SQLAlchemy | 2.0.23 |
| Migrations | Alembic | 1.13.0 |
| Task queue | Celery | 5.3.4 |
| Message broker | Redis | 5.0.1 |
| SMS gateway | Twilio | 8.10.0 |
| Validation | Pydantic | 2.5.0 |
| Serialization | Marshmallow | 3.20.1 |
| Image processing | Pillow | 10.1.0 |
| HTTP client | Requests | 2.31.0 |
| Geolocation | Geopy | 2.3.0 |
| Environment | python-dotenv | 1.0.0 |
| Runtime | Python | 3.14.3 |

### 4.2 Frontend

| Component | Technology |
|---|---|
| Markup | HTML5 |
| Styling | CSS3 (vanilla, shared stylesheet) |
| Logic | Vanilla JavaScript (ES2020+, modules) |
| Auth | JWT in sessionStorage |
| Maps | Google Maps deep links (no API key) |
| Signatures | HTML5 Canvas API |
| GPS | Browser Geolocation API |
| Charts | CSS-rendered (bar charts via flexbox, no Chart.js) |

### 4.3 Testing

| Component | Technology | Version |
|---|---|---|
| Test framework | pytest | 9.0.3 |
| Coverage | pytest-cov | 7.1.0 |
| Client | Flask test client | (built-in) |

---

## 5. Data Model

### 5.1 Core Entities (Production Schema — `backend/app/models/__init__.py`)

| Entity | Key Fields | Relationships |
|---|---|---|
| `Warehouse` | id, name, location, lat/lon, region, district, capacity | has many Orders, Batches |
| `Farmer` | id, name, phone, aadhaar_hash, lat/lon, district | has many Orders |
| `Order` | id, farmer_id, warehouse_id, status, total_amount, items[] | belongs to Farmer, Warehouse; part of Batch |
| `Batch` | id, warehouse_id, district, status, orders[] | has many Routes |
| `Route` | id, batch_id, agent_id, optimised_sequence[], total_km | has many Deliveries |
| `Delivery` | id, route_id, order_id, status, stop_number, eta | has one ProofOfDelivery |
| `ProofOfDelivery` | id, delivery_id, signature_data, photo_urls[], risk_level, gps_lat/lon | belongs to Delivery |

### 5.2 Enumerations

| Enum | Values |
|---|---|
| `OrderStatus` | PENDING, BATCHED, DISPATCHED, IN_TRANSIT, DELIVERED, FAILED |
| `DeliveryStatus` | ASSIGNED, OUT_FOR_DELIVERY, ARRIVED, DELIVERED, FAILED |
| `InputType` | SEEDS, FERTILIZER_BASAL, FERTILIZER_TOP_DRESSING, CHEMICAL, MECHANIZATION |

### 5.3 Mock Data (Development)

**Warehouses:** `warehouse-001` (Central Warehouse, Amritsar, Punjab)

**Inventory SKUs (9 items):**
SEED-001 (Wheat Seeds), SEED-002 (Paddy Seeds), FERT-001 (DAP), FERT-002 (Urea), FERT-003 (MOP), CHEM-001 (Pesticide), CHEM-002 (Fungicide), MECH-001 (Sprayer), MECH-002 (Harvester Parts)

**Pending Orders (8 orders):**
Amritsar ×3, Ludhiana ×3, Patiala ×2

**Route Stops (mock ROUTE-001):**
DEL-001 (Harjeet Singh), DEL-002 (Sukhwinder Kaur), DEL-003 (Balwinder Gill)

**Analytics (mock aggregate):**
847 total orders | 612 delivered (72.3%) | 89 in transit | 103 pending | 43 failed | 87.4% on-time

---

## 6. Security Model

### 6.1 Authentication

- **Mechanism**: Custom JWT (HMAC-SHA256, stdlib only)
- **Token expiry**: 8 hours (configurable via `JWT_EXPIRY_HOURS`)
- **Storage**: Client-side `sessionStorage` (not localStorage or cookies)
- **Transport**: `Authorization: Bearer <token>` header on every API call
- **Secret**: `JWT_SECRET` environment variable (never hardcoded)

### 6.2 Authorization (Role-Based Access Control)

| Role | Access |
|---|---|
| `admin` | All endpoints and all dashboards |
| `warehouse_mgr` | Inventory, batching, dispatch, analytics (non-CEO), driver map |
| `field_agent` | Assigned deliveries, PoD submission, geofence check, driver map |
| `supervisor` | Flagged delivery review, geofence check results |
| `farmer` | Own order status and delivery tracking only |

### 6.3 Security Practices

- Passwords stored as SHA-256 hashes (upgrade to bcrypt for production)
- All protected routes use `@require_auth(*roles)` decorator
- CORS enabled with `supports_credentials=True` (restrict `CORS_ORIGINS` in production)
- No credentials hardcoded in source — all via environment variables
- Signature data (base64) and GPS coordinates validated server-side
- Geofence deviation > 200 m auto-escalates to supervisor (anti-diversion)
- File uploads: extension allowlist enforced (`png`, `jpg`, `jpeg`, `pdf`, `gif`), 50 MB max

---

## 7. API Reference Summary

Base URL (development): `http://localhost:5000/api/v1`

### 7.1 Authentication
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | Public | Issue JWT token |
| GET | `/auth/me` | All roles | Current user info |
| POST | `/auth/logout` | All roles | Client-side token discard |
| GET | `/auth/users` | admin | List all users |

### 7.2 Core Resources
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/deliveries/{id}` | admin, warehouse_mgr, field_agent, supervisor | Delivery detail |
| GET | `/orders/{id}` | admin, warehouse_mgr | Order detail with items |
| POST | `/proof-of-delivery/{id}` | field_agent, admin | Submit PoD (signature + GPS + photos) |

### 7.3 Inventory (US-01)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/inventory/warehouses/{id}/stock` | admin, warehouse_mgr | Live stock levels, filterable |
| POST | `/inventory/warehouses/{id}/sync` | admin, warehouse_mgr | Force re-sync from upstream |

### 7.4 Batching & Release Orders (US-02, US-03)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/batches/by-district` | admin, warehouse_mgr | Orders grouped by district |
| POST | `/batches/create-from-district` | admin, warehouse_mgr | Create batch from a district |
| POST | `/batches/regional-cluster` | admin, warehouse_mgr | K-Means clustering of deliveries |
| POST | `/batches/{id}/release-order` | admin, warehouse_mgr | Generate Release Order document |

### 7.5 SMS Alerts (US-04)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/deliveries/{id}/send-sms` | admin, warehouse_mgr, field_agent | Send SMS to one farmer |
| POST | `/deliveries/bulk-sms` | admin, warehouse_mgr | Send SMS to all farmers on a route |

### 7.6 Dispatch Pipeline
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dispatch/eligibility-check/{farmer_id}` | admin, warehouse_mgr | GrowForMe credit check |
| POST | `/dispatch/inventory-check` | admin, warehouse_mgr | Verify stock availability |
| POST | `/dispatch/route` | admin, warehouse_mgr | Full dispatch pipeline (TSP optimised) |
| POST | `/dispatch/geofence-check` | field_agent, admin, supervisor | Real-time GPS geofence validation |
| POST | `/dispatch/monitoring/push` | admin, warehouse_mgr | Push monitoring event |
| POST | `/dispatch/predict-window` | admin, warehouse_mgr | Predict delivery time window |

### 7.7 Analytics (US-06)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/analytics/overview` | admin | Full KPIs + all breakdowns |
| GET | `/analytics/by-region` | admin, warehouse_mgr | Regional performance data |
| GET | `/analytics/by-input-type` | admin, warehouse_mgr | Input type breakdown |
| GET | `/analytics/weekly-trend` | admin, warehouse_mgr | 4-week rolling trend |

### 7.8 Routing (US-07)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/routes/{id}/map` | admin, warehouse_mgr, field_agent | Optimised stop sequence + Maps links |
| POST | `/routes/{id}/stops/{n}/complete` | field_agent, admin | Mark stop complete |

### 7.9 Role Dashboards
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dashboard/admin/stats` | admin | System-wide counts and user stats |
| GET | `/dashboard/warehouse/stats` | admin, warehouse_mgr | Warehouse KPIs |
| GET | `/dashboard/field-agent/deliveries` | field_agent, admin | Assigned delivery list |
| GET | `/dashboard/supervisor/flagged` | supervisor, admin | High-risk PoDs for review |
| POST | `/dashboard/supervisor/review/{id}` | supervisor, admin | Approve / escalate / reject PoD |
| GET | `/dashboard/farmer/status` | farmer, admin | Order and delivery status |

### 7.10 System
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | Public | Service health check |
| GET | `/openapi.json` | Public | OpenAPI 3.0 specification |

---

## 8. Algorithms

### 8.1 K-Means++ Regional Clustering (`backend/app/services/batching.py`)

- **Purpose**: Divide large delivery sets into route-sized batches
- **Implementation**: Pure Python stdlib (no NumPy/sklearn)
- **Parameters**: `MAX_BATCH_SIZE = 15` stops per batch; `k = ceil(n / MAX_BATCH_SIZE)`
- **Initialisation**: K-Means++ weighted centroid seeding (reduces poor initialisation risk)
- **Convergence**: Lloyd's iterations until centroid delta < 0.0001° or 100 iterations
- **Input**: List of `{latitude, longitude, delivery_id, ...}` dicts
- **Output**: List of `RegionalBatch` objects with delivery assignments

### 8.2 TSP Route Optimisation (`backend/app/services/routing.py`)

- **Step 1 — Nearest Neighbour**: Greedy O(n²) construction starting from warehouse
- **Step 2 — 2-OPT**: Local search improvement reversing sub-route segments
- **Distance**: Haversine formula (great-circle, metres)
- **Result**: 15–25% distance reduction over unoptimised order
- **Scale**: Optimal for ≤ 30 stops; performance degrades beyond this

### 8.3 Geofence Validation (`backend/app/services/anomaly_detection.py`)

- **Default radius**: 50 metres
- **Distance**: Haversine (inline `_haversine_m()` in `app_simple.py`)
- **Risk bands**: LOW (within geofence), MEDIUM (outside radius), HIGH (> 200 m deviation)
- **Auto-escalation**: HIGH risk triggers supervisor review queue

---

## 9. Frontend Pages

| Page | Path | Accessible By | User Story |
|---|---|---|---|
| Login | `login/index.html` | Public | All |
| Admin Dashboard | `dashboard/admin.html` | admin | System overview |
| Warehouse Dashboard | `dashboard/warehouse.html` | admin, warehouse_mgr | Dispatch pipeline |
| Inventory & Batching | `dashboard/inventory.html` | admin, warehouse_mgr | US-01, US-02, US-03 |
| Analytics Dashboard | `dashboard/analytics.html` | admin | US-06 |
| Driver Route Map | `dashboard/driver_map.html` | admin, warehouse_mgr, field_agent | US-04, US-07 |
| Field Agent Dashboard | `dashboard/field_agent.html` | admin, field_agent | US-05, US-07 |
| Supervisor Dashboard | `dashboard/supervisor.html` | admin, supervisor | Risk review |
| Farmer Dashboard | `dashboard/farmer.html` | admin, farmer | Order tracking |
| PoD Interface | `pod-interface/index.html` | field_agent (direct link) | US-05 |

---

## 10. Configuration Reference

All configuration is environment-variable driven. Copy `backend/.env.example` to `backend/.env`.

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `smarttech-dev-jwt-secret-change-in-production` | HMAC signing key — **must change in production** |
| `JWT_EXPIRY_HOURS` | `8` | Token validity window |
| `DATA_SOURCE` | `mock` | `mock` (in-memory) or `growforme_api` (live) |
| `DATABASE_URL` | `sqlite:///smarttech_dev.db` | SQLAlchemy connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + result backend |
| `TWILIO_ACCOUNT_SID` | — | Twilio credentials for SMS |
| `TWILIO_AUTH_TOKEN` | — | Twilio credentials for SMS |
| `TWILIO_PHONE_NUMBER` | — | Twilio sender number |
| `GROWFORME_API_URL` | — | Upstream Input Acquisition API base URL |
| `GROWFORME_API_KEY` | — | Upstream API authentication key |
| `UPLOAD_FOLDER` | `uploads` | PoD photo storage directory |

---

## 11. Testing

### 11.1 Test Suite Summary

| File | Tests | Coverage |
|---|---|---|
| `tests/test_api.py` | 28 | Auth, delivery, PoD, batching, geofence, dispatch, OpenAPI |
| `tests/test_batching.py` | 16 | K-Means algorithm correctness |
| `tests/test_geofencing.py` | 9 | Geofence, anomaly detection, risk bands |
| **Total** | **53** | All passing |

### 11.2 Test Patterns

- All tests use the Flask test client via `importlib.util` (bypasses SQLAlchemy)
- Protected endpoints require `Authorization: Bearer <token>` header
- An `admin_token` fixture in `conftest.py` generates a valid token using `_create_token()`
- Session-scoped fixtures for `app`, `client`, `admin_token`; function-scoped for `sample_deliveries`

---

## 12. Deployment

### 12.1 Development

```powershell
# Backend
.\.venv\Scripts\python.exe backend/app_simple.py

# Frontend (separate terminal)
cd frontend
python -m http.server 8000
```

### 12.2 Production (Docker)

```bash
docker-compose up -d
```

### 12.3 Production (Manual)

```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

> **Note**: Production uses `backend/app/__init__.py` with full SQLAlchemy. Currently blocked by Python 3.14.3 / SQLAlchemy 2.0.23 incompatibility. Development uses `app_simple.py` exclusively.

---

## 13. Known Constraints & Future Work

| Item | Detail |
|---|---|
| SQLAlchemy incompatibility | Python 3.14.3 incompatible with SQLAlchemy 2.0.23. Use mock backend until resolved (upgrade SQLAlchemy or downgrade Python) |
| Password hashing | Currently SHA-256. Replace with bcrypt/argon2 for production |
| SMS (mock) | Twilio calls are simulated in mock mode. Set credentials in `.env` and `DATA_SOURCE=growforme_api` for live SMS |
| Photo storage | PoD photos stored as filesystem paths. Migrate to S3/GCS for production |
| Real-time updates | No WebSocket; dashboards poll on page load. Add SSE or WebSocket for live updates |
| PDF Release Orders | RO currently returned as JSON. Add WeasyPrint/ReportLab PDF generation |
| Route persistence | Route completion state is in-memory (resets on server restart). Persist to DB |
| Test coverage | New endpoints (analytics, inventory sync, SMS, release order, route map) not yet in test suite |
