"""Main pipeline: fetch CBS housing data, validate, transform, and store."""

import logging
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from pydantic import ValidationError

from src.models import CBSHousingRecord
from src.storage import insert_housing_records, upload_raw_json

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.getLogger("azure").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

DEFAULT_API_URL = "https://opendata.cbs.nl/ODataApi/odata/85792ENG/TypedDataSet"


def fetch_data() -> list[dict]:
    """Fetch housing purchase price records from the CBS OData API."""
    api_url = os.environ.get("API_URL", DEFAULT_API_URL)

    response = requests.get(api_url, timeout=30)
    response.raise_for_status()

    payload = response.json()
    records = payload.get("value", [])

    log.info("Fetched %d records from CBS API", len(records))
    return records


def validate(raw_records: list[dict]) -> tuple[list[CBSHousingRecord], list[dict]]:
    """Validate raw CBS records and accumulate per-record errors."""
    valid = []
    errors = []

    for index, record in enumerate(raw_records):
        try:
            valid.append(CBSHousingRecord(**record))
        except ValidationError as error:
            errors.append(
                {
                    "index": index,
                    "record": record,
                    "errors": error.errors(),
                }
            )
    log.info("Validated %d / %d records", len(valid), len(raw_records))

    if errors:
        log.warning("Found %d invalid records", len(errors))

    return valid, errors


def transform(records: list[CBSHousingRecord]) -> pd.DataFrame:
    """Transform validated CBS records using pandas.

    Real transformation work:
    - rename CBS technical column names
    - parse year and quarter from Periods
    - convert numeric columns
    - handle null values
    - add ingestion timestamp
    """
    df = pd.DataFrame([record.model_dump() for record in records])

    df = df.rename(
        columns={
            "ID": "cbs_id",
            "Regions": "region_code",
            "Periods": "period",
            "PriceIndexPurchasePrices_1": "price_index_purchase_prices",
            "ChangesComparedToOnePeriodEarlier_2": "change_price_previous_period",
            "ChangesComparedToOneYearEarlier_3": "change_price_previous_year",
            "NumberOfDwellingsSold_4": "number_of_dwellings_sold",
            "ChangesComparedToOnePeriodEarlier_5": "change_sales_previous_period",
            "ChangesComparedToOneYearEarlier_6": "change_sales_previous_year",
            "AveragePurchasePrice_7": "average_purchase_price",
            "TotalValuePurchasePrices_8": "total_value_purchase_prices",
        }
    )

    df["region_code"] = df["region_code"].astype(str).str.strip()
    df["period"] = df["period"].astype(str).str.strip()
    df["period_year"] = pd.to_numeric(df["period"].str[:4], errors="coerce")
    df["period_type"] = (
        df["period"]
        .str[4:6]
        .map(
            {
                "KW": "quarter",
                "JJ": "year",
            }
        )
    )
    df["period_quarter"] = pd.to_numeric(df["period"].str[-2:], errors="coerce")
    df.loc[df["period_type"] == "year", "period_quarter"] = None

    numeric_columns = [
        "price_index_purchase_prices",
        "change_price_previous_period",
        "change_price_previous_year",
        "number_of_dwellings_sold",
        "change_sales_previous_period",
        "change_sales_previous_year",
        "average_purchase_price",
        "total_value_purchase_prices",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["cbs_id", "region_code", "period"])
    df = df.sort_values("cbs_id").tail(500)
    df["ingested_at"] = datetime.now(timezone.utc)

    log.info("Transformed %d rows", len(df))
    return df


def run() -> None:
    """Run the full pipeline: fetch -> validate -> transform -> store."""
    log.info("Pipeline starting")

    raw = fetch_data()
    records, errors = validate(raw)

    if errors:
        log.warning(
            "Continuing with %d valid records after validation errors", len(records)
        )

    if not records:
        log.error("No valid records to store")
        sys.exit(1)

    df = transform(records)

    if df.empty:
        log.error("No transformed rows to store")

        sys.exit(1)

    insert_housing_records(df)
    upload_raw_json(raw)

    log.info("Pipeline finished: %d records stored", len(df))


if __name__ == "__main__":
    required_env_vars = [
        "POSTGRES_URL",
        "AZURE_STORAGE_CONNECTION_STRING",
    ]

    for var in required_env_vars:
        if var not in os.environ:
            log.error("Missing required environment variable: %s", var)
            sys.exit(1)

    run()
