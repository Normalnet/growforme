/**
 * Signature Capture Handler
 * Handles digital signature drawing and conversion
 */

class SignatureCapture {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.isDrawing = false;
        this.lastX = 0;
        this.lastY = 0;
        this.isTouch = false;
        
        this.setupCanvas();
        this.setupEventListeners();
    }

    setupCanvas() {
        // Set canvas size to match display size
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        // Set drawing context
        this.ctx.strokeStyle = '#333';
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
    }

    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e, false));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e, false));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseout', () => this.stopDrawing());

        // Touch events
        this.canvas.addEventListener('touchstart', (e) => this.startDrawing(e, true));
        this.canvas.addEventListener('touchmove', (e) => this.draw(e, true));
        this.canvas.addEventListener('touchend', () => this.stopDrawing());
        this.canvas.addEventListener('touchcancel', () => this.stopDrawing());
    }

    getCoordinates(e, isTouch) {
        const rect = this.canvas.getBoundingClientRect();
        
        if (isTouch) {
            const touch = e.touches[0];
            return {
                x: touch.clientX - rect.left,
                y: touch.clientY - rect.top
            };
        } else {
            return {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top
            };
        }
    }

    startDrawing(e, isTouch) {
        e.preventDefault();
        this.isDrawing = true;
        this.isTouch = isTouch;
        
        const coords = this.getCoordinates(e, isTouch);
        this.lastX = coords.x;
        this.lastY = coords.y;
    }

    draw(e, isTouch) {
        if (!this.isDrawing) return;
        
        e.preventDefault();
        
        const coords = this.getCoordinates(e, isTouch);
        
        // Draw line from last point to current point
        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(coords.x, coords.y);
        this.ctx.stroke();
        
        this.lastX = coords.x;
        this.lastY = coords.y;
    }

    stopDrawing() {
        this.isDrawing = false;
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    getData() {
        // Return canvas as base64 data URL
        return this.canvas.toDataURL('image/png');
    }

    isEmpty() {
        // Check if canvas has any drawn content
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] > 1) { // If alpha channel is not 0
                return false;
            }
        }
        
        return true;
    }
}

// Export for use in app
window.SignatureCapture = SignatureCapture;
