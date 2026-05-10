{{ config(materialized='table', tags=['marts', 'dimension', 'sellers'], meta={'layer': 'marts', 'domain': 'sellers'}) }}

select
    seller_id,
    seller_city,
    seller_state,
    seller_zip_code_prefix,
    seller_city || ', ' || seller_state as seller_city_state
from {{ ref('stg_sellers') }}
