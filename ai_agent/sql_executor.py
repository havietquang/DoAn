import logging
import re
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import create_engine, text, exc
from sqlalchemy.pool import QueuePool

from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool configuration
POOL_SIZE = 5
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30
DEFAULT_MAX_ROWS = 1000
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LIMIT_RE = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)
NUMERIC_TYPES = {
    "smallint", "integer", "bigint", "decimal", "numeric", "real",
    "double precision", "smallserial", "serial", "bigserial", "money"
}

def _connection_string() -> str:
    return (
        "postgresql+psycopg2://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


# Create engine with connection pooling
engine = create_engine(
    _connection_string(),
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_pre_ping=True,  # Test connections before use
    future=True
)


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    connection = None
    try:
        connection = engine.connect()
        yield connection
    except exc.SQLAlchemyError as e:
        logger.error(f"Database connection error: {str(e)}")
        raise
    finally:
        if connection:
            connection.close()


def validate_query(sql: str) -> None:
    """Validate SQL query for safety"""
    normalized_sql = sql.strip().lower()
    sql_without_terminal_semicolon = normalized_sql.rstrip(";").strip()

    if not sql_without_terminal_semicolon:
        raise ValueError("Query is empty")

    # Must be SELECT
    if not (
        sql_without_terminal_semicolon.startswith("select")
        or sql_without_terminal_semicolon.startswith("with")
    ):
        raise ValueError("Only SELECT queries are allowed")

    if "analytics." not in sql_without_terminal_semicolon:
        raise ValueError("Queries must use the analytics schema")

    if ";" in sql_without_terminal_semicolon:
        raise ValueError("Multiple SQL statements not allowed")

    has_comment = any(
        marker in sql_without_terminal_semicolon
        for marker in ("--", "/*", "*/")
    )
    if has_comment:
        raise ValueError("SQL comments are not allowed")

    # Block dangerous operations
    dangerous_keywords = [
        "drop", "delete", "update", "insert", "alter", "create",
        "truncate", "exec", "execute", "merge", "copy", "grant", "revoke",
        "call", "do", "vacuum", "analyze"
    ]

    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", normalized_sql):
            raise ValueError(f"Query contains forbidden keyword: {keyword}")

    dangerous_functions = ["pg_sleep", "pg_read_file", "pg_ls_dir", "dblink"]
    for function_name in dangerous_functions:
        if re.search(rf"\b{function_name}\s*\(", normalized_sql):
            raise ValueError(f"Query contains forbidden function: {function_name}")

    # Reasonable query length limit
    if len(sql) > 10000:
        raise ValueError("Query too long (max 10000 characters)")


def _apply_limit(sql: str, max_rows: Optional[int]) -> str:
    clean_sql = sql.strip().rstrip(";")
    if max_rows is None:
        return clean_sql
    if max_rows < 1 or max_rows > DEFAULT_MAX_ROWS:
        raise ValueError(f"max_rows must be between 1 and {DEFAULT_MAX_ROWS}")
    if LIMIT_RE.search(clean_sql):
        return clean_sql
    return f"SELECT * FROM ({clean_sql}) AS agent_query LIMIT {max_rows}"


def run_select_query(
    sql: str,
    timeout: int = 30,
    max_rows: Optional[int] = DEFAULT_MAX_ROWS,
) -> List[Dict[str, Any]]:
    """Execute SELECT query with proper error handling and validation"""
    import time

    start_time = time.time()

    try:
        logger.info(f"Executing query: {sql[:100]}...")

        # Validate query
        validate_query(sql)
        limited_sql = _apply_limit(sql, max_rows)

        # Execute with timeout
        with get_db_connection() as connection:
            # Set statement timeout
            connection.execute(text(f"SET statement_timeout = {timeout * 1000}"))

            # Execute query
            dataframe = pd.read_sql_query(text(limited_sql), connection)

        execution_time = time.time() - start_time
        logger.info(f"Query executed successfully. Rows: {len(dataframe)}, Time: {execution_time:.2f}s")

        return dataframe.to_dict(orient="records")

    except exc.OperationalError as e:
        if "statement timeout" in str(e).lower():
            logger.warning(f"Query timeout after {timeout}s")
            raise ValueError(f"Query execution timed out after {timeout} seconds")
        else:
            logger.error(f"Database operational error: {str(e)}")
            raise ValueError(f"Database connection error: {str(e)}")

    except exc.ProgrammingError as e:
        logger.warning(f"SQL syntax error: {str(e)}")
        raise ValueError(f"SQL syntax error: {str(e)}")

    except exc.DataError as e:
        logger.warning(f"Data error: {str(e)}")
        raise ValueError(f"Data processing error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error executing query: {str(e)}", exc_info=True)
        raise ValueError(f"Query execution failed: {str(e)}")


def test_connection() -> bool:
    """Test database connection"""
    try:
        with get_db_connection() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False


def get_table_info(schema: str = "analytics") -> List[Dict[str, Any]]:
    """Get information about tables in the schema"""
    try:
        query = """
        SELECT
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema = :schema
        ORDER BY table_name
        """

        with get_db_connection() as connection:
            df = pd.read_sql_query(text(query), connection, params={"schema": schema})

        return df.to_dict(orient="records")

    except Exception as e:
        logger.error(f"Failed to get table info: {str(e)}")
        return []


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return f'"{identifier}"'


def get_schema_catalog(schema: str = "analytics") -> List[Dict[str, Any]]:
    """Return tables, descriptions from dbt metadata if available, and column metadata."""
    try:
        query = """
        SELECT
            t.table_name,
            t.table_type,
            c.column_name,
            c.ordinal_position,
            c.data_type,
            c.is_nullable
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON c.table_schema = t.table_schema
           AND c.table_name = t.table_name
        WHERE t.table_schema = :schema
        ORDER BY t.table_name, c.ordinal_position
        """

        with get_db_connection() as connection:
            df = pd.read_sql_query(text(query), connection, params={"schema": schema})

        if df.empty:
            return []

        catalog: List[Dict[str, Any]] = []
        for table_name, table_df in df.groupby("table_name", sort=False):
            columns = [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                }
                for _, row in table_df.iterrows()
            ]
            catalog.append({
                "schema": schema,
                "table_name": table_name,
                "table_type": table_df.iloc[0]["table_type"],
                "columns": columns,
            })

        return catalog

    except Exception as e:
        logger.error(f"Failed to get schema catalog: {str(e)}", exc_info=True)
        return []


def _scalar_query(sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
    with get_db_connection() as connection:
        return connection.execute(text(sql), params or {}).scalar()


def get_table_profiles(schema: str = "analytics", max_tables: int = 20) -> List[Dict[str, Any]]:
    """Profile analytics tables so the chatbot can explain table contents."""
    catalog = get_schema_catalog(schema)
    profiles: List[Dict[str, Any]] = []

    for table in catalog[:max_tables]:
        table_name = table["table_name"]
        qualified_table = f"{_quote_identifier(schema)}.{_quote_identifier(table_name)}"

        try:
            row_count = _scalar_query(f"SELECT COUNT(*) FROM {qualified_table}")
        except Exception as e:
            logger.warning(f"Failed to count rows for {qualified_table}: {str(e)}")
            row_count = None

        column_profiles: List[Dict[str, Any]] = []
        for column in table["columns"]:
            column_name = column["name"]
            quoted_column = _quote_identifier(column_name)
            column_profile = {
                "name": column_name,
                "type": column["type"],
                "nullable": column["nullable"],
            }

            try:
                stats_sql = (
                    f"SELECT COUNT(*) FILTER (WHERE {quoted_column} IS NULL) AS null_count, "
                    f"COUNT(DISTINCT {quoted_column}) AS distinct_count "
                    f"FROM {qualified_table}"
                )
                with get_db_connection() as connection:
                    stats = connection.execute(text(stats_sql)).mappings().first()

                if stats:
                    column_profile["null_count"] = stats["null_count"]
                    column_profile["distinct_count"] = stats["distinct_count"]

                if column["type"] in NUMERIC_TYPES:
                    numeric_sql = (
                        f"SELECT MIN({quoted_column}) AS min_value, "
                        f"MAX({quoted_column}) AS max_value, "
                        f"AVG({quoted_column}) AS avg_value "
                        f"FROM {qualified_table}"
                    )
                    with get_db_connection() as connection:
                        numeric_stats = connection.execute(text(numeric_sql)).mappings().first()
                    if numeric_stats:
                        column_profile.update({
                            "min_value": numeric_stats["min_value"],
                            "max_value": numeric_stats["max_value"],
                            "avg_value": numeric_stats["avg_value"],
                        })
            except Exception as e:
                logger.debug(f"Failed profiling {qualified_table}.{column_name}: {str(e)}")

            column_profiles.append(column_profile)

        profiles.append({
            "schema": schema,
            "table_name": table_name,
            "row_count": row_count,
            "columns": column_profiles,
        })

    return profiles
