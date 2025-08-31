# shared/db.py
import os
import logging
from contextlib import contextmanager
from psycopg2 import pool
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Connection Pool Initialization ---
connection_pool = None

def init_pool():
    """Initializes the database connection pool."""
    global connection_pool
    if connection_pool is None:
        try:
            logging.info("Initializing database connection pool...")
            connection_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dbname=os.environ.get('POSTGRES_DB'),
                user=os.environ.get('POSTGRES_USER'),
                password=os.environ.get('POSTGRES_PASSWORD'),
                host=os.environ.get('POSTGRES_HOST', 'localhost'),
                port=os.environ.get('POSTGRES_PORT')
            )
            logging.info("Database connection pool initialized successfully.")
        except Exception as e:
            logging.exception("Failed to initialize database connection pool.")
            raise e

def close_pool():
    """Closes all connections in the pool."""
    global connection_pool
    if connection_pool:
        logging.info("Closing database connection pool.")
        connection_pool.closeall()
        connection_pool = None

@contextmanager
def get_db_cursor(commit=False):
    """
    Provides a database cursor from the connection pool. This context manager
    handles connection borrowing, returning, and transaction logic automatically.
    """
    if not connection_pool:
        init_pool()

    conn = None
    try:
        conn = connection_pool.getconn()
        with conn.cursor() as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logging.exception("Database transaction failed.")
        raise e
    finally:
        if conn:
            connection_pool.putconn(conn)
