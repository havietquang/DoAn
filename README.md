# Building a Data Warehouse for Olist E-commerce Dataset and Applying an AI Agent for Natural Language Data Querying

This starter project is designed for a graduation thesis demo. It shows how to ingest the Olist e-commerce CSV dataset, load it into PostgreSQL, transform it into a star schema with dbt, orchestrate the pipeline with Airflow, and expose an AI-powered natural language query interface through a FastAPI service and a minimal MCP server.

## Architecture Overview

The solution contains five connected layers:

1. Data ingestion
   Python scripts read CSV files from `data/raw_csv/`, perform light cleaning with Pandas, and load them into the `raw` schema in PostgreSQL.

2. Data warehouse storage
   PostgreSQL stores both the raw layer (`raw`) and transformed analytical models (`analytics`).

3. Data transformation
   dbt builds staging models and a simple star schema:
   - `analytics.fact_orders`
   - `analytics.dim_customers`
   - `analytics.dim_products`
   - `analytics.dim_sellers`
   - `analytics.dim_date`

4. Workflow orchestration
   Airflow runs the ETL pipeline in order:
   - ingestion
   - `dbt run`
   - `dbt test`

5. AI Agent
   A FastAPI app receives a natural language question, translates it to SQL with either:
   - a simple built-in mock LLM mapper, or
   - the OpenAI API if `OPENAI_API_KEY` is configured

   It then executes the SQL against PostgreSQL and returns the result with a short explanation.

   The same AI module also includes a minimal MCP server entry point so an MCP-compatible client can call warehouse tools.

## Project Structure

```text
project_root/
├── .env.example
├── README.md
├── docker-compose.yml
├── airflow/
│   └── dags/
│       └── etl_pipeline.py
├── ai_agent/
│   ├── app.py
│   ├── config.py
│   ├── llm_interface.py
│   ├── mcp_server.py
│   └── sql_executor.py
├── data/
│   └── raw_csv/
│       ├── olist_customers_dataset.csv
│       ├── olist_order_items_dataset.csv
│       ├── olist_orders_dataset.csv
│       ├── olist_products_dataset.csv
│       └── olist_sellers_dataset.csv
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── schema.yml
│       ├── staging/
│       │   ├── stg_customers.sql
│       │   ├── stg_order_items.sql
│       │   ├── stg_orders.sql
│       │   ├── stg_products.sql
│       │   └── stg_sellers.sql
│       └── marts/
│           ├── dim_customers.sql
│           ├── dim_date.sql
│           ├── dim_products.sql
│           ├── dim_sellers.sql
│           └── fact_orders.sql
├── docker/
│   ├── Dockerfile.ai
│   ├── Dockerfile.airflow
│   └── Dockerfile.dbt
├── ingestion/
│   ├── db_connection.py
│   └── load_data.py
└── requirements/
    ├── ai.txt
    ├── airflow.txt
    └── dbt.txt
```

## How to Run

### 1. Prepare environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

If you want to use the OpenAI API instead of the mock LLM rules, set:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 2. Start all services

```bash
docker compose up --build
```

This starts:
- PostgreSQL on port `5432`
- Airflow on port `8080`
- AI Agent API on port `8000`
- A dbt utility container for manual dbt commands

### 3. Run the ETL pipeline in Airflow

Open Airflow:

```text
http://localhost:8080
```

Airflow standalone creates an admin account automatically and prints the password in the container logs.

Trigger the DAG:

```text
olist_etl_pipeline
```

The DAG runs:
- `ingest_raw_csv_to_postgres`
- `dbt_run_models`
- `dbt_test_models`

### 4. Query the AI Agent

Example HTTP request:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Total revenue by month"}'
```

Expected behavior:
- The AI layer maps the question to SQL
- The SQL runs against `analytics.fact_orders`
- A JSON response returns the generated SQL, query result, and explanation

## Example Natural Language Questions

These work out of the box with the mock rule-based LLM:

- `Total revenue by month`
- `Total orders by state`
- `Top sellers by revenue`

If you configure `OPENAI_API_KEY`, you can ask a wider range of analytical questions.

## MCP Server

The project also includes a minimal MCP server implementation:

```bash
docker compose exec ai_agent bash -lc "cd /opt/project/ai_agent && python mcp_server.py"
```

It exposes two tools:
- `schema_overview`
- `query_warehouse`

## Manual Commands

### Run ingestion manually

```bash
docker compose exec airflow bash -lc "cd /opt/project && python ingestion/load_data.py"
```

### Run dbt manually

```bash
docker compose exec dbt bash -lc "cd /opt/project/dbt_project && dbt run --profiles-dir ."
docker compose exec dbt bash -lc "cd /opt/project/dbt_project && dbt test --profiles-dir ."
```

## Notes for Thesis Demo

- The provided CSV files are a small demo subset so the project runs quickly.
- In a real thesis implementation, replace the sample CSVs with the full Olist dataset.
- The star schema is intentionally simple but realistic enough for reporting and AI-driven querying.
- The AI agent is designed to be safe for demo use by only allowing `SELECT` statements.

## Suggested Demo Flow

1. Show the raw CSV files.
2. Run the Airflow DAG.
3. Show tables created in PostgreSQL under `raw` and `analytics`.
4. Ask the AI agent: `Total revenue by month`.
5. Explain how the LLM translates natural language into SQL over the warehouse.
