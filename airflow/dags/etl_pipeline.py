from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

from olist_pipeline.constants import DEFAULT_ARGS, PROJECT_ROOT
from olist_pipeline.cosmos_helpers import build_dbt_task_group
from olist_pipeline.validations import (
    check_postgres_connectivity,
    validate_analytics_layer,
    validate_raw_layer,
    verify_source_files,
)


with DAG(
    dag_id="olist_etl_pipeline",
    default_args=DEFAULT_ARGS,
    description=(
        "Enterprise-style Olist warehouse pipeline with helper modules, "
        "layered ingestion checks, and Cosmos dbt task groups."
    ),
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["olist", "warehouse", "dbt", "airflow", "cosmos"],
    max_active_runs=1,
) as dag:
    with TaskGroup(
        "preflight_checks",
        tooltip="Validate source files and database connectivity before ingestion",
    ) as preflight_group:
        check_source_files = PythonOperator(
            task_id="check_source_files",
            python_callable=verify_source_files,
            execution_timeout=timedelta(minutes=3),
        )

        check_database_connection = PythonOperator(
            task_id="check_database_connection",
            python_callable=check_postgres_connectivity,
            execution_timeout=timedelta(minutes=3),
        )

        check_source_files >> check_database_connection

    with TaskGroup(
        "raw_ingestion",
        tooltip="Load raw CSV files into PostgreSQL and validate raw-layer quality",
    ) as raw_ingestion_group:
        ingest_raw_csv = BashOperator(
            task_id="ingest_raw_csv_to_postgres",
            bash_command=f"cd {PROJECT_ROOT} && python ingestion/load_data.py",
            execution_timeout=timedelta(minutes=30),
        )

        validate_raw_data = PythonOperator(
            task_id="validate_raw_layer",
            python_callable=validate_raw_layer,
            execution_timeout=timedelta(minutes=10),
        )

        ingest_raw_csv >> validate_raw_data

    with TaskGroup(
        "dbt_transformations",
        tooltip="Render each dbt model as a separate Airflow task using Astronomer Cosmos",
    ) as dbt_group:
        dbt_staging = build_dbt_task_group(
            group_id="staging_models",
            select=["path:models/staging"],
        )

        dbt_silver = build_dbt_task_group(
            group_id="silver_models",
            select=["path:models/silver"],
        )

        dbt_marts = build_dbt_task_group(
            group_id="mart_models",
            select=["path:models/marts"],
        )

        dbt_staging >> dbt_silver >> dbt_marts

    with TaskGroup(
        "quality_assurance",
        tooltip="Validate final analytics outputs after Cosmos dbt execution",
    ) as quality_group:
        validate_analytics_outputs = PythonOperator(
            task_id="validate_analytics_outputs",
            python_callable=validate_analytics_layer,
            execution_timeout=timedelta(minutes=10),
        )

    with TaskGroup(
        "publish_artifacts",
        tooltip="Generate dbt documentation artifacts for warehouse exploration",
    ) as publish_group:
        dbt_generate_docs = BashOperator(
            task_id="dbt_generate_docs",
            bash_command=(
                "rm -rf /tmp/dbt_docs_target && "
                "cd /opt/project/dbt_project && "
                "dbt docs generate --profiles-dir . "
                "--target-path /tmp/dbt_docs_target "
                "--no-partial-parse"
            ),
            execution_timeout=timedelta(minutes=10),
        )

    preflight_group >> raw_ingestion_group >> dbt_group >> quality_group >> publish_group
    dbt_group >> validate_analytics_outputs
