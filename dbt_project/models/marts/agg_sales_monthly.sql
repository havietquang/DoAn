{{ config(materialized='table', tags=['marts', 'aggregate', 'orders'], meta={'layer': 'marts', 'domain': 'orders'}) }}

select
    d.year,
    d.quarter,
    d.month,
    d.year_month,
    count(distinct f.order_id) as total_orders,
    sum(f.item_count) as total_items,
    round(sum(f.total_amount), 2) as total_revenue,
    round(sum(f.freight_value), 2) as total_freight,
    round(avg(f.total_amount), 2) as average_order_value,
    round(avg(f.average_review_score), 2) as average_review_score,
    round(avg(f.delivery_lead_days), 2) as average_delivery_days,
    round(
        100.0 * avg(
            case
                when f.is_delivered_on_time is null then null
                when f.is_delivered_on_time then 1.0
                else 0.0
            end
        ),
        2
    ) as on_time_delivery_rate
from {{ ref('fact_orders') }} as f
inner join {{ ref('dim_date') }} as d
    on f.order_date = d.date_day
group by 1, 2, 3, 4
