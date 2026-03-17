{{
	config(
		materialized="table" ,
		alias="listing_agg_nps_reviews" ,
		schema="main"
	)
}}

with with_nps_scores as (
  select
    listing_id,
    count(case when review_sentiment = 'positive' then 1 else null end) as positive,
    count(case when review_sentiment = 'negative' then 1 else null end) as negative,
    count(*) as reviews_total
  from {{ ref('fct_reviews') }} r
  group by 1
),

final as (
  select
    l.listing_id,
    l.listing_name,
    l.room_type,
    round(((s.positive-s.negative) / s.reviews_total) * 100, 0) as nps_total,
    s.reviews_total,
  from {{ ref('dim_listings') }} l
  join with_nps_scores s
    on s.listing_id = l.listing_id
)

select * from final
