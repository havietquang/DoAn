{{ config(materialized='table', tags=['marts', 'aggregate', 'products'], meta={'layer': 'marts', 'domain': 'products'}) }}

select
    p.product_category_name,
    p.product_category_name_english,
    p.product_size_tier,
    count(distinct i.order_id) as total_orders,
    count(*) as total_order_items,
    round(sum(i.item_total_amount), 2) as total_revenue,
    round(sum(i.freight_value), 2) as total_freight,
    round(avg(i.item_total_amount), 2) as average_item_value,
    round(avg(i.review_score), 2) as average_review_score,
    count(distinct i.customer_id) as distinct_customers
from {{ ref('fact_order_items') }} as i
inner join {{ ref('dim_products') }} as p
    on i.product_id = p.product_id
group by 1, 2, 3
