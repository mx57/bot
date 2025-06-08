import json
import pandas as pd
import argparse
import os
import sys # For exiting

# Attempt to import database and TA libraries
try:
    import psycopg2
    import psycopg2.extras
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    class psycopg2: # Mock
        @staticmethod
        def connect(*args, **kwargs): raise ImportError("psycopg2-binary not installed")
        class extras:
            @staticmethod
            def execute_values(*args, **kwargs): raise ImportError("psycopg2-binary not installed")
        class Error(Exception): pass # Mock base error class
    print("Warning: psycopg2-binary not installed. Database operations will be unavailable.")

try:
    from ta.trend import MACD, SMAIndicator
    from ta.momentum import RSIIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    print("Warning: 'ta' library not found. Please install it by running: pip install ta")
    class MACD: pass
    class SMAIndicator: pass
    class RSIIndicator: pass


def get_db_connection(db_host, db_port, db_user, db_password, db_name):
    """Establishes a connection to the PostgreSQL database."""
    if not DB_AVAILABLE:
        print("Database operations unavailable: psycopg2-binary is not installed.")
        return None
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, user=db_user, password=db_password, dbname=db_name)
        print(f"Successfully connected to database '{db_name}' on {db_host}:{db_port}")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database '{db_name}' on {db_host}:{db_port}: {e}")
        return None

def get_asset_id(conn, symbol: str) -> int | None:
    """Retrieves asset_id from the 'assets' table for a given symbol."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT asset_id FROM assets WHERE symbol = %s;", (symbol,))
            result = cur.fetchone()
            if result:
                return result[0]
            else:
                print(f"Asset symbol '{symbol}' not found in database.")
                return None
    except psycopg2.Error as e:
        print(f"Error fetching asset_id for symbol '{symbol}': {e}")
        return None

def load_data(args, conn) -> tuple[pd.DataFrame | None, int | None]:
    """Loads data from JSON file or database based on provided arguments."""
    asset_id = None
    if not args.no_db_input:
        if not conn:
            print("DB connection not available, and --no_db_input not specified. Cannot load data from DB.")
            if not args.input_json_file:
                print("No --input_json_file provided as fallback. Aborting.")
                return None, None
            else:
                print("Attempting to load from --input_json_file as fallback.")
                return load_data_from_json_file(args.input_json_file), None # asset_id is None for JSON input

        print(f"Attempting to load data from database for symbol: {args.symbol}")
        asset_id = get_asset_id(conn, args.symbol)
        if not asset_id:
            return None, None

        query_parts = ["SELECT time, open, high, low, close, volume FROM price_data WHERE asset_id = %s"]
        params = [asset_id]

        if args.start_date:
            query_parts.append("AND time >= %s")
            params.append(args.start_date)
        if args.end_date:
            query_parts.append("AND time <= %s")
            params.append(args.end_date)

        query_parts.append("ORDER BY time")
        if args.limit:
            query_parts.append("DESC LIMIT %s") # Fetch latest if limit is used
            params.append(args.limit)
            # Re-sort ASC after limiting
            base_query = " ".join(query_parts)
            query = f"SELECT * FROM ({base_query}) sub ORDER BY time ASC"
        else:
            query_parts.append("ASC")
            query = " ".join(query_parts)

        try:
            print(f"Executing DB query: {query} with params: {params}")
            df = pd.read_sql_query(query, conn, params=params)
            if df.empty:
                print(f"No price data found in database for asset_id {asset_id} with given criteria.")
                return None, asset_id

            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            print(f"Loaded {len(df)} records from database for asset_id {asset_id}.")
            return df, asset_id
        except Exception as e:
            print(f"Error loading data from database: {e}")
            return None, asset_id # Return asset_id as it was fetched

    elif args.input_json_file:
        print(f"Loading data from JSON file: {args.input_json_file}")
        return load_data_from_json_file(args.input_json_file), None # asset_id is None for JSON input
    else:
        print("Error: No data source specified. Use --input_json_file or configure DB access (omit --no_db_input).")
        return None, None

def load_data_from_json_file(filepath: str) -> pd.DataFrame | None:
    """Loads and prepares data from a JSON file (legacy behavior)."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        if not data: return None

        if isinstance(data[0], list) and len(data[0]) == 2: # CoinGecko-like
            df = pd.DataFrame(data, columns=['timestamp', 'close'])
            df['open'] = df['close']; df['high'] = df['close']; df['low'] = df['close']; df['volume'] = 0
        elif isinstance(data[0], dict) and 'timestamp' in data[0] and 'close' in data[0]: # Binance-like
            df = pd.DataFrame(data)
        else:
            print("Unknown JSON data format.")
            return None

        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        except Exception:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')

        df = df.set_index('timestamp')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                df[col] = 0.0 if col != 'volume' else 0 # Default price to 0, volume to 0
        df.sort_index(inplace=True)
        return df
    except Exception as e:
        print(f"Error loading/processing JSON file {filepath}: {e}")
        return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if not TA_AVAILABLE:
        print("Error: 'ta' library is not available. Cannot calculate indicators.")
        return df
    if 'close' not in df.columns or df['close'].isnull().all() or len(df) < 20: # Need enough data for SMA 20
        print("Error: 'close' price data is insufficient or missing. Skipping some indicators.")
        return df

    df_calc = df.copy()
    try:
        sma_20 = SMAIndicator(close=df_calc['close'], window=20, fillna=True)
        df_calc['SMA_20'] = sma_20.sma_indicator()
    except Exception as e: print(f"Could not calculate SMA_20: {e}")
    try:
        rsi_14 = RSIIndicator(close=df_calc['close'], window=14, fillna=True)
        df_calc['RSI_14'] = rsi_14.rsi()
    except Exception as e: print(f"Could not calculate RSI_14: {e}")
    try:
        macd = MACD(close=df_calc['close'], window_slow=26, window_fast=12, window_sign=9, fillna=True)
        df_calc['MACD_line'] = macd.macd()
        df_calc['MACD_signal'] = macd.macd_signal()
        df_calc['MACD_hist'] = macd.macd_diff()
    except Exception as e: print(f"Could not calculate MACD: {e}")
    return df_calc

def save_data(df_with_indicators: pd.DataFrame, args, conn, asset_id: int | None):
    """Saves data to JSON and/or database."""
    if args.output_json_file:
        print(f"Saving data with indicators to JSON: {args.output_json_file}")
        df_to_save = df_with_indicators.reset_index()
        df_to_save['timestamp'] = df_to_save['time'].dt.strftime('%Y-%m-%dT%H:%M:%S%z') if 'time' in df_to_save else df_to_save['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')

        # Select only relevant columns for JSON output (original OHLCV + indicators)
        cols_to_save = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        indicator_cols = [col for col in df_with_indicators.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
        cols_to_save.extend(indicator_cols)

        # Filter out columns not present in df_to_save (e.g. if OHLCV were not in original JSON)
        cols_to_save = [col for col in cols_to_save if col in df_to_save.columns]

        try:
            output_dir = os.path.dirname(args.output_json_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir); print(f"Created directory: {output_dir}")
            with open(args.output_json_file, 'w') as f:
                json.dump(df_to_save[cols_to_save].to_dict(orient='records'), f, indent=4)
            print(f"Successfully saved JSON to {args.output_json_file}")
        except Exception as e:
            print(f"Error saving JSON to {args.output_json_file}: {e}")

    if not args.no_db_output:
        if not conn:
            print("DB connection not available. Cannot save indicators to DB.")
            return
        if not asset_id:
            print("Asset ID not available (e.g. data loaded from JSON without symbol context for DB). Cannot save indicators to DB.")
            return

        print(f"Preparing to save indicators to database for asset_id: {asset_id}")
        indicator_cols = [col for col in ['SMA_20', 'RSI_14', 'MACD_line', 'MACD_signal', 'MACD_hist'] if col in df_with_indicators.columns]
        if not indicator_cols:
            print("No indicator columns found in DataFrame to save to DB.")
            return

        df_for_db = df_with_indicators.reset_index()[['time'] + indicator_cols]
        df_melted = df_for_db.melt(id_vars=['time'], value_vars=indicator_cols,
                                   var_name='indicator_name', value_name='value')
        df_melted['asset_id'] = asset_id
        df_melted.dropna(subset=['value'], inplace=True) # Remove rows where indicator calculation might have failed

        if df_melted.empty:
            print("No indicator data to save to database after processing.")
            return

        records_to_insert = [(row.time, row.asset_id, row.indicator_name, row.value) for row in df_melted.itertuples(index=False)]

        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO technical_indicators (time, asset_id, indicator_name, value)
                    VALUES %s
                    ON CONFLICT (asset_id, time, indicator_name) DO UPDATE SET value = EXCLUDED.value;
                    """,
                    records_to_insert
                )
                conn.commit()
                print(f"Successfully saved {len(records_to_insert)} indicator records to database for asset_id {asset_id}.")
        except psycopg2.Error as e:
            print(f"Error saving indicators to database: {e}")
            conn.rollback()
        except Exception as e:
            print(f"A non-psycopg2 error occurred while saving indicators to DB: {e}")
            conn.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate technical indicators and save to JSON or DB.")

    # Data source
    parser.add_argument('--symbol', type=str, help="Asset symbol (e.g., BTCUSDT or bitcoin) for DB operations.")
    parser.add_argument('--input_json_file', type=str, help="Path to input JSON data file.")
    parser.add_argument('--no_db_input', action='store_true', help="Force loading from JSON if --input_json_file is provided.")

    # DB connection
    parser.add_argument('--db_host', default='localhost', help="DB host")
    parser.add_argument('--db_port', default=5432, type=int, help="DB port")
    parser.add_argument('--db_user', default='postgres', help="DB user")
    parser.add_argument('--db_password', help="DB password")
    parser.add_argument('--db_name', default='crypto_data', help="DB name")

    # Data filtering (for DB source)
    parser.add_argument('--start_date', type=str, help="Start date for DB query (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)")
    parser.add_argument('--end_date', type=str, help="End date for DB query")
    parser.add_argument('--limit', type=int, help="Limit records from DB (fetches latest N records)")

    # Output
    parser.add_argument('--output_json_file', type=str, help="Path for output JSON file with indicators.")
    parser.add_argument('--no_db_output', action='store_true', help="Disable saving indicators to DB.")

    args = parser.parse_args()

    # Validate arguments
    if not args.no_db_input and not args.symbol:
        parser.error("--symbol is required if loading data from database (i.e., --no_db_input is not set).")
    if (not args.no_db_input or not args.no_db_output) and not args.db_password and DB_AVAILABLE:
        # Only require password if DB operations are intended and DB_AVAILABLE (psycopg2 installed)
        print("Warning: --db_password not provided. Database operations might fail if password is required.")


    conn = None
    asset_id_from_db = None # To store asset_id if fetched/used by DB operations

    if not args.no_db_input or not args.no_db_output:
        if DB_AVAILABLE and args.db_password: # Only try to connect if relevant flags are set and psycopg2 is there
            conn = get_db_connection(args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)
        elif not DB_AVAILABLE:
             print("DB operations requested but psycopg2 is not installed. Skipping DB operations.")
        # If password not provided, warning already printed. Connection will be None.

    # Load data
    ohlcv_df, asset_id_from_load = load_data(args, conn)

    if asset_id_from_load: # If data loaded from DB, we have asset_id
        asset_id_context = asset_id_from_load
    elif conn and args.symbol: # If data from JSON, but DB output is intended, try to get asset_id
        asset_id_context = get_asset_id(conn, args.symbol)
        if not asset_id_context and not args.no_db_output:
            print(f"Warning: Symbol {args.symbol} not found in DB. Cannot save indicators to DB if it's a new asset not yet in `assets` table via fetch_data.py.")
    else:
        asset_id_context = None


    if ohlcv_df is not None and not ohlcv_df.empty:
        print("Calculating indicators...")
        df_with_indicators = calculate_indicators(ohlcv_df)

        # Pass asset_id_context to save_data
        save_data(df_with_indicators, args, conn, asset_id_context)
    else:
        print("Failed to load data or data is empty. No analysis performed.")

    if conn:
        conn.close()
        print("Database connection closed.")

    print("Technical analyzer script finished.")
