-- Fail if any orders have negative total_amount
SELECT *
FROM {{ ref('fact_orders') }}
WHERE total_amount < 0