import requests
import json
import datetime
import argparse
import os

# Placeholder for user to add their Binance API keys
# IMPORTANT: Replace with your actual Binance API key and secret
BINANCE_API_KEY = "YOUR_BINANCE_API_KEY"
BINANCE_API_SECRET = "YOUR_BINANCE_API_SECRET"

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    # Mock classes if binance library is not installed, to allow script to be parsed
    class BinanceAPIException(Exception): pass
    class Client: pass


def get_coingecko_data(coin_id: str, vs_currency: str, days: int):
    """
    Fetches historical market data for a specific coin from CoinGecko.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency={vs_currency}&days={days}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        prices = data.get('prices', [])
        normalized_prices = []
        for timestamp_ms, price in prices:
            timestamp_s = timestamp_ms / 1000
            dt_object = datetime.datetime.fromtimestamp(timestamp_s, tz=datetime.timezone.utc)
            iso_format = dt_object.isoformat()
            normalized_prices.append([iso_format, price])
        return normalized_prices
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from CoinGecko: {e}")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON response from CoinGecko.")
        return None

def get_binance_data(api_key: str, api_secret: str, symbol: str, interval: str, start_str: str = None, end_str: str = None, limit: int = 500):
    """
    Fetches historical klines (OHLCV) data from Binance.

    Args:
        api_key: Binance API key.
        api_secret: Binance API secret.
        symbol: Trading symbol (e.g., "BTCUSDT").
        interval: Kline interval (e.g., "1h", "4h", "1d").
        start_str: Start date string (e.g., "1 Jan, 2020").
        end_str: End date string (e.g., "1 Jan, 2021").
        limit: Number of klines to fetch if start_str is not provided.

    Returns:
        A list of dictionaries, each representing a kline, or None if an error occurs.
    """
    if not BINANCE_AVAILABLE:
        print("Binance library not installed. Please install 'python-binance' to use this feature.")
        return None

    if api_key == "YOUR_BINANCE_API_KEY" or api_secret == "YOUR_BINANCE_API_SECRET":
        print("Warning: Using placeholder Binance API keys. Please replace them with your actual keys in the script.")
        # Allow script to proceed for structural validation, but it won't fetch real data.

    client = Client(api_key, api_secret)
    try:
        if start_str:
            klines = client.get_historical_klines(symbol, interval, start_str=start_str, end_str=end_str)
        else:
            klines = client.get_historical_klines(symbol, interval, limit=limit)

        normalized_klines = []
        for kline in klines:
            timestamp_ms = kline[0]
            # Convert timestamp from milliseconds to seconds
            timestamp_s = timestamp_ms / 1000
            # Create datetime object with UTC timezone
            dt_object = datetime.datetime.fromtimestamp(timestamp_s, tz=datetime.timezone.utc)
            # Format to ISO 8601
            iso_format = dt_object.isoformat()

            normalized_klines.append({
                'timestamp': iso_format,
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5])
            })
        return normalized_klines
    except BinanceAPIException as e:
        print(f"Error fetching data from Binance: {e}")
        return None
    except Exception as e: # Catch other potential errors, like connection issues if keys are fake
        print(f"An unexpected error occurred with Binance client: {e}")
        return None


def save_data_to_json(data: list, filename: str, directory: str):
    """
    Saves data to a JSON file in the specified directory.
    """
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
    parser = argparse.ArgumentParser(description="Fetch cryptocurrency data from CoinGecko or Binance.")
    parser.add_argument('source', choices=['coingecko', 'binance'], help="Data source: 'coingecko' or 'binance'")
    parser.add_argument('--output_dir', type=str, default='crypto_screener_ai/data_collection/', help="Directory to save the output JSON file. Defaults to 'crypto_screener_ai/data_collection/'.")

    # CoinGecko specific arguments
    parser.add_argument('--coin_id', type=str, help="Coin ID for CoinGecko (e.g., 'bitcoin')")
    parser.add_argument('--vs_currency', type=str, help="Currency for CoinGecko (e.g., 'usd')")
    parser.add_argument('--days', type=int, help="Number of days for CoinGecko historical data")

    # Binance specific arguments
    parser.add_argument('--symbol', type=str, help="Trading symbol for Binance (e.g., 'BTCUSDT')")
    parser.add_argument('--interval', type=str, help="Kline interval for Binance (e.g., '1h', '1d')")
    parser.add_argument('--start_date', type=str, help="Start date for Binance (e.g., '1 Jan, 2023')")
    parser.add_argument('--end_date', type=str, help="End date for Binance (e.g., '31 Jan, 2023')")
    parser.add_argument('--limit', type=int, default=500, help="Number of klines for Binance (default 500 if no start_date)")

    args = parser.parse_args()

    if args.source == 'coingecko':
        if not all([args.coin_id, args.vs_currency, args.days is not None]):
            parser.error("For CoinGecko, --coin_id, --vs_currency, and --days are required.")
        print(f"Fetching data for {args.coin_id} in {args.vs_currency} for the last {args.days} days from CoinGecko...")
        price_data = get_coingecko_data(args.coin_id, args.vs_currency, args.days)
        if price_data:
            output_filename = f"{args.coin_id}_{args.vs_currency}_{args.days}_days_coingecko_data.json"
            print(f"Saving data to {output_filename} in {args.output_dir}...")
            save_data_to_json(price_data, output_filename, args.output_dir)
        else:
            print(f"Failed to fetch data for {args.coin_id} from CoinGecko.")

    elif args.source == 'binance':
        if not BINANCE_AVAILABLE:
             print("Cannot fetch from Binance: 'python-binance' library is not installed. Please run 'pip install python-binance'.")
        elif not all([args.symbol, args.interval]):
            parser.error("For Binance, --symbol and --interval are required.")
        else:
            print(f"Fetching data for {args.symbol} with interval {args.interval} from Binance...")
            if BINANCE_API_KEY == "YOUR_BINANCE_API_KEY" or BINANCE_API_SECRET == "YOUR_BINANCE_API_SECRET":
                print("NOTE: Using placeholder API keys for Binance. The script will attempt to run but may not fetch data unless valid keys are provided in the script.")

            kline_data = get_binance_data(BINANCE_API_KEY, BINANCE_API_SECRET, args.symbol, args.interval, args.start_date, args.end_date, args.limit)
            if kline_data:
                time_period_str = f"{args.start_date}_to_{args.end_date}" if args.start_date and args.end_date else f"last_{args.limit}"
                output_filename = f"{args.symbol}_{args.interval}_{time_period_str}_binance_data.json".replace(" ", "_").replace(",", "")
                print(f"Saving data to {output_filename} in {args.output_dir}...")
                save_data_to_json(kline_data, output_filename, args.output_dir)
            else:
                print(f"Failed to fetch data for {args.symbol} from Binance.")
    else:
        parser.error("Invalid source specified.")
