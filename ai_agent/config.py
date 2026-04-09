import os


class Settings:
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "olist_dw")
    postgres_user = os.getenv("POSTGRES_USER", "olist")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "olist")

    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    api_host = os.getenv("AI_AGENT_HOST", "0.0.0.0")
    api_port = int(os.getenv("AI_AGENT_PORT", "8000"))


settings = Settings()
