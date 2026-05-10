{{ config(
    materialized='view',
    tags=['silver', 'orders'],
    meta={
        'layer': 'silver',
        'domain': 'orders'
    }
) }}

-- One row per order item: enrich item detail with order, payment, and review context.

select
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    oi.product_id,
    oi.seller_id,
    o.order_purchase_date as order_date,
    o.order_purchase_timestamp,
    o.order_status,
    oi.shipping_limit_date,
    oi.price,
    oi.freight_value,
    oi.item_total_amount,
    ot.order_total_amount,
    ps.payment_amount as order_payment_amount,
    lr.review_score,
    case
        when coalesce(ot.order_total_amount, 0) = 0 then null
        else round(oi.item_total_amount / ot.order_total_amount, 6)
    end as item_share_of_order_amount
from {{ ref('stg_order_items') }} as oi
inner join {{ ref('stg_orders') }} as o
    on oi.order_id = o.order_id
left join {{ ref('int_order_totals') }} as ot
    on oi.order_id = ot.order_id
left join {{ ref('int_order_payments_summary') }} as ps
    on oi.order_id = ps.order_id
left join {{ ref('int_latest_order_review') }} as lr
    on oi.order_id = lr.order_id
