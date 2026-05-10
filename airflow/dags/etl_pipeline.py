from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup


default_args = {
    "owner": "thesis-demo",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
    "email_on_failure": False,
    "email_on_retry": False,
}


def validate_data_quality():
    """Validate data quality after ingestion"""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(
        host="postgres",
        database="olist_dw",
        user="olist_user",
        password="olist_pass"
    )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if tables have data
            tables = ['olist_orders_dataset', 'olist_customers_dataset', 'olist_products_dataset']
            for table in tables:
                cur.execute(f"SELECT COUNT(*) as count FROM raw.{table}")
                result = cur.fetchone()
                if result['count'] == 0:
                    raise ValueError(f"Table raw.{table} is empty")

            # Check for data consistency
            cur.execute("""
                SELECT COUNT(*) as orders_with_customers
                FROM raw.olist_orders_dataset o
                LEFT JOIN raw.olist_customers_dataset c ON o.customer_id = c.customer_id
                WHERE c.customer_id IS NULL
            """)
            orphaned_orders = cur.fetchone()['orders_with_customers']
            if orphaned_orders > 0:
                raise ValueError(f"Found {orphaned_orders} orders without customers")

            print(f"✓ Data quality validation passed")

    finally:
        conn.close()


with DAG(
    dag_id="olist_etl_pipeline",
    default_args=default_args,
    description="Ingest Olist data, build dbt warehouse models, and run tests",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["olist", "thesis", "dw"],
    max_active_runs=1,
) as dag:

    with TaskGroup("data_ingestion", tooltip="Load raw CSV data into PostgreSQL") as ingest_group:
        ingest_data = BashOperator(
            task_id="ingest_raw_csv_to_postgres",
            bash_command="cd /opt/project && python ingestion/load_data.py",
            execution_timeout=timedelta(minutes=30),
        )

        validate_quality = PythonOperator(
            task_id="validate_data_quality",
            python_callable=validate_data_quality,
            execution_timeout=timedelta(minutes=5),
        )

        ingest_data >> validate_quality

    with TaskGroup("dbt_transformations", tooltip="Run dbt models and tests") as dbt_group:
        dbt_deps = BashOperator(
            task_id="dbt_install_deps",
            bash_command="cd /opt/project/dbt_project && dbt deps --profiles-dir .",
            execution_timeout=timedelta(minutes=10),
        )

        dbt_run = BashOperator(
            task_id="dbt_run_models",
            bash_command="cd /opt/project/dbt_project && dbt run --profiles-dir . --fail-fast",
            execution_timeout=timedelta(minutes=30),
        )

        dbt_test = BashOperator(
            task_id="dbt_test_models",
            bash_command="cd /opt/project/dbt_project && dbt test --profiles-dir . --fail-fast",
            execution_timeout=timedelta(minutes=15),
        )

        dbt_docs = BashOperator(
            task_id="dbt_generate_docs",
            bash_command="cd /opt/project/dbt_project && dbt docs generate --profiles-dir .",
            execution_timeout=timedelta(minutes=10),
        )

        dbt_deps >> dbt_run >> dbt_test >> dbt_docs

    # Set dependencies
    ingest_group >> dbt_group
