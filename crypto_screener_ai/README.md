# AI Crypto Screener

This project is an AI-powered cryptocurrency screener designed to provide automated analysis of the crypto market, including trend prediction, risk assessment, and trading signal generation.

## Project Goal

To create a comprehensive tool for traders, investors, and analysts that combines multi-modal data analysis with actionable tactical recommendations.

## Modules

The project is structured into the following main modules:

*   **Data Collection (`data_collection/`)**: Responsible for gathering data from various sources (e.g., crypto exchanges, on-chain analytics platforms, news feeds).
*   **Analysis Modules (`analysis_modules/`)**: Contains scripts for technical analysis, fundamental analysis, sentiment analysis, etc.
*   **AI Core (`ai_core/`)**: Houses the machine learning models for price prediction, asset correlation, and risk/reward ranking.
*   **API (`api/`)**: Provides a REST API for interacting with the system and integrating with external tools or trading bots.
*   **UI (`ui/`)**: (Future Scope) Will contain the web interface for visualizing data and interacting with the screener.

## Getting Started

### Prerequisites

*   Python 3.8+
*   pip (Python package installer)

### Setup and Installation

1.  **Clone the repository (if applicable, otherwise create the project directory manually):**
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

### Running the Data Collection Script

To fetch sample data (e.g., Bitcoin prices for the last 7 days from CoinGecko):

1.  Navigate to the data collection directory:
    ```bash
    cd data_collection
    ```

2.  Run the `fetch_data.py` script:
    ```bash
    python fetch_data.py
    ```
    This will create a JSON file (e.g., `bitcoin_usd_7_days_data.json`) in the `data_collection` directory containing the fetched price data.

## Future Development

This project is under active development. Future enhancements will include:
*   Implementation of more data sources.
*   Development of advanced analytical modules.
*   Training and integration of AI/ML models.
*   Building a user-friendly web interface.
