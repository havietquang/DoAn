from llm_interface import generate_sql
from sql_executor import run_select_query

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - only needed when MCP mode is used
    raise RuntimeError("Install the 'mcp' package to run the MCP server.") from exc


mcp = FastMCP("olist-warehouse-agent")


@mcp.tool()
def schema_overview() -> str:
    return (
        "Analytics schema tables: "
        "analytics.fact_orders, analytics.dim_customers, analytics.dim_products, "
        "analytics.dim_sellers, analytics.dim_date."
    )


@mcp.tool()
def query_warehouse(question: str) -> dict:
    sql = generate_sql(question)
    rows = run_select_query(sql)
    return {
        "question": question,
        "sql": sql,
        "result": rows,
        "explanation": "Generated SQL from natural language and executed it on PostgreSQL.",
    }


if __name__ == "__main__":
    mcp.run()
