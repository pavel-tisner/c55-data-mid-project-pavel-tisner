"""Pydantic models for CBS housing purchase price data."""

from pydantic import BaseModel, Field, field_validator


class CBSHousingRecord(BaseModel):
    """A single record from CBS OData table 85792ENG.

    Dataset: Existing owner-occupied dwellings; purchase prices, region and period.
    """

    ID: int
    Regions: str = Field(min_length=1)
    Periods: str = Field(min_length=6)

    PriceIndexPurchasePrices_1: float | None = None
    ChangesComparedToOnePeriodEarlier_2: float | None = None
    ChangesComparedToOneYearEarlier_3: float | None = None

    NumberOfDwellingsSold_4: int | None = Field(default=None, ge=0)
    ChangesComparedToOnePeriodEarlier_5: float | None = None
    ChangesComparedToOneYearEarlier_6: float | None = None

    AveragePurchasePrice_7: int | None = Field(default=None, ge=0)
    TotalValuePurchasePrices_8: int | None = Field(default=None, ge=0)

    @field_validator("Regions")
    @classmethod
    def region_must_be_stripped(cls, value: str) -> str:
        """Strip whitespace from CBS region codes."""
        stripped = value.strip()

        if not stripped:
            raise ValueError("region code cannot be empty")

        return stripped

    @field_validator("Periods")
    @classmethod
    def period_must_be_cbs_period(cls, value: str) -> str:
        """Check that period looks like a CBS quarter, for example 1995KW01."""

        stripped = value.strip()

        if len(stripped) != 8:
            raise ValueError(f"period must have 8 characters, got: {value}")

        year_part = stripped[:4]
        period_type = stripped[4:6]
        period_number = stripped[6:]

        if not year_part.isdigit():
            raise ValueError(f"period year must be numeric, got: {value}")

        if period_type == "KW" and period_number in ["01", "02", "03", "04"]:
            return stripped

        if period_type == "JJ" and period_number == "00":
            return stripped

        raise ValueError(
            f"period must be a CBS quarter like 1995KW01 or year like 1995JJ00, got: {value}"
        )
