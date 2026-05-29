import os
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
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

# Fail-fast for missing secrets in all environments
missing_secrets = []
if not os.environ.get('SECRET_KEY'):
    missing_secrets.append("SECRET_KEY")
if not os.environ.get('JWT_SECRET_KEY'):
    missing_secrets.append("JWT_SECRET_KEY")
if not os.environ.get('ENCRYPTION_KEY'):
    missing_secrets.append("ENCRYPTION_KEY")

if missing_secrets:
    error_msg = f"Missing required environment variables: {', '.join(missing_secrets)}. Application cannot start securely."
    logger.error(error_msg)
    raise ValueError(error_msg)

# Dictionary to access config classes by name
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
