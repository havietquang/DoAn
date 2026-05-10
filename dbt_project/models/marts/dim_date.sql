{{ config(materialized='table', tags=['marts', 'dimension', 'date'], meta={'layer': 'marts', 'domain': 'date'}) }}

with date_spine as (
    select distinct
        order_purchase_date as date_day
    from {{ ref('stg_orders') }}
    where order_purchase_date is not null
)

select
    date_day,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month,
    trim(to_char(date_day, 'Month')) as month_name,
    extract(week from date_day) as week_of_year,
    to_char(date_day, 'YYYY-MM') as year_month,
    extract(day from date_day) as day_of_month,
    extract(isodow from date_day) as day_of_week,
    trim(to_char(date_day, 'Day')) as day_name,
    case
        when extract(isodow from date_day) in (6, 7) then true
        else false
    end as is_weekend
from date_spine
