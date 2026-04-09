from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "thesis-demo",
    "depends_on_past": False,
}


with DAG(
    dag_id="olist_etl_pipeline",
    default_args=default_args,
    description="Ingest Olist data, build dbt warehouse models, and run tests",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["olist", "thesis", "dw"],
) as dag:
    ingest_data = BashOperator(
        task_id="ingest_raw_csv_to_postgres",
        bash_command="cd /opt/project && python ingestion/load_data.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run_models",
        bash_command="cd /opt/project/dbt_project && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test_models",
        bash_command="cd /opt/project/dbt_project && dbt test --profiles-dir .",
    )

    ingest_data >> dbt_run >> dbt_test
