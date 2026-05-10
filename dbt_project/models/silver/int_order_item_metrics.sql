{{ config(
    materialized='view',
    tags=['silver', 'orders'],
    meta={
        'layer': 'silver',
        'domain': 'orders'
    }
) }}

-- One row per order_id: aggregate line-item level sales metrics.

select
    order_id,
    min(product_id) as primary_product_id,
    min(seller_id) as primary_seller_id,
    count(*) as item_count,
    count(distinct product_id) as distinct_product_count,
    count(distinct seller_id) as distinct_seller_count,
    sum(price) as gross_item_amount,
    sum(freight_value) as freight_amount,
    sum(item_total_amount) as total_amount
from {{ ref('stg_order_items') }}
group by 1
