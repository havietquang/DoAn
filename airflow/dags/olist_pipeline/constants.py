from pathlib import Path


PROJECT_ROOT = Path("/opt/project")
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"
DBT_PROFILES_PATH = DBT_PROJECT_DIR / "profiles.yml"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw_csv"

RAW_TABLES = [
    "olist_orders_dataset",
    "olist_order_items_dataset",
    "olist_order_payments_dataset",
    "olist_order_reviews_dataset",
    "olist_customers_dataset",
    "olist_products_dataset",
    "olist_sellers_dataset",
    "product_category_name_translation",
]

EXPECTED_RAW_FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]

ANALYTICS_TABLES = [
    "dim_customers",
    "dim_products",
    "dim_sellers",
    "dim_date",
    "fact_orders",
    "fact_order_items",
    "agg_sales_monthly",
    "agg_seller_performance",
    "agg_category_performance",
]

DEFAULT_ARGS = {
    "owner": "thesis-demo",
    "depends_on_past": False,
    "retries": 2,
}
