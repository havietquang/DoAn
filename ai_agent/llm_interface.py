from __future__ import annotations

import logging
from textwrap import dedent
from typing import Optional, Dict, List
from datetime import datetime

from config import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback remains usable
    OpenAI = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WAREHOUSE_CONTEXT = dedent(
    """
    You are an expert SQL analyst for an e-commerce analytics database.
    Generate PostgreSQL queries for the analytics schema.

    Available tables:
    - analytics.fact_orders(order_id, customer_id, order_date, order_status, item_count, distinct_product_count, distinct_seller_count, gross_item_amount, freight_value, total_amount, payment_amount, primary_payment_type, average_review_score, delivery_lead_days, delivery_delay_days, is_delivered_on_time)
    - analytics.fact_order_items(order_id, order_item_id, customer_id, product_id, seller_id, order_date, order_status, price, freight_value, item_total_amount, order_total_amount, review_score)
    - analytics.dim_customers(customer_id, customer_unique_id, customer_city, customer_state, customer_zip_code_prefix, customer_city_state)
    - analytics.dim_products(product_id, product_category_name, product_category_name_english, product_weight_g, product_weight_kg, product_length_cm, product_height_cm, product_width_cm, product_volume_cm3, product_size_tier)
    - analytics.dim_sellers(seller_id, seller_city, seller_state, seller_zip_code_prefix, seller_city_state)
    - analytics.dim_date(date_day, year, quarter, month, month_name, week_of_year, year_month, day_of_month, day_of_week, day_name, is_weekend)
    - analytics.agg_sales_monthly(year, quarter, month, year_month, total_orders, total_items, total_revenue, total_freight, average_order_value, average_review_score, average_delivery_days, on_time_delivery_rate)
    - analytics.agg_seller_performance(seller_id, seller_state, seller_city, total_orders, total_order_items, total_revenue, total_freight, average_item_value, average_review_score, distinct_products_sold)
    - analytics.agg_category_performance(product_category_name, product_category_name_english, product_size_tier, total_orders, total_order_items, total_revenue, total_freight, average_item_value, average_review_score, distinct_customers)

    Rules:
    - Always qualify tables with the analytics schema
    - Use proper JOINs for dimension tables
    - Format numbers with ROUND() for currency
    - Use appropriate aggregation functions
    - Order results meaningfully
    - Return only the SQL query, no explanations
    """
).strip()


RULE_BASED_SQL = {
    "total revenue by month": """
        SELECT
            d.year_month,
            ROUND(SUM(f.total_amount), 2) as total_revenue
        FROM analytics.fact_orders f
        JOIN analytics.dim_date d ON f.order_date = d.date_day
        GROUP BY d.year_month
        ORDER BY d.year_month;
    """,
    "total orders by state": """
        SELECT
            c.customer_state,
            COUNT(DISTINCT f.order_id) as total_orders
        FROM analytics.fact_orders f
        JOIN analytics.dim_customers c ON f.customer_id = c.customer_id
        GROUP BY c.customer_state
        ORDER BY total_orders DESC;
    """,
    "top sellers by revenue": """
        SELECT
            seller_id,
            seller_state,
            total_revenue
        FROM analytics.agg_seller_performance
        ORDER BY total_revenue DESC
        LIMIT 10;
    """,
    "average order value": """
        SELECT
            ROUND(AVG(f.total_amount), 2) as avg_order_value,
            COUNT(*) as total_orders
        FROM analytics.fact_orders f;
    """,
    "orders by product category": """
        SELECT
            product_category_name_english,
            total_orders,
            total_revenue
        FROM analytics.agg_category_performance
        ORDER BY total_revenue DESC;
    """,
}


class ConversationMemory:
    """Simple conversation memory for context"""

    def __init__(self, max_messages: int = 10):
        self.messages: List[Dict] = []
        self.max_messages = max_messages

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def get_recent_messages(self, limit: int = 5) -> List[Dict]:
        return self.messages[-limit:] if self.messages else []


# Global conversation memory
conversation_memory = ConversationMemory()


def validate_sql_query(sql: str) -> bool:
    """Basic SQL validation"""
    sql_lower = sql.lower().strip()

    # Must be SELECT statement
    if not sql_lower.startswith("select"):
        return False

    # Must contain FROM
    if "from" not in sql_lower:
        return False

    # Must use analytics schema
    if "analytics." not in sql_lower:
        return False

    # Check for dangerous operations
    dangerous_keywords = ["drop", "delete", "update", "insert", "alter", "create"]
    for keyword in dangerous_keywords:
        if keyword in sql_lower:
            return False

    return True


def generate_sql(question: str, use_memory: bool = True) -> str:
    """Generate SQL with improved error handling and logging"""
    start_time = datetime.now()
    logger.info(f"Generating SQL for question: {question}")

    try:
        normalized_question = question.strip().lower()

        # Check rule-based queries first
        if normalized_question in RULE_BASED_SQL:
            sql = dedent(RULE_BASED_SQL[normalized_question]).strip()
            logger.info("Used rule-based SQL generation")
            conversation_memory.add_message("user", question)
            conversation_memory.add_message("assistant", f"Generated SQL: {sql}")
            return sql

        # Use OpenAI if available
        if settings.openai_api_key and OpenAI is not None:
            client = OpenAI(api_key=settings.openai_api_key)

            messages = [
                {"role": "system", "content": WAREHOUSE_CONTEXT}
            ]

            # Add conversation context if enabled
            if use_memory:
                recent_messages = conversation_memory.get_recent_messages()
                for msg in recent_messages:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            messages.append({"role": "user", "content": question})

            response = client.chat.completions.create(
                model=settings.openai_model,
                temperature=0,
                max_tokens=500,
                messages=messages,
            )

            sql = response.choices[0].message.content.strip()

            # Validate generated SQL
            if not validate_sql_query(sql):
                logger.warning(f"Generated invalid SQL: {sql}")
                raise ValueError("Generated SQL failed validation")

            logger.info("Successfully generated SQL using OpenAI")
            conversation_memory.add_message("user", question)
            conversation_memory.add_message("assistant", f"Generated SQL: {sql}")

            return sql

        # Fallback to supported queries
        supported_queries = list(RULE_BASED_SQL.keys())
        raise ValueError(
            f"Question not supported by rule-based queries. "
            f"Try one of: {', '.join(supported_queries)}, "
            "or set OPENAI_API_KEY for advanced queries."
        )

    except Exception as e:
        logger.error(f"Failed to generate SQL: {str(e)}")
        raise

    finally:
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"SQL generation took {duration:.2f} seconds")


def get_supported_queries() -> List[str]:
    """Return list of supported rule-based queries"""
    return list(RULE_BASED_SQL.keys())
