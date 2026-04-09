from __future__ import annotations

from textwrap import dedent

from config import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback remains usable
    OpenAI = None


WAREHOUSE_CONTEXT = dedent(
    """
    You are generating SQL for a PostgreSQL analytics schema.
    Available tables:
    - analytics.fact_orders(order_id, customer_id, product_id, seller_id, order_date, order_status, price, freight_value, total_amount)
    - analytics.dim_customers(customer_id, customer_unique_id, customer_city, customer_state, customer_zip_code_prefix)
    - analytics.dim_products(product_id, product_category_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
    - analytics.dim_sellers(seller_id, seller_city, seller_state, seller_zip_code_prefix)
    - analytics.dim_date(date_day, year, month, year_month, day_of_month, day_name)
    Return SQL only. Use PostgreSQL syntax and always qualify tables with the analytics schema.
    """
).strip()


RULE_BASED_SQL = {
    "total revenue by month": """
        select
            d.year_month,
            round(sum(f.total_amount), 2) as total_revenue
        from analytics.fact_orders f
        join analytics.dim_date d
            on f.order_date = d.date_day
        group by d.year_month
        order by d.year_month;
    """,
    "total orders by state": """
        select
            c.customer_state,
            count(distinct f.order_id) as total_orders
        from analytics.fact_orders f
        join analytics.dim_customers c
            on f.customer_id = c.customer_id
        group by c.customer_state
        order by total_orders desc;
    """,
    "top sellers by revenue": """
        select
            s.seller_id,
            s.seller_state,
            round(sum(f.total_amount), 2) as total_revenue
        from analytics.fact_orders f
        join analytics.dim_sellers s
            on f.seller_id = s.seller_id
        group by s.seller_id, s.seller_state
        order by total_revenue desc;
    """,
}


def generate_sql(question: str) -> str:
    normalized_question = question.strip().lower()
    if normalized_question in RULE_BASED_SQL:
        # Fast demo path that works without an external LLM key.
        return dedent(RULE_BASED_SQL[normalized_question]).strip()

    if settings.openai_api_key and OpenAI is not None:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            messages=[
                {"role": "system", "content": WAREHOUSE_CONTEXT},
                {"role": "user", "content": question},
            ],
        )
        return response.choices[0].message.content.strip()

    raise ValueError(
        "Question not supported by the mock LLM. Try 'Total revenue by month', "
        "'Total orders by state', or 'Top sellers by revenue', or set OPENAI_API_KEY."
    )
