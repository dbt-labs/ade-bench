COPY RAW_HOSTS FROM '/Users/joel/Documents/GitHub/ade-bench/shared/databases/snowflake/airbnb/raw_hosts.parquet' (FORMAT 'parquet', COMPRESSION 'ZSTD');
COPY RAW_LISTINGS FROM '/Users/joel/Documents/GitHub/ade-bench/shared/databases/snowflake/airbnb/raw_listings.parquet' (FORMAT 'parquet', COMPRESSION 'ZSTD');
COPY RAW_REVIEWS FROM '/Users/joel/Documents/GitHub/ade-bench/shared/databases/snowflake/airbnb/raw_reviews.parquet' (FORMAT 'parquet', COMPRESSION 'ZSTD');
