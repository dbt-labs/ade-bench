-- Fails if fct_reviews row count doesn't match the non-null source rows.
-- The broken model drops 5 injected reviews; the fix must capture all of them.

WITH source AS (
  SELECT COUNT(*) AS cnt FROM raw_reviews WHERE comments IS NOT NULL
),
actual AS (
  SELECT COUNT(*) AS cnt FROM fct_reviews
)
SELECT
  source.cnt AS expected,
  actual.cnt AS got,
  'fct_reviews is missing rows from source' AS reason
FROM source, actual
WHERE source.cnt != actual.cnt
