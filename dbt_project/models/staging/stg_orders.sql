{{ config(materialized='view', tags=['staging', 'orders'], meta={'layer': 'staging', 'domain': 'orders'}) }}

select
    order_id,
    customer_id,
    lower(trim(order_status)) as order_status,
    cast(order_purchase_timestamp as timestamp) as order_purchase_timestamp,
    cast(order_purchase_timestamp as date) as order_purchase_date,
    cast(order_approved_at as timestamp) as order_approved_at,
    cast(order_delivered_carrier_date as timestamp) as order_delivered_carrier_date,
    cast(order_delivered_customer_date as timestamp) as order_delivered_customer_date,
    cast(order_estimated_delivery_date as timestamp) as order_estimated_delivery_date,
    cast(order_estimated_delivery_date as date) as order_estimated_delivery_date_day
from {{ source('raw', 'olist_orders_dataset') }}
