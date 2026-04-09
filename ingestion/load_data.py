from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_connection import get_engine


RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw_csv"


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


def ensure_schemas(engine) -> None:
    with engine.begin() as connection:
        # Keep raw and analytics schemas separated for warehouse clarity.
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS analytics;"))


def load_csv_to_postgres(engine, csv_path: Path) -> None:
    table_name = csv_path.stem
    dataframe = basic_cleaning(pd.read_csv(csv_path))
    dataframe.to_sql(
        name=table_name,
        con=engine,
        schema="raw",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=500,
    )
    print(f"Loaded {csv_path.name} -> raw.{table_name} ({len(dataframe)} rows)")


def main() -> None:
    engine = get_engine()
    ensure_schemas(engine)
    # Load every CSV file in the raw_csv directory into the raw schema.
    for csv_path in sorted(RAW_DATA_DIR.glob("*.csv")):
        load_csv_to_postgres(engine, csv_path)
    print("Raw layer ingestion completed successfully.")


if __name__ == "__main__":
    main()
