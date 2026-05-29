import os

# Set required environment variables for tests before any backend modules are imported
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret-key-long-enough'
os.environ['ENCRYPTION_KEY'] = 'test-encryption-key-for-fernet'
