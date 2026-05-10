import logging
from typing import Dict, List, Any
from datetime import datetime

from llm_interface import generate_sql, get_supported_queries
from sql_executor import run_select_query, test_connection, get_table_info

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - only needed when MCP mode is used
    raise RuntimeError("Install the 'mcp' package to run the MCP server.") from exc

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("olist-warehouse-agent")


@mcp.tool()
def schema_overview() -> str:
    """Get overview of available tables in the analytics schema"""
    try:
        logger.info("Getting schema overview")

        tables = get_table_info("analytics")
        if not tables:
            return "No tables found in analytics schema. Run dbt models first."

        table_names = [t['table_name'] for t in tables]
        return (
            f"Analytics schema tables ({len(table_names)}): "
            f"{', '.join(table_names)}. "
            "Use query_warehouse tool for natural language queries."
        )

    except Exception as e:
        logger.error(f"Failed to get schema overview: {str(e)}")
        return f"Error getting schema overview: {str(e)}"


@mcp.tool()
def query_warehouse(question: str) -> Dict[str, Any]:
    """Execute natural language query against the Olist analytics warehouse"""
    start_time = datetime.now()

    try:
        logger.info(f"Processing MCP query: {question}")

        # Generate SQL
        sql = generate_sql(question)

        # Execute query
        rows = run_select_query(sql)

        execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"MCP query completed. Rows: {len(rows)}, Time: {execution_time:.2f}s")

        return {
            "question": question,
            "sql": sql,
            "result": rows,
            "row_count": len(rows),
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat(),
            "explanation": "Generated SQL from natural language and executed it on PostgreSQL analytics schema.",
        }

    except ValueError as e:
        logger.warning(f"MCP query validation error: {str(e)}")
        return {
            "error": "Query validation failed",
            "detail": str(e),
            "question": question,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"MCP query execution failed: {str(e)}", exc_info=True)
        return {
            "error": "Query execution failed",
            "detail": str(e),
            "question": question,
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def get_supported_queries_list() -> Dict[str, Any]:
    """Get list of supported rule-based queries that work without OpenAI API key"""
    try:
        queries = get_supported_queries()
        return {
            "supported_queries": queries,
            "count": len(queries),
            "note": "These queries work without requiring OpenAI API key",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get supported queries: {str(e)}")
        return {
            "error": "Failed to get supported queries",
            "detail": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def test_database_connection() -> Dict[str, Any]:
    """Test connection to the analytics database"""
    try:
        success = test_connection()
        return {
            "connection_test": "passed" if success else "failed",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return {
            "connection_test": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    logger.info("Starting Olist Warehouse MCP Server")
    mcp.run()
