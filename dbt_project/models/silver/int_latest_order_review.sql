{{ config(
    materialized='view',
    tags=['silver', 'reviews'],
    meta={
        'layer': 'silver',
        'domain': 'reviews'
    }
) }}

-- One row per order_id: keep the latest available review score.

select
    order_id,
    review_score
from (
    select
        order_id,
        review_score,
        row_number() over (
            partition by order_id
            order by review_creation_date desc nulls last, review_id desc
        ) as row_num
    from {{ ref('stg_order_reviews') }}
) ranked
where row_num = 1
