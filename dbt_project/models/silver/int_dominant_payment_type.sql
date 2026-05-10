{{ config(
    materialized='view',
    tags=['silver', 'payments'],
    meta={
        'layer': 'silver',
        'domain': 'payments'
    }
) }}

-- One row per order_id: choose the dominant payment type for reporting.

with payment_type_ranking as (
    select
        order_id,
        payment_type,
        count(*) as payment_type_count,
        sum(payment_value) as payment_type_amount
    from {{ ref('stg_order_payments') }}
    group by 1, 2
)

select
    order_id,
    payment_type as primary_payment_type
from (
    select
        order_id,
        payment_type,
        row_number() over (
            partition by order_id
            order by payment_type_count desc, payment_type_amount desc, payment_type
        ) as row_num
    from payment_type_ranking
) ranked
where row_num = 1
