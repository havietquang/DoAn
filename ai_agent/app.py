import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from config import settings
from llm_interface import generate_sql, get_supported_queries
from sql_executor import run_select_query

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'logs/api_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Olist AI Query Agent",
    version="2.0.0",
    description="Natural language to SQL interface for Olist e-commerce analytics"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the data")
    limit: Optional[int] = Field(100, description="Maximum number of rows to return")


class QueryResponse(BaseModel):
    question: str
    sql: str
    result: List[Dict[str, Any]]
    row_count: int
    execution_time: float
    explanation: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime


@app.get("/health")
def healthcheck():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now(),
        "version": "2.0.0"
    }


@app.get("/supported-queries")
def get_supported_queries_endpoint():
    """Get list of supported rule-based queries"""
    return {
        "supported_queries": get_supported_queries(),
        "note": "These queries work without OpenAI API key"
    }


@app.post("/query", response_model=QueryResponse)
async def query_data(request: QueryRequest):
    """Execute natural language query against the analytics database"""
    start_time = datetime.now()

    try:
        logger.info(f"Processing query: {request.question}")

        # Generate SQL
        sql = generate_sql(request.question)
        logger.info(f"Generated SQL: {sql}")

        # Execute query
        rows = run_select_query(sql)

        # Apply limit if specified
        if request.limit and len(rows) > request.limit:
            rows = rows[:request.limit]

        execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"Query completed successfully. Rows: {len(rows)}, Time: {execution_time:.2f}s")

        return QueryResponse(
            question=request.question,
            sql=sql,
            result=rows,
            row_count=len(rows),
            execution_time=execution_time,
            explanation="AI agent translated natural language to SQL and executed it on the analytics schema.",
            timestamp=datetime.now()
        )

    except ValueError as e:
        # Handle known validation errors
        logger.warning(f"Query validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Query execution failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return {
        "error": "HTTP Exception",
        "detail": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.now()
    }


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return {
        "error": "Internal Server Error",
        "detail": "An unexpected error occurred",
        "timestamp": datetime.now()
    }


if __name__ == "__main__":
    logger.info(f"Starting Olist AI Query Agent on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )
