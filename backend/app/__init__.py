"""
Flask Application Factory
"""

import os
from flask import Flask
from flask_cors import CORS
from config import config
from app.models import db
import logging

def create_app(config_name=None):
    """
    Create and configure Flask application.
    
    Args:
        config_name: Configuration name ('development', 'production', 'testing')
    
    Returns:
        Flask application instance
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Register blueprints
    from app.api.inventory import inventory_bp
    from app.api.orders import orders_bp
    from app.api.batching import batching_bp
    from app.api.delivery import delivery_bp
    from app.api.proof_of_delivery import pod_bp
    from app.api.health import health_bp
    from app.api.dispatch import dispatch_bp

    app.register_blueprint(health_bp, url_prefix='/api/v1')
    app.register_blueprint(inventory_bp, url_prefix='/api/v1')
    app.register_blueprint(orders_bp, url_prefix='/api/v1')
    app.register_blueprint(batching_bp, url_prefix='/api/v1')
    app.register_blueprint(delivery_bp, url_prefix='/api/v1')
    app.register_blueprint(pod_bp, url_prefix='/api/v1')
    app.register_blueprint(dispatch_bp, url_prefix='/api/v1/dispatch')
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create database tables on app context
    with app.app_context():
        db.create_all()
    
    return app
