"""
Flask Application Entry Point
"""

import os
from app import create_app

# Create Flask app instance
app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    debug = os.getenv('FLASK_ENV') == 'development'
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    app.run(host=host, port=port, debug=debug)
