"""Storage functions for Postgres and Blob Storage."""

import base64
import json
import logging
import os
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import psycopg2
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from psycopg2.extras import execute_values

log = logging.getLogger(__name__)


def insert_housing_records(df: pd.DataFrame) -> None:
    """Insert transformed CBS housing records into Azure Postgres."""
    db_url = os.environ["POSTGRES_URL"]
    schema = os.environ.get("DB_SCHEMA", "public")

    rows = [_row_to_values(row) for _, row in df.iterrows()]

    with closing(psycopg2.connect(db_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")  # noqa: S608
            cur.execute(f"SET search_path TO {schema}")  # noqa: S608
            cur.execute("""
                DROP TABLE IF EXISTS cbs_housing_purchase_prices
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cbs_housing_purchase_prices (
                    id SERIAL PRIMARY KEY,
                    cbs_id INTEGER NOT NULL,
                    region_code TEXT NOT NULL,
                    region_name TEXT,
                    period TEXT NOT NULL,
                    period_year INTEGER,
                    period_type TEXT,
                    period_quarter INTEGER,
                    price_index_purchase_prices DOUBLE PRECISION,
                    change_price_previous_period DOUBLE PRECISION,
                    change_price_previous_year DOUBLE PRECISION,
                    number_of_dwellings_sold INTEGER,
                    change_sales_previous_period DOUBLE PRECISION,
                    change_sales_previous_year DOUBLE PRECISION,
                    average_purchase_price INTEGER,
                    total_value_purchase_prices INTEGER,
                    ingested_at TIMESTAMP NOT NULL
                )
            """)

            execute_values(
                cur,
                """
                INSERT INTO cbs_housing_purchase_prices (
                    cbs_id,
                    region_code,
                    region_name,
                    period,
                    period_year,
                    period_type,
                    period_quarter,
                    price_index_purchase_prices,
                    change_price_previous_period,
                    change_price_previous_year,
                    number_of_dwellings_sold,
                    change_sales_previous_period,
                    change_sales_previous_year,
                    average_purchase_price,
                    total_value_purchase_prices,
                    ingested_at
                )
                VALUES %s
                """,
                rows,
            )

        conn.commit()

    log.info("Inserted %d rows into %s.cbs_housing_purchase_prices", len(df), schema)


def upload_raw_json(raw_data: list[dict[str, Any]]) -> None:
    """Upload raw CBS API response records to Azure Blob Storage as JSON."""
    conn_str_b64 = os.environ.get("AZURE_STORAGE_CONNECTION_STRING_B64")
    if conn_str_b64:
        conn_str = base64.b64decode(conn_str_b64).decode("utf-8")
    else:
        conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]

    container_name = os.environ.get("BLOB_CONTAINER", "raw")

    blob_prefix = os.environ.get("BLOB_PREFIX", "cbs_housing")
    client = BlobServiceClient.from_connection_string(conn_str)

    container = client.get_container_client(container_name)

    try:
        container.create_container()
    except ResourceExistsError:
        pass

    blob_name = (
        f"{blob_prefix}/{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}.json"
    )

    container.upload_blob(
        name=blob_name,
        data=json.dumps(raw_data).encode("utf-8"),
        overwrite=True,
    )
    log.info("Uploaded raw data to blob: %s", blob_name)


def _row_to_values(row: pd.Series) -> tuple:
    """Convert one DataFrame row to values for Postgres insert."""
    return (
        int(row["cbs_id"]),
        row["region_code"],
        row["region_name"],
        row["period"],
        _none_if_nan(row["period_year"]),
        row["period_type"],
        _none_if_nan(row["period_quarter"]),
        _none_if_nan(row["price_index_purchase_prices"]),
        _none_if_nan(row["change_price_previous_period"]),
        _none_if_nan(row["change_price_previous_year"]),
        _none_if_nan(row["number_of_dwellings_sold"]),
        _none_if_nan(row["change_sales_previous_period"]),
        _none_if_nan(row["change_sales_previous_year"]),
        _none_if_nan(row["average_purchase_price"]),
        _none_if_nan(row["total_value_purchase_prices"]),
        row["ingested_at"].to_pydatetime()
        if hasattr(row["ingested_at"], "to_pydatetime")
        else row["ingested_at"],
    )


def _none_if_nan(value):
    """Convert pandas NaN values to None before inserting into Postgres."""
    if pd.isna(value):
        return None
    return value
