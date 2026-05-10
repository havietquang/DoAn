{{ config(materialized='table', tags=['marts', 'dimension', 'customers'], meta={'layer': 'marts', 'domain': 'customers'}) }}

select
    customer_id,
    customer_unique_id,
    customer_city,
    customer_state,
    customer_zip_code_prefix,
    customer_city || ', ' || customer_state as customer_city_state
from {{ ref('stg_customers') }}
