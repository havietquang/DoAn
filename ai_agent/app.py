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
      --bg: #f4f6f5;
      --surface: #ffffff;
      --surface-soft: #f8faf9;
      --ink: #14211d;
      --muted: #63746f;
      --line: #d9e1de;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --accent-soft: #dff5f1;
      --warn: #ea7a2a;
      --blue-soft: #eef6ff;
      --shadow: 0 18px 55px rgba(20, 33, 29, .12);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: linear-gradient(135deg, #edf2f0 0%, #f8f3eb 100%);
    }

    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      min-height: 100vh;
      padding: 28px 0;
      display: grid;
      grid-template-columns: 330px minmax(0, 1fr);
      gap: 18px;
      align-items: stretch;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }

    .intro {
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      color: #fff;
      background: var(--accent);
      font-weight: 800;
    }

    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.05;
      letter-spacing: 0;
    }

    p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 14px;
    }

    .status {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--surface-soft);
    }

    .status-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
    }

    .status-row strong { color: var(--ink); }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 7px;
      background: #22c55e;
      box-shadow: 0 0 0 4px rgba(34, 197, 94, .14);
    }

    .section-title {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }

    .examples {
      display: grid;
      gap: 9px;
    }

    button.example {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      color: var(--ink);
      padding: 12px 13px;
      text-align: left;
      font: 700 13px/1.25 inherit;
      cursor: pointer;
      transition: border-color .15s ease, transform .15s ease, background .15s ease;
    }

    button.example:hover {
      border-color: var(--accent);
      background: var(--accent-soft);
      transform: translateY(-1px);
    }

    .tips {
      margin-top: auto;
      padding-top: 4px;
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .chat {
      height: calc(100vh - 56px);
      min-height: 640px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .chat-header {
      padding: 18px 20px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      background: var(--surface-soft);
    }

    .chat-title {
      display: grid;
      gap: 3px;
    }

    .chat-title strong { font-size: 16px; }
    .chat-title span { color: var(--muted); font-size: 13px; }

    .badge {
      flex: 0 0 auto;
      border: 1px solid rgba(15, 118, 110, .22);
      color: var(--accent-strong);
      background: var(--accent-soft);
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 12px;
      font-weight: 800;
    }

    .messages {
      flex: 1;
      padding: 22px;
      overflow-y: auto;
      display: grid;
      align-content: start;
      gap: 16px;
      background:
        linear-gradient(rgba(248, 250, 249, .97), rgba(248, 250, 249, .97)),
        repeating-linear-gradient(0deg, transparent, transparent 31px, rgba(20, 33, 29, .04) 32px);
    }

    .bubble {
      width: fit-content;
      max-width: min(780px, 88%);
      padding: 14px 16px;
      border-radius: 16px;
      line-height: 1.55;
      font-size: 14px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .user {
      justify-self: end;
      background: var(--accent);
      color: white;
      border-bottom-right-radius: 5px;
      box-shadow: 0 10px 24px rgba(15, 118, 110, .22);
    }

    .bot {
      justify-self: start;
      background: white;
      border: 1px solid var(--line);
      border-bottom-left-radius: 5px;
    }

    .bot.result {
      width: min(820px, 92%);
      padding: 0;
      overflow: hidden;
      white-space: normal;
      box-shadow: 0 12px 30px rgba(20, 33, 29, .08);
    }

    .analysis-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, var(--blue-soft), #fff);
    }

    .analysis-head strong {
      display: block;
      font-size: 14px;
    }

    .analysis-head span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
    }

    .analysis-body {
      padding: 15px 16px 4px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .analysis-body::first-line {
      font-weight: 800;
      color: var(--accent-strong);
    }

    .data-section {
      padding: 0 16px 16px;
    }

    .section-label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .05em;
    }

    .loading {
      color: var(--muted);
    }

    .result-meta {
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    details {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
      background: var(--surface-soft);
    }

    summary {
      cursor: pointer;
      padding: 9px 11px;
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 800;
    }

    .sql {
      margin: 0;
      padding: 12px;
      background: #10231f;
      color: #dff5ed;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      overflow-x: auto;
      white-space: pre;
    }

    .table-wrap {
      margin-top: 8px;
      max-width: 100%;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: white;
    }

    table {
      width: 100%;
      min-width: 420px;
      border-collapse: collapse;
      font-size: 12px;
    }

    th, td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
    }

    th {
      color: var(--muted);
      background: var(--surface-soft);
      font-weight: 800;
    }

    tr:last-child td { border-bottom: none; }

    form {
      display: flex;
      gap: 10px;
      padding: 16px;
      border-top: 1px solid var(--line);
      background: white;
    }

    input {
      flex: 1;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 13px 14px;
      font: 15px inherit;
      color: var(--ink);
      background: var(--surface-soft);
      outline: none;
    }

    input:focus {
      border-color: var(--accent);
      background: white;
      box-shadow: 0 0 0 4px rgba(15, 118, 110, .12);
    }

    button.send {
      border: none;
      border-radius: 12px;
      min-width: 76px;
      padding: 0 18px;
      background: var(--warn);
      color: white;
      font: 800 14px inherit;
      cursor: pointer;
      transition: transform .15s ease, background .15s ease;
    }

    button.send:hover {
      background: #d96516;
      transform: translateY(-1px);
    }

    button.send:disabled,
    input:disabled {
      opacity: .62;
      cursor: wait;
    }

    @media (max-width: 860px) {
      main {
        width: 100%;
        min-height: 100vh;
        padding: 0;
        grid-template-columns: 1fr;
        gap: 0;
      }

      .panel {
        border-radius: 0;
        box-shadow: none;
        border-left: none;
        border-right: none;
      }

      .intro {
        padding: 16px;
        gap: 14px;
      }

      .brand { align-items: flex-start; }
      h1 { font-size: 24px; }
      .status { grid-template-columns: 1fr 1fr; }
      .tips { display: none; }

      .examples {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      button.example {
        min-height: 48px;
        font-size: 12px;
      }

      .chat {
        height: calc(100vh - 250px);
        min-height: 520px;
      }

      .chat-header {
        padding: 14px 16px;
        align-items: flex-start;
      }

      .messages { padding: 14px; }
      .bubble { max-width: 94%; font-size: 13px; }
      .bot.result { width: 100%; }
      .analysis-head { display: block; }
      form { padding: 12px; }
      button.send { min-width: 64px; padding: 0 14px; }
      table { min-width: 360px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="panel intro">
      <div class="brand">
        <div class="logo">AI</div>
        <div>
          <h1>Olist Analytics Chatbot</h1>
          <p>Hỏi dữ liệu ecommerce bằng ngôn ngữ tự nhiên.</p>
        </div>
      </div>

      <div class="status" aria-label="Trạng thái hệ thống">
        <div class="status-row"><span><span class="dot"></span>API</span><strong>Online</strong></div>
        <div class="status-row"><span>Schema</span><strong>analytics</strong></div>
        <div class="status-row"><span>Mode</span><strong>SELECT only</strong></div>
        <div class="status-row"><span>Tables</span><strong>9 marts</strong></div>
      </div>

      <div>
        <p class="section-title">Câu hỏi mẫu</p>
        <div class="examples">
          <button class="example">Total revenue by month</button>
          <button class="example">Top sellers by revenue</button>
          <button class="example">Orders by product category</button>
          <button class="example">Total orders by state</button>
        </div>
      </div>

      <div class="tips">
        <span>Gợi ý: hỏi về doanh thu, đơn hàng, seller, khách hàng, category hoặc thời gian.</span>
        <span>Câu SQL được hiển thị để dễ demo và kiểm tra kết quả.</span>
      </div>
    </section>

    <section class="panel chat">
      <header class="chat-header">
        <div class="chat-title">
          <strong>Chat với data warehouse</strong>
          <span>Trả lời dựa trên PostgreSQL schema analytics</span>
        </div>
        <div class="badge">Live data</div>
      </header>

      <div id="messages" class="messages">
        <div class="bubble bot">
          Nhập câu hỏi hoặc chọn câu hỏi mẫu bên trái. Kết quả sẽ gồm phần trả lời, bảng dữ liệu xem nhanh và SQL đã chạy.
        </div>
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
    const sendButton = document.querySelector(".send");

    function formatValue(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString("en-US") : value.toLocaleString("en-US", { maximumFractionDigits: 2 });
      return String(value);
    }

    function renderTable(rows) {
      if (!rows || rows.length === 0) return null;
      const columns = Object.keys(rows[0]).slice(0, 6);
      const tableWrap = document.createElement("div");
      tableWrap.className = "table-wrap";
      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");
      columns.forEach((column) => {
        const th = document.createElement("th");
        th.textContent = column;
        headRow.appendChild(th);
      });
      thead.appendChild(headRow);
      table.appendChild(thead);

      const tbody = document.createElement("tbody");
      rows.slice(0, 5).forEach((row) => {
        const tr = document.createElement("tr");
        columns.forEach((column) => {
          const td = document.createElement("td");
          td.textContent = formatValue(row[column]);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      return tableWrap;
    }

    function addBubble(content, cls, options = {}) {
      const el = document.createElement("div");
      el.className = `bubble ${cls}`;

      if (options.loading) {
        el.classList.add("loading");
        el.textContent = content;
      }

      if (options.meta) {
        el.classList.add("result");
        const head = document.createElement("div");
        head.className = "analysis-head";
        const titleWrap = document.createElement("div");
        const title = document.createElement("strong");
        const subtitle = document.createElement("span");
        title.textContent = "AI phân tích kết quả";
        subtitle.textContent = "Dựa trên SQL vừa sinh và dữ liệu trả về từ PostgreSQL";
        titleWrap.appendChild(title);
        titleWrap.appendChild(subtitle);
        const meta = document.createElement("div");
        meta.className = "result-meta";
        meta.textContent = options.meta;
        head.appendChild(titleWrap);
        head.appendChild(meta);
        el.appendChild(head);

        const body = document.createElement("div");
        body.className = "analysis-body";
        body.textContent = content;
        el.appendChild(body);
      } else if (!options.loading) {
        el.textContent = content;
      }

      const table = renderTable(options.rows);
      if (table) {
        const dataSection = document.createElement("div");
        dataSection.className = "data-section";
        const label = document.createElement("div");
        label.className = "section-label";
        label.textContent = "Bảng dữ liệu xem nhanh";
        dataSection.appendChild(label);
        dataSection.appendChild(table);
        el.appendChild(dataSection);
      }

      if (options.sql) {
        const sqlSection = document.createElement("div");
        sqlSection.className = "data-section";
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        const code = document.createElement("pre");
        summary.textContent = "Xem SQL";
        code.className = "sql";
        code.textContent = options.sql;
        details.appendChild(summary);
        details.appendChild(code);
        sqlSection.appendChild(details);
        el.appendChild(sqlSection);
      }

      messages.appendChild(el);
      messages.scrollTop = messages.scrollHeight;
      return el;
    }

    async function sendMessage(text) {
      addBubble(text, "user");
      input.value = "";
      input.disabled = true;
      sendButton.disabled = true;
      const pending = addBubble("Đang phân tích dữ liệu và chạy SQL...", "bot", { loading: true });

      try {
        const res = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, limit: 100 })
        });
        const data = await res.json();
        pending.remove();
        if (!res.ok) throw new Error(data.detail || "Request failed");
        addBubble(data.answer, "bot", {
          sql: data.sql,
          rows: data.result,
          meta: `${data.row_count} dòng trả về trong ${data.execution_time.toFixed(2)}s`
        });
      } catch (err) {
        pending.textContent = `Lỗi: ${err.message}`;
      } finally {
        input.disabled = false;
        sendButton.disabled = false;
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

        explanation = generate_answer(request.question, sql, rows)

        logger.info(f"Query completed successfully. Rows: {len(rows)}, Time: {execution_time:.2f}s")

        return QueryResponse(
            question=request.question,
            sql=sql,
            result=rows,
            row_count=len(rows),
            execution_time=execution_time,
            explanation=explanation,
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
