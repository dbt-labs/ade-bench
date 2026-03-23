{{
    config(
        materialized="table",
        alias="daily_agg_nps_reviews",
        schema="main"
    )
}}

with with_nps_scores as (
  select
    *,
    case
      when review_sentiment = 'positive' then 1
      when review_sentiment = 'negative' then -1
      else 0 end as nps_score
  from {{ ref('fct_reviews') }}
),

daily as (
  select
    review_date,
    count(case when nps_score = 1 then 1 else null end) as positive,
    count(case when nps_score = -1 then 1 else null end) as negative,
    count(case when nps_score = 0 then 1 else null end) as neutral,
    count(*) as reviews_daily,
    (positive + neutral - negative)::FLOAT / reviews_daily as nps_daily
  from with_nps_scores
  group by 1
),

rolling as (
  select
    review_date,
    nps_daily,
    reviews_daily,
    sum(positive) over (order by review_date range between interval '27 day' preceding and current row) as positive_28d,
    sum(negative) over (order by review_date range between interval '27 day' preceding and current row) as negative_28d,
    sum(reviews_daily) over (order by review_date range between interval '27 day' preceding and current row) as reviews_28d,
    (positive_28d - negative_28d)::FLOAT / reviews_28d as nps_28d
  from daily
)

select
  review_date,
  round(nps_daily * 100, 0) as nps_daily,
  reviews_daily,
  round(nps_28d * 100, 0) as nps_28d,
  reviews_28d
from rolling
