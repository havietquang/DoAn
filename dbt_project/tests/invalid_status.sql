-- Fail if invalid order status
SELECT *
FROM {{ ref('fact_orders') }}
WHERE order_status NOT IN ('processing', 'approved', 'shipped', 'delivered', 'cancelled')