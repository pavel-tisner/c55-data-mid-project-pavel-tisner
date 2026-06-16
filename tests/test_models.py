"""Tests for CBS housing Pydantic models."""

import pytest
from pydantic import ValidationError
from src.models import CBSHousingRecord


def test_valid_cbs_housing_quarter_record():
    """A valid CBS housing record should be accepted."""
    record = CBSHousingRecord(
        ID=0,
        Regions="NL01  ",
        Periods="1995KW01",
        PriceIndexPurchasePrices_1=28.9,
        ChangesComparedToOnePeriodEarlier_2=None,
        ChangesComparedToOneYearEarlier_3=None,
        NumberOfDwellingsSold_4=30734,
        ChangesComparedToOnePeriodEarlier_5=None,
        ChangesComparedToOneYearEarlier_6=None,
        AveragePurchasePrice_7=89792,
        TotalValuePurchasePrices_8=2760,
    )

    assert record.ID == 0
    assert record.Regions == "NL01"
    assert record.Periods == "1995KW01"
    assert record.AveragePurchasePrice_7 == 89792


def test_valid_cbs_housing_year_record():
    """A valid CBS yearly housing record should be accepted."""
    record = CBSHousingRecord(
        ID=4,
        Regions="NL01  ",
        Periods="1995JJ00",
        PriceIndexPurchasePrices_1=29.6,
        NumberOfDwellingsSold_4=154568,
        AveragePurchasePrice_7=93750,
        TotalValuePurchasePrices_8=14491,
    )

    assert record.Regions == "NL01"
    assert record.Periods == "1995JJ00"


def test_missing_period_is_rejected():
    """Periods is required because the transform derives year and quarter from it."""
    with pytest.raises(ValidationError):
        CBSHousingRecord(
            ID=1,
            Regions="NL01  ",
            PriceIndexPurchasePrices_1=28.9,
            NumberOfDwellingsSold_4=30734,
            AveragePurchasePrice_7=89792,
            TotalValuePurchasePrices_8=2760,
        )


def test_invalid_period_format_is_rejected():
    """Periods must match a CBS quarter or year format."""
    with pytest.raises(ValidationError):
        CBSHousingRecord(
            ID=1,
            Regions="NL01  ",
            Periods="1995XX99",
            PriceIndexPurchasePrices_1=28.9,
            NumberOfDwellingsSold_4=30734,
            AveragePurchasePrice_7=89792,
            TotalValuePurchasePrices_8=2760,
        )


def test_negative_average_purchase_price_is_rejected():
    """Average purchase price cannot be negative."""
    with pytest.raises(ValidationError):
        CBSHousingRecord(
            ID=2,
            Regions="NL01  ",
            Periods="1995KW01",
            PriceIndexPurchasePrices_1=28.9,
            NumberOfDwellingsSold_4=30734,
            AveragePurchasePrice_7=-1,
            TotalValuePurchasePrices_8=2760,
        )
