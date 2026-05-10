-- Fail if invalid order status
SELECT *
FROM {{ ref('fact_orders') }}
WHERE order_status NOT IN (
    'approved',
    'canceled',
    'created',
    'delivered',
    'invoiced',
    'processing',
    'shipped',
    'unavailable'
)
