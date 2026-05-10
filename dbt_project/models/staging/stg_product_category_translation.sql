{{ config(materialized='view', tags=['staging', 'products'], meta={'layer': 'staging', 'domain': 'products'}) }}

select
    trim(product_category_name) as product_category_name,
    trim(product_category_name_english) as product_category_name_english
from {{ source('raw', 'product_category_name_translation') }}
