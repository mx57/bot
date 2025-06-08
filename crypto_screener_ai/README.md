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

*   **AI Core (`ai_core/`)**: (Future Scope) Houses the machine learning models for price prediction, asset correlation, and risk/reward ranking.
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

### Using the Data Collection Script (`fetch_data.py`)

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

*   **Fetching from CoinGecko (JSON only, no DB interaction):**
    ```bash
    python data_collection/fetch_data.py coingecko --coin_id bitcoin --vs_currency usd --days 7 --save_json --no_db --output_dir path/to/your_json_output_dir/
    ```

*   **Fetching from Binance and saving to Database (credentials from `.env` or CLI):**
    ```bash
    # Example assuming .env is configured for DB and Binance API keys:
    python data_collection/fetch_data.py binance --symbol BTCUSDT --interval 1h --limit 100
    # To specify DB credentials and Binance keys via CLI (overrides .env):
    python data_collection/fetch_data.py binance --symbol BTCUSDT --interval 1h --limit 100 \
        --binance_api_key YOUR_KEY --binance_api_secret YOUR_SECRET \
        --db_host myhost --db_user myuser --db_password mypass --db_name mydb
    ```
    **Note on API Keys:** For Binance, ensure `BINANCE_API_KEY` and `BINANCE_API_SECRET` are set in your `.env` file or passed via CLI. The script falls back to non-functional placeholders if keys are not found.

### Using the Technical Analyzer Script (`technical_analyzer.py`)

The `technical_analyzer.py` script in `analysis_modules` loads price data (from DB or JSON), calculates a range of technical indicators, and saves them (to DB and/or JSON).

**Key CLI Arguments:**
*   `--symbol <asset_symbol>`: Asset symbol for DB operations (e.g., 'BTCUSDT' or 'bitcoin'). Required if using DB for input or output unless `--input_json_file` and `--no_db_input` are solely used.
*   `--input_json_file <path>`: Path to load data from JSON. Can act as a fallback if DB input fails.
*   `--no_db_input`: If set, data must be loaded from `--input_json_file`.
*   Database connection: `--db_host`, `--db_port`, `--db_user`, `--db_password`, `--db_name` (optional, overrides `.env` and script defaults).
*   Data filtering (for DB source): `--start_date`, `--end_date`, `--limit`.
*   `--output_json_file <path>`: Path to save output with indicators as JSON.
*   `--no_db_output`: To disable saving indicators to the database. (If DB operations are intended, relevant DB credentials must be available via CLI or `.env`).

**Key Indicators Calculated:**
*   Simple Moving Average (e.g., `SMA_20`)
*   Relative Strength Index (e.g., `RSI_14`)
*   Moving Average Convergence Divergence (`MACD_line`, `MACD_signal`, `MACD_hist`)
*   Bollinger Bands (`bb_bbm`, `bb_bbh`, `bb_bbl`)
*   Ichimoku Cloud (`ichimoku_conv`, `ichimoku_base`, `ichimoku_a`, `ichimoku_b`, `ichimoku_lag`) - *Requires sufficient data length (e.g., >52 periods for default settings) and full OHLC data.*
*   Volume Weighted Average Price (`vwap`) - *Requires volume data; will be null if volume is zero or unavailable.*
*   Stochastic Oscillator (`stoch_k`, `stoch_d`) - *Requires full OHLC data.*
*   Average True Range (`atr`) - *Requires full OHLC data.*

**Note on Data Requirements:**
While the script can process data containing only 'close' prices (e.g., from CoinGecko, where OHL data is duplicated from Close and Volume is 0), for the most accurate and meaningful calculations, especially for indicators like Ichimoku Cloud, VWAP, Stochastic Oscillator, and ATR, it is highly recommended to use input data that includes complete Open, High, Low, Close, and Volume (OHLCV) information (e.g., data fetched from Binance). The script will attempt to calculate all indicators but will print warnings if necessary input columns (like 'volume' for VWAP or distinct OHL for others) are missing, appear to be duplicated from the 'close' price, or if data length is insufficient for an indicator's window. In such cases, the values for affected indicators may be `null` (or `NaN`).

**Examples:**

*   **Loading from JSON, saving indicators to JSON (DB disabled):**
    ```bash
    python analysis_modules/technical_analyzer.py --input_json_file path/to/your_input_data.json --output_json_file path/to_analysis_output/indicators.json --no_db_input --no_db_output
    ```

*   **Loading from DB, calculating indicators, saving back to DB (credentials from `.env` or CLI, also saving JSON):**
    ```bash
    # Example assuming .env is configured for DB:
    python analysis_modules/technical_analyzer.py --symbol BTCUSDT --limit 1000 --output_json_file path/to_analysis_output/btcusdt_indicators.json
    # To specify DB credentials via CLI:
    python analysis_modules/technical_analyzer.py --symbol BTCUSDT --limit 1000 --db_host myhost --db_user myuser --db_password mypass --db_name mydb --output_json_file path/to_analysis_output/btcusdt_indicators.json
    ```

### Using the Fundamental Analyzer Script (`fundamental_analyzer.py`)

This script fetches detailed fundamental data for specified cryptocurrencies from CoinGecko and stores it in the `asset_fundamentals` database table.

**Key Command-Line Arguments:**

*   `--symbol <coingecko_id>`: Fetches fundamental data for the specified CoinGecko ID (e.g., `bitcoin`, `ethereum`). The script assumes this ID also matches a `symbol` in your `assets` table for CoinGecko-sourced assets.
*   `--all-assets`: Iterates through all assets found in your `assets` table and attempts to fetch fundamental data for each, using their `symbol` as the CoinGecko ID. (Note: This currently assumes symbols from your `assets` table are valid CoinGecko IDs, which might need refinement if your `assets` table contains symbols from multiple sources like Binance tickers).
*   Database arguments (`--db_host`, `--db_port`, `--db_user`, `--db_password`, `--db_name`): Specify database connection details. These are optional if corresponding environment variables are set in your `.env` file (e.g., `DB_HOST`, `DB_PASSWORD`). (Database connection is required for this script).

**Examples:**

1.  **Fetch fundamental data for a single asset (e.g., Bitcoin):**
    ```bash
    python analysis_modules/fundamental_analyzer.py --symbol bitcoin
    ```
    *(Ensure DB credentials are in `.env` or provided as CLI arguments)*

2.  **Fetch fundamental data for all assets in the database:**
    ```bash
    python analysis_modules/fundamental_analyzer.py --all-assets
    ```
    *(This will iterate through all assets, respecting API rate limits. It can take a while for many assets.)*

## Future Development

This project is under active development. Future enhancements will include:
*   Implementation of more data sources and analytical modules.
*   Development and integration of AI/ML models for prediction and ranking.
*   Building a user-friendly web interface for visualization and interaction.
```
