{{ config(materialized='table', tags=['marts', 'dimension', 'products'], meta={'layer': 'marts', 'domain': 'products'}) }}

with translated_categories as (
    select
        product_category_name,
        product_category_name_english
    from {{ ref('stg_product_category_translation') }}
),
products as (
    select
        p.product_id,
        p.product_category_name,
        coalesce(tc.product_category_name_english, p.product_category_name) as product_category_name_english,
        p.product_name_length,
        p.product_description_length,
        p.product_photos_qty,
        p.product_weight_g,
        round(p.product_weight_g / 1000.0, 3) as product_weight_kg,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm,
        round(
            coalesce(p.product_length_cm, 0)
            * coalesce(p.product_height_cm, 0)
            * coalesce(p.product_width_cm, 0),
            2
        ) as product_volume_cm3
    from {{ ref('stg_products') }} as p
    left join translated_categories as tc
        on p.product_category_name = tc.product_category_name
)

select
    product_id,
    product_category_name,
    product_category_name_english,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_weight_kg,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    product_volume_cm3,
    case
        when product_volume_cm3 >= 50000 or product_weight_g >= 30000 then 'bulky'
        when product_volume_cm3 >= 10000 or product_weight_g >= 10000 then 'medium'
        when product_volume_cm3 > 0 then 'small'
        else 'unknown'
    end as product_size_tier
from products
