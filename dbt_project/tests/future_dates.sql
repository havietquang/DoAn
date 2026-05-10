-- Fail if any orders have future dates
SELECT *
FROM {{ ref('fact_orders') }}
WHERE order_date > CURRENT_DATE