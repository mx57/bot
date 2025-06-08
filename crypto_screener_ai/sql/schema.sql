-- Schema for AI Crypto Screener Database

-- Ensure the TimescaleDB extension is available.
-- This should be run after connecting to your target database (e.g., crypto_data).
-- CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Table for storing asset metadata
CREATE TABLE IF NOT EXISTS assets (
    asset_id SERIAL PRIMARY KEY,
    symbol TEXT UNIQUE NOT NULL,     -- e.g., BTCUSDT (for Binance), bitcoin (for CoinGecko)
    name TEXT,                       -- e.g., Bitcoin
    source TEXT                      -- e.g., coingecko, binance
    -- Add other relevant metadata like description, category, etc. later if needed
);

-- Hypertable for storing OHLCV price data
CREATE TABLE IF NOT EXISTS price_data (
    time TIMESTAMPTZ NOT NULL,
    asset_id INTEGER NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION NOT NULL, -- Close price is mandatory
    volume DOUBLE PRECISION,
    CONSTRAINT fk_asset
        FOREIGN KEY(asset_id)
        REFERENCES assets(asset_id)
        ON DELETE CASCADE, -- If an asset is deleted, its price data is also deleted
    PRIMARY KEY (asset_id, time) -- Composite primary key
);

-- Convert price_data to a TimescaleDB hypertable, partitioned by time
-- This command should be run AFTER the table is created.
-- Note: chunk_time_interval can be adjusted based on data volume and query patterns.
-- For example, 7 days is a common interval.
SELECT create_hypertable('price_data', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');

-- Optional: Add indexes for frequently queried columns
CREATE INDEX IF NOT EXISTS idx_price_data_asset_id_time ON price_data (asset_id, time DESC);
-- For CoinGecko data that might only have 'close', we still define the full OHLCV structure.
-- The application layer will handle inserting NULLs for missing OHLCV fields if necessary.


-- Hypertable for storing calculated technical indicators
CREATE TABLE IF NOT EXISTS technical_indicators (
    time TIMESTAMPTZ NOT NULL,
    asset_id INTEGER NOT NULL,
    indicator_name TEXT NOT NULL,    -- e.g., 'SMA_20', 'RSI_14', 'MACD_line'
    value DOUBLE PRECISION NOT NULL,
    CONSTRAINT fk_asset_indicator
        FOREIGN KEY(asset_id)
        REFERENCES assets(asset_id)
        ON DELETE CASCADE,
    PRIMARY KEY (asset_id, time, indicator_name) -- Composite primary key
);

-- Convert technical_indicators to a TimescaleDB hypertable
SELECT create_hypertable('technical_indicators', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');

-- Optional: Add indexes
CREATE INDEX IF NOT EXISTS idx_technical_indicators_asset_id_time ON technical_indicators (asset_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_name ON technical_indicators (indicator_name);


/*
-- Alternative Schema for Technical Indicators: Wide Format
-- If you prefer to have indicators as separate columns in a single table joined with price_data.
-- This might be simpler if the set of indicators is fixed and always calculated together.
-- However, the "long format" (key-value pair as above) is more flexible if you plan to add many diverse indicators
-- or allow users to define their own.

CREATE TABLE IF NOT EXISTS price_and_indicators (
    time TIMESTAMPTZ NOT NULL,
    asset_id INTEGER NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    sma_20 DOUBLE PRECISION,
    rsi_14 DOUBLE PRECISION,
    macd_line DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_hist DOUBLE PRECISION,
    -- Add more indicator columns here as needed
    CONSTRAINT fk_asset_price_indicator
        FOREIGN KEY(asset_id)
        REFERENCES assets(asset_id)
        ON DELETE CASCADE,
    PRIMARY KEY (asset_id, time)
);

SELECT create_hypertable('price_and_indicators', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_price_indicators_asset_id_time ON price_and_indicators (asset_id, time DESC);
*/

-- Consider adding tables for:
-- - News/Sentiment Data
-- - On-chain Metrics
-- - User Settings / Portfolios
-- as the project evolves.
```
