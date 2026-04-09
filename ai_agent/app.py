from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from config import settings
from llm_interface import generate_sql
from sql_executor import run_select_query


app = FastAPI(title="Olist AI Query Agent", version="1.0.0")


class QueryRequest(BaseModel):
    question: str


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.post("/query")
def query_data(request: QueryRequest):
    try:
        sql = generate_sql(request.question)
        rows = run_select_query(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "question": request.question,
        "sql": sql,
        "result": rows,
        "explanation": "The AI agent translated the natural language request into SQL and executed it on the analytics schema.",
    }


if __name__ == "__main__":
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
