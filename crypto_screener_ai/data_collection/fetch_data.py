import requests
import json
import datetime
import argparse
import os
import sys

# Add project root to sys.path to allow absolute imports like crypto_screener_ai.common
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv() # Load .env file for environment variables

# Attempt to import database and Binance libraries
try:
    import psycopg2
    import psycopg2.extras
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    # Mock psycopg2 for environments where it's not installed, allowing script to be parsed
    class psycopg2:
        @staticmethod
        def connect(*args, **kwargs): raise ImportError("psycopg2-binary not installed")
        class extras:
            @staticmethod
            def execute_values(*args, **kwargs): raise ImportError("psycopg2-binary not installed")
    print("Warning: psycopg2-binary not installed. Database operations will not be available.")

# Import from common utility
from crypto_screener_ai.common.db_utils import get_db_connection

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    class BinanceAPIException(Exception): pass
    class Client: pass
    print("Warning: python-binance not installed. Binance data fetching will not be available.")

# Placeholder for user to add their Binance API keys
# Global BINANCE_API_KEY and BINANCE_API_SECRET placeholders are removed.
# They will be resolved in main from CLI args or .env.


# Removed local get_db_connection function, will use imported one

def ensure_asset_exists(conn, symbol: str, name: str, source: str) -> int | None:
    """
    Ensures an asset exists in the 'assets' table and returns its asset_id.
    If 'name' is None, it will use the symbol as the name.
    """
    asset_name = name if name else symbol
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO assets (symbol, name, source)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, assets.name),
                    source = COALESCE(EXCLUDED.source, assets.source)
                RETURNING asset_id;
                """,
                (symbol, asset_name, source)
            )
            asset_id = cur.fetchone()[0]
            conn.commit()
            print(f"Ensured asset '{symbol}' (ID: {asset_id}) exists in the database.")
            return asset_id
    except psycopg2.Error as e:
        print(f"Error ensuring asset '{symbol}' exists: {e}")
        conn.rollback()
        return None
    except Exception as e:
        print(f"A non-psycopg2 error occurred in ensure_asset_exists: {e}")
        conn.rollback()
        return None


def insert_price_data(conn, asset_id: int, price_data_list: list):
    """
    Inserts a list of price data records into the 'price_data' table.
    price_data_list should be a list of dicts, each with 'timestamp', 'close',
    and optional 'open', 'high', 'low', 'volume'.
    """
    if not price_data_list:
        print("No price data to insert.")
        return False

    # Transform list of dicts into list of tuples for execute_values
    # (time, asset_id, open, high, low, close, volume)
    records_to_insert = []
    for record in price_data_list:
        records_to_insert.append((
            record['timestamp'],
            asset_id,
            record.get('open'), # Will be None if not present
            record.get('high'),
            record.get('low'),
            record['close'],    # Close is mandatory
            record.get('volume')
        ))

    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO price_data (time, asset_id, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (asset_id, time) DO NOTHING;
                """,
                records_to_insert
            )
            conn.commit()
            print(f"Successfully inserted/updated {len(records_to_insert)} price data records for asset ID {asset_id}.")
            return True
    except psycopg2.Error as e:
        print(f"Error inserting price data for asset ID {asset_id}: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"A non-psycopg2 error occurred in insert_price_data: {e}")
        conn.rollback()
        return False


def get_coingecko_data(coin_id: str, vs_currency: str, days: int):
    """Fetches historical market data for a specific coin from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency={vs_currency}&days={days}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        prices = data.get('prices', [])
        # Format for database insertion: list of dicts
        # {'timestamp': iso_timestamp_str, 'close': float_val}
        # Other OHLCV fields will be NULL for CoinGecko data.
        formatted_data = []
        for timestamp_ms, price in prices:
            timestamp_s = timestamp_ms / 1000
            dt_object = datetime.datetime.fromtimestamp(timestamp_s, tz=datetime.timezone.utc)
            iso_format = dt_object.isoformat()
            formatted_data.append({'timestamp': iso_format, 'close': price, 'open': None, 'high': None, 'low': None, 'volume': None})
        return formatted_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from CoinGecko: {e}")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON response from CoinGecko.")
        return None

def get_binance_data(api_key: str, api_secret: str, symbol: str, interval: str, start_str: str = None, end_str: str = None, limit: int = 500):
    """Fetches historical klines (OHLCV) data from Binance."""
    if not BINANCE_AVAILABLE:
        print("Binance library not installed. Please install 'python-binance' to use this feature.")
        return None

    # Check if the current API keys are the default placeholders from os.getenv
    is_using_placeholders = (
        api_key == "YOUR_BINANCE_API_KEY_PLACEHOLDER" or
        api_secret == "YOUR_BINANCE_API_SECRET_PLACEHOLDER"
    )

    if is_using_placeholders:
        print("Warning: Using SCRIPT DEFAULT placeholder Binance API keys. "
              "Please set your actual BINANCE_API_KEY and BINANCE_API_SECRET in a .env file or as environment variables.")

    # For testing purposes, to confirm .env was read (this part can be removed later)
    # if api_key == "key_from_dotenv_test":
    #     print("--- [Internal Test Log] Successfully loaded API key from .env file for testing. ---")


    client = Client(api_key, api_secret)
    try:
        if start_str:
            klines = client.get_historical_klines(symbol, interval, start_str=start_str, end_str=end_str)
        else:
            klines = client.get_historical_klines(symbol, interval, limit=limit)

        # Format for database insertion: list of dicts
        formatted_data = []
        for kline in klines:
            timestamp_s = kline[0] / 1000
            dt_object = datetime.datetime.fromtimestamp(timestamp_s, tz=datetime.timezone.utc)
            iso_format = dt_object.isoformat()
            formatted_data.append({
                'timestamp': iso_format,
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5])
            })
        return formatted_data
    except BinanceAPIException as e:
        print(f"Error fetching data from Binance: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred with Binance client: {e}")
        return None

def save_data_to_json(data: list, filename: str, directory: str):
    """Saves data (list of dicts) to a JSON file in the specified directory."""
    if not data:
        print("No data provided to save to JSON.")
        return

    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"Created directory: {directory}")
        except OSError as e:
            print(f"Error creating directory {directory}: {e}")
            return

    filepath = os.path.join(directory, filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Data successfully saved to {filepath}")
    except IOError as e:
        print(f"Error saving data to JSON file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch cryptocurrency data and optionally save to DB and/or JSON.")

    # Data source arguments
    parser.add_argument('source', choices=['coingecko', 'binance'], help="Data source")
    parser.add_argument('--output_dir', type=str, default='crypto_screener_ai/data_collection/', help="Directory to save JSON files.")

    # CoinGecko specific
    parser.add_argument('--coin_id', type=str, help="Coin ID for CoinGecko (e.g., 'bitcoin')")
    parser.add_argument('--vs_currency', type=str, help="Currency for CoinGecko (e.g., 'usd')")
    parser.add_argument('--days', type=int, help="Number of days for CoinGecko")

    # Binance specific
    parser.add_argument('--symbol', type=str, help="Trading symbol for Binance (e.g., 'BTCUSDT')")
    parser.add_argument('--interval', type=str, help="Kline interval for Binance (e.g., '1h')")
    parser.add_argument('--start_date', type=str, help="Start date for Binance (e.g., '1 Jan, 2023')")
    parser.add_argument('--end_date', type=str, help="End date for Binance (e.g., '31 Jan, 2023')")
    parser.add_argument('--limit', type=int, default=500, help="Kline limit for Binance")

    # Database arguments
    parser.add_argument('--db_host', default=None, help="Database host (overrides .env, default: 'localhost')")
    parser.add_argument('--db_port', default=None, type=int, help="Database port (overrides .env, default: 5432)")
    parser.add_argument('--db_user', default=None, help="Database user (overrides .env, default: 'postgres')")
    parser.add_argument('--db_password', default=None, help="Database password (overrides .env or environment)")
    parser.add_argument('--db_name', default=None, help="Database name (overrides .env, default: 'crypto_data')")

    # Binance API Key arguments
    parser.add_argument('--binance_api_key', default=None, help="Binance API Key (overrides .env)")
    parser.add_argument('--binance_api_secret', default=None, help="Binance API Secret (overrides .env)")

    # Control flags
    parser.add_argument('--save_json', action='store_true', help="Save data to a JSON file.")
    parser.add_argument('--no_db', action='store_true', help="Disable database insertion.")

    args = parser.parse_args()

    fetched_data = None
    asset_symbol_for_db = None
    asset_name_for_db = None
    source_for_db = args.source

    # Resolve Binance API Keys: CLI > .env > Fallback Placeholder
    active_binance_api_key = args.binance_api_key or os.getenv('BINANCE_API_KEY', "YOUR_BINANCE_API_KEY_PLACEHOLDER")
    active_binance_api_secret = args.binance_api_secret or os.getenv('BINANCE_API_SECRET', "YOUR_BINANCE_API_SECRET_PLACEHOLDER")

    if args.source == 'coingecko':
        if not all([args.coin_id, args.vs_currency, args.days is not None]):
            parser.error("For CoinGecko, --coin_id, --vs_currency, and --days are required.")
        print(f"Fetching data for {args.coin_id} vs {args.vs_currency} for last {args.days} days from CoinGecko...")
        fetched_data = get_coingecko_data(args.coin_id, args.vs_currency, args.days)
        asset_symbol_for_db = args.coin_id
        asset_name_for_db = args.coin_id.capitalize()
        output_filename_base = f"{args.coin_id}_{args.vs_currency}_{args.days}_days_coingecko"

    elif args.source == 'binance':
        if not BINANCE_AVAILABLE:
             print("Cannot fetch from Binance: 'python-binance' library is not installed.")
             sys.exit(1)
        if not all([args.symbol, args.interval]):
            parser.error("For Binance, --symbol and --interval are required.")

        # The warning for placeholders is now handled inside get_binance_data by passing resolved keys
        print(f"Fetching data for {args.symbol} interval {args.interval} from Binance...")
        fetched_data = get_binance_data(
            active_binance_api_key, active_binance_api_secret,
            args.symbol, args.interval, args.start_date, args.end_date, args.limit
        )
        asset_symbol_for_db = args.symbol
        asset_name_for_db = args.symbol
        time_period_str = f"{args.start_date}_to_{args.end_date}" if args.start_date and args.end_date else f"last_{args.limit}"
        output_filename_base = f"{args.symbol}_{args.interval}_{time_period_str}_binance".replace(" ", "_").replace(",", "")

    if fetched_data:
        print(f"Successfully fetched {len(fetched_data)} data points.")

        # Database Insertion Logic
        if not args.no_db:
            if not DB_AVAILABLE:
                print("Database operations skipped as psycopg2-binary is not available.")
            else:
                # Resolve DB parameters: CLI > .env > default
                db_host = args.db_host or os.getenv('DB_HOST', 'localhost')

                db_port_str = os.getenv('DB_PORT', '5432') # Default from .env or hardcoded
                if args.db_port is not None: # CLI overrides .env
                    db_port_str = str(args.db_port)
                try:
                    db_port = int(db_port_str)
                except ValueError:
                    print(f"Warning: Invalid DB_PORT '{db_port_str}'. Using default 5432.")
                    db_port = 5432

                db_user = args.db_user or os.getenv('DB_USER', 'postgres')
                db_name = args.db_name or os.getenv('DB_NAME', 'crypto_data')
                db_password = args.db_password or os.getenv('DB_PASSWORD')

                if not db_password:
                    print("Error: Database password must be provided via CLI (--db_password) or .env (DB_PASSWORD) when --no_db is not specified.")
                else:
                    conn = get_db_connection(db_host, db_port, db_user, db_password, db_name)
                    if conn:
                        asset_id = ensure_asset_exists(conn, asset_symbol_for_db, asset_name_for_db, source_for_db)
                        if asset_id:
                            if insert_price_data(conn, asset_id, fetched_data):
                                print("Database insertion successful.")
                            else:
                                print("Database insertion failed.")
                        else:
                            print(f"Failed to get/create asset_id for {asset_symbol_for_db}. Skipping price data insertion.")
                        conn.close()
                        print("Database connection closed.")
                    else:
                        print("Failed to connect to database (using resolved credentials). Skipping database operations.")
        else:
            print("Skipping database insertion as --no_db flag is set.")

        # JSON Saving Logic
        if args.save_json:
            output_filename = f"{output_filename_base}_data.json"
            print(f"Saving data to {output_filename} in {args.output_dir}...")
            save_data_to_json(fetched_data, output_filename, args.output_dir)
        else:
            print("Skipping JSON file saving as --save_json flag is not set.")

    else:
        print(f"Failed to fetch data from {args.source}.")

    print("Data fetching script finished.")
