import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Support both PostgreSQL and SQLite
    db_url = os.getenv('DATABASE_URL', 'sqlite:///smarttech_dev.db')
    if not db_url:
        db_url = 'sqlite:///smarttech_dev.db'
    
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # API Configuration
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    # Celery Configuration
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    
    # Twilio SMS Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Routing Algorithm Configuration
    MAX_ORDERS_PER_BATCH = 50
    OPTIMAL_ROUTE_DISTANCE_KM = 100
    MAX_DELIVERY_STOPS_PER_ROUTE = 30
    
    # File Upload
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'gif'}
    
    # GrowForMe Integration Configuration
    DATA_SOURCE = os.getenv('DATA_SOURCE', 'mock')  # 'mock' or 'growforme_api'
    GROWFORME_API_URL = os.getenv('GROWFORME_API_URL', '')
    GROWFORME_API_KEY = os.getenv('GROWFORME_API_KEY', '')
    GROWFORME_DATABASE_URL = os.getenv('GROWFORME_DATABASE_URL', '')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost:5432/smarttech_input_test'
    REDIS_URL = 'redis://localhost:6379/1'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
