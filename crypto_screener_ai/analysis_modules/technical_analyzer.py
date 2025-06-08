import json
import pandas as pd
import argparse
import os

# Attempt to import 'ta' library and specific indicators
try:
    from ta.trend import MACD, SMAIndicator
    from ta.momentum import RSIIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    print("Warning: 'ta' library not found. Please install it by running: pip install ta")
    # Define dummy classes if 'ta' is not available, so the script can be parsed
    class MACD: pass
    class SMAIndicator: pass
    class RSIIndicator: pass

def load_data_from_json(filepath: str) -> pd.DataFrame:
    """
    Loads JSON data from filepath, converts to a pandas DataFrame,
    and prepares it for technical analysis.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if not data:
            print(f"No data found in {filepath}")
            return None

        # Assuming data is a list of lists (CoinGecko) or list of dicts (Binance)
        # For CoinGecko: [[timestamp_iso, price], ...]
        # For Binance: [{'timestamp': iso_timestamp, 'open': float, ...}, ...]

        # Sniff the data structure to determine the source type
        if isinstance(data[0], list) and len(data[0]) == 2: # Likely CoinGecko
            print("Detected CoinGecko data format (timestamp, price).")
            df = pd.DataFrame(data, columns=['timestamp', 'close'])
            # CoinGecko data only has 'close' price. Other OHLC indicators might not work
            # or will require dummy OHL data if those indicators are essential.
            # For SMA, RSI, MACD on 'close', this is fine.
            df['open'] = df['close'] # Dummy data for OHLC consistency
            df['high'] = df['close'] # Dummy data
            df['low'] = df['close']  # Dummy data
            df['volume'] = 0 # Dummy data

        elif isinstance(data[0], dict) and 'timestamp' in data[0] and 'close' in data[0]: # Likely Binance
            print("Detected Binance data format (OHLCV).")
            df = pd.DataFrame(data)
        else:
            print("Unknown data format in JSON file.")
            return None

        # Convert timestamp column to datetime objects
        # Pandas can usually infer ISO8601, but if specific format issues arise,
        # providing format='ISO8601' or a more specific strptime format might be needed.
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp']) # Let pandas infer
        except Exception as e:
            print(f"Pandas.to_datetime initial attempt failed: {e}. Trying with format='ISO8601'.")
            try:
                 df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
            except Exception as e2:
                print(f"Pandas.to_datetime with format='ISO8601' also failed: {e2}. Trying with infer_datetime_format=True.")
                # Fallback for mixed or slightly off formats, deprecated but might work for some cases
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], infer_datetime_format=True)
                except Exception as e3:
                    print(f"All attempts to parse datetime failed: {e3}. Please check timestamp format in source file.")
                    return None


        df = df.set_index('timestamp')

        # Ensure OHLCV columns are numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else: # Add column if missing (e.g. volume for coingecko)
                 df[col] = 0 # default to 0 if not present

        df.sort_index(inplace=True) # Ensure data is sorted by time
        return df

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while loading data: {e}")
        return None

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical indicators (SMA, RSI, MACD) and adds them to the DataFrame.
    """
    if not TA_AVAILABLE:
        print("Error: 'ta' library is not available. Cannot calculate indicators.")
        return df # Return original df

    if 'close' not in df.columns or df['close'].isnull().all():
        print("Error: 'close' price data is missing or all null. Cannot calculate indicators.")
        return df

    # SMA - 20 period
    try:
        sma_20 = SMAIndicator(close=df['close'], window=20, fillna=True)
        df['SMA_20'] = sma_20.sma_indicator()
    except Exception as e:
        print(f"Could not calculate SMA_20: {e}")

    # RSI - 14 period
    try:
        rsi_14 = RSIIndicator(close=df['close'], window=14, fillna=True)
        df['RSI_14'] = rsi_14.rsi()
    except Exception as e:
        print(f"Could not calculate RSI_14: {e}")

    # MACD - default periods (12, 26, 9)
    try:
        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9, fillna=True)
        df['MACD_line'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_hist'] = macd.macd_diff() # Histogram
    except Exception as e:
        print(f"Could not calculate MACD: {e}")

    return df

def save_data_to_json(df: pd.DataFrame, filepath: str):
    """
    Saves the DataFrame (with indicators) to a JSON file.
    Converts datetime index to ISO format string.
    """
    try:
        # Reset index to make timestamp a column again for JSON export
        df_to_save = df.reset_index()
        # Convert timestamp to ISO format string
        df_to_save['timestamp'] = df_to_save['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')

        data_list = df_to_save.to_dict(orient='records')

        # Create directory if it doesn't exist
        output_dir = os.path.dirname(filepath)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")

        with open(filepath, 'w') as f:
            json.dump(data_list, f, indent=4)
        print(f"Data with indicators successfully saved to {filepath}")
    except IOError as e:
        print(f"Error saving data to JSON file {filepath}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving data: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate technical indicators from OHLCV JSON data.")
    parser.add_argument('input_file', type=str, help="Path to the input JSON data file (e.g., from fetch_data.py).")
    parser.add_argument('output_file', type=str, help="Path for the output JSON file with indicators.")

    args = parser.parse_args()

    print(f"Loading data from {args.input_file}...")
    ohlcv_df = load_data_from_json(args.input_file)

    if ohlcv_df is not None and not ohlcv_df.empty:
        print("Calculating indicators...")
        df_with_indicators = calculate_indicators(ohlcv_df.copy()) # Use .copy() to avoid SettingWithCopyWarning
        if df_with_indicators is not None:
            print(f"Saving data with indicators to {args.output_file}...")
            save_data_to_json(df_with_indicators, args.output_file)
        else:
            print("Failed to calculate indicators.")
    else:
        print(f"Failed to load data from {args.input_file}. Please check the file and format.")

    if not TA_AVAILABLE:
        print("\nReminder: The 'ta' library was not found during script execution. "
              "Please install it (`pip install ta`) for indicators to be calculated.")
