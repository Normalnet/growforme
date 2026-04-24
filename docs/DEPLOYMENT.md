# Deployment Guide - SmartTechBuddy Input Distribution

## Table of Contents

1. [Free Demonstration Deployment (Recommended for Quick Previews)](#free-demonstration-deployment)
2. [Development Deployment](#development-deployment)
3. [Production Deployment (VPS/Ubuntu)](#production-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Monitoring & Logging](#monitoring--logging)

---

## Free Demonstration Deployment

Since you have already pushed your code to GitHub, the easiest way to host this system for free is to split the architecture across modern serverless/PaaS platforms. 

**Recommended Free Stack:**
- **Frontend**: Vercel (or Netlify/GitHub Pages)
- **Backend API**: Render.com (Free Web Service)
- **Database**: Neon.tech (Free Serverless PostgreSQL)
- **Redis Cache**: Upstash.com (Free Serverless Redis)

### Step 1: Database Setup (Neon.tech)
1. Go to [Neon.tech](https://neon.tech) and create a free account.
2. Create a new Postgres project.
3. Once created, copy the connection string (it looks like `postgres://user:password@ep-something.pooler.supabase.com/neondb`).
4. Keep this URL handy for the Backend deployment.

### Step 2: Redis Setup (Upstash)
1. Go to [Upstash.com](https://upstash.com) and create a free account.
2. Create a new Redis Database.
3. Once created, scroll down to the **Connect** section and copy the `Redis URL` (looks like `rediss://default:password@endpoint.upstash.io:6379`).

### Step 3: Backend Deployment (Render.com)
1. Go to [Render.com](https://render.com) and sign in with GitHub.
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.
4. Configure the Web Service:
   - **Name**: `smarttech-backend`
   - **Root Directory**: `backend` (Important!)
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"`
   - **Instance Type**: Free Plan
5. Expand **Advanced** / **Environment Variables** and add:
   - `DATABASE_URL`: *(Paste the Neon Postgres URL here)*
   - `REDIS_URL`: *(Paste the Upstash URL here)*
   - `SECRET_KEY`: *(Generate a random string)*
   - `CORS_ORIGINS`: `*` *(We will restrict this later to your Vercel URL)*
6. Click **Create Web Service**. Render will now build and deploy your API.
7. Copy the deployed API URL (e.g., `https://smarttech-backend.onrender.com`).

*(Note: The Render free tier sleeps after 15 minutes of inactivity. First requests after sleeping may take ~50 seconds to spin up).*

### Step 4: Link Frontend to Backend
1. In your local code, go to `frontend/pod-interface/js/app.js` and any other frontend JS files (like `frontend/shared/auth.js`).
2. Find the API base URL (usually `http://localhost:5000/api/v1`).
3. Change it to your new Render Backend URL (e.g., `https://smarttech-backend.onrender.com/api/v1`).
4. Commit and push this change to GitHub.

```javascript
// Example in frontend/pod-interface/js/app.js
const API_BASE_URL = 'https://smarttech-backend.onrender.com/api/v1';
```

### Step 5: Frontend Deployment (Vercel)
1. Go to [Vercel.com](https://vercel.com) and log in with GitHub.
2. Click **Add New** -> **Project**.
3. Import your GitHub repository.
4. Configure Project:
   - **Framework Preset**: Other / Vanilla
   - **Root Directory**: `frontend` (Click edit and select the `frontend` folder).
5. Click **Deploy**. Vercel will instantly host your HTML/CSS/JS.

### Final Verification
1. Visit your Vercel URL (e.g., `https://inputdistribution.vercel.app`).
2. Ensure you enable CORS in your backend codebase so Vercel can communicate with Render. Update `backend/app/__init__.py` to allow origins or configure it via the `.env` variables if supported.

---

## Development Deployment

### Local Setup (Windows/macOS/Linux)

#### 1. Clone Repository
```bash
git clone https://github.com/growforme/input-distribution.git
cd inputDistribution/backend
```

#### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

`.env` file should contain:
```env
FLASK_ENV=development
DATABASE_URL=postgresql://postgres:password@localhost:5432/smarttech_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-development-secret-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
```

#### 5. Initialize Database
```bash
python
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

#### 6. Run Development Server
```bash
python run.py
```

Server runs on `http://localhost:5000/api/v1`

#### 7. Frontend Development
```bash
cd ../frontend/pod-interface
# Option 1: Direct browser
open index.html

# Option 2: Local server
python -m http.server 8000
# Access at http://localhost:8000
```

---

## Production Deployment

### Prerequisites

- Ubuntu 20.04 LTS or higher
- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Nginx or Apache
- SSL Certificate (Let's Encrypt recommended)

### 1. Server Setup

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.9 python3.9-venv python3-pip
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y redis-server
sudo apt install -y npm
sudo apt install -y nginx
sudo apt install -y certbot python3-certbot-nginx
```

### 2. PostgreSQL Setup

```bash
# Create database
sudo -u postgres createdb smarttech_prod

# Create user
sudo -u postgres psql
CREATE USER smarttech_user WITH PASSWORD 'secure_password';
ALTER ROLE smarttech_user SET client_encoding TO 'utf8';
ALTER ROLE smarttech_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE smarttech_user SET default_transaction_deferrable TO on;
ALTER ROLE smarttech_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE smarttech_prod TO smarttech_user;
\q

# Enable PostgreSQL to start on boot
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 3. Application Deployment

```bash
# Create application directory
sudo mkdir -p /var/www/smarttech
sudo chown $USER:$USER /var/www/smarttech
cd /var/www/smarttech

# Clone repository
git clone https://github.com/growforme/input-distribution.git .

# Create virtual environment
python3.9 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
pip install gunicorn

# Create production .env
cat > backend/.env << EOF
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://smarttech_user:secure_password@localhost:5432/smarttech_prod
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=https://yourdomain.com
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890
INPUT_ACQUISITION_API_URL=https://api.input-acquisition.com
INPUT_ACQUISITION_API_KEY=your-api-key
UPLOAD_FOLDER=/var/www/smarttech/uploads
EOF

# Initialize database
cd backend
python << PYEOF
from app import create_app, db
app = create_app('production')
with app.app_context():
    db.create_all()
PYEOF

cd ..
```

### 4. Systemd Service

Create `/etc/systemd/system/smarttech.service`:

```ini
[Unit]
Description=SmartTechBuddy Input Distribution
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/smarttech/backend
ExecStart=/var/www/smarttech/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app('production')"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smarttech
sudo systemctl start smarttech
sudo systemctl status smarttech
```

### 5. Nginx Configuration

Create `/etc/nginx/sites-available/smarttech`:

```nginx
upstream smarttech {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Logging
    access_log /var/log/nginx/smarttech_access.log;
    error_log /var/log/nginx/smarttech_error.log;
    
    # Max upload size
    client_max_body_size 50M;
    
    # API endpoints
    location /api/ {
        proxy_pass http://smarttech;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
    
    # Frontend
    location / {
        root /var/www/smarttech/frontend/pod-interface;
        try_files $uri $uri/ /index.html;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Uploads
    location /uploads/ {
        alias /var/www/smarttech/uploads/;
        expires 90d;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/smarttech /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. SSL Certificate

```bash
# Get certificate
sudo certbot certonly --nginx -d yourdomain.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 7. Firewall Configuration

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Docker Deployment

### 1. Create Dockerfile

`backend/Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy application
COPY . .

# Create upload directory
RUN mkdir -p uploads

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:create_app('production')"]
```

### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: smarttech_db
      POSTGRES_USER: smarttech_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - smarttech
    ports:
      - "5432:5432"

  # Redis Cache
  redis:
    image: redis:7-alpine
    networks:
      - smarttech
    ports:
      - "6379:6379"

  # Flask API
  api:
    build: ./backend
    environment:
      FLASK_ENV: production
      DATABASE_URL: postgresql://smarttech_user:secure_password@db:5432/smarttech_db
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: your-secret-key
      TWILIO_ACCOUNT_SID: your-twilio-sid
      TWILIO_AUTH_TOKEN: your-twilio-token
    depends_on:
      - db
      - redis
    networks:
      - smarttech
    ports:
      - "5000:5000"
    volumes:
      - ./backend/uploads:/app/uploads

  # Nginx Reverse Proxy
  nginx:
    image: nginx:latest
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./frontend/pod-interface:/usr/share/nginx/html:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    networks:
      - smarttech

volumes:
  postgres_data:

networks:
  smarttech:
    driver: bridge
```

### 3. Deploy with Docker

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

---

## Configuration

### Environment Variables

```env
# Core
FLASK_ENV=production
SECRET_KEY=<32-char-random-string>

# Database
DATABASE_URL=postgresql://user:password@host:5432/db

# Redis
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=https://yourdomain.com

# Twilio
TWILIO_ACCOUNT_SID=<your-sid>
TWILIO_AUTH_TOKEN=<your-token>
TWILIO_PHONE_NUMBER=+1234567890

# Input Acquisition API
INPUT_ACQUISITION_API_URL=https://api.input-acquisition.com
INPUT_ACQUISITION_API_KEY=<your-api-key>

# File Upload
UPLOAD_FOLDER=/var/www/smarttech/uploads
MAX_CONTENT_LENGTH=52428800  # 50MB
```

### Database Backups

```bash
# Backup
pg_dump smarttech_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
psql smarttech_prod < backup_file.sql

# Automated backups with cron
0 2 * * * pg_dump smarttech_prod > /backups/db_$(date +\%Y\%m\%d).sql
```

---

## Monitoring & Logging

### Application Logs

```bash
# Systemd logs
sudo journalctl -u smarttech -f

# Docker logs
docker-compose logs -f api

# Nginx logs
sudo tail -f /var/log/nginx/smarttech_error.log
```

### Health Checks

```bash
# API health
curl https://yourdomain.com/api/v1/health

# System status
curl https://yourdomain.com/api/v1/status

# Version
curl https://yourdomain.com/api/v1/version
```

### Performance Monitoring

```bash
# Database connections
sudo -u postgres psql -d smarttech_prod -c "SELECT * FROM pg_stat_activity;"

# Slow queries
# Enable in PostgreSQL and check logs

# Redis info
redis-cli info
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check status
sudo systemctl status smarttech

# View logs
sudo journalctl -u smarttech -n 50

# Test configuration
cd /var/www/smarttech/backend
python -c "from app import create_app; app = create_app()"
```

### Database Connection Error

```bash
# Test connection
psql postgresql://smarttech_user:password@localhost:5432/smarttech_prod

# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check database exists
sudo -u postgres psql -l | grep smarttech
```

### Nginx 502 Bad Gateway

```bash
# Verify API is running
curl localhost:5000

# Check Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### High Memory Usage

```bash
# Monitor processes
htop

# Check Python processes
ps aux | grep python

# Restart service
sudo systemctl restart smarttech
```

---

## Security Best Practices

✅ **Implemented**
- [x] HTTPS/SSL encryption
- [x] SQL injection prevention (ORM)
- [x] CORS configuration
- [x] Environment variable protection
- [x] Firewall rules

✅ **Recommended**
- [ ] Regular security audits
- [ ] Dependency vulnerability scanning
- [ ] Database encryption
- [ ] API rate limiting
- [ ] Two-factor authentication
- [ ] Audit logging
- [ ] DDoS protection

---

## Scaling Considerations

- **Horizontal**: Add more API instances behind load balancer
- **Vertical**: Increase server resources (CPU, RAM)
- **Database**: Enable read replicas, partitioning
- **Caching**: Leverage Redis more aggressively
- **CDN**: Use CloudFlare for static assets

---

**Last Updated**: April 16, 2026  
**Version**: 1.0.0
