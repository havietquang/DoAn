from __future__ import annotations

from .constants import ANALYTICS_TABLES, EXPECTED_RAW_FILES, RAW_DATA_DIR, RAW_TABLES


def _get_connection():
    import psycopg2

    return psycopg2.connect(
        host="postgres",
        database="olist_dw",
        user="olist_user",
        password="olist_pass",
    )


def verify_source_files() -> None:
    """Ensure required CSV files exist before ingestion starts."""
    missing_files: list[str] = []
    empty_files: list[str] = []

    for file_name in EXPECTED_RAW_FILES:
        file_path = RAW_DATA_DIR / file_name
        if not file_path.exists():
            missing_files.append(file_name)
            continue
        if file_path.stat().st_size == 0:
            empty_files.append(file_name)

    if missing_files:
        raise FileNotFoundError(f"Missing raw CSV files: {missing_files}")

    if empty_files:
        raise ValueError(f"Empty raw CSV files detected: {empty_files}")

    print(f"Verified {len(EXPECTED_RAW_FILES)} raw source files.")


def check_postgres_connectivity() -> None:
    """Verify PostgreSQL is reachable and schemas can be queried."""
    connection = _get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user;")
            database_name, database_user = cursor.fetchone()
            cursor.execute("SELECT current_schema();")
            current_schema = cursor.fetchone()[0]

        print(
            "PostgreSQL connectivity check passed: "
            f"database={database_name}, user={database_user}, schema={current_schema}"
        )
    finally:
        connection.close()


def validate_raw_layer() -> None:
    """Validate raw ingestion completeness and key relationships."""
    from psycopg2.extras import RealDictCursor

    connection = _get_connection()

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            for table_name in RAW_TABLES:
                cursor.execute(f"SELECT COUNT(*) AS row_count FROM raw.{table_name}")
                row_count = cursor.fetchone()["row_count"]
                if row_count == 0:
                    raise ValueError(f"Raw table raw.{table_name} is empty")

            cursor.execute(
                """
                SELECT COUNT(*) AS orphaned_orders
                FROM raw.olist_orders_dataset AS o
                LEFT JOIN raw.olist_customers_dataset AS c
                    ON o.customer_id = c.customer_id
                WHERE c.customer_id IS NULL
                """
            )
            orphaned_orders = cursor.fetchone()["orphaned_orders"]
            if orphaned_orders > 0:
                raise ValueError(
                    f"Found {orphaned_orders} orders without matching customers"
                )

            cursor.execute(
                """
                SELECT COUNT(*) AS orphaned_items
                FROM raw.olist_order_items_dataset AS oi
                LEFT JOIN raw.olist_orders_dataset AS o
                    ON oi.order_id = o.order_id
                WHERE o.order_id IS NULL
                """
            )
            orphaned_items = cursor.fetchone()["orphaned_items"]
            if orphaned_items > 0:
                raise ValueError(
                    f"Found {orphaned_items} order items without matching orders"
                )

        print("Raw layer validation passed.")
    finally:
        connection.close()


def validate_analytics_layer() -> None:
    """Validate final analytics objects after dbt build and test."""
    from psycopg2.extras import RealDictCursor

    connection = _get_connection()

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            for table_name in ANALYTICS_TABLES:
                cursor.execute(f"SELECT COUNT(*) AS row_count FROM analytics.{table_name}")
                row_count = cursor.fetchone()["row_count"]
                if row_count == 0:
                    raise ValueError(f"Analytics table analytics.{table_name} is empty")

            cursor.execute(
                """
                SELECT COUNT(*) AS invalid_facts
                FROM analytics.fact_orders
                WHERE total_amount < 0
                   OR freight_value < 0
                   OR order_date IS NULL
                """
            )
            invalid_facts = cursor.fetchone()["invalid_facts"]
            if invalid_facts > 0:
                raise ValueError(
                    f"Found {invalid_facts} invalid records in analytics.fact_orders"
                )

            cursor.execute(
                """
                SELECT COUNT(*) AS missing_dimensions
                FROM analytics.fact_order_items AS f
                LEFT JOIN analytics.dim_products AS p
                    ON f.product_id = p.product_id
                LEFT JOIN analytics.dim_sellers AS s
                    ON f.seller_id = s.seller_id
                WHERE p.product_id IS NULL
                   OR s.seller_id IS NULL
                """
            )
            missing_dimensions = cursor.fetchone()["missing_dimensions"]
            if missing_dimensions > 0:
                raise ValueError(
                    f"Found {missing_dimensions} fact rows with missing product or seller dimensions"
                )

        print("Analytics layer validation passed.")
    finally:
        connection.close()
