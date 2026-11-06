"""Classify OSRS skill requirements with boostability.

This module evaluates individual skill thresholds only.
It does not approve Wiki observations, infer quest completion
or establish player eligibility.
"""


def classify_skill_requirement(
    required_level,
    boostable,
    player_level,
):
    """Classify one requirement without assuming temporary boosts."""

    if (
        type(required_level) is not int
        or not 1 <= required_level <= 99
    ):
        raise ValueError(
            "Required skill level must be an integer from 1 to 99."
        )

    if boostable not in ("yes", "no", "unknown"):
        raise ValueError(
            "Boostability must be yes, no or unknown."
        )

    if (
        type(player_level) is not int
        or not 1 <= player_level <= 99
    ):
        return "UNKNOWN_SKILL"

    if player_level >= required_level:
        return "MEETS_RECORDED_LEVEL"

    if boostable == "no":
        return "BELOW_NONBOOSTABLE"

    if boostable == "yes":
        return "BOOST_REQUIRED_UNCONFIRMED"

    return "UNKNOWN_BOOSTABILITY"
