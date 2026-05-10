{{ config(
    materialized='table',
    tags=['marts', 'fact', 'orders'],
    meta={
        'layer': 'marts',
        'domain': 'orders',
        'grain': 'order'
    }
) }}

-- Final fact table at order grain for BI and downstream querying.

select
    order_id,
    customer_id,
    product_id,
    seller_id,
    order_date,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    order_estimated_delivery_date_day,
    order_status,
    item_count,
    distinct_product_count,
    distinct_seller_count,
    gross_item_amount,
    freight_value,
    total_amount,
    payment_amount,
    payment_record_count,
    distinct_payment_type_count,
    max_payment_installments,
    primary_payment_type,
    review_count,
    average_review_score,
    max_review_score,
    min_review_score,
    approval_lead_hours,
    delivery_lead_days,
    delivery_delay_days,
    is_delivered_on_time
from {{ ref('int_orders_enriched') }}
