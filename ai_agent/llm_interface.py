from __future__ import annotations

import logging
import json
import re
from decimal import Decimal
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple
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


def clean_generated_sql(sql: str) -> str:
    """Normalize common LLM SQL output formats before validation/execution."""
    cleaned = sql.strip()
    fenced_match = re.search(r"```(?:sql)?\s*(.*?)```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()
    return cleaned


def validate_sql_query(sql: str) -> bool:
    """Basic SQL validation"""
    sql_lower = clean_generated_sql(sql).lower().strip().rstrip(";").strip()

    # Must be SELECT statement
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        return False

    # Must contain FROM
    if "from" not in sql_lower:
        return False

    # Must use analytics schema
    if "analytics." not in sql_lower:
        return False

    if ";" in sql_lower:
        return False

    if "--" in sql_lower or "/*" in sql_lower or "*/" in sql_lower:
        return False

    # Check for dangerous operations
    dangerous_keywords = [
        "drop", "delete", "update", "insert", "alter", "create",
        "truncate", "exec", "execute", "merge", "copy", "grant", "revoke",
        "call", "do", "vacuum", "analyze",
    ]
    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", sql_lower):
            return False

    dangerous_functions = ["pg_sleep", "pg_read_file", "pg_ls_dir", "dblink"]
    for function_name in dangerous_functions:
        if re.search(rf"\b{function_name}\s*\(", sql_lower):
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

            sql = clean_generated_sql(response.choices[0].message.content)

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


def _as_number(value: Any) -> Optional[float]:
    """Convert common database numeric values to float for lightweight analysis."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _format_number(value: Any) -> str:
    number = _as_number(value)
    if number is None:
        return str(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}".rstrip("0").rstrip(".")
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _pick_metric_column(rows: List[Dict[str, Any]]) -> Optional[str]:
    if not rows:
        return None

    preferred_terms = (
        "revenue", "amount", "orders", "items", "customers", "sellers",
        "freight", "value", "rate", "score", "days", "count", "total", "avg",
    )
    columns = list(rows[0].keys())
    numeric_columns = [
        column for column in columns
        if any(_as_number(row.get(column)) is not None for row in rows[:20])
    ]
    for term in preferred_terms:
        for column in numeric_columns:
            if term in column.lower():
                return column
    return numeric_columns[0] if numeric_columns else None


def _pick_dimension_column(rows: List[Dict[str, Any]], metric_column: Optional[str]) -> Optional[str]:
    if not rows:
        return None
    for column in rows[0].keys():
        if column == metric_column:
            continue
        if any(row.get(column) not in (None, "") for row in rows[:20]):
            return column
    return None


def _metric_stats(rows: List[Dict[str, Any]], metric_column: str) -> Tuple[float, float, float]:
    values = [_as_number(row.get(metric_column)) for row in rows]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return 0.0, 0.0, 0.0
    return sum(numeric_values), min(numeric_values), max(numeric_values)


def _build_rule_based_analysis(question: str, sql: str, rows: List[Dict[str, Any]]) -> str:
    """Create a detailed Vietnamese analysis without relying on an LLM."""
    if not rows:
        return (
            "Tóm tắt phân tích\n"
            "- Truy vấn đã chạy thành công nhưng không trả về dòng dữ liệu nào.\n"
            "- Điều này thường có nghĩa là điều kiện lọc quá hẹp hoặc dữ liệu chưa có bản ghi phù hợp.\n\n"
            "Gợi ý kiểm tra\n"
            "- Mở phần SQL để xem bảng và điều kiện lọc đang dùng.\n"
            "- Thử hỏi lại với khoảng thời gian rộng hơn hoặc bỏ bớt điều kiện lọc."
        )

    columns = list(rows[0].keys())
    metric_column = _pick_metric_column(rows)
    dimension_column = _pick_dimension_column(rows, metric_column)

    lines = [
        "Tóm tắt phân tích",
        f"- Câu hỏi: {question}",
        f"- Truy vấn trả về {len(rows)} dòng với các trường: {', '.join(columns)}.",
    ]

    if metric_column:
        total, min_value, max_value = _metric_stats(rows, metric_column)
        lines.append(f"- Chỉ số chính được phân tích là `{metric_column}`.")
        lines.append(
            f"- Tổng `{metric_column}` trong kết quả là {_format_number(total)}; "
            f"giá trị nhỏ nhất {_format_number(min_value)}, lớn nhất {_format_number(max_value)}."
        )

    if dimension_column and metric_column:
        ranked_rows = sorted(
            rows,
            key=lambda row: _as_number(row.get(metric_column)) if _as_number(row.get(metric_column)) is not None else float("-inf"),
            reverse=True,
        )
        top_row = ranked_rows[0]
        bottom_row = ranked_rows[-1]
        lines.extend([
            "",
            "Điểm nổi bật",
            f"- Cao nhất: {dimension_column} = {top_row.get(dimension_column)} "
            f"với `{metric_column}` = {_format_number(top_row.get(metric_column))}.",
            f"- Thấp nhất trong tập kết quả: {dimension_column} = {bottom_row.get(dimension_column)} "
            f"với `{metric_column}` = {_format_number(bottom_row.get(metric_column))}.",
        ])

        first_value = _as_number(rows[0].get(metric_column))
        last_value = _as_number(rows[-1].get(metric_column))
        if first_value is not None and last_value is not None and len(rows) > 1:
            change = last_value - first_value
            pct_change = (change / first_value * 100) if first_value else None
            direction = "tăng" if change > 0 else "giảm" if change < 0 else "không đổi"
            change_text = _format_number(abs(change))
            if pct_change is not None:
                change_text = f"{change_text} ({abs(pct_change):.2f}%)"
            lines.append(
                f"- So sánh dòng đầu và dòng cuối theo thứ tự SQL: `{metric_column}` {direction} {change_text}."
            )

    lines.extend([
        "",
        "Diễn giải nghiệp vụ",
        "- Kết quả này nên được đọc theo đúng grain của SQL: mỗi dòng là một nhóm dữ liệu sau khi GROUP BY hoặc một bản ghi từ bảng mart.",
        "- Nếu SQL dùng bảng aggregate như `agg_sales_monthly`, `agg_category_performance` hoặc `agg_seller_performance`, số liệu đã được chuẩn hóa ở lớp marts để phục vụ dashboard và phân tích nhanh.",
        "",
        "Gợi ý tiếp theo",
        "- Có thể drill-down thêm theo thời gian, bang/khu vực, seller hoặc product category để tìm nguyên nhân biến động.",
        "- Mở phần SQL bên dưới để kiểm tra logic join, group by và order by trước khi đưa số liệu vào báo cáo.",
    ])
    return "\n".join(lines)


def generate_answer(question: str, sql: str, rows: List[Dict[str, Any]]) -> str:
    """Generate a user-facing analytical answer from SQL result rows."""
    safe_rows = rows[:50]

    if settings.openai_api_key and OpenAI is not None:
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = dedent(
            f"""
            You are a Vietnamese data analyst chatbot for the Olist e-commerce warehouse.
            Answer the user's question using only the SQL result below.

            Requirements:
            - Reply in Vietnamese.
            - Give a clear, detailed analysis after the SQL has been generated and executed.
            - Structure the answer with these sections: Tóm tắt phân tích, Điểm nổi bật, Diễn giải nghiệp vụ, Gợi ý tiếp theo.
            - Mention important numbers, leaders/laggards, trends, and what the metric means.
            - Explain the result in business language, not only by repeating rows.
            - If the result is empty, say the data does not contain enough information.
            - Do not invent facts outside the SQL result.
            - Keep the answer practical for an ecommerce analytics report.

            Question:
            {question}

            SQL:
            {sql}

            Result rows as JSON:
            {json.dumps(safe_rows, ensure_ascii=False, default=str)}
            """
        ).strip()

        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            max_tokens=700,
            messages=[
                {"role": "system", "content": "You explain data analysis results accurately."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    if not rows:
        return _build_rule_based_analysis(question, sql, rows)

    return _build_rule_based_analysis(question, sql, rows)
