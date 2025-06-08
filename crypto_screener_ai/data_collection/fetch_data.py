import requests
import json
import datetime
import argparse
import os

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
# IMPORTANT: Replace with your actual Binance API key and secret for Binance functionality
BINANCE_API_KEY = "YOUR_BINANCE_API_KEY"
BINANCE_API_SECRET = "YOUR_BINANCE_API_SECRET"


def get_db_connection(db_host, db_port, db_user, db_password, db_name):
    """Establishes a connection to the PostgreSQL database."""
    if not DB_AVAILABLE:
        print("Database operations unavailable: psycopg2-binary is not installed.")
        return None
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            dbname=db_name
        )
        print(f"Successfully connected to database '{db_name}' on {db_host}:{db_port}")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database '{db_name}' on {db_host}:{db_port}: {e}")
        return None

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

    if api_key == "YOUR_BINANCE_API_KEY" or api_secret == "YOUR_BINANCE_API_SECRET":
        print("Warning: Using placeholder Binance API keys. Please replace them with your actual keys in the script for real data.")

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
    parser.add_argument('--db_host', default='localhost', help="Database host")
    parser.add_argument('--db_port', default=5432, type=int, help="Database port")
    parser.add_argument('--db_user', default='postgres', help="Database user")
    parser.add_argument('--db_password', help="Database password (required if --no_db is not set and not using other auth)")
    parser.add_argument('--db_name', default='crypto_data', help="Database name")

    # Control flags
    parser.add_argument('--save_json', action='store_true', help="Save data to a JSON file.")
    parser.add_argument('--no_db', action='store_true', help="Disable database insertion.")

    args = parser.parse_args()

    fetched_data = None
    asset_symbol_for_db = None # Used as 'symbol' in assets table
    asset_name_for_db = None   # Used as 'name' in assets table
    source_for_db = args.source

    if args.source == 'coingecko':
        if not all([args.coin_id, args.vs_currency, args.days is not None]):
            parser.error("For CoinGecko, --coin_id, --vs_currency, and --days are required.")
        print(f"Fetching data for {args.coin_id} vs {args.vs_currency} for last {args.days} days from CoinGecko...")
        fetched_data = get_coingecko_data(args.coin_id, args.vs_currency, args.days)
        asset_symbol_for_db = args.coin_id # e.g., "bitcoin"
        asset_name_for_db = args.coin_id.capitalize() # e.g., "Bitcoin"
        output_filename_base = f"{args.coin_id}_{args.vs_currency}_{args.days}_days_coingecko"

    elif args.source == 'binance':
        if not BINANCE_AVAILABLE:
             print("Cannot fetch from Binance: 'python-binance' library is not installed.")
             exit(1) # Exit if essential library is missing for chosen source
        if not all([args.symbol, args.interval]):
            parser.error("For Binance, --symbol and --interval are required.")
        print(f"Fetching data for {args.symbol} interval {args.interval} from Binance...")
        fetched_data = get_binance_data(BINANCE_API_KEY, BINANCE_API_SECRET, args.symbol, args.interval, args.start_date, args.end_date, args.limit)
        asset_symbol_for_db = args.symbol # e.g., "BTCUSDT"
        asset_name_for_db = args.symbol   # For Binance, symbol is often the common name used
        time_period_str = f"{args.start_date}_to_{args.end_date}" if args.start_date and args.end_date else f"last_{args.limit}"
        output_filename_base = f"{args.symbol}_{args.interval}_{time_period_str}_binance".replace(" ", "_").replace(",", "")

    if fetched_data:
        print(f"Successfully fetched {len(fetched_data)} data points.")

        # Database Insertion Logic
        if not args.no_db:
            if not DB_AVAILABLE:
                print("Database operations skipped as psycopg2-binary is not available.")
            elif not args.db_password:
                print("Error: --db_password is required for database operations unless --no_db is specified.")
                # Or handle other auth methods if implemented
            else:
                conn = get_db_connection(args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)
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
                    print("Failed to connect to database. Skipping database operations.")
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
