#!/usr/bin/env bash
set -euo pipefail

AIRFLOW_USER="${AIRFLOW_ADMIN_USERNAME:-admin}"
AIRFLOW_PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-admin}"
AIRFLOW_EMAIL="${AIRFLOW_ADMIN_EMAIL:-admin@example.com}"

airflow db migrate

if airflow users list | awk '{print $2}' | grep -qx "${AIRFLOW_USER}"; then
  airflow users reset-password --username "${AIRFLOW_USER}" --password "${AIRFLOW_PASSWORD}"
else
  airflow users create \
    --username "${AIRFLOW_USER}" \
    --password "${AIRFLOW_PASSWORD}" \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email "${AIRFLOW_EMAIL}"
fi

airflow scheduler &
exec airflow webserver
