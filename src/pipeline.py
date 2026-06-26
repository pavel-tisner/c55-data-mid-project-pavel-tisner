"""Main pipeline orchestration: fetch, validate, transform, and store CBS data."""

import logging
import os
import sys

from src.ingest import fetch_data, fetch_region_data
from src.storage import insert_housing_records, upload_raw_json
from src.transform import build_region_lookup, transform
from src.validate import validate, validate_regions

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.getLogger("azure").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

def run() -> None:
    """Run the full pipeline: fetch -> validate -> transform -> store."""
    log.info("Pipeline starting")

    raw = fetch_data()
    raw_regions = fetch_region_data()

    records, errors = validate(raw)
    region_records = validate_regions(raw_regions)
    region_lookup = build_region_lookup(region_records)

    if errors:
        log.warning(
            "Continuing with %d valid records after validation errors", len(records)
        )

    if not records:
        log.error("No valid records to store")
        sys.exit(1)

    df = transform(records, region_lookup)

    if df.empty:
        log.error("No transformed rows to store")
        sys.exit(1)

    insert_housing_records(df)
    upload_raw_json(raw)

    log.info("Pipeline finished: %d records stored", len(df))


if __name__ == "__main__":
    if not os.environ.get("POSTGRES_URL"):
        log.error("Missing required environment variable: POSTGRES_URL")
        sys.exit(1)

    if not (
        os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        or os.environ.get("AZURE_STORAGE_CONNECTION_STRING_B64")
    ):
        log.error(
            "Missing required environment variable: "
            "AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_CONNECTION_STRING_B64"
        )
        sys.exit(1)

    run()
