import pytest

from utils import team_balancing


def make_player(
    name,
    total_level,
    combat_level,
    attack=1,
    strength=1,
    defence=1,
    ranged=1,
    prayer=1,
    magic=1,
    slayer=1
):
    skills = {
        "overall": {
            "level": total_level
        },
        "attack": {
            "level": attack
        },
        "strength": {
            "level": strength
        },
        "defence": {
            "level": defence
        },
        "ranged": {
            "level": ranged
        },
        "prayer": {
            "level": prayer
        },
        "magic": {
            "level": magic
        },
        "slayer": {
            "level": slayer
        }
    }

    return {
        "id": hash(name),
        "displayName": name,
        "combatLevel": combat_level,
        "latestSnapshot": {
            "data": {
                "skills": skills
            }
        }
    }


def test_calculate_player_balance_scores_uses_non_combat_level_total():
    player = make_player(
        "Skiller",
        total_level=1500,
        combat_level=80,
        attack=70,
        strength=70,
        defence=70,
        ranged=70,
        prayer=60,
        magic=75,
        slayer=65
    )

    result = team_balancing.calculate_player_balance_scores(
        player
    )

    assert result["player_name"] == "Skiller"
    assert result["total_level"] == 1500
    assert result["combat_level"] == 80
    assert result["combat_skill_total"] == 480
    assert result["skilling_score"] == 1020
    assert result["overall_score"] == 1500


def test_build_balanced_teams_spreads_players_across_team_count():
    players = [
        make_player("Player A", 2200, 126, 99, 99, 99, 99, 99, 99, 99),
        make_player("Player B", 2100, 120, 99, 99, 99, 99, 90, 99, 90),
        make_player("Player C", 1800, 100, 80, 80, 80, 80, 80, 80, 80),
        make_player("Player D", 1600, 90, 70, 70, 70, 70, 70, 70, 70),
        make_player("Player E", 1400, 80, 60, 60, 60, 60, 60, 60, 60),
        make_player("Player F", 1200, 70, 50, 50, 50, 50, 50, 50, 50)
    ]

    result = team_balancing.build_balanced_teams(
        players,
        team_count=3
    )

    assert len(result) == 3
    assert [team["player_count"] for team in result] == [2, 2, 2]

    assigned_players = {
        player["player_name"]
        for team in result
        for player in team["players"]
    }

    assert assigned_players == {
        "Player A",
        "Player B",
        "Player C",
        "Player D",
        "Player E",
        "Player F"
    }

    for team in result:
        assert team["reasons"]


def test_build_balanced_teams_requires_positive_team_count():
    with pytest.raises(
        ValueError,
        match="Team count must be greater than zero."
    ):
        team_balancing.build_balanced_teams(
            [],
            team_count=0
        )


def test_build_balanced_teams_keeps_apart_players_where_possible():
    players = [
        make_player("Winner One", 2200, 126, 99, 99, 99, 99, 99, 99, 99),
        make_player("Winner Two", 2100, 120, 99, 99, 99, 99, 90, 99, 90),
        make_player("Winner Three", 2000, 115, 90, 90, 90, 90, 90, 90, 90),
        make_player("Player Four", 1500, 90, 70, 70, 70, 70, 70, 70, 70),
        make_player("Player Five", 1400, 80, 60, 60, 60, 60, 60, 60, 60),
        make_player("Player Six", 1300, 70, 50, 50, 50, 50, 50, 50, 50)
    ]

    result = team_balancing.build_balanced_teams(
        players,
        team_count=3,
        keep_apart_groups=[
            [
                "Winner One",
                "Winner Two",
                "Winner Three"
            ]
        ]
    )

    for team in result:
        team_player_names = {
            player["player_name"]
            for player in team["players"]
        }

        assert len(
            team_player_names.intersection(
                {
                    "Winner One",
                    "Winner Two",
                    "Winner Three"
                }
            )
        ) == 1

        assert team["keep_apart_conflicts"] == []

        assert (
            "No keep-apart conflicts in this suggested team."
            in team["reasons"]
        )


def test_build_balanced_teams_reports_keep_apart_conflict_when_unavoidable():
    players = [
        make_player("Winner One", 2200, 126, 99, 99, 99, 99, 99, 99, 99),
        make_player("Winner Two", 2100, 120, 99, 99, 99, 99, 90, 99, 90),
        make_player("Winner Three", 2000, 115, 90, 90, 90, 90, 90, 90, 90)
    ]

    result = team_balancing.build_balanced_teams(
        players,
        team_count=2,
        keep_apart_groups=[
            [
                "Winner One",
                "Winner Two",
                "Winner Three"
            ]
        ]
    )

    conflict_teams = [
        team
        for team in result
        if team["keep_apart_conflicts"]
    ]

    assert len(conflict_teams) == 1

    conflict = conflict_teams[0]["keep_apart_conflicts"][0]

    assert conflict["player_name"] in {
        "Winner One",
        "Winner Two",
        "Winner Three"
    }

    assert len(conflict["conflicts_with"]) == 1

    assert any(
        "Keep-apart conflict:"
        in reason
        for reason in conflict_teams[0]["reasons"]
    )


def test_parse_keep_apart_text_builds_groups_from_lines():
    result = team_balancing.parse_keep_apart_text(
        """
        Winner One, Winner Two, Winner Three
        Solo Player
        Alpha, Bravo, alpha
        """
    )

    assert result == [
        [
            "Winner One",
            "Winner Two",
            "Winner Three"
        ],
        [
            "Alpha",
            "Bravo"
        ]
    ]
