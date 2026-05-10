import logging
from contextlib import contextmanager
from typing import List, Dict, Any
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

    # Must be SELECT
    if not normalized_sql.startswith("select"):
        raise ValueError("Only SELECT queries are allowed")

    # Block dangerous operations
    dangerous_keywords = [
        "drop", "delete", "update", "insert", "alter", "create",
        "truncate", "exec", "execute", "merge"
    ]

    for keyword in dangerous_keywords:
        if keyword in normalized_sql:
            raise ValueError(f"Query contains forbidden keyword: {keyword}")

    # Check for multiple statements
    if ";" in normalized_sql and normalized_sql.count(";") > 1:
        raise ValueError("Multiple SQL statements not allowed")

    # Reasonable query length limit
    if len(sql) > 10000:
        raise ValueError("Query too long (max 10000 characters)")


def run_select_query(sql: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """Execute SELECT query with proper error handling and validation"""
    import time

    start_time = time.time()

    try:
        logger.info(f"Executing query: {sql[:100]}...")

        # Validate query
        validate_query(sql)

        # Execute with timeout
        with get_db_connection() as connection:
            # Set statement timeout
            connection.execute(text(f"SET statement_timeout = {timeout * 1000}"))

            # Execute query
            dataframe = pd.read_sql_query(text(sql), connection)

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
        WHERE table_schema = %s
        ORDER BY table_name
        """

        with get_db_connection() as connection:
            df = pd.read_sql_query(text(query), connection, params=[schema])

        return df.to_dict(orient="records")

    except Exception as e:
        logger.error(f"Failed to get table info: {str(e)}")
        return []
