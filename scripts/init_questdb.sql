-- QuestDB Initialization Script
-- Optimized for HMM and Hawkes Process Training
-- High-performance Time-series Storage
CREATE TABLE IF NOT EXISTS market_ticks (
    timestamp TIMESTAMP,
    symbol SYMBOL INDEX,
    price DOUBLE,
    volume DOUBLE,
    side SYMBOL,
    hawkes_intensity DOUBLE,
    llm_sentiment_score FLOAT
) TIMESTAMP(timestamp) PARTITION BY DAY WAL;
-- The `PARTITION BY DAY WAL` ensures Write-Ahead Logging is active,
-- allowing concurrent ingestion and microsecond-level querying.
