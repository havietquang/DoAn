{{ config(
    materialized='table',
    tags=['marts', 'fact', 'orders'],
    meta={
        'layer': 'marts',
        'domain': 'orders',
        'grain': 'order_item'
    }
) }}

-- Final fact table at order-item grain for detailed sales analysis.

select
    order_id,
    order_item_id,
    customer_id,
    product_id,
    seller_id,
    order_date,
    order_purchase_timestamp,
    order_status,
    shipping_limit_date,
    price,
    freight_value,
    item_total_amount,
    order_total_amount,
    order_payment_amount,
    item_share_of_order_amount,
    review_score
from {{ ref('int_order_items_enriched') }}
