import pandas as pd
from sqlalchemy import create_engine, text

from config import settings


def _connection_string() -> str:
    return (
        "postgresql+psycopg2://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


engine = create_engine(_connection_string(), future=True)


def run_select_query(sql: str) -> list[dict]:
    normalized_sql = sql.strip().lower()
    if not normalized_sql.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    with engine.connect() as connection:
        dataframe = pd.read_sql_query(text(sql), connection)
    return dataframe.to_dict(orient="records")
