import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from config import settings
from llm_interface import generate_answer, generate_sql, get_supported_queries
from sql_executor import get_schema_catalog, get_table_profiles, run_select_query

# Setup logging
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'api_{datetime.now().strftime("%Y%m%d")}.log'),
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
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the data")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Maximum number of rows to return")


class QueryResponse(BaseModel):
    question: str
    sql: str
    result: List[Dict[str, Any]]
    row_count: int
    execution_time: float
    explanation: str
    timestamp: datetime


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message for the analytics chatbot")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Maximum number of rows to include")


class ChatResponse(BaseModel):
    message: str
    answer: str
    sql: str
    result: List[Dict[str, Any]]
    row_count: int
    execution_time: float
    timestamp: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime


CHATBOT_HTML = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Olist AI Data Chatbot</title>
  <style>
    :root {
      --ink: #17221f;
      --muted: #60706b;
      --paper: #f7f1e5;
      --card: rgba(255,255,255,.78);
      --accent: #0d6b57;
      --accent-2: #e07a35;
      --line: rgba(23,34,31,.14);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 18%, rgba(224,122,53,.28), transparent 28rem),
        radial-gradient(circle at 85% 10%, rgba(13,107,87,.20), transparent 30rem),
        linear-gradient(135deg, #f7f1e5 0%, #e9dcc6 100%);
    }
    main {
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0;
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 24px;
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: 0 24px 70px rgba(38, 31, 20, .14);
      backdrop-filter: blur(14px);
    }
    .intro { padding: 28px; }
    h1 { margin: 0 0 14px; font-size: 42px; line-height: .95; letter-spacing: -.04em; }
    p { color: var(--muted); line-height: 1.55; }
    .examples { display: grid; gap: 10px; margin-top: 24px; }
    button.example {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff8ed;
      color: var(--ink);
      padding: 10px 14px;
      text-align: left;
      cursor: pointer;
    }
    .chat { min-height: 720px; display: flex; flex-direction: column; overflow: hidden; }
    .messages { flex: 1; padding: 24px; overflow-y: auto; display: grid; align-content: start; gap: 14px; }
    .bubble { max-width: 86%; padding: 14px 16px; border-radius: 18px; line-height: 1.5; white-space: pre-wrap; }
    .user { justify-self: end; background: var(--accent); color: white; border-bottom-right-radius: 6px; }
    .bot { justify-self: start; background: white; border: 1px solid var(--line); border-bottom-left-radius: 6px; }
    .sql {
      margin-top: 10px;
      padding: 10px;
      border-radius: 12px;
      background: #10231f;
      color: #dff5ed;
      font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      overflow-x: auto;
    }
    form { display: flex; gap: 10px; padding: 18px; border-top: 1px solid var(--line); background: rgba(255,255,255,.55); }
    input {
      flex: 1;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 14px 16px;
      font: 16px Georgia, "Times New Roman", serif;
      background: white;
    }
    button.send {
      border: none;
      border-radius: 999px;
      padding: 0 22px;
      background: var(--accent-2);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; padding: 20px 0; }
      .chat { min-height: 620px; }
      h1 { font-size: 34px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="panel intro">
      <h1>Olist AI Data Chatbot</h1>
      <p>Chatbot đọc bảng analytics trong PostgreSQL, tự sinh SQL an toàn, chạy truy vấn và trả lời bằng kết quả thật từ data warehouse.</p>
      <div class="examples">
        <button class="example">Total revenue by month</button>
        <button class="example">Top sellers by revenue</button>
        <button class="example">Orders by product category</button>
        <button class="example">Total orders by state</button>
      </div>
    </section>
    <section class="panel chat">
      <div id="messages" class="messages">
        <div class="bubble bot">Nhập câu hỏi về doanh thu, đơn hàng, seller, khách hàng hoặc danh mục sản phẩm.</div>
      </div>
      <form id="chat-form">
        <input id="message" placeholder="Ví dụ: top category theo revenue" autocomplete="off" />
        <button class="send" type="submit">Gửi</button>
      </form>
    </section>
  </main>
  <script>
    const messages = document.querySelector("#messages");
    const input = document.querySelector("#message");
    const form = document.querySelector("#chat-form");

    function addBubble(content, cls, sql) {
      const el = document.createElement("div");
      el.className = `bubble ${cls}`;
      el.textContent = content;
      if (sql) {
        const code = document.createElement("div");
        code.className = "sql";
        code.textContent = sql;
        el.appendChild(code);
      }
      messages.appendChild(el);
      messages.scrollTop = messages.scrollHeight;
    }

    async function sendMessage(text) {
      addBubble(text, "user");
      input.value = "";
      input.disabled = true;
      addBubble("Đang phân tích dữ liệu...", "bot");
      const pending = messages.lastChild;
      try {
        const res = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, limit: 100 })
        });
        const data = await res.json();
        pending.remove();
        if (!res.ok) throw new Error(data.detail || "Request failed");
        addBubble(`${data.answer}\\n\\nSố dòng: ${data.row_count}`, "bot", data.sql);
      } catch (err) {
        pending.textContent = `Lỗi: ${err.message}`;
      } finally {
        input.disabled = false;
        input.focus();
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (text) sendMessage(text);
    });
    document.querySelectorAll(".example").forEach((btn) => {
      btn.addEventListener("click", () => sendMessage(btn.textContent.trim()));
    });
  </script>
</body>
</html>
"""


@app.get("/health")
def healthcheck():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now(),
        "version": "2.0.0"
    }


@app.get("/", response_class=HTMLResponse)
def chatbot_ui():
    """Browser chatbot UI for the AI analytics layer."""
    return CHATBOT_HTML


@app.get("/supported-queries")
def get_supported_queries_endpoint():
    """Get list of supported rule-based queries"""
    return {
        "supported_queries": get_supported_queries(),
        "note": "These queries work without OpenAI API key"
    }


@app.get("/schema")
def schema_catalog():
    """Return analytics schema catalog for the chatbot and demo."""
    catalog = get_schema_catalog("analytics")
    return {
        "schema": "analytics",
        "tables": catalog,
        "table_count": len(catalog),
        "timestamp": datetime.now(),
    }


@app.get("/profile")
def table_profile():
    """Return row counts and basic column statistics for analytics tables."""
    profiles = get_table_profiles("analytics")
    return {
        "schema": "analytics",
        "profiles": profiles,
        "table_count": len(profiles),
        "timestamp": datetime.now(),
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
        rows = run_select_query(sql, max_rows=request.limit or 100)

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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chatbot endpoint: question -> SQL -> data -> analytical answer."""
    start_time = datetime.now()

    try:
        logger.info(f"Processing chat message: {request.message}")

        sql = generate_sql(request.message)
        rows = run_select_query(sql, max_rows=request.limit or 100)
        if request.limit and len(rows) > request.limit:
            rows = rows[:request.limit]

        answer = generate_answer(request.message, sql, rows)
        execution_time = (datetime.now() - start_time).total_seconds()

        return ChatResponse(
            message=request.message,
            answer=answer,
            sql=sql,
            result=rows,
            row_count=len(rows),
            execution_time=execution_time,
            timestamp=datetime.now(),
        )

    except ValueError as e:
        logger.warning(f"Chat validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Chat failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Exception",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
            "timestamp": datetime.now().isoformat(),
        },
    )


if __name__ == "__main__":
    logger.info(f"Starting Olist AI Query Agent on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )
