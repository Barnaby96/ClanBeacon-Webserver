from decimal import Decimal

from utils.osrs_drop_group_data import DROP_GROUP_DATA
from utils.osrs_drop_rate_metadata import (
    parse_drop_rate,
    parse_single_rate_term,
)


def test_parse_single_fraction_rate():
    estimate = parse_drop_rate(
        "1/512"
    )

    assert estimate.parseable
    assert estimate.minimum_expected_rolls == Decimal(
        "512"
    )
    assert estimate.maximum_expected_rolls == Decimal(
        "512"
    )
    assert estimate.representative_expected_rolls == Decimal(
        "512"
    )


def test_parse_always_rate_as_one_expected_roll():
    estimate = parse_drop_rate(
        "Always"
    )

    assert estimate.parseable
    assert estimate.minimum_expected_rolls == Decimal(
        "1"
    )
    assert estimate.maximum_expected_rolls == Decimal(
        "1"
    )


def test_parse_multiplied_fraction_rate():
    assert parse_single_rate_term(
        "7 x 1/2448"
    ) == Decimal(
        "2448"
    ) / Decimal(
        "7"
    )


def test_parse_semicolon_alternative_rates():
    estimate = parse_drop_rate(
        "1/15; 1/14"
    )

    assert estimate.parseable
    assert estimate.minimum_expected_rolls == Decimal(
        "14"
    )
    assert estimate.maximum_expected_rolls == Decimal(
        "15"
    )
    assert estimate.representative_expected_rolls == Decimal(
        "14.5"
    )


def test_parse_range_rates_with_decimal_denominators():
    estimate = parse_drop_rate(
        "1/206.67 - 1/8.43"
    )

    assert estimate.parseable
    assert estimate.minimum_expected_rolls == Decimal(
        "8.43"
    )
    assert estimate.maximum_expected_rolls == Decimal(
        "206.67"
    )


def test_parse_unknown_rate_as_unparseable():
    estimate = parse_drop_rate(
        "varies by contribution"
    )

    assert not estimate.parseable
    assert estimate.minimum_expected_rolls is None
    assert estimate.maximum_expected_rolls is None
    assert estimate.representative_expected_rolls is None


def test_all_generated_drop_rates_are_parseable():
    unparseable_rates = sorted(
        {
            rate
            for record in DROP_GROUP_DATA
            for rate in record.get(
                "drop_rates",
                ()
            )
            if rate
            and not parse_drop_rate(
                rate
            ).parseable
        }
    )

    assert unparseable_rates == []
