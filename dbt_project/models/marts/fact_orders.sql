with order_level as (
    select
        oi.order_id,
        o.customer_id,
        oi.product_id,
        oi.seller_id,
        cast(o.order_purchase_timestamp as date) as order_date,
        o.order_status,
        oi.price,
        oi.freight_value,
        (oi.price + oi.freight_value) as total_amount
    from {{ ref('stg_order_items') }} as oi
    inner join {{ ref('stg_orders') }} as o
        on oi.order_id = o.order_id
)

select
    order_id,
    customer_id,
    product_id,
    seller_id,
    order_date,
    order_status,
    price,
    freight_value,
    total_amount
from order_level
