import argparse
import os
import json
import requests # Will be used for API calls
import time # For rate limiting
import sys
from datetime import datetime # For handling timestamps

# Adjust sys.path to allow imports from the crypto_screener_ai directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) # This assumes analysis_modules is one level down from project root
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
from crypto_screener_ai.common.db_utils import get_db_connection, get_asset_id # Assuming common is in crypto_screener_ai
# Mock DB_AVAILABLE for environments where psycopg2 might not be installed initially for linting/testing
DB_AVAILABLE = True
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    DB_AVAILABLE = False
    # print("psycopg2 not installed, database functionality will be limited.") # Optional warning

# Load environment variables from .env file
load_dotenv()

# --- API fetching and DB interaction functions ---
def fetch_coingecko_coin_details(coin_id: str):
    """
    Fetches detailed coin data from CoinGecko for a given coin_id.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    params = {
        'localization': 'false',
        'tickers': 'false',
        'market_data': 'true',
        'community_data': 'true',
        'developer_data': 'false',
        'sparkline': 'false'
    }
    print(f"Fetching details for {coin_id} from CoinGecko...")
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors
        api_data = response.json()

        details = {
            'description': api_data.get('description', {}).get('en') if api_data.get('description') else None,
            'categories': api_data.get('categories', []),
            'homepage_url': api_data.get('links', {}).get('homepage', [None])[0] if api_data.get('links', {}).get('homepage') else None,
            'blockchain_site_urls': [site for site in api_data.get('links', {}).get('blockchain_site', []) if site], # Filter out empty strings
            'twitter_handle': api_data.get('links', {}).get('twitter_screen_name'),
            'facebook_username': api_data.get('links', {}).get('facebook_username'),
            'telegram_channel_identifier': api_data.get('links', {}).get('telegram_channel_identifier'),
            'subreddit_url': api_data.get('links', {}).get('subreddit_url'),
            'market_cap_usd': api_data.get('market_data', {}).get('market_cap', {}).get('usd'),
            'circulating_supply': api_data.get('market_data', {}).get('circulating_supply'),
            'total_supply': api_data.get('market_data', {}).get('total_supply'),
            'max_supply': api_data.get('market_data', {}).get('max_supply'),
            'last_updated_api': api_data.get('market_data', {}).get('last_updated')
        }

        if details['last_updated_api']:
            try:
                # Convert ISO 8601 string to datetime object
                details['last_updated_api'] = datetime.fromisoformat(details['last_updated_api'].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse last_updated_api timestamp: {details['last_updated_api']}. Error: {e}")
                details['last_updated_api'] = None

        # Ensure arrays are stored as lists, not None if empty
        details['categories'] = details.get('categories') or []
        details['blockchain_site_urls'] = details.get('blockchain_site_urls') or []


        print(f"Successfully fetched details for {coin_id}.")
        time.sleep(6) # Rate limiting
        return details

    except requests.exceptions.Timeout:
        print(f"Error: Timeout while fetching data for {coin_id} from CoinGecko.")
        time.sleep(6) # Still sleep on timeout before potential retry or next call
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP error {e.response.status_code} while fetching data for {coin_id}: {e.response.text}")
        time.sleep(6)
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed for {coin_id}: {e}")
        time.sleep(6)
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response for {coin_id}.")
        time.sleep(6)
        return None


def update_asset_fundamentals(conn, asset_id: int, details: dict) -> bool:
    """
    Inserts or updates fundamental data for a given asset_id in the asset_fundamentals table.
    `details` dictionary is expected to contain keys matching the table columns.
    """
    if not DB_AVAILABLE:
        print("Error: psycopg2 library not available for DB operations.")
        return False
    if conn is None:
        print("Error: Database connection not provided.")
        return False
    if not details:
        print(f"Warning: No details provided for asset_id {asset_id}. Skipping update.")
        return False

    cols_to_update = [
        "description", "categories", "homepage_url", "blockchain_site_urls",
        "twitter_handle", "facebook_username", "telegram_channel_identifier",
        "subreddit_url", "market_cap_usd", "circulating_supply", "total_supply",
        "max_supply", "last_updated_api"
    ]

    set_conflict_clauses = [f"{col} = EXCLUDED.{col}" for col in cols_to_update]
    # Ensure fetched_at is always updated on conflict as well
    set_conflict_sql = ", ".join(set_conflict_clauses) + ", fetched_at = CURRENT_TIMESTAMP"

    sql_query_final = f"""
        INSERT INTO asset_fundamentals (
            asset_id, description, categories, homepage_url, blockchain_site_urls,
            twitter_handle, facebook_username, telegram_channel_identifier, subreddit_url,
            market_cap_usd, circulating_supply, total_supply, max_supply,
            last_updated_api, fetched_at
        ) VALUES (
            %(asset_id)s, %(description)s, %(categories)s, %(homepage_url)s, %(blockchain_site_urls)s,
            %(twitter_handle)s, %(facebook_username)s, %(telegram_channel_identifier)s, %(subreddit_url)s,
            %(market_cap_usd)s, %(circulating_supply)s, %(total_supply)s, %(max_supply)s,
            %(last_updated_api)s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (asset_id) DO UPDATE
        SET {set_conflict_sql};
    """

    data_for_sql = {'asset_id': asset_id}
    for col in cols_to_update:
        data_for_sql[col] = details.get(col)

    try:
        with conn.cursor() as cur:
            cur.execute(sql_query_final, data_for_sql)
        conn.commit()
        print(f"Successfully updated fundamental data for asset_id: {asset_id}")
        return True
    except psycopg2.Error as e:
        print(f"Database error updating fundamental data for asset_id {asset_id}: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"An unexpected error occurred updating asset_id {asset_id}: {e}")
        conn.rollback()
        return False

def main():
    parser = argparse.ArgumentParser(description="Fetch and store fundamental data for crypto assets.")

    # Database connection arguments (optional, defaults to .env or hardcoded)
    parser.add_argument('--db_host', default=os.getenv('DB_HOST', 'localhost'), help='Database host.')
    parser.add_argument('--db_port', default=os.getenv('DB_PORT', '5432'), help='Database port.')
    parser.add_argument('--db_user', default=os.getenv('DB_USER'), help='Database user.')
    parser.add_argument('--db_password', default=os.getenv('DB_PASSWORD'), help='Database password.')
    parser.add_argument('--db_name', default=os.getenv('DB_NAME', 'crypto_data'), help='Database name.')

    # Asset selection arguments
    parser.add_argument('--symbol', type=str, help='Specific asset symbol (e.g., bitcoin or BTCUSDT) to fetch data for. Assumed to be CoinGecko ID if fetching from CoinGecko.')
    parser.add_argument('--all-assets', action='store_true', help='Fetch data for all relevant assets in the database.')
    # parser.add_argument('--source-filter', type=str, default='coingecko', help='Filter assets by source if --all-assets is used (e.g., coingecko).') # Future enhancement

    args = parser.parse_args()

    if not DB_AVAILABLE:
        print("Error: psycopg2 library is not installed. Database operations cannot proceed.")
        sys.exit(1)

    if not args.db_password:
        print("Error: Database password not provided via CLI or .env file (DB_PASSWORD).")
        # sys.exit(1) # Commenting out for now to allow testing script structure without DB

    print("Fundamental Analyzer script started.")
    print(f"Args: {args}")

    # Refined DB Password Check (moved from earlier in the subtask description)
    # For this script, DB connection is essential for its main purpose.
    # Using os.getenv directly here as args.db_password already incorporates the .env value via its default.
    # The crucial part is that one of them (CLI or .env) must provide the password.
    if not args.db_password: # This now correctly checks the resolved password (CLI or .env)
        print("Error: Database password must be provided either via --db_password or DB_PASSWORD in .env file.")
        sys.exit(1)

    conn = None
    try:
        conn = get_db_connection(args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)

        if conn is None:
            print("Failed to connect to the database. Exiting.")
            sys.exit(1)

        if args.symbol:
            print(f"Processing fundamental data for symbol: {args.symbol}")
            # Assuming args.symbol is the CoinGecko ID for fetching,
            # and also the symbol stored in our 'assets' table for CoinGecko assets.
            asset_id = get_asset_id(conn, args.symbol)
            if asset_id:
                print(f"Found asset_id: {asset_id} for symbol: {args.symbol}. Fetching details from CoinGecko...")
                details = fetch_coingecko_coin_details(args.symbol) # args.symbol is used as coin_id
                if details:
                    if update_asset_fundamentals(conn, asset_id, details):
                        print(f"Successfully stored/updated fundamentals for {args.symbol}.")
                    else:
                        print(f"Failed to store/update fundamentals for {args.symbol}.")
                else:
                    print(f"Could not fetch details for coin_id: {args.symbol} from CoinGecko.")
            else:
                print(f"Asset with symbol '{args.symbol}' not found in the database. Cannot store fundamentals.")
                print("Consider adding this asset first using the data collection script (fetch_data.py).")

        elif args.all_assets:
            print("Processing fundamental data for all assets found in the 'assets' table...")
            assets_to_fetch = []
            try:
                with conn.cursor() as cur:
                    # For now, assume all symbols in 'assets' table might be valid CoinGecko IDs.
                    # A 'source' column in 'assets' table would be useful for filtering.
                    cur.execute("SELECT asset_id, symbol FROM assets ORDER BY symbol;")
                    assets_to_fetch = cur.fetchall()
            except psycopg2.Error as e:
                print(f"Database error fetching list of all assets: {e}")
                conn.rollback()

            if not assets_to_fetch:
                print("No assets found in the database to process.")
            else:
                print(f"Found {len(assets_to_fetch)} assets. Fetching fundamentals (with rate limiting)...")
                for i, (asset_id, symbol) in enumerate(assets_to_fetch):
                    print(f"Processing asset {i+1}/{len(assets_to_fetch)}: ID={asset_id}, Symbol/CoinGeckoID='{symbol}'")
                    # Assumption: The 'symbol' from assets table is a valid CoinGecko ID.
                    # This might not be true if symbols from other sources (e.g., Binance tickers) are also in this table.
                    details = fetch_coingecko_coin_details(symbol)
                    if details:
                        if update_asset_fundamentals(conn, asset_id, details):
                            print(f"Successfully stored/updated fundamentals for {symbol} (ID: {asset_id}).")
                        else:
                             print(f"Failed to store/update fundamentals for {symbol} (ID: {asset_id}).")
                    else:
                        print(f"Could not fetch details for coin_id: {symbol}. Skipping DB update for this asset.")
                    # Rate limiting is already inside fetch_coingecko_coin_details.
                    # An additional small delay here might be useful if processing a very large number of assets.
                    # time.sleep(1)
        else:
            print("Please specify an asset symbol using --symbol or use the --all-assets flag.")

    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

    print("Fundamental Analyzer script finished.")

if __name__ == "__main__":
    main()
