{{ config(
    materialized='view',
    tags=['silver', 'orders'],
    meta={
        'layer': 'silver',
        'domain': 'orders'
    }
) }}

-- One row per order_id: combine sales, payment, review, and delivery KPIs.

select
    o.order_id,
    o.customer_id,
    im.primary_product_id as product_id,
    im.primary_seller_id as seller_id,
    o.order_purchase_date as order_date,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.order_estimated_delivery_date_day,
    o.order_status,
    coalesce(im.item_count, 0) as item_count,
    coalesce(im.distinct_product_count, 0) as distinct_product_count,
    coalesce(im.distinct_seller_count, 0) as distinct_seller_count,
    coalesce(im.gross_item_amount, 0) as gross_item_amount,
    coalesce(im.freight_amount, 0) as freight_value,
    coalesce(im.total_amount, 0) as total_amount,
    coalesce(ps.payment_amount, 0) as payment_amount,
    coalesce(ps.payment_record_count, 0) as payment_record_count,
    coalesce(ps.distinct_payment_type_count, 0) as distinct_payment_type_count,
    ps.max_payment_installments,
    dpt.primary_payment_type,
    rs.review_count,
    rs.average_review_score,
    rs.max_review_score,
    rs.min_review_score,
    case
        when o.order_approved_at is null then null
        else round(extract(epoch from (o.order_approved_at - o.order_purchase_timestamp)) / 3600.0, 2)
    end as approval_lead_hours,
    case
        when o.order_delivered_customer_date is null then null
        else round(extract(epoch from (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400.0, 2)
    end as delivery_lead_days,
    case
        when o.order_delivered_customer_date is null
            or o.order_estimated_delivery_date is null then null
        else round(
            extract(
                epoch from (
                    o.order_delivered_customer_date - o.order_estimated_delivery_date
                )
            ) / 86400.0,
            2
        )
    end as delivery_delay_days,
    case
        when o.order_delivered_customer_date is null
            or o.order_estimated_delivery_date is null then null
        when o.order_delivered_customer_date <= o.order_estimated_delivery_date then true
        else false
    end as is_delivered_on_time
from {{ ref('stg_orders') }} as o
left join {{ ref('int_order_item_metrics') }} as im
    on o.order_id = im.order_id
left join {{ ref('int_order_payments_summary') }} as ps
    on o.order_id = ps.order_id
left join {{ ref('int_dominant_payment_type') }} as dpt
    on o.order_id = dpt.order_id
left join {{ ref('int_order_reviews_summary') }} as rs
    on o.order_id = rs.order_id
