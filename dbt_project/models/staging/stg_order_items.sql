{{ config(materialized='view', tags=['staging', 'orders'], meta={'layer': 'staging', 'domain': 'orders'}) }}

select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    cast(shipping_limit_date as timestamp) as shipping_limit_date,
    cast(price as numeric(12, 2)) as price,
    cast(freight_value as numeric(12, 2)) as freight_value,
    cast(price as numeric(12, 2)) + cast(freight_value as numeric(12, 2)) as item_total_amount
from {{ source('raw', 'olist_order_items_dataset') }}
