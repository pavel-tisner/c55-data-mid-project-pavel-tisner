"""Validate CBS records using Pydantic models."""

import logging
from pydantic import ValidationError
from src.models import CBSHousingRecord, CBSRegionRecord

log = logging.getLogger(__name__)


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


def validate_regions(raw_regions: list[dict]) -> list[CBSRegionRecord]:
    """Validate CBS region lookup records, skipping invalid entries."""
    valid_regions = []

    for record in raw_regions:
        try:
            valid_regions.append(CBSRegionRecord(**record))
        except ValidationError as error:
            log.warning("Skipping invalid region record: %s", error)

    log.info("Validated %d region records", len(valid_regions))
    return valid_regions
