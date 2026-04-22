# SmartTechBuddy Input Distribution — Developer Reference

> **Living document** — update this file whenever endpoints, pages, credentials, or architecture changes.
> Last updated: April 22, 2026

---

## Quick Start (30 seconds)

```powershell
# Terminal 1 — start backend API (port 5000)
.\.venv\Scripts\python.exe backend/app_simple.py

# Terminal 2 — start frontend file server (port 8000)
# Run from the project root — the --directory flag avoids the need to cd into frontend
.\.venv\Scripts\python.exe -m http.server 8000 --directory frontend
```

Open: **http://localhost:8000/login/**

---

## Demo Login Credentials

| Role | Email | Password | Dashboard URL |
|---|---|---|---|
| **Admin** (full access) | `admin@smarttech.com` | `Admin@1234` | `/dashboard/admin.html` |
| **Warehouse Manager** | `warehouse@smarttech.com` | `Warehouse@1234` | `/dashboard/warehouse.html` |
| **Field Agent** | `agent1@smarttech.com` | `Agent@1234` | `/dashboard/field_agent.html` |
| **Supervisor** | `supervisor@smarttech.com` | `Super@1234` | `/dashboard/supervisor.html` |
| **Farmer** | `farmer@growforme.com` | `Farmer@1234` | `/dashboard/farmer.html` |

> All credentials are click-to-fill on the login page — click any demo card and it auto-submits.

---

## Live URLs (Development)

### Backend API
| URL | What it is |
|---|---|
| `http://localhost:5000/api/v1/health` | Health check — confirms backend is running |
| `http://localhost:5000/api/v1/openapi.json` | OpenAPI 3.0 spec (all endpoints) |
| `http://localhost:5000/api/v1/status` | Detailed system status |

### Frontend Pages
| URL | Role | User Story |
|---|---|---|
| `http://localhost:8000/login/` | Public | Entry point for all users |
| `http://localhost:8000/dashboard/admin.html` | admin | System overview + navigation hub |
| `http://localhost:8000/dashboard/analytics.html` | admin | US-06: CEO Delivered vs Pending |
| `http://localhost:8000/dashboard/inventory.html` | admin, warehouse_mgr | US-01/02/03: Stock sync, district batching, Release Orders |
| `http://localhost:8000/dashboard/warehouse.html` | admin, warehouse_mgr | Dispatch pipeline + K-Means UI |
| `http://localhost:8000/dashboard/driver_map.html?route_id=ROUTE-001` | admin, warehouse_mgr, field_agent | US-04/07: Driver route + SMS |
| `http://localhost:8000/dashboard/field_agent.html` | admin, field_agent | Assigned deliveries |
| `http://localhost:8000/dashboard/supervisor.html` | admin, supervisor | Flagged PoD review |
| `http://localhost:8000/dashboard/farmer.html` | admin, farmer | Order and delivery tracking |
| `http://localhost:8000/pod-interface/index.html?delivery_id=DEL-001` | field_agent | US-05: Digital Proof of Delivery |

---

## How to Test Each User Story End-to-End

### US-01 — Inventory Sync
1. Log in as `warehouse@smarttech.com`
2. Navigate to **Inventory & Batching** (`/dashboard/inventory.html`)
3. Observe 9 SKUs loaded with stock status badges (ok / low_stock / out_of_stock)
4. Use the **Input Type** dropdown to filter (e.g., SEEDS only)
5. Check **Low Stock Only** to filter understock items
6. Click **Force Sync** — see "synced X items" toast notification
7. **API test**: `curl http://localhost:5000/api/v1/inventory/warehouses/warehouse-001/stock` (requires Bearer token)

### Regional Batching
1. Still on `inventory.html` (warehouse_mgr login)
2. Scroll to the **District Batching** panel
3. See 8 pending orders grouped by Accra, Kumasi, Tamale
4. Click **Batch District** on any row → K-Means sub-groups into route-sized batches (≤15 stops)
5. See batch ID returned (e.g., `BATCH-accra-1713800000`)
6. **API test**: `GET /api/v1/batches/by-district?district=Accra`

### US-03 — Release Order
1. Still on `inventory.html`
2. Scroll to the **Release Order Generator** panel
3. Enter a batch ID (e.g., the one returned from step 4 above) and select a district
4. Click **Generate Release Order**
5. See the RO rendered with: RO number, line items table, total value, instructions, signature requirements
6. **API test**: `POST /api/v1/batches/BATCH-TEST-001/release-order`

### US-04 — SMS Alerts
1. Log in as `agent1@smarttech.com`
2. Navigate to **Driver Route Map** (`/dashboard/driver_map.html?route_id=ROUTE-001`)
3. Click **SMS All Farmers** (bottom bar) → toast shows "X SMS alerts sent"
4. Expand any stop card → click **SMS Farmer** → per-farmer toast confirmation
5. **API test**: `POST /api/v1/deliveries/DEL-001/send-sms` with body `{"event":"out_for_delivery","farmer_name":"Test","eta_minutes":20}`

### US-05 — Digital Proof of Delivery
1. Log in as `agent1@smarttech.com`
2. Navigate to **PoD Interface** (`/pod-interface/index.html?delivery_id=DEL-001`)
3. Click **Capture GPS** — browser prompts for location permission (grant it)
4. Observe geofence check result (will be LOW risk in development with same coords)
5. Draw a signature on the canvas pad
6. Upload a photo (optional)
7. Check off items in the delivery verification list
8. Select delivery condition (perfect / minor damage / etc.)
9. Click **Submit Proof of Delivery** → see POD ID and risk assessment returned
10. **API test**: `POST /api/v1/proof-of-delivery/DEL-001` with JSON body (see TRD Section 7.2)

### US-06 — Analytics Dashboard
1. Log in as `admin@smarttech.com`
2. Navigate to **Analytics** (`/dashboard/analytics.html`)
3. See 8 KPI stat cards at top
4. Regional stacked bar chart (Greater Accra, Ashanti, Eastern, Northern, Central)
5. Delivery rate + on-time rate gauge bars
6. Input type horizontal bar chart
7. Weekly trend bars (Apr 1–28)
8. Regional detail table with colour-coded rate badges
9. **API test**: `GET /api/v1/analytics/overview`

### US-07 — Intelligent Routing
1. Log in as `agent1@smarttech.com`
2. Navigate to **Driver Map** (`/dashboard/driver_map.html?route_id=ROUTE-001`)
3. See route header: 3 stops, distance, duration, optimisation % reduction
4. Click **Open Route in Maps** → opens multi-stop Google Maps URL
5. Expand stop card (click header) → see all action buttons
6. Click **Navigate** on any stop → opens Google Maps turn-by-turn for that farm
7. Click **Mark Done** → card turns green
8. **API test**: `GET /api/v1/routes/ROUTE-001/map`

---

## Mock Data Reference

### Warehouses
| ID | Name | Location |
|---|---|---|
| `warehouse-001` | Central Warehouse | Accra, Greater Accra (5.6037, -0.1870) |

### Deliveries
| ID | Farmer | District |
|---|---|---|
| `DEL-001` | Kofi Yeboah | Accra |
| `DEL-002` | Abena Osei | Accra |
| `DEL-003` | Yaw Asare | Kumasi |

### Orders
| ID | Items | Details |
|---|---|---|
| `ORD-001` | 5 items (all input types) | Accra farmer, GH₵5,000 |

### Routes
| ID | Stops | Use |
|---|---|---|
| `ROUTE-001` | DEL-001, DEL-002, DEL-003 | Driver map testing |

### Inventory SKUs (warehouse-001)
| SKU | Product | Type | Status |
|---|---|---|---|
| SEED-001 | Wheat Seeds | SEEDS | ok |
| SEED-002 | Paddy Seeds | SEEDS | low_stock |
| FERT-001 | DAP Fertilizer | FERTILIZER_BASAL | ok |
| FERT-002 | Urea | FERTILIZER_TOP_DRESSING | ok |
| FERT-003 | MOP | FERTILIZER_BASAL | low_stock |
| CHEM-001 | Chlorpyrifos Pesticide | CHEMICAL | ok |
| CHEM-002 | Mancozeb Fungicide | CHEMICAL | ok |
| MECH-001 | Knapsack Sprayer | MECHANIZATION | out_of_stock |
| MECH-002 | Harvester Blade Set | MECHANIZATION | ok |

---

## Modifying Mock Data & Credentials

Since the system currently uses the `app_simple.py` mock server, all data is loaded from in-memory Python dictionaries. Here is how to modify them:

### 1. Changing User Logins (Backend)
1. Open `backend/app_simple.py`.
2. Locate the `MOCK_USERS` dictionary near the top of the file.
3. Add, remove, or modify user entries. To change a password, update the `password_hash` using the `_sha("YourPassword")` helper method.
   ```python
   "custom@smarttech.com": {
       "id": "usr-999",
       "name": "Custom User",
       "role": "admin", # Roles: admin, warehouse_mgr, field_agent, supervisor, farmer
       "password_hash": _sha("SecurePass@123")
   }
   ```

### 2. Updating Login UI (Frontend Click-to-Fill)
If you change the dummy credentials on the backend, update the frontend login buttons to match:
1. Open `frontend/login/index.html`.
2. Find the `<div class="demo-accounts">` section towards the bottom.
3. Update the `onclick="fill('email@domain.com','Pass!123')"` arguments for each demo card to match your new emails and passwords.

### 3. Modifying System Data (Orders, Routes, Inventory)
1. Open `backend/app_simple.py`.
2. Locate and modify the relevant mock dictionaries:
   - **`MOCK_WAREHOUSE_INVENTORY`**: Add new item SKUs, adjust current stock counts, or change stock statuses (`ok`, `low_stock`, `out_of_stock`).
   - **`MOCK_PENDING_ORDERS`**: Add new orders, modify farmers, or alter requested SKUs and districts to test the K-Means Regional Batching logic.
   - **`MOCK_ROUTE_STOPS`**: Set up new delivery routes, adjust driver GPS coordinates, or test different route lengths.
   - **`MOCK_ANALYTICS`**: Tweak the hardcoded data structures to change the statistics rendering on the CEO analytics dashboard.
3. **Restart the backend server** (`Ctrl+C` and re-run `python backend/app_simple.py`) for the new dictionary data to take effect.

---

## Running the Tests

```powershell
# Run full test suite (53 tests)
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Run a single test file
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -v

# Run with coverage report
.\.venv\Scripts\python.exe -m pytest tests/ --cov=backend --cov-report=term-missing

# Run a single test by name
.\.venv\Scripts\python.exe -m pytest tests/test_api.py::TestGeofenceEndpoint::test_within_geofence -s
```

### Test Files
| File | What it tests | Count |
|---|---|---|
| `tests/test_api.py` | Auth, delivery, PoD, batching, geofence, dispatch pipeline | 28 |
| `tests/test_batching.py` | K-Means algorithm correctness and edge cases | 16 |
| `tests/test_geofencing.py` | Geofence distance, risk bands, anomaly detection | 9 |

### Auth in Tests
Protected endpoints need a token. Use the `admin_token` fixture from `conftest.py`:
```python
def test_my_endpoint(self, client, admin_token):
    r = client.get('/api/v1/my-endpoint',
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
```

---

## API Quick-Test (curl)

```powershell
# 1. Get a token
$response = Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/v1/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"admin@smarttech.com","password":"Admin@1234"}'
$token = $response.token

# 2. Use the token
Invoke-RestMethod -Uri http://localhost:5000/api/v1/analytics/overview `
  -Headers @{Authorization="Bearer $token"} | ConvertTo-Json -Depth 5

# 3. Test inventory sync
Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/v1/inventory/warehouses/warehouse-001/sync `
  -Headers @{Authorization="Bearer $token"}

# 4. Test geofence (same location = LOW risk)
Invoke-RestMethod -Method Post `
  -Uri http://localhost:5000/api/v1/dispatch/geofence-check `
  -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"farm_latitude":5.6037,"farm_longitude":-0.1870,"delivery_latitude":5.6037,"delivery_longitude":-0.1870}'
```

---

## Project File Structure

```
inputDistribution/
├── backend/
│   ├── app_simple.py          ← PRIMARY DEV SERVER (~1,600 lines, all endpoints here)
│   ├── config.py              ← Environment-driven configuration
│   ├── requirements.txt       ← Python dependencies
│   ├── run.py                 ← Production entry (uses app/__init__.py — currently blocked)
│   └── app/
│       ├── __init__.py        ← Flask app factory (production, uses SQLAlchemy)
│       ├── api/               ← Blueprint route handlers (production)
│       ├── models/__init__.py ← SQLAlchemy ORM models
│       ├── services/
│       │   ├── batching.py            ← K-Means++ clustering (pure stdlib)
│       │   ├── routing.py             ← Nearest Neighbour TSP + 2-OPT
│       │   ├── proof_of_delivery.py   ← PoD creation, SMS, risk assessment
│       │   ├── inventory.py           ← Stock sync, reorder checks
│       │   ├── anomaly_detection.py   ← Geofence, risk scoring
│       │   └── ecosystem_integration.py ← GrowForMe API client
│       └── database/          ← DB utilities
├── frontend/
│   ├── login/index.html       ← Login page (all roles, demo cards)
│   ├── dashboard/
│   │   ├── admin.html         ← Admin: stats + navigation hub
│   │   ├── analytics.html     ← CEO: US-06 analytics charts
│   │   ├── inventory.html     ← Warehouse: US-01/02/03 inventory + batching + RO
│   │   ├── warehouse.html     ← Warehouse: dispatch pipeline + K-Means UI
│   │   ├── driver_map.html    ← Driver: US-04/07 route map + SMS
│   │   ├── field_agent.html   ← Agent: assigned deliveries
│   │   ├── supervisor.html    ← Supervisor: flagged PoD review
│   │   └── farmer.html        ← Farmer: order tracking
│   ├── pod-interface/
│   │   ├── index.html         ← PoD capture form (US-05)
│   │   ├── css/styles.css
│   │   └── js/
│   │       ├── app.js         ← PoD logic: GPS, geofence, submit
│   │       └── signature.js   ← Canvas signature pad
│   └── shared/
│       ├── auth.js            ← JWT helpers: getToken, apiFetch, requireAuth, renderNav
│       └── dashboard.css      ← Shared styles: navbar, stat cards, badges, tables
├── tests/
│   ├── conftest.py            ← Fixtures: app, client, admin_token, sample_deliveries
│   ├── test_api.py            ← 28 integration tests
│   ├── test_batching.py       ← 16 algorithm tests
│   └── test_geofencing.py     ← 9 geofence tests
├── docs/
│   ├── TECH_REQUIREMENTS.md   ← Formal requirements document
│   ├── DEVELOPER_REFERENCE.md ← This file
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── GROWFORME_INTEGRATION.md
└── pytest.ini
```

---

## Key Implementation Notes

### Why `app_simple.py` and not `run.py`?
Python 3.14.3 is incompatible with SQLAlchemy 2.0.23. `run.py` imports `app/__init__.py` which imports SQLAlchemy and crashes on startup. All development happens in `app_simple.py` (pure Flask, no ORM). The `app/` folder is the production target — use it once SQLAlchemy is updated or Python downgraded.

### JWT — No External Library
JWT is implemented using stdlib `hmac` + `hashlib` + `base64`. Format: `header.payload.signature` (URL-safe base64). The `_create_token()` and `_verify_token()` functions are in `app_simple.py`.

### How `auth.js` Works
Every dashboard imports `auth.js` as an ES module:
```javascript
import { requireAuth, renderNav, apiFetch } from '../shared/auth.js';
const user = requireAuth('admin', 'warehouse_mgr'); // redirects to login if wrong role
```
`apiFetch(path, options)` auto-attaches `Authorization: Bearer <token>` to all requests and handles 401 → redirect to login.

### Geofence Field Names
The geofence endpoint uses `farm_latitude`/`farm_longitude` and `delivery_latitude`/`delivery_longitude` — NOT `farmer_latitude`. This is intentional and matches `pod-interface/js/app.js`.

### Google Maps Links
Driver map uses deep links — no API key required:
```
https://www.google.com/maps/dir/?api=1&destination=LAT,LON&travelmode=driving
```
Multi-stop full route uses the waypoints param with all stops concatenated.

### Running the Venv
PowerShell execution policy blocks normal venv activation. Always run Python directly:
```powershell
.\.venv\Scripts\python.exe        # instead of: venv\Scripts\Activate.ps1
```

---

## Environment Variables (`.env`)

Copy `backend/.env.example` to `backend/.env` and set:

```env
JWT_SECRET=your-strong-random-secret-here
JWT_EXPIRY_HOURS=8
DATA_SOURCE=mock

# Set these for live SMS:
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# Set these for live inventory sync:
GROWFORME_API_URL=https://api.growforme.com/v1
GROWFORME_API_KEY=your_api_key

# Set for production DB:
DATABASE_URL=postgresql://user:password@localhost:5432/smarttech
REDIS_URL=redis://localhost:6379/0
```

---

## Common Issues & Fixes

| Symptom | Cause | Fix |
|---|---|---|
| `404 File not found` on `/login/` | HTTP server started from project root, not `frontend/` | Use `--directory frontend` flag: `.\.venv\Scripts\python.exe -m http.server 8000 --directory frontend` |
| `ImportError: cannot import name X from sqlalchemy` | Python 3.14.3 incompatibility | Use `app_simple.py`; don't run `run.py` |
| `401 Unauthorized` on API call | Missing or expired token | Re-login; check `sessionStorage` for `token` key |
| GPS not captured in PoD | Browser requires HTTPS for Geolocation API | Use localhost (allowed) or serve over HTTPS |
| Canvas signature missing | Canvas API not supported | Use Chrome/Firefox; check browser console |
| Frontend JS errors on load | ES module `import` failed | Serve via HTTP server, not `file://` protocol |
| `KeyError` in tests | Auth token not passed to protected endpoint | Add `headers={"Authorization": f"Bearer {admin_token}"}` to test |
| Static files 404 | Wrong relative path | All frontend paths are relative to the file's directory |

---

## Changelog

### April 22, 2026 — Session 2
- Added 7 user story backend endpoints to `app_simple.py`
- Created `analytics.html` — CEO analytics dashboard (US-06)
- Created `inventory.html` — inventory sync + district batching + Release Order UI (US-01/02/03)
- Created `driver_map.html` — mobile driver route map with SMS and navigation (US-04/07)
- Updated `admin.html` — navigation panel + expanded endpoint table
- Updated `field_agent.html` — route map link + bulk SMS button
- Fixed 19 failing tests — added `admin_token` fixture to `conftest.py`; all protected test routes now pass auth header
- **Test count: 53 passing**

### Prior Session — Session 1
- Flask mock backend established (`app_simple.py`)
- JWT auth implemented (stdlib only)
- K-Means++ batching service (`app/services/batching.py`)
- TSP routing service (`app/services/routing.py`)
- Geofence / anomaly detection service (`app/services/anomaly_detection.py`)
- Login page with 5 demo accounts
- Role dashboards: admin, warehouse, field_agent, supervisor, farmer
- PoD interface with GPS, signature canvas, photo upload
- Initial 53-test suite established
