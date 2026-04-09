import os

from sqlalchemy import create_engine


def build_connection_string() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "olist_dw")
    user = os.getenv("POSTGRES_USER", "olist")
    password = os.getenv("POSTGRES_PASSWORD", "olist")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def get_engine():
    return create_engine(build_connection_string(), future=True)
