import argparse
import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Adjust sys.path for local imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_CORE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(AI_CORE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
from crypto_screener_ai.common.db_utils import get_db_connection, get_asset_id

# --- Mock DB_AVAILABLE for environments where psycopg2 might not be installed ---
DB_AVAILABLE = True
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    DB_AVAILABLE = False
    print("Warning: psycopg2 not installed, database functionality will be limited.")

# --- Mock ML_LIBS_AVAILABLE for environments where ML libs might not be installed ---
ML_LIBS_AVAILABLE = True
try:
    from sklearn.preprocessing import MinMaxScaler
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    # from tensorflow.keras.callbacks import EarlyStopping # For later
except ImportError:
    ML_LIBS_AVAILABLE = False
    print("Warning: TensorFlow or Scikit-learn not installed. ML functionality will be limited.")

load_dotenv()

# --- Placeholder for functions ---
def load_asset_data(conn, asset_id: int, start_date_str: str = None, end_date_str: str = None) -> pd.DataFrame | None:
    """
    Loads OHLCV price data and technical indicators for a given asset_id and date range.
    Merges them into a single DataFrame.
    """
    if not DB_AVAILABLE:
        print("Error: psycopg2 not available for load_asset_data.")
        return None
    if conn is None:
        print("Error: Database connection not provided for load_asset_data.")
        return None

    # Construct date range query part
    date_conditions = []
    params = {'asset_id': asset_id}
    if start_date_str:
        try:
            # Ensure start_date_str is valid datetime format before using in query
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S%z')
            date_conditions.append("time >= %(start_date)s")
            params['start_date'] = start_date
        except ValueError:
            print(f"Warning: Invalid start_date format '{start_date_str}'. Ignoring.")
    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S%z')
            date_conditions.append("time <= %(end_date)s")
            params['end_date'] = end_date
        except ValueError:
            print(f"Warning: Invalid end_date format '{end_date_str}'. Ignoring.")

    date_sql_part = " AND ".join(date_conditions)
    if date_sql_part:
        date_sql_part = "AND " + date_sql_part

    # Fetch Price Data (OHLCV)
    price_sql = f"""
        SELECT time, open, high, low, close, volume
        FROM price_data
        WHERE asset_id = %(asset_id)s {date_sql_part}
        ORDER BY time ASC;
    """
    # print(f"DEBUG: Price SQL: {price_sql} with params {params}") # For debugging
    try:
        df_price = pd.read_sql_query(price_sql, conn, params=params, index_col='time')
        if df_price.empty:
            print(f"No price data found for asset_id {asset_id} within the specified date range.")
            return None
        # Ensure index is DatetimeIndex
        df_price.index = pd.to_datetime(df_price.index, utc=True)

    except (psycopg2.Error, pd.io.sql.DatabaseError) as e:
        print(f"Database error fetching price data for asset_id {asset_id}: {e}")
        if conn and not conn.closed: conn.rollback() # Rollback if connection is still open
        return None
    except Exception as e:
        print(f"An unexpected error occurred fetching price data for asset_id {asset_id}: {e}")
        return None


    # Fetch Technical Indicators
    indicators_sql = f"""
        SELECT time, indicator_name, value
        FROM technical_indicators
        WHERE asset_id = %(asset_id)s {date_sql_part}
        ORDER BY time ASC, indicator_name ASC;
    """
    # print(f"DEBUG: Indicators SQL: {indicators_sql} with params {params}") # For debugging
    try:
        df_indicators_long = pd.read_sql_query(indicators_sql, conn, params=params)
        if df_indicators_long.empty:
            print(f"No technical indicators found for asset_id {asset_id} within the date range. Proceeding with price data only.")
            return df_price # Return price data if no indicators found

        # Pivot indicators from long to wide format
        # Ensure 'time' is datetime for proper pivot and merge later
        df_indicators_long['time'] = pd.to_datetime(df_indicators_long['time'], utc=True)
        df_indicators_wide = df_indicators_long.pivot_table(index='time', columns='indicator_name', values='value')

        # Merge price data with indicators
        # Use a left merge to keep all price data points; indicators might not exist for all timestamps
        df_merged = df_price.merge(df_indicators_wide, on='time', how='left')

        # df_merged.sort_index(inplace=True) # Already sorted by time from SQL query

        print(f"Successfully loaded and merged data for asset_id {asset_id}. Shape: {df_merged.shape}")
        return df_merged

    except (psycopg2.Error, pd.io.sql.DatabaseError) as e:
        print(f"Database error fetching technical indicators for asset_id {asset_id}: {e}")
        if conn and not conn.closed: conn.rollback()
        print("Warning: Proceeding with price data only due to indicator loading error.")
        return df_price
    except Exception as e: # Catch other errors like pivot_table issues
        print(f"An unexpected error occurred fetching/processing indicators for asset_id {asset_id}: {e}")
        print("Warning: Proceeding with price data only due to an unexpected indicator processing error.")
        return df_price

def preprocess_data(df: pd.DataFrame, sequence_length: int, target_column: str = 'close'):
    """
    Preprocesses the data for LSTM model:
    1. Selects features (target_column + other relevant features).
    2. Handles missing values.
    3. Scales features using MinMaxScaler.
    4. Creates sequences (X, y) for time-series forecasting.
    Returns X, y, and the scaler object.
    """
    if not ML_LIBS_AVAILABLE:
        print("Error: ML libraries (sklearn, tensorflow) not available for preprocess_data.")
        return None, None, None
    if df is None or df.empty:
        print("Error: Input DataFrame is empty or None for preprocessing.")
        return None, None, None

    print(f"Starting preprocessing. Initial data shape: {df.shape}")

    # --- 1. Feature Selection ---
    # Select relevant features. For now, use all columns available after loading.
    # A more sophisticated approach might involve feature engineering or selection based on importance.
    # Ensure target_column is present.
    if target_column not in df.columns:
        print(f"Error: Target column '{target_column}' not found in DataFrame.")
        return None, None, None

    features_df = df.copy()
    # print(f"DEBUG: Columns before NaN handling: {features_df.columns.tolist()}")
    # print(f"DEBUG: NaN summary before handling: {features_df.isnull().sum()}")


    # --- 2. Handle Missing Values ---
    # Technical indicators often have NaNs at the beginning.
    # Forward fill might be appropriate for time series, then drop any rows that still have NaNs,
    # especially if the target column is NaN.
    features_df.ffill(inplace=True)
    # Drop rows where the target variable is still NaN after ffill (important!)
    features_df.dropna(subset=[target_column], inplace=True)
    # Drop any other rows that might still contain NaNs in other feature columns
    features_df.dropna(inplace=True)

    if features_df.empty:
        print("Error: DataFrame became empty after handling NaNs. Not enough data or too many initial NaNs.")
        return None, None, None

    print(f"Data shape after NaN handling: {features_df.shape}")

    # --- 3. Scale Features ---
    # Using all columns in features_df for scaling for now
    scaler = MinMaxScaler(feature_range=(0, 1))
    # Note: Ideally, scaler should be fit ONLY on training data.
    # For simplicity in this function now, fitting on all data. This will be refined when train/test split is done *before* preprocessing.
    scaled_data = scaler.fit_transform(features_df)

    # --- 4. Create Sequences ---
    X = []
    y = []

    # Find the index of the target column in the scaled_data array (after features_df was used for scaling)
    # This assumes features_df columns directly map to scaled_data columns.
    target_col_index = features_df.columns.get_loc(target_column)

    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i-sequence_length:i, :]) # All features for the sequence
        y.append(scaled_data[i, target_col_index])    # Only the target column's value at time i

    if not X: # If not enough data to create any sequences
        print(f"Error: Not enough data (after NaN handling and scaling) to create sequences of length {sequence_length}. Data length: {len(scaled_data)}")
        return None, None, None

    X, y = np.array(X), np.array(y)

    # Reshape X to be 3D [samples, time steps, features] as expected by LSTM
    # X = np.reshape(X, (X.shape[0], X.shape[1], X.shape[2])) # X is already 3D if created as list of 2D arrays

    print(f"Preprocessing complete. X shape: {X.shape}, y shape: {y.shape}")
    return X, y, scaler

def build_lstm_model(input_shape, lstm_units=50, dropout_rate=0.2, optimizer='adam', loss='mean_squared_error'):
    """
    Builds a basic LSTM model for price prediction.
    input_shape: (sequence_length, num_features)
    """
    if not ML_LIBS_AVAILABLE:
        print("Error: TensorFlow Keras not available for build_lstm_model.")
        return None

    model = Sequential()

    # First LSTM layer
    # input_shape is (timesteps, features) which is (sequence_length, num_features_in_X)
    model.add(LSTM(units=lstm_units, return_sequences=True, input_shape=input_shape))
    model.add(Dropout(dropout_rate))

    # Second LSTM layer (optional, can add more or remove)
    # No need to specify input_shape for subsequent LSTM layers if return_sequences=True in previous
    model.add(LSTM(units=lstm_units, return_sequences=False)) # return_sequences=False as it's before Dense
    model.add(Dropout(dropout_rate))

    # Dense output layer
    model.add(Dense(units=1)) # Predicting a single value (e.g., next close price)

    model.compile(optimizer=optimizer, loss=loss)

    print("LSTM model built successfully.")
    return model
# --- End Placeholder ---

def main():
    parser = argparse.ArgumentParser(description="Load data, preprocess, and train/evaluate an LSTM model for price prediction.")

    # Database connection arguments
    parser.add_argument('--db_host', default=os.getenv('DB_HOST', 'localhost'), help='Database host.')
    parser.add_argument('--db_port', default=os.getenv('DB_PORT', '5432'), help='Database port.')
    parser.add_argument('--db_user', default=os.getenv('DB_USER'), help='Database user.')
    parser.add_argument('--db_password', default=os.getenv('DB_PASSWORD'), help='Database password.')
    parser.add_argument('--db_name', default=os.getenv('DB_NAME', 'crypto_data'), help='Database name.')

    # Data selection arguments
    parser.add_argument('--symbol', type=str, required=True, help='Asset symbol (e.g., bitcoin or BTCUSDT) to fetch data for.')
    parser.add_argument('--start_date', type=str, default=(datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d'), help='Start date for data loading (YYYY-MM-DD). Defaults to 3 years ago.')
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'), help='End date for data loading (YYYY-MM-DD). Defaults to today.')

    # Preprocessing and Model arguments
    parser.add_argument('--sequence_length', type=int, default=60, help='Length of input sequences for LSTM.')
    parser.add_argument('--target_column', type=str, default='close', help='The column to predict.')
    parser.add_argument('--epochs', type=int, default=1, help='Number of epochs for training (minimal for testing pipeline).') # Default 1 for initial test
    parser.add_argument('--batch_size', type=int, default=1, help='Batch size for training (minimal for testing pipeline).') # Default 1 for initial test

    args = parser.parse_args()

    if not DB_AVAILABLE:
        print("Error: psycopg2 library is not installed. Database operations cannot proceed.")
        sys.exit(1)
    if not ML_LIBS_AVAILABLE:
        print("Error: TensorFlow or Scikit-learn not installed. ML operations cannot proceed. (Continuing for non-ML tests)")
        # sys.exit(1) # Temporarily allow script to continue for testing data loading

    if not args.db_password and not os.getenv('DB_PASSWORD'):
        print("Error: Database password not provided via CLI (--db_password) or .env file (DB_PASSWORD).")
        sys.exit(1)

    print("AI Price Predictor script started.")
    print(f"Args: {args}")

    conn = None
    try:
        print(f"Attempting DB connection with: Host={args.db_host}, Port={args.db_port}, User={args.db_user}, DB={args.db_name}")
        conn = get_db_connection(args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)
        if conn is None:
            print("Failed to connect to the database. Exiting.")
            sys.exit(1)

        asset_id = get_asset_id(conn, args.symbol)
        if not asset_id:
            print(f"Asset ID for symbol {args.symbol} not found. Exiting.")
            sys.exit(1)

        print(f"Loading data for asset_id: {asset_id} ({args.symbol}) from {args.start_date} to {args.end_date}...")
        df_raw = load_asset_data(conn, asset_id, args.start_date, args.end_date)

        if df_raw is None or df_raw.empty:
            print("No data loaded. Exiting.")
            sys.exit(1)

        print("Data loaded successfully. First 5 rows:")
        print(df_raw.head())
        print(f"Data shape: {df_raw.shape}")
        print(f"Data columns: {df_raw.columns.tolist()}")

        nan_summary = df_raw.isnull().sum()
        print(f"NaN summary:\n{nan_summary[nan_summary > 0]}") # Print only columns with NaNs

        print(f"Preprocessing data with sequence length {args.sequence_length}...")
        X, y, scaler = preprocess_data(df_raw, args.sequence_length, args.target_column)

        if X is None or y is None:
            print("Data preprocessing failed. Exiting.")
            sys.exit(1)

        if X.shape[0] == 0:
           print("Not enough data to create sequences after preprocessing. Exiting.")
           sys.exit(1)

        print(f"X sample (first sequence, first 3 steps):\n{X[0][:3]}")
        print(f"y sample (first 3 values):\n{y[:3]}")

        # --- Train/Validation Split ---
        if X.shape[0] < 2: # Need at least 2 samples to split and train/validate
            print("Error: Not enough samples generated by preprocessing to perform a train/validation split. Exiting.")
            sys.exit(1)

        train_split_idx = int(X.shape[0] * 0.8)

        if train_split_idx == 0 or train_split_idx == X.shape[0]:
            print(f"Warning: Train/validation split resulted in an empty set for train or validation (train_split_idx: {train_split_idx}, total_samples: {X.shape[0]}). Adjusting to ensure both sets are non-empty if possible, or exiting if not enough data.")
            if X.shape[0] >= 2:
                train_split_idx = X.shape[0] - 1
            else:
                print("Error: Still not enough data for a meaningful train/val split. Exiting.")
                sys.exit(1)

        X_train, X_val = X[:train_split_idx], X[train_split_idx:]
        y_train, y_val = y[:train_split_idx], y[train_split_idx:]

        if X_train.shape[0] == 0 or X_val.shape[0] == 0:
            print(f"Error: Train or validation set is empty after split. X_train shape: {X_train.shape}, X_val shape: {X_val.shape}. Exiting.")
            sys.exit(1)

        print(f"Data successfully split. Shapes: X_train: {X_train.shape}, y_train: {y_train.shape}, X_val: {X_val.shape}, y_val: {y_val.shape}")
        # ---------------------------------------------------------------------------

        print("Building LSTM model...")
        if X_train.ndim == 3 and X_train.shape[1] > 0 and X_train.shape[2] > 0:
            model_input_shape = (X_train.shape[1], X_train.shape[2]) # Use X_train's shape
            model = build_lstm_model(model_input_shape)
            if model:
                model.summary()

                # Basic Model Training Call
                if ML_LIBS_AVAILABLE: # Check again, in case it was only mocked for earlier stages
                    print(f"Starting model training for {args.epochs} epoch(s) with batch_size {args.batch_size} (minimal test run)...")
                    try:
                        history = model.fit(
                            X_train, y_train,
                            epochs=args.epochs,
                            batch_size=args.batch_size,
                            validation_data=(X_val, y_val),
                            verbose=1
                        )
                        print("Model training finished (minimal test run).")
                        # print(f"Validation loss: {history.history['val_loss'][-1]}")
                    except Exception as e:
                        print(f"An error occurred during model training: {e}")
                else:
                    print("Skipping model training as ML libraries are not available (re-check).")
            else:
                print("Failed to build LSTM model. Skipping training.")
        else:
            print(f"Error: X_train has an invalid shape for model building: {X_train.shape}. Cannot determine input_shape.")
            model = None

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

    print("AI Price Predictor script finished.")

if __name__ == "__main__":
    main()
