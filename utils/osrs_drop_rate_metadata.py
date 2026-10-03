from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


RATE_PATTERN = re.compile(
    r"^(?:(?P<multiplier>\d+(?:\.\d+)?)\s*x\s*)?"
    r"1\s*/\s*(?P<denominator>\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DropRateEstimate:
    raw_rate: str
    parseable: bool
    minimum_expected_rolls: Decimal | None = None
    maximum_expected_rolls: Decimal | None = None
    representative_expected_rolls: Decimal | None = None


def normalise_drop_rate_text(value):
    return " ".join(
        str(
            value or ""
        )
        .strip()
        .split()
    )


def parse_decimal(value):
    try:
        return Decimal(
            str(
                value
            )
        )
    except InvalidOperation:
        return None


def parse_single_rate_term(term):
    text = normalise_drop_rate_text(
        term
    )

    if not text:
        return None

    if text.lower() == "always":
        return Decimal("1")

    match = RATE_PATTERN.match(
        text
    )

    if not match:
        return None

    denominator = parse_decimal(
        match.group(
            "denominator"
        )
    )
    multiplier = parse_decimal(
        match.group(
            "multiplier"
        )
        or "1"
    )

    if (
        denominator is None
        or multiplier is None
        or multiplier == 0
    ):
        return None

    return denominator / multiplier


def iter_rate_terms(raw_rate):
    text = normalise_drop_rate_text(
        raw_rate
    )

    if not text:
        return

    for semicolon_part in re.split(
        r"\s*;\s*",
        text,
    ):
        for range_part in re.split(
            r"\s+-\s+",
            semicolon_part,
        ):
            cleaned = normalise_drop_rate_text(
                range_part
            )

            if cleaned:
                yield cleaned


def parse_drop_rate(raw_rate):
    text = normalise_drop_rate_text(
        raw_rate
    )

    values = tuple(
        value
        for value in (
            parse_single_rate_term(
                term
            )
            for term in iter_rate_terms(
                text
            )
        )
        if value is not None
    )

    if not values:
        return DropRateEstimate(
            raw_rate=text,
            parseable=False,
        )

    return DropRateEstimate(
        raw_rate=text,
        parseable=True,
        minimum_expected_rolls=min(
            values
        ),
        maximum_expected_rolls=max(
            values
        ),
        representative_expected_rolls=sum(
            values,
            Decimal("0"),
        )
        / Decimal(
            len(
                values
            )
        ),
    )
