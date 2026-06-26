"""Ingest data from CBS Open Data API."""

import logging
import os
import requests

log = logging.getLogger(__name__)

DEFAULT_API_URL = "https://opendata.cbs.nl/ODataApi/odata/85792ENG/TypedDataSet"
DEFAULT_REGIONS_URL = "https://opendata.cbs.nl/ODataApi/odata/85792ENG/Regions"


def fetch_data() -> list[dict]:
    """Fetch housing purchase price records from the CBS OData API."""
    api_url = os.environ.get("API_URL", DEFAULT_API_URL)

    response = requests.get(api_url, timeout=30)
    response.raise_for_status()

    payload = response.json()
    records = payload.get("value", [])

    log.info("Fetched %d records from CBS API", len(records))
    return records


def fetch_region_data() -> list[dict]:
    """Fetch region lookup records from the CBS Regions endpoint."""
    regions_url = os.environ.get("REGIONS_URL", DEFAULT_REGIONS_URL)

    response = requests.get(regions_url, timeout=30)
    response.raise_for_status()

    payload = response.json()
    records = payload.get("value", [])

    log.info("Fetched %d region records from CBS API", len(records))
    return records
