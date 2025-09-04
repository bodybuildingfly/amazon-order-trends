import os
import base64
import hashlib
from cryptography.fernet import Fernet

fernet = None

def initialize_fernet(app):
    """Initializes the Fernet instance from the app's configuration."""
    global fernet
    encryption_key = app.config.get('ENCRYPTION_KEY')
    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set in the application configuration.")
    
    key_digest = hashlib.sha256(encryption_key.encode('utf-8')).digest()
    derived_key = base64.urlsafe_b64encode(key_digest)
    fernet = Fernet(derived_key)

def get_fernet():
    """Returns the initialized Fernet instance."""
    if fernet is None:
        # This is a fallback, but initialize_fernet should be called at app startup.
        raise RuntimeError("Fernet has not been initialized. Call initialize_fernet(app) first.")
    return fernet
