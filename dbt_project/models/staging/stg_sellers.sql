{{ config(materialized='view', tags=['staging', 'sellers'], meta={'layer': 'staging', 'domain': 'sellers'}) }}

select
    seller_id,
    seller_zip_code_prefix,
    initcap(seller_city) as seller_city,
    seller_state
from {{ source('raw', 'olist_sellers_dataset') }}
