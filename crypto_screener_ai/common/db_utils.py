import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file, if it exists.
# This should be called as early as possible.
load_dotenv()

DB_AVAILABLE = True
try:
    import psycopg2
except ImportError:
    DB_AVAILABLE = False
    # Mock psycopg2 for environments where it's not installed, allowing script to be parsed
    # This helps in environments where DB operations are not intended or possible.
    class psycopg2:
        @staticmethod
        def connect(*args, **kwargs):
            raise ImportError("psycopg2-binary not installed. DB operations are not available.")
        class Error(Exception): # Base error class for psycopg2
            pass
    print("Warning: psycopg2-binary not installed. Database utility functions will not operate correctly.")


def get_db_connection(db_host=None, db_port=None, db_user=None, db_password=None, db_name=None):
    """
    Establishes a connection to the PostgreSQL database.
    Uses environment variables as fallback if specific parameters are not provided.
    """
    if not DB_AVAILABLE:
        print("Database operations unavailable: psycopg2-binary is not installed.")
        return None

    # Example of using environment variables (can be expanded)
    # For now, direct parameters are prioritized as per existing script structure.
    # db_host = db_host or os.getenv('DB_HOST', 'localhost')
    # db_port = db_port or os.getenv('DB_PORT', '5432')
    # db_user = db_user or os.getenv('DB_USER', 'postgres')
    # db_password = db_password # Password should ideally be passed directly or via secure means
    # db_name = db_name or os.getenv('DB_NAME', 'crypto_data')

    if not all([db_host, db_port, db_user, db_password, db_name]):
        print("Error: Database connection parameters (host, port, user, password, name) must all be provided.")
        # This check might be too strict if some parameters have valid defaults elsewhere or from env.
        # However, aligning with current script requiring explicit password.
        return None

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            dbname=db_name
        )
        # print(f"Database connection successful to '{db_name}' on {db_host}:{db_port}") # Optional: for debugging
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL database '{db_name}' on {db_host}:{db_port}: {e}")
        return None

def get_asset_id(conn, symbol: str) -> int | None:
    """
    Retrieves asset_id from the 'assets' table for a given symbol.
    """
    if not DB_AVAILABLE: # Should not happen if conn is valid, but good check
        print("psycopg2-binary not installed. Cannot perform get_asset_id.")
        return None
    if conn is None:
        print("Database connection is not available for get_asset_id.")
        return None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT asset_id FROM assets WHERE symbol = %s;", (symbol,))
            result = cur.fetchone()
            if result:
                return result[0]
            else:
                # print(f"Asset with symbol '{symbol}' not found.") # Optional debug
                return None
    except psycopg2.Error as e:
        print(f"Database error while fetching asset_id for symbol '{symbol}': {e}")
        # It's good practice to rollback if an error occurs during a transaction,
        # though a SELECT query alone doesn't typically start a transaction that needs rollback.
        # However, if the connection is in an error state, future operations might fail.
        # For a simple SELECT, often just returning None is enough.
        # conn.rollback() # Optional, depending on broader transaction strategy
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_asset_id for symbol '{symbol}': {e}")
        return None

# __init__.py file for the 'common' package
# This allows 'common' to be treated as a package, enabling imports like:
# from crypto_screener_ai.common.db_utils import ...
# or from ..common.db_utils import ... (if scripts are run as modules)

# To make the directory a package, create an empty __init__.py file in it.
# This will be done as a separate step if 'create_file_with_block' cannot create it
# with just a comment, or if this file itself should be __init__.py.
# For now, this file is db_utils.py.
# An __init__.py in crypto_screener_ai/common/ would be:
# crypto_screener_ai/common/__init__.py (can be empty)
