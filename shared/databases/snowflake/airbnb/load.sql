COPY RAW_HOSTS FROM '/Users/benn/local/code/ade-bench/shared/databases/snowflake/airbnb/raw_hosts.parquet' (FORMAT 'parquet', COMPRESSION 'ZSTD');
COPY RAW_LISTINGS FROM '/Users/benn/local/code/ade-bench/shared/databases/snowflake/airbnb/raw_listings.parquet' (FORMAT 'parquet', COMPRESSION 'ZSTD');
COPY RAW_REVIEWS FROM '/Users/benn/local/code/ade-bench/shared/databases/snowflake/airbnb/raw_reviews.parquet' (FORMAT 'parquet', COMPRESSION 'ZSTD');
