-- Fails if any of the 5 injected same-date reviews are missing from fct_reviews.
-- The broken > filter drops them; the fixed >= filter captures them.

WITH injected (listing_id, review_date, reviewer_name) AS (
  VALUES
    (706237,  DATE '2021-10-22', 'Klaus'),
    (869793,  DATE '2021-10-22', 'Sabine'),
    (2201228, DATE '2021-10-22', 'Michael'),
    (4110390, DATE '2021-10-22', 'Laura'),
    (5040353, DATE '2021-10-22', 'Thomas')
)
SELECT i.listing_id, i.review_date, i.reviewer_name
FROM injected i
WHERE NOT EXISTS (
  SELECT 1
  FROM fct_reviews f
  WHERE f.listing_id    = i.listing_id
    AND f.review_date   = i.review_date
    AND f.reviewer_name = i.reviewer_name
)
