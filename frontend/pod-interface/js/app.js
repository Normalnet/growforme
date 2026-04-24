/**
 * SmartTechBuddy Proof of Delivery - Main Application Logic
 */

class ProofOfDeliveryApp {
    constructor() {
        this.apiBaseUrl = this.getApiBaseUrl();
        this.deliveryId = this.getDeliveryIdFromUrl();
        this.signature = null;
        this.photos = [];
        this.itemsVerified = {};
        
        this.init();
    }

    getApiBaseUrl() {
        // Use local API for development if on localhost, else use the deployed Render API
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://localhost:5000/api/v1';
        }
        return 'https://smarttech-simple-api.onrender.com/api/v1';
    }

    getDeliveryIdFromUrl() {
        const params = new URLSearchParams(window.location.search);
        return params.get('delivery_id') || 'TEST-DELIVERY-001';
    }

    async init() {
        try {
            // Initialize components
            this.setupSignatureCapture();
            this.setupEventListeners();
            this.generateDeviceId();
            
            // Load delivery details
            await this.loadDeliveryDetails();
            
            // Get user location (optional on load, user can click button)
            console.log('📍 GPS: Click "Get Current Location" button to capture GPS coordinates');
            
        } catch (error) {
            console.error('Initialize error:', error);
            this.showError('Failed to initialize application');
        }
    }

    setupSignatureCapture() {
        this.signatureCapture = new SignatureCapture('signatureCanvas');
        
        const clearBtn = document.getElementById('clearSignature');
        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.signatureCapture.clear();
            });
        }
    }

    setupEventListeners() {
        // Form submission
        const form = document.getElementById('podForm');
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // Photo upload
        const photoUpload = document.getElementById('photoUpload');
        if (photoUpload) {
            photoUpload.addEventListener('change', (e) => this.handlePhotoUpload(e));
        }

        // Get location button
        const getLocationBtn = document.getElementById('getLocationBtn');
        if (getLocationBtn) {
            getLocationBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.getLocation();
            });
        }

        // Reset button
        const resetBtn = document.getElementById('resetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', (e) => {
                this.signatureCapture.clear();
            });
        }
    }

    generateDeviceId() {
        let deviceId = localStorage.getItem('smarttech_device_id');
        
        if (!deviceId) {
            deviceId = 'DEVICE-' + this.generateUUID().toUpperCase();
            localStorage.setItem('smarttech_device_id', deviceId);
        }
        
        const deviceInput = document.getElementById('deviceID');
        if (deviceInput) {
            deviceInput.value = deviceId;
        }
    }

    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    async loadDeliveryDetails() {
        try {
            const token = localStorage.getItem('auth_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            const response = await fetch(
                `${this.apiBaseUrl}/deliveries/${this.deliveryId}`,
                { 
                    method: 'GET',
                    headers: headers
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const delivery = await response.json();
            
            // Populate delivery information
            document.getElementById('deliveryNumber').textContent = delivery.delivery_number;
            document.getElementById('deliveryID').value = delivery.id;

            // Store farmer location for geofence check after GPS capture
            if (delivery.farmer && delivery.farmer.latitude) {
                this.farmerLocation = {
                    latitude: delivery.farmer.latitude,
                    longitude: delivery.farmer.longitude,
                };
            }

            // Load order items
            await this.loadOrderItems(delivery.order_id);

        } catch (error) {
            console.error('Error loading delivery:', error);
            this.showError('Could not load delivery details');
        }
    }

    async loadOrderItems(orderId) {
        try {
            const token = localStorage.getItem('auth_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(
                `${this.apiBaseUrl}/orders/${orderId}`,
                { 
                    method: 'GET',
                    headers: headers
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const order = await response.json();
            this.renderOrderItems(order.items);

        } catch (error) {
            console.error('Error loading order items:', error);
            const container = document.getElementById('itemsContainer');
            if (container) {
                container.innerHTML = '<p class="error-text">Failed to load order items. Check connection or backend status.</p>';
            }
        }
    }

    renderOrderItems(items) {
        const container = document.getElementById('itemsContainer');
        if (!container) return;

        container.innerHTML = '';

        if (!items || items.length === 0) {
            container.innerHTML = '<p class="loading-text">No items to verify</p>';
            return;
        }

        items.forEach(item => {
            const itemCard = document.createElement('div');
            itemCard.className = 'item-card';
            itemCard.innerHTML = `
                <div class="item-info">
                    <div class="item-name">${item.product_name}</div>
                    <div class="item-details">
                        <span class="item-type">${item.input_type}</span>
                        Qty: ${item.quantity} ${item.unit}
                    </div>
                </div>
                <input type="checkbox" class="item-checkbox" data-item-id="${item.id}" 
                       onchange="app.updateItemVerification(this)">
            `;
            container.appendChild(itemCard);
            
            this.itemsVerified[item.id] = false;
        });
    }

    updateItemVerification(checkbox) {
        const itemId = checkbox.dataset.itemId;
        this.itemsVerified[itemId] = checkbox.checked;
    }

    handlePhotoUpload(event) {
        const files = event.target.files;
        const preview = document.getElementById('photoPreview');
        
        if (!preview) return;

        for (const file of files) {
            if (!file.type.startsWith('image/')) {
                this.showError('Please select valid image files');
                continue;
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                this.photos.push(e.target.result);
                this.renderPhotoPreview();
            };
            reader.readAsDataURL(file);
        }
    }

    renderPhotoPreview() {
        const preview = document.getElementById('photoPreview');
        if (!preview) return;

        preview.innerHTML = '';

        this.photos.forEach((photo, index) => {
            const item = document.createElement('div');
            item.className = 'photo-preview-item';
            item.innerHTML = `
                <img src="${photo}" alt="Photo ${index + 1}">
                <button type="button" class="remove-photo" onclick="app.removePhoto(${index})">
                    ×
                </button>
            `;
            preview.appendChild(item);
        });
    }

    removePhoto(index) {
        this.photos.splice(index, 1);
        this.renderPhotoPreview();
    }

    getLocation() {
        if (!navigator.geolocation) {
            this.showError('Geolocation is not supported by your browser');
            return;
        }

        const button = document.getElementById('getLocationBtn');
        if (button) {
            button.disabled = true;
            button.innerHTML = '⏳ Getting location...';
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude, accuracy } = position.coords;
                
                document.getElementById('latitude').value = latitude.toFixed(6);
                document.getElementById('longitude').value = longitude.toFixed(6);
                document.getElementById('accuracy').value = accuracy.toFixed(2);
                
                if (button) {
                    button.disabled = false;
                    button.innerHTML = '📍 Location Captured ✓';
                }
                
                // Update map
                this.updateMap(latitude, longitude);
                console.log(`✓ GPS Location: ${latitude.toFixed(6)}, ${longitude.toFixed(6)} (±${accuracy.toFixed(0)}m)`);

                // Run real-time geofence check against the registered farm
                this.runGeofenceCheck(latitude, longitude);
            },
            (error) => {
                console.error('Geolocation error:', error);
                
                let errorMsg = 'Could not get location: ';
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMsg += 'Permission denied. Please enable location access in your browser settings.';
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMsg += 'Location information is unavailable.';
                        break;
                    case error.TIMEOUT:
                        errorMsg += 'The request to get user location timed out.';
                        break;
                    default:
                        errorMsg += error.message;
                }
                
                this.showError(errorMsg);
                
                if (button) {
                    button.disabled = false;
                    button.innerHTML = '📍 Get Current Location (Error - Try again)';
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0
            }
        );
    }

    updateMap(lat, lon) {
        // Simple map implementation - you can integrate with actual map library like Leaflet
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            mapContainer.innerHTML = `
                <div style="padding: 10px; text-align: center; height: 100%;">
                    <p>📍 Location: ${lat.toFixed(4)}, ${lon.toFixed(4)}</p>
                    <p style="font-size: 12px; color: #666;">
                        <a href="https://maps.google.com/?q=${lat},${lon}" target="_blank">
                            View on Google Maps
                        </a>
                    </p>
                </div>
            `;
        }
    }

    async runGeofenceCheck(deliveryLat, deliveryLon) {
        /**
         * Call /dispatch/geofence-check to validate the agent is at the right farm.
         * The farm coordinates come from the delivery data loaded at startup.
         */
        if (!this.farmerLocation) return;

        try {
            const token = localStorage.getItem('auth_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${this.apiBaseUrl}/dispatch/geofence-check`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    farm_latitude: this.farmerLocation.latitude,
                    farm_longitude: this.farmerLocation.longitude,
                    delivery_latitude: deliveryLat,
                    delivery_longitude: deliveryLon,
                }),
            });

            if (!response.ok) return;
            const result = await response.json();
            this.renderGeofencePanel(result);
        } catch (err) {
            console.warn('Geofence check failed:', err.message);
        }
    }

    renderGeofencePanel(geo) {
        const panel   = document.getElementById('geofencePanel');
        const badge   = document.getElementById('geofenceBadge');
        const detail  = document.getElementById('geofenceDetail');
        const flagsEl = document.getElementById('geofenceFlags');
        if (!panel) return;

        const riskClass = `risk-${geo.risk_level.toLowerCase()}`;
        const icon = geo.risk_level === 'LOW' ? '✅' :
                     geo.risk_level === 'MEDIUM' ? '⚠️' : '🚨';

        badge.className  = `geofence-badge ${riskClass}`;
        badge.innerHTML  = `${icon} Geofence: ${geo.risk_level} RISK — ${geo.deviation_meters} m from farm`;

        detail.innerHTML = geo.is_within_geofence
            ? `✓ You are within the ${geo.geofence_radius_meters} m geofence of the registered farm.`
            : `✗ You are ${geo.deviation_meters} m from the registered farm (geofence: ${geo.geofence_radius_meters} m).`;

        flagsEl.innerHTML = (geo.flags || []).map(f => `
            <div class="geofence-flag-item severity-${f.severity.toLowerCase()}">
                <span class="flag-icon">${f.severity === 'HIGH' ? '🚨' : '⚠️'}</span>
                <span>${f.message}</span>
            </div>
        `).join('');

        panel.style.display = 'block';
    }

    async handleFormSubmit(event) {
        event.preventDefault();

        // Validate form
        if (!this.validateForm()) {
            return;
        }

        // Collect form data
        const formData = new FormData(document.getElementById('podForm'));
        
        // Add signature
        if (!this.signatureCapture.isEmpty()) {
            formData.append('signature_data', this.signatureCapture.getData());
        } else {
            this.showError('Signature is required');
            return;
        }

        // Add photos
        if (this.photos.length > 0) {
            formData.append('photos', JSON.stringify(this.photos));
        }

        // Add verified items
        formData.append('items_verified', JSON.stringify(this.itemsVerified));

        // Submit
        await this.submitPoD(formData);
    }

    validateForm() {
        const farmerName = document.getElementById('farmerName').value.trim();
        const farmerPhone = document.getElementById('farmerPhone').value.trim();
        const condition = document.getElementById('deliveryCondition').value;
        const latitude = document.getElementById('latitude').value;
        const longitude = document.getElementById('longitude').value;

        if (!farmerName) {
            this.showError('Farmer name is required');
            return false;
        }

        if (!farmerPhone) {
            this.showError('Farmer phone is required');
            return false;
        }

        if (!condition) {
            this.showError('Delivery condition is required');
            return false;
        }

        if (!latitude || !longitude) {
            this.showError('Location is required. Please get your location.');
            return false;
        }

        if (this.signatureCapture.isEmpty()) {
            this.showError('Signature is required');
            return false;
        }

        return true;
    }

    async submitPoD(formData) {
        const submitBtn = document.querySelector('#submitBtn');
        const originalText = submitBtn.innerText;
        
        try {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';

            const deliveryId = document.getElementById('deliveryID').value;
            
            const token = localStorage.getItem('auth_token');
            const headers = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(
                `${this.apiBaseUrl}/proof-of-delivery/${deliveryId}`,
                {
                    method: 'POST',
                    headers: headers,
                    body: formData
                }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to submit PoD');
            }

            const result = await response.json();

            // Show risk assessment summary
            this.renderRiskSummary(result);

            // Show success message
            this.showSuccess('Proof of Delivery submitted successfully!');

            // Reset form
            setTimeout(() => {
                document.getElementById('podForm').reset();
                this.signatureCapture.clear();
                this.photos = [];
                this.renderPhotoPreview();
            }, 3000);

        } catch (error) {
            console.error('Submit error:', error);
            this.showError(error.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = originalText;
        }
    }

    renderRiskSummary(result) {
        const el = document.getElementById('riskSummary');
        if (!el || !result.risk_assessment) return;

        const ra  = result.risk_assessment;
        const riskClass = `risk-${ra.risk_level.toLowerCase()}`;
        const icon = ra.risk_level === 'LOW' ? '✅' : ra.risk_level === 'MEDIUM' ? '⚠️' : '🚨';
        const mp  = result.monitoring_push || {};

        const flagHtml = (ra.flags || []).map(f => `
            <div class="geofence-flag-item severity-${f.severity.toLowerCase()}">
                <span class="flag-icon">${f.severity === 'HIGH' ? '🚨' : '⚠️'}</span>
                <span>${f.message}</span>
            </div>
        `).join('');

        el.innerHTML = `
            <div class="risk-summary-header ${riskClass}">
                ${icon} Delivery Risk Level: ${ra.risk_level}
                ${ra.requires_review ? ' — <em>Queued for supervisor review</em>' : ''}
                ${ra.auto_approved   ? ' — <em>Auto-approved</em>' : ''}
            </div>
            <div class="risk-summary-body">
                <div class="risk-summary-row">
                    <span class="risk-label">PoD ID</span>
                    <span class="risk-value">${result.pod_id}</span>
                </div>
                <div class="risk-summary-row">
                    <span class="risk-label">GPS Deviation</span>
                    <span class="risk-value">${ra.gps_deviation_meters != null ? ra.gps_deviation_meters + ' m' : 'N/A'}</span>
                </div>
                <div class="risk-summary-row">
                    <span class="risk-label">Within Geofence (50 m)</span>
                    <span class="risk-value">${ra.is_within_geofence ? '✅ Yes' : '❌ No'}</span>
                </div>
                <div class="risk-summary-row">
                    <span class="risk-label">SMS Sent</span>
                    <span class="risk-value">${result.sms_alert_sent ? '✅ ' + result.farmer_phone : '❌ Not sent'}</span>
                </div>
                <div class="risk-summary-row">
                    <span class="risk-label">Growth Tracking</span>
                    <span class="risk-value">${mp.growth_tracking_initiated ? '✅ Initiated' : '⏳ Pending'}</span>
                </div>
            </div>
            ${flagHtml ? `<div class="geofence-flags">${flagHtml}</div>` : ''}
        `;
        el.style.display = 'block';
    }

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        const errorText = document.getElementById('errorText');
        
        if (errorDiv && errorText) {
            errorText.innerText = message;
            errorDiv.style.display = 'block';
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }

    showSuccess(message) {
        const successDiv = document.getElementById('successMessage');
        
        if (successDiv) {
            successDiv.innerHTML = `<strong>✓ Success!</strong> ${message}`;
            successDiv.style.display = 'block';
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                successDiv.style.display = 'none';
            }, 5000);
        }
    }
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new ProofOfDeliveryApp();
});
