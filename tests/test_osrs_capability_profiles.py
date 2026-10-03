import pytest

from utils.osrs_capability_profiles import (
    CAPABILITY_SCORE_FIELDS,
    build_average_team_capability_profile_from_players,
    build_capability_profile_from_team,
    build_capability_profiles_from_teams,
)


def test_capability_score_fields_include_team_builder_scores():
    assert "skilling_score" in CAPABILITY_SCORE_FIELDS
    assert "raid_score" in CAPABILITY_SCORE_FIELDS
    assert "wilderness_boss_score" in CAPABILITY_SCORE_FIELDS
    assert "clue_activity_score" in CAPABILITY_SCORE_FIELDS


def test_build_capability_profile_from_team_uses_team_scores():
    profile = build_capability_profile_from_team(
        {
            "team_id": 7,
            "team_name": "Armadyl",
            "players": [
                {
                    "player_name": "One",
                },
                {
                    "player_name": "Two",
                },
            ],
            "skilling_score": 300,
            "raid_score": 8,
            "wilderness_boss_score": 2,
        }
    )

    assert profile.profile_id == "7"
    assert profile.display_name == "Armadyl"
    assert profile.player_count == 2
    assert profile.score_for(
        "skilling_score"
    ) == 300
    assert profile.score_for(
        "raid_score"
    ) == 8
    assert profile.score_for(
        "wilderness_boss_score"
    ) == 2
    assert profile.score_for(
        "missing_score"
    ) == 0


def test_build_capability_profiles_from_teams_preserves_team_order():
    profile_set = build_capability_profiles_from_teams(
        (
            {
                "team_id": 1,
                "team_name": "First",
                "players": [],
            },
            {
                "team_id": 2,
                "team_name": "Second",
                "players": [],
            },
        )
    )

    assert profile_set.source == "teams"
    assert [
        profile.display_name
        for profile in profile_set.profiles
    ] == [
        "First",
        "Second",
    ]


def test_average_team_profile_uses_group_scores_and_estimated_team_size():
    profile_set = build_average_team_capability_profile_from_players(
        players=(
            {
                "skilling_score": 100,
                "raid_score": 4,
            },
            {
                "skilling_score": 200,
                "raid_score": 2,
            },
            {
                "skilling_score": 300,
                "raid_score": 0,
            },
            {
                "skilling_score": 400,
                "raid_score": 2,
            },
        ),
        estimated_team_size=2,
    )

    profile = profile_set.profiles[0]

    assert profile_set.source == "wom_group_average"
    assert profile_set.estimated_team_size == 2
    assert profile.player_count == 2
    assert profile.score_for(
        "skilling_score"
    ) == 500
    assert profile.score_for(
        "raid_score"
    ) == 4


def test_average_team_profile_rejects_invalid_estimated_team_size():
    with pytest.raises(
        ValueError
    ):
        build_average_team_capability_profile_from_players(
            players=(),
            estimated_team_size=0,
        )
