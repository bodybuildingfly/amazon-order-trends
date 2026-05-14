import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default-secret-key-for-dev-and-testing-purposes-only'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'default-secret-key-for-dev-and-testing-purposes-only'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_TOKEN_LOCATION = ["headers", "query_string"]
    JWT_QUERY_STRING_NAME = "token"
    
    # Custom config
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    FLASK_ENV = 'production'
    # Use the environment variables directly, without falling back to defaults in production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')

# Ensure required secrets are set for production environments
if os.environ.get('FLASK_ENV') == 'production':
    if not os.environ.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY environment variable is required in production.")
    if not os.environ.get('JWT_SECRET_KEY'):
        raise ValueError("JWT_SECRET_KEY environment variable is required in production.")
    if not os.environ.get('ENCRYPTION_KEY'):
        raise ValueError("ENCRYPTION_KEY environment variable is required in production.")

# Dictionary to access config classes by name
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
