# AI Crypto Screener

This project is an AI-powered cryptocurrency screener designed to provide automated analysis of the crypto market, including trend prediction, risk assessment, and trading signal generation.

## Project Goal

To create a comprehensive tool for traders, investors, and analysts that combines multi-modal data analysis with actionable tactical recommendations.

## Modules

The project is structured into the following main modules:

*   **Data Collection (`data_collection/`)**: Responsible for gathering data from various sources. Currently supports:
    *   CoinGecko API for historical price data.
    *   Binance API for historical OHLCV (Open, High, Low, Close, Volume) kline data.
    The `fetch_data.py` script uses command-line arguments and environment variables (via an `.env` file) to specify the data source, asset identifiers, date ranges, API keys, database credentials, and output options.

*   **Analysis Modules (`analysis_modules/`)**: Contains scripts for data analysis. Currently includes:
    *   `technical_analyzer.py`: Calculates a suite of common technical indicators from price data. Data can be loaded from the database or a JSON file, and results can be saved back to the database (long format) or a JSON file (wide format). Configuration is managed via CLI arguments and environment variables.
    *   `fundamental_analyzer.py`: Fetches and stores detailed fundamental data for cryptocurrencies (e.g., market cap, supply, description, social links) from sources like CoinGecko. Configuration is managed via CLI arguments and environment variables.

*   **AI Core (`ai_core/`)**:
    *   **Prediction (`ai_core/prediction/`)**: Houses machine learning models for price prediction.
        *   `price_predictor.py`: Loads historical price and indicator data, preprocesses it for time-series forecasting, and defines/trains a basic LSTM model for price prediction.

*   **API (`api/`)**: (Future Scope) Provides a REST API for interacting with the system and integrating with external tools or trading bots.
*   **UI (`ui/`)**: (Future Scope) Will contain the web interface for visualizing data and interacting with the screener.
*   **Database (`docs/database_setup.md`, `sql/schema.sql`)**: PostgreSQL with TimescaleDB extension is used for data storage. Setup instructions and schema are provided.
*   **Common Utilities (`common/`)**: Contains shared utility modules, such as `db_utils.py` for database connection handling.

## Getting Started

### Prerequisites

*   Python 3.8+
*   pip (Python package installer)
*   Docker (for database setup as per `docs/database_setup.md`)

### Key Dependencies

The `requirements.txt` file manages all Python dependencies. Key libraries include:
*   `requests`: For general HTTP requests (used by CoinGecko fetcher).
*   `python-binance`: For Binance API interaction.
*   `pandas`: For data manipulation and analysis.
*   `numpy`: For numerical operations (often a pandas dependency).
*   `ta`: For calculating technical indicators.
*   `psycopg2-binary`: For PostgreSQL database interaction.
*   `python-dotenv`: For loading environment variables from an `.env` file.
*   `scikit-learn`: For machine learning utilities (e.g., data scaling).
*   `tensorflow` (or `tensorflow-cpu`): For building and training deep learning models (LSTM).

### Configuration

Sensitive information such as database credentials and API keys are managed using environment variables, typically loaded from an `.env` file located in the project root (`crypto_screener_ai/.env`).

**Setup:**

1.  **Create your `.env` file:** Copy the example file to `.env`:
    ```bash
    cp .env.example .env
    ```
2.  **Edit `.env`:** Open the `.env` file and fill in your actual database connection details (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME) and any API keys (e.g., BINANCE_API_KEY, BINANCE_API_SECRET) you intend to use.

The `.env` file is listed in `.gitignore` and should **not** be committed to your version control system.

**Credential Precedence:**
The scripts will prioritize credentials in the following order:
1.  Command-line arguments (if provided for a specific parameter).
2.  Environment variables (loaded from your `.env` file).
3.  Default values specified in the scripts (e.g., for `DB_HOST='localhost'`, `DB_PORT=5432`. Note: Passwords and secret keys generally do not have hardcoded defaults and must be provided via CLI or `.env` if the related service is used).

### Setup and Installation

1.  **Clone the repository (if applicable, otherwise ensure you are in the `crypto_screener_ai` project directory):**
    ```bash
    # git clone <repository_url> # If you have a git repo
    # cd crypto_screener_ai
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Database Integration

This project now supports PostgreSQL with the TimescaleDB extension for robust data storage and time-series analysis. Connection parameters are configured via CLI arguments or an `.env` file as described in the "Configuration" section.

The database schema (defined in `sql/schema.sql`) includes the following key tables:
*   `assets`: Stores metadata about each cryptocurrency asset.
*   `price_data` (hypertable): Stores time-series OHLCV price data.
*   `technical_indicators` (hypertable): Stores calculated technical indicator values.
*   `asset_fundamentals`: Stores detailed fundamental data for each asset (market cap, supply, description, links, etc.).

#### Database Setup

1.  **Environment Setup**: For detailed instructions on setting up a local PostgreSQL + TimescaleDB instance using Docker, please refer to the [Database Setup Guide](docs/database_setup.md).
2.  **Schema Initialization**: Once your database is running and the TimescaleDB extension is enabled (as per the setup guide), apply the schema by executing the commands in [sql/schema.sql](sql/schema.sql) against your target database.
    ```bash
    # Example using psql, assuming your database is named 'crypto_data' and user 'postgres'
    # psql -h localhost -U postgres -d crypto_data -f sql/schema.sql
    ```
    *(You might be prompted for the password for the `postgres` user if not set in environment variables like PGPASSWORD or via your local PostgreSQL configuration.)*

### Using the Scripts

#### Data Collection Script (`fetch_data.py`)

The `fetch_data.py` script in the `data_collection` directory allows you to fetch data and store it in the database and/or a JSON file.

**Key CLI Arguments:**
*   `source`: `coingecko` or `binance`.
*   CoinGecko specific: `--coin_id`, `--vs_currency`, `--days`.
*   Binance specific: `--symbol`, `--interval`, `--start_date`, `--end_date`, `--limit`.
*   Binance API: `--binance_api_key`, `--binance_api_secret` (optional, overrides `.env` and script defaults).
*   Database connection: `--db_host`, `--db_port`, `--db_user`, `--db_password`, `--db_name` (optional, overrides `.env` and script defaults).
*   Output control:
    *   `--save_json`: To also save the fetched data to a JSON file.
    *   `--no_db`: To disable saving data to the database. (If DB operations are intended, relevant DB credentials must be available via CLI or `.env`).
    *   `--output_dir`: Specifies directory for JSON files.

**Examples:**
*   See the script's help message for detailed examples: `python data_collection/fetch_data.py --help`
*   **Fetching from CoinGecko (JSON only):**
    ```bash
    python data_collection/fetch_data.py coingecko --coin_id bitcoin --vs_currency usd --days 7 --save_json --no_db --output_dir path/to/your_json_output_dir/
    ```
*   **Fetching from Binance and saving to Database:**
    ```bash
    # Assumes .env is configured for DB and Binance API keys
    python data_collection/fetch_data.py binance --symbol BTCUSDT --interval 1h --limit 100
    ```
    **Note on API Keys:** For Binance, ensure `BINANCE_API_KEY` and `BINANCE_API_SECRET` are set in your `.env` file or passed via CLI.

#### Technical Analyzer Script (`technical_analyzer.py`)

Loads price data (from DB or JSON), calculates a range of technical indicators, and saves them (to DB and/or JSON).

**Key CLI Arguments:**
*   `--symbol <asset_symbol>`: Asset symbol for DB operations.
*   `--input_json_file <path>`: Path to load data from JSON.
*   `--no_db_input`: If set, data must be loaded from `--input_json_file`.
*   Database connection args (optional, override `.env`).
*   Data filtering for DB: `--start_date`, `--end_date`, `--limit`.
*   `--output_json_file <path>`: Path to save output as JSON.
*   `--no_db_output`: Disables saving indicators to DB. (If DB operations are intended, relevant DB credentials must be available).

**Key Indicators Calculated:** (See script help for full list and `technical_analyzer.py` for details)
*   SMA, RSI, MACD, Bollinger Bands, Ichimoku Cloud, VWAP, Stochastic Oscillator, ATR.
*   **Note on Data Requirements:** Full OHLCV data (e.g., from Binance) is recommended for accuracy of many indicators. The script issues warnings for missing/dummy data.

**Examples:**
*   See the script's help message for detailed examples: `python analysis_modules/technical_analyzer.py --help`
*   **JSON in, JSON out (DB disabled):**
    ```bash
    python analysis_modules/technical_analyzer.py --input_json_file path/to/input.json --output_json_file path/to/output.json --no_db_input --no_db_output
    ```
*   **DB in, DB out (and JSON out):**
    ```bash
    # Assumes .env is configured for DB
    python analysis_modules/technical_analyzer.py --symbol BTCUSDT --limit 1000 --output_json_file path/to/output.json
    ```

#### Fundamental Analyzer Script (`fundamental_analyzer.py`)

This script fetches detailed fundamental data for specified cryptocurrencies from CoinGecko and stores it in the `asset_fundamentals` database table.

**Key Command-Line Arguments:**
*   `--symbol <coingecko_id>`: Fetches fundamental data for the specified CoinGecko ID (e.g., `bitcoin`). Assumes this ID matches a `symbol` in your `assets` table.
*   `--all-assets`: Iterates through assets in your `assets` table to fetch their fundamental data. (Assumes symbols are valid CoinGecko IDs).
*   Database arguments (`--db_host`, etc.): Optional if set in your `.env` file. Database connection is required.

**Examples:**
*   See the script's help message for detailed examples: `python analysis_modules/fundamental_analyzer.py --help`
*   **Fetch for a single asset (DB configured in `.env`):**
    ```bash
    python analysis_modules/fundamental_analyzer.py --symbol bitcoin
    ```
*   **Fetch for all assets (DB configured in `.env`):**
    ```bash
    python analysis_modules/fundamental_analyzer.py --all-assets
    ```

#### AI Price Predictor Script (`price_predictor.py`)

This script provides an initial implementation of an LSTM-based model for cryptocurrency price prediction. It handles data loading from the database (price data + indicators), preprocessing, model building, and a basic training loop.

**Prerequisites for ML:**
*   Ensure TensorFlow and Scikit-learn are installed (these are in `requirements.txt`).
*   A populated database with price data and technical indicators for the assets you wish to model.

**Key Command-Line Arguments:**
*   `--symbol <asset_symbol>`: **Required.** The symbol of the asset to model (must exist in your `assets` table).
*   `--start_date <YYYY-MM-DD>`: Start date for loading historical data (default: 3 years ago).
*   `--end_date <YYYY-MM-DD>`: End date for loading historical data (default: today).
*   `--sequence_length <int>`: Length of input sequences for LSTM (default: 60).
*   `--target_column <col_name>`: Data column to predict (default: 'close').
*   `--epochs <int>`: Training epochs (default: 1).
*   `--batch_size <int>`: Training batch size (default: 1).
*   Database arguments (`--db_host`, etc.): Optional if set in `.env` file.

**Example:**
*   See the script's help message for detailed examples: `python ai_core/prediction/price_predictor.py --help`
*   **Run prediction pipeline for Bitcoin (DB configured in `.env`):**
    ```bash
    python ai_core/prediction/price_predictor.py --symbol bitcoin --epochs 5
    ```
    *(This loads data, preprocesses, builds an LSTM model, prints summary, and trains for 5 epochs.)*

## Future Development

This project is under active development. Future enhancements will include:
*   Implementation of more data sources and analytical modules.
*   Development and integration of AI/ML models for prediction and ranking.
*   Building a user-friendly web interface for visualization and interaction.
```
