# AI Crypto Screener

This project is an AI-powered cryptocurrency screener designed to provide automated analysis of the crypto market, including trend prediction, risk assessment, and trading signal generation.

## Project Goal

To create a comprehensive tool for traders, investors, and analysts that combines multi-modal data analysis with actionable tactical recommendations.

## Modules

The project is structured into the following main modules:

*   **Data Collection (`data_collection/`)**: Responsible for gathering data from various sources. Currently supports:
    *   CoinGecko API for historical price data.
    *   Binance API for historical OHLCV (Open, High, Low, Close, Volume) kline data.
    The `fetch_data.py` script uses command-line arguments to specify the data source, asset identifiers, date ranges, and output options (database and/or JSON).

*   **Analysis Modules (`analysis_modules/`)**: Contains scripts for data analysis. Currently includes:
    *   `technical_analyzer.py`: Calculates common technical indicators (SMA, RSI, MACD) from price data loaded from the database or a JSON file, and can save results back to the database or a JSON file.

*   **AI Core (`ai_core/`)**: (Future Scope) Houses the machine learning models for price prediction, asset correlation, and risk/reward ranking.
*   **API (`api/`)**: (Future Scope) Provides a REST API for interacting with the system and integrating with external tools or trading bots.
*   **UI (`ui/`)**: (Future Scope) Will contain the web interface for visualizing data and interacting with the screener.
*   **Database (`docs/database_setup.md`, `sql/schema.sql`)**: PostgreSQL with TimescaleDB extension is used for data storage. Setup instructions and schema are provided.

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

This project now supports PostgreSQL with the TimescaleDB extension for robust data storage and time-series analysis.

#### Database Setup

1.  **Environment Setup**: For detailed instructions on setting up a local PostgreSQL + TimescaleDB instance using Docker, please refer to the [Database Setup Guide](docs/database_setup.md).
2.  **Schema Initialization**: Once your database is running and the TimescaleDB extension is enabled (as per the setup guide), apply the schema by executing the commands in [sql/schema.sql](sql/schema.sql) against your target database (e.g., `crypto_data`). You can use `psql` or a database management tool for this.
    ```bash
    # Example using psql, assuming your database is named 'crypto_data' and user 'postgres'
    # psql -h localhost -U postgres -d crypto_data -f sql/schema.sql
    ```
    *(You might be prompted for the password for the `postgres` user)*

### Using the Data Collection Script (`fetch_data.py`)

The `fetch_data.py` script in the `data_collection` directory allows you to fetch data and store it in the database and/or a JSON file.

**Key CLI Arguments:**
*   `source`: `coingecko` or `binance`.
*   CoinGecko specific: `--coin_id`, `--vs_currency`, `--days`.
*   Binance specific: `--symbol`, `--interval`, `--start_date`, `--end_date`, `--limit`.
*   Database connection: `--db_host`, `--db_port`, `--db_user`, `--db_password`, `--db_name`.
*   Output control:
    *   `--save_json`: To also save the fetched data to a JSON file.
    *   `--no_db`: To disable saving data to the database.
    *   `--output_dir`: Specifies directory for JSON files (default: `crypto_screener_ai/data_collection/`).

**Examples:**

*   **Fetching from CoinGecko and saving to JSON only:**
    ```bash
    python data_collection/fetch_data.py coingecko --coin_id bitcoin --vs_currency usd --days 7 --save_json --no_db --output_dir data_collection_output/
    ```

*   **Fetching from Binance and saving to Database (and optionally JSON):**
    ```bash
    # Ensure API keys are set in fetch_data.py for Binance
    python data_collection/fetch_data.py binance --symbol BTCUSDT --interval 1h --limit 100 --db_host localhost --db_user youruser --db_password yourpass --db_name crypto_data
    # To also save a JSON copy:
    python data_collection/fetch_data.py binance --symbol BTCUSDT --interval 1h --limit 100 --db_host localhost --db_user youruser --db_password yourpass --db_name crypto_data --save_json --output_dir data_collection_output/
    ```
    **Note on Binance API Keys:** For the Binance data source, replace placeholder API keys in `data_collection/fetch_data.py` with your actual credentials.

### Using the Technical Analyzer Script (`technical_analyzer.py`)

The `technical_analyzer.py` script in `analysis_modules` loads price data (from DB or JSON), calculates technical indicators (SMA, RSI, MACD), and saves them (to DB and/or JSON).

**Key CLI Arguments:**
*   `--symbol`: Asset symbol for DB operations (required if using DB input without `--no_db_input`).
*   `--input_json_file`: Path to load data from JSON.
*   `--no_db_input`: If set, data must be from `--input_json_file`.
*   Database connection: `--db_host`, `--db_port`, `--db_user`, `--db_password`, `--db_name`.
*   Data filtering (for DB source): `--start_date`, `--end_date`, `--limit`.
*   `--output_json_file`: Path to save output with indicators as JSON.
*   `--no_db_output`: To disable saving indicators to the database.

**Examples:**

*   **Loading from JSON, saving indicators to JSON (DB disabled):**
    ```bash
    python analysis_modules/technical_analyzer.py --input_json_file data_collection_output/bitcoin_usd_7_days_coingecko_data.json --output_json_file analysis_output/bitcoin_indicators.json --no_db_input --no_db_output
    ```

*   **Loading from DB, calculating indicators, saving back to DB (and optionally JSON):**
    ```bash
    # Calculates indicators for BTCUSDT using last 1000 records from DB, saves indicators to DB
    python analysis_modules/technical_analyzer.py --symbol BTCUSDT --db_host localhost --db_user youruser --db_password yourpass --db_name crypto_data --limit 1000
    # Same as above, but also saves a JSON output
    python analysis_modules/technical_analyzer.py --symbol BTCUSDT --db_host localhost --db_user youruser --db_password yourpass --db_name crypto_data --limit 1000 --output_json_file analysis_output/btcusdt_indicators.json
    ```

## Future Development

This project is under active development. Future enhancements will include:
*   Implementation of more data sources and analytical modules.
*   Development and integration of AI/ML models for prediction and ranking.
*   Building a user-friendly web interface for visualization and interaction.
```
