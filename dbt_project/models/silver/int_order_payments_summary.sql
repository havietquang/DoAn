{{ config(
    materialized='view',
    tags=['silver', 'payments'],
    meta={
        'layer': 'silver',
        'domain': 'payments'
    }
) }}

-- One row per order_id: summarize payment behavior and amount collected.

select
    order_id,
    count(*) as payment_record_count,
    count(distinct payment_type) as distinct_payment_type_count,
    sum(payment_value) as payment_amount,
    max(payment_installments) as max_payment_installments
from {{ ref('stg_order_payments') }}
group by 1
