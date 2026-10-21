import pytest


@pytest.mark.parametrize(
    "snapshot_data, expected",
    [
        ({"skills": {"fishing": {"level": 87}}}, 87),
        ({"skills": {"fishing": {"level": 0}}}, 0),
        ({"skills": {"fishing": {"level": None}}}, None),
        ({"skills": {}}, None),
        ({}, None),
    ],
)
def test_wom_skill_level_preserves_unknown_values(
    snapshot_data,
    expected,
):
    from utils.osrs_procedural_capability import get_wom_skill_level

    player_data = {
        "latestSnapshot": {
            "data": snapshot_data,
        },
    }

    assert get_wom_skill_level(
        player_data,
        "fishing",
    ) == expected


@pytest.mark.parametrize(
    "snapshot_data, expected",
    [
        ({"bosses": {"zulrah": {"kills": 250}}}, 250),
        ({"bosses": {"zulrah": {"kills": 0}}}, 0),
        ({"bosses": {"zulrah": {"kills": None}}}, None),
        ({"bosses": {}}, None),
        ({}, None),
    ],
)
def test_wom_boss_kc_preserves_unknown_values(
    snapshot_data,
    expected,
):
    from utils.osrs_procedural_capability import get_wom_boss_kills

    player_data = {
        "latestSnapshot": {
            "data": snapshot_data,
        },
    }

    assert get_wom_boss_kills(
        player_data,
        "zulrah",
    ) == expected


def test_wom_missing_snapshot_returns_unknown():
    from utils.osrs_procedural_capability import (
        get_wom_skill_level,
        get_wom_boss_kills,
    )

    assert get_wom_skill_level({}, "fishing") is None
    assert get_wom_boss_kills({}, "zulrah") is None