from pathlib import Path
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import text

from db_connection import get_engine


RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw_csv"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'logs/ingestion_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [column.strip().lower() for column in df.columns]
    return df


def basic_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    for column in df.columns:
        if "timestamp" in column or column.endswith("_at") or column.endswith("_date"):
            df[column] = pd.to_datetime(df[column], errors="coerce")
    object_columns = df.select_dtypes(include="object").columns
    for column in object_columns:
        df[column] = df[column].str.strip()
    return df


def validate_dataframe(df: pd.DataFrame, table_name: str) -> list[str]:
    """Validate dataframe before loading"""
    issues = []

    # Check if empty
    if df.empty:
        issues.append("DataFrame is empty")
        return issues

    # Primary key validation
    pk_map = {
        "olist_orders_dataset": "order_id",
        "olist_customers_dataset": "customer_id",
        "olist_products_dataset": "product_id",
        "olist_sellers_dataset": "seller_id",
    }

    if table_name in pk_map:
        pk = pk_map[table_name]
        if pk in df.columns:
            dups = df[pk].duplicated().sum()
            if dups > 0:
                issues.append(f"Found {dups} duplicate primary keys in {pk}")

            nulls = df[pk].isnull().sum()
            if nulls > 0:
                issues.append(f"Found {nulls} NULL values in primary key {pk}")

    # Check for unexpected NULL in critical columns
    critical_cols = ["customer_id", "order_id", "product_id", "seller_id"]
    for col in critical_cols:
        if col in df.columns and df[col].isnull().any():
            nulls = df[col].isnull().sum()
            issues.append(f"Found {nulls} NULL values in {col}")

    # Check numeric ranges
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        if (df[col] < 0).any() and "price" in col:
            issues.append(f"Found negative values in {col}")

    return issues


def ensure_schemas(engine) -> None:
    with engine.begin() as connection:
        # Keep raw and analytics schemas separated for warehouse clarity.
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS analytics;"))


def load_csv_to_postgres(engine, csv_path: Path, truncate: bool = True) -> int:
    """Load CSV with validation and error handling"""
    table_name = csv_path.stem

    try:
        logger.info(f"Starting to load {csv_path.name}")

        # Read and clean data
        df = basic_cleaning(pd.read_csv(csv_path))
        logger.info(f"Read {len(df)} rows from {csv_path.name}")

        # Validate data
        issues = validate_dataframe(df, table_name)
        if issues:
            for issue in issues:
                logger.warning(f"Data quality: {issue}")

        # Truncate if full refresh
        if truncate:
            with engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE raw.{table_name} CASCADE;"))
                logger.info(f"Truncated raw.{table_name}")

        # Load data
        df.to_sql(
            name=table_name,
            con=engine,
            schema="raw",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
        )

        logger.info(f"✓ Successfully loaded {csv_path.name} → raw.{table_name} ({len(df)} rows)")
        return len(df)

    except Exception as e:
        logger.error(f"✗ Failed to load {csv_path.name}: {str(e)}")
        raise


def main() -> None:
    logger.info("Starting data ingestion pipeline")

    engine = get_engine()
    ensure_schemas(engine)

    results = {
        "success": 0,
        "failed": 0,
        "total_rows": 0,
        "errors": []
    }

    # Load every CSV file in the raw_csv directory into the raw schema.
    for csv_path in sorted(RAW_DATA_DIR.glob("*.csv")):
        try:
            rows = load_csv_to_postgres(engine, csv_path)
            results["success"] += 1
            results["total_rows"] += rows
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{csv_path.name}: {str(e)}")

    logger.info(f"Ingestion summary: {results['success']} success, {results['failed']} failed, {results['total_rows']} total rows")

    if results["failed"] > 0:
        logger.error(f"Ingestion failed for {results['failed']} files: {results['errors']}")
        raise Exception(f"Ingestion failed for {results['failed']} files: {results['errors']}")

    logger.info("✓ Raw layer ingestion completed successfully.")


if __name__ == "__main__":
    main()
