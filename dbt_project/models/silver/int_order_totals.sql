{{ config(
    materialized='view',
    tags=['silver', 'orders'],
    meta={
        'layer': 'silver',
        'domain': 'orders'
    }
) }}

-- One row per order_id: total commercial value from all order items.

select
    order_id,
    sum(item_total_amount) as order_total_amount
from {{ ref('stg_order_items') }}
group by 1
