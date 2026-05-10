{{ config(
    materialized='view',
    tags=['silver', 'reviews'],
    meta={
        'layer': 'silver',
        'domain': 'reviews'
    }
) }}

-- One row per order_id: summarize review quantity and score quality.

select
    order_id,
    count(*) as review_count,
    round(avg(review_score), 2) as average_review_score,
    max(review_score) as max_review_score,
    min(review_score) as min_review_score
from {{ ref('stg_order_reviews') }}
group by 1
