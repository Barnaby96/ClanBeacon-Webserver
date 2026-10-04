import pytest

from utils.osrs_capability_profiles import (
    build_capability_profiles_from_rostered_players,
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


def test_build_capability_profiles_from_rostered_players_uses_db_roster_shape():
    fetched_names = []

    def fake_fetch_player(player_name):
        fetched_names.append(
            player_name
        )

        return {
            "name": player_name,
        }

    def fake_score_player(player_data):
        return {
            "player_name": player_data["name"],
            "skilling_score": 100,
            "raid_score": 2,
            "wilderness_boss_score": 1,
        }

    result = build_capability_profiles_from_rostered_players(
        {
            "Zamorak": (
                (
                    1,
                    "Alice",
                    0,
                    0,
                    0,
                    0,
                ),
                (
                    2,
                    "Bob",
                    0,
                    0,
                    0,
                    0,
                ),
            ),
            "Saradomin": (
                (
                    3,
                    "Charlie",
                    0,
                    0,
                    0,
                    0,
                ),
            ),
        },
        fetch_player=fake_fetch_player,
        score_player=fake_score_player,
    )

    assert fetched_names == [
        "Alice",
        "Bob",
        "Charlie",
    ]

    assert result.failed_players == ()
    assert result.profile_set.source == "current_teams"

    zamorak_profile = result.profile_set.profiles[0]
    assert zamorak_profile.display_name == "Zamorak"
    assert zamorak_profile.player_count == 2
    assert zamorak_profile.score_for(
        "skilling_score"
    ) == 200
    assert zamorak_profile.score_for(
        "raid_score"
    ) == 4
    assert zamorak_profile.score_for(
        "wilderness_boss_score"
    ) == 2


def test_build_capability_profiles_from_rostered_players_records_failures():
    def fake_fetch_player(player_name):
        if player_name == "Broken":
            raise RuntimeError(
                "WOM failed"
            )

        return {
            "name": player_name,
        }

    def fake_score_player(player_data):
        return {
            "player_name": player_data["name"],
            "solo_boss_score": 3,
        }

    result = build_capability_profiles_from_rostered_players(
        {
            "Armadyl": (
                (
                    1,
                    "Working",
                ),
                (
                    2,
                    "Broken",
                ),
            ),
        },
        fetch_player=fake_fetch_player,
        score_player=fake_score_player,
    )

    assert result.failed_players == (
        {
            "team_name": "Armadyl",
            "player_name": "Broken",
            "error": "WOM failed",
        },
    )

    profile = result.profile_set.profiles[0]
    assert profile.display_name == "Armadyl"
    assert profile.player_count == 1
    assert profile.score_for(
        "solo_boss_score"
    ) == 3
