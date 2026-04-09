with date_spine as (
    select distinct
        cast(order_purchase_timestamp as date) as date_day
    from {{ ref('stg_orders') }}
    where order_purchase_timestamp is not null
)

select
    date_day,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    to_char(date_day, 'YYYY-MM') as year_month,
    extract(day from date_day) as day_of_month,
    trim(to_char(date_day, 'Day')) as day_name
from date_spine
