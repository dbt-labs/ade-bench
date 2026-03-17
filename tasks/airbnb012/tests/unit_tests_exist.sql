-- Fails if no unit tests were defined for the NPS models.
-- check_unit_tests.py (run in test_setup) writes the unit_test_manifest table.

WITH counts AS (
  SELECT
    model_name,
    COUNT(*) AS test_count
  FROM unit_test_manifest
  WHERE model_name IN ('listing_agg_nps_reviews', 'daily_agg_nps_reviews')
  GROUP BY model_name
),
models AS (
  SELECT model_name
  FROM (VALUES
    ('listing_agg_nps_reviews'),
    ('daily_agg_nps_reviews')
  ) t(model_name)
)
SELECT
  m.model_name,
  'No unit tests defined for model' AS reason
FROM models m
LEFT JOIN counts c USING (model_name)
WHERE COALESCE(c.test_count, 0) = 0
