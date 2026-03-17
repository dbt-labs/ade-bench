-- Fails if the agent's unit tests did NOT catch a logic bug in a broken model variant.
-- run_broken_model_tests.py (run in test_setup) writes the broken_model_results table.

SELECT
  variant_id,
  model_name,
  'Unit tests failed to detect injected bug' AS reason
FROM broken_model_results
WHERE caught_bug = FALSE
