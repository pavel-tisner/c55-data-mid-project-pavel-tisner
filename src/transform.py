"""Transform validated CBS records using pandas."""

import logging
from datetime import datetime, timezone
import pandas as pd
from src.models import CBSHousingRecord, CBSRegionRecord

log = logging.getLogger(__name__)


def build_region_lookup(region_records: list[CBSRegionRecord]) -> pd.DataFrame:
    """Build a region lookup DataFrame with code and human-readable name."""
    rows = [
        {
            "region_code": region.Key,
            "region_name": region.Title,
        }
        for region in region_records
    ]

    lookup_df = pd.DataFrame(rows)
    lookup_df = lookup_df.drop_duplicates(subset=["region_code"])

    log.info("Built region lookup with %d rows", len(lookup_df))
    return lookup_df


def transform(
    records: list[CBSHousingRecord],
    region_lookup: pd.DataFrame,
) -> pd.DataFrame:
    """Transform validated CBS records using pandas."""
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
    df = df.merge(region_lookup, on="region_code", how="left")
    df["region_name"] = df["region_name"].fillna(df["region_code"])

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
