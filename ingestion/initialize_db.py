# ingestion/initialize_db.py
import os
import sys
import logging

# Add the project root to the Python path to allow importing from 'shared'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import get_db_cursor

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_tables():
    """
    Reads the schema.sql file and executes it against the database
    to create the necessary application tables.
    """
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    
    if not os.path.exists(schema_path):
        logging.error(f"Schema file not found at: {schema_path}")
        return

    logging.info("Connecting to the database to initialize schema...")
    
    try:
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        with get_db_cursor(commit=True) as cur:
            logging.info("Executing schema.sql...")
            cur.execute(schema_sql)
            logging.info("Tables created successfully (if they didn't already exist).")
        
        logging.info("Database initialization complete.")

    except Exception as e:
        logging.exception("An error occurred during database initialization.")

if __name__ == "__main__":
    create_tables()
