select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    initcap(customer_city) as customer_city,
    customer_state
from {{ source('raw', 'olist_customers_dataset') }}
