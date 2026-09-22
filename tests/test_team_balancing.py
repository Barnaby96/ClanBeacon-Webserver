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


def test_calculate_player_balance_scores_includes_bossing_categories():
    player = make_player(
        "PvM Tester",
        total_level=2200,
        combat_level=126,
        attack=99,
        strength=99,
        defence=99,
        ranged=99,
        prayer=99,
        magic=99,
        slayer=99
    )

    player["latestSnapshot"]["data"]["bosses"] = {
        "vorkath": {
            "kills": 151
        },
        "alchemical_hydra": {
            "kills": 51
        },
        "duke_sucellus": {
            "kills": 11
        },
        "tzkal_zuk": {
            "kills": 1
        },
        "general_graardor": {
            "kills": 501
        },
        "chambers_of_xeric": {
            "kills": 26
        },
        "callisto": {
            "kills": 1501
        },
        "barrows_chests": {
            "kills": 51
        },
        "wintertodt": {
            "kills": 501
        },
        "mimic": {
            "kills": 11
        }
    }

    player["latestSnapshot"]["data"]["activities"] = {
        "guardians_of_the_rift": {
            "score": 151
        },
        "clue_scrolls_elite": {
            "score": 11
        },
        "clue_scrolls_master": {
            "score": 1
        }
    }

    result = team_balancing.calculate_player_balance_scores(
        player
    )

    assert result["solo_boss_score"] == 4
    assert result["slayer_boss_score"] == 3
    assert result["dt2_boss_score"] == 2
    assert result["endgame_boss_score"] == 5
    assert result["group_boss_score"] == 5
    assert result["raid_score"] == 6
    assert result["wilderness_boss_score"] == 4
    assert result["midgame_boss_score"] == 3
    assert result["activity_boss_score"] == 9
    assert result["clue_activity_score"] == 5


def test_build_balanced_teams_tracks_bossing_category_totals():
    solo_player = make_player(
        "Solo Boss Player",
        2000,
        120
    )
    solo_player["latestSnapshot"]["data"]["bosses"] = {
        "zulrah": {
            "kills": 501
        }
    }

    raid_player = make_player(
        "Raid Player",
        2000,
        120
    )
    raid_player["latestSnapshot"]["data"]["bosses"] = {
        "tombs_of_amascut": {
            "kills": 151
        }
    }

    result = team_balancing.build_balanced_teams(
        [
            solo_player,
            raid_player
        ],
        team_count=2
    )

    assert sum(
        team["solo_boss_score"]
        for team in result
    ) == 5

    assert sum(
        team["raid_score"]
        for team in result
    ) == 10

    assert all(
        "solo_boss_score" in team
        for team in result
    )

    assert all(
        "raid_score" in team
        for team in result
    )




def make_layout_team(team_number, players, keep_apart_conflicts=None):
    scored_players = [
        team_balancing.calculate_player_balance_scores(
            player
        )
        for player in players
    ]

    team = {
        "team_number": team_number,
        "players": scored_players,
        "player_count": len(
            scored_players
        ),
        "total_level": sum(
            player["total_level"]
            for player in scored_players
        ),
        "combat_level": sum(
            player["combat_level"]
            for player in scored_players
        ),
        "skilling_score": sum(
            player["skilling_score"]
            for player in scored_players
        ),
        "keep_apart_conflicts": keep_apart_conflicts or []
    }

    for score_field in team_balancing.BOSS_SCORE_FIELDS:
        team[score_field] = sum(
            player[score_field]
            for player in scored_players
        )

    return team


def test_score_team_layout_penalises_stacked_raid_coverage():
    raid_player_one = make_player(
        "Raid Player One",
        2100,
        126
    )
    raid_player_one["latestSnapshot"]["data"]["bosses"] = {
        "tombs_of_amascut": {
            "kills": 151
        }
    }

    raid_player_two = make_player(
        "Raid Player Two",
        2100,
        126
    )
    raid_player_two["latestSnapshot"]["data"]["bosses"] = {
        "chambers_of_xeric": {
            "kills": 151
        }
    }

    non_raid_player_one = make_player(
        "Non Raid Player One",
        2100,
        126
    )

    non_raid_player_two = make_player(
        "Non Raid Player Two",
        2100,
        126
    )

    stacked_layout = [
        make_layout_team(
            1,
            [
                raid_player_one,
                raid_player_two
            ]
        ),
        make_layout_team(
            2,
            [
                non_raid_player_one,
                non_raid_player_two
            ]
        )
    ]

    spread_layout = [
        make_layout_team(
            1,
            [
                raid_player_one,
                non_raid_player_one
            ]
        ),
        make_layout_team(
            2,
            [
                raid_player_two,
                non_raid_player_two
            ]
        )
    ]

    stacked_score = team_balancing.score_team_layout(
        stacked_layout
    )
    spread_score = team_balancing.score_team_layout(
        spread_layout
    )

    assert stacked_score["total_penalty"] > spread_score["total_penalty"]
    assert (
        stacked_score["coverage"]["penalties"]["missing_raid_player"]
        > spread_score["coverage"]["penalties"]["missing_raid_player"]
    )


def test_score_team_layout_penalises_stacked_strong_skillers():
    strong_skiller_one = make_player(
        "Strong Skiller One",
        2200,
        100
    )

    strong_skiller_two = make_player(
        "Strong Skiller Two",
        2190,
        100
    )

    weaker_skiller_one = make_player(
        "Weaker Skiller One",
        1500,
        100
    )

    weaker_skiller_two = make_player(
        "Weaker Skiller Two",
        1500,
        100
    )

    stacked_layout = [
        make_layout_team(
            1,
            [
                strong_skiller_one,
                strong_skiller_two
            ]
        ),
        make_layout_team(
            2,
            [
                weaker_skiller_one,
                weaker_skiller_two
            ]
        )
    ]

    spread_layout = [
        make_layout_team(
            1,
            [
                strong_skiller_one,
                weaker_skiller_one
            ]
        ),
        make_layout_team(
            2,
            [
                strong_skiller_two,
                weaker_skiller_two
            ]
        )
    ]

    stacked_score = team_balancing.score_team_layout(
        stacked_layout
    )
    spread_score = team_balancing.score_team_layout(
        spread_layout
    )

    assert stacked_score["total_penalty"] > spread_score["total_penalty"]
    assert (
        stacked_score["coverage"]["penalties"]["missing_strong_skiller"]
        > spread_score["coverage"]["penalties"]["missing_strong_skiller"]
    )


def test_score_team_layout_penalises_keep_apart_conflicts_heavily():
    clean_layout = [
        make_layout_team(
            1,
            [
                make_player(
                    "Player One",
                    2000,
                    120
                )
            ]
        ),
        make_layout_team(
            2,
            [
                make_player(
                    "Player Two",
                    2000,
                    120
                )
            ]
        )
    ]

    conflict_layout = [
        make_layout_team(
            1,
            [
                make_player(
                    "Player One",
                    2000,
                    120
                )
            ],
            keep_apart_conflicts=[
                {
                    "player_name": "Player One",
                    "conflicts_with": [
                        "Player Two"
                    ]
                }
            ]
        ),
        make_layout_team(
            2,
            [
                make_player(
                    "Player Two",
                    2000,
                    120
                )
            ]
        )
    ]

    clean_score = team_balancing.score_team_layout(
        clean_layout
    )
    conflict_score = team_balancing.score_team_layout(
        conflict_layout
    )

    assert (
        conflict_score["total_penalty"]
        - clean_score["total_penalty"]
    ) >= team_balancing.COVERAGE_PENALTY_WEIGHTS["keep_apart_conflict"]




def test_optimise_team_layout_uses_player_moves_to_improve_score():
    raid_player = make_player(
        "Raid Player",
        2100,
        126
    )
    raid_player["latestSnapshot"]["data"]["bosses"] = {
        "tombs_of_amascut": {
            "kills": 151
        }
    }

    filler_one = make_player(
        "Filler One",
        2000,
        110
    )
    filler_two = make_player(
        "Filler Two",
        2000,
        110
    )
    filler_three = make_player(
        "Filler Three",
        2000,
        110
    )

    starting_layout = [
        make_layout_team(
            1,
            [
                raid_player,
                filler_one,
                filler_two
            ]
        ),
        make_layout_team(
            2,
            [
                filler_three
            ]
        )
    ]

    optimised_layout = team_balancing._optimise_team_layout(
        starting_layout,
        []
    )

    starting_score = team_balancing.score_team_layout(
        starting_layout
    )
    optimised_score = team_balancing.score_team_layout(
        optimised_layout
    )

    assert optimised_score["total_penalty"] < starting_score["total_penalty"]
    assert sorted(
        team["player_count"]
        for team in optimised_layout
    ) == [
        2,
        2
    ]


def test_optimise_team_layout_uses_player_swaps_to_improve_coverage():
    raid_player_one = make_player(
        "Raid Player One",
        2100,
        126
    )
    raid_player_one["latestSnapshot"]["data"]["bosses"] = {
        "tombs_of_amascut": {
            "kills": 151
        }
    }

    raid_player_two = make_player(
        "Raid Player Two",
        2100,
        126
    )
    raid_player_two["latestSnapshot"]["data"]["bosses"] = {
        "chambers_of_xeric": {
            "kills": 151
        }
    }

    non_raid_player_one = make_player(
        "Non Raid Player One",
        2100,
        126
    )

    non_raid_player_two = make_player(
        "Non Raid Player Two",
        2100,
        126
    )

    starting_layout = [
        make_layout_team(
            1,
            [
                raid_player_one,
                raid_player_two
            ]
        ),
        make_layout_team(
            2,
            [
                non_raid_player_one,
                non_raid_player_two
            ]
        )
    ]

    optimised_layout = team_balancing._optimise_team_layout(
        starting_layout,
        []
    )

    starting_score = team_balancing.score_team_layout(
        starting_layout
    )
    optimised_score = team_balancing.score_team_layout(
        optimised_layout
    )

    raid_counts = [
        sum(
            1
            for player in team["players"]
            if player["raid_score"] > 0
        )
        for team in optimised_layout
    ]

    assert optimised_score["total_penalty"] < starting_score["total_penalty"]
    assert sorted(
        raid_counts
    ) == [
        1,
        1
    ]




def test_build_optimisation_summary_describes_improvements():
    greedy_score = {
        "total_penalty": 300,
        "gap_penalties": {
            stat_name: {
                "penalty": 0
            }
            for stat_name in team_balancing.BALANCE_GAP_WEIGHTS
        },
        "coverage": {
            "penalties": {
                penalty_name: 0
                for penalty_name in team_balancing.COVERAGE_PENALTY_WEIGHTS
            }
        }
    }
    greedy_score["gap_penalties"]["raid_score"]["penalty"] = 90
    greedy_score["coverage"]["penalties"]["missing_raid_player"] = 1500

    optimised_score = {
        "total_penalty": 100,
        "gap_penalties": {
            stat_name: {
                "penalty": 0
            }
            for stat_name in team_balancing.BALANCE_GAP_WEIGHTS
        },
        "coverage": {
            "penalties": {
                penalty_name: 0
                for penalty_name in team_balancing.COVERAGE_PENALTY_WEIGHTS
            }
        }
    }
    optimised_score["gap_penalties"]["raid_score"]["penalty"] = 45
    optimised_score["coverage"]["penalties"]["missing_raid_player"] = 0

    summary = team_balancing._build_optimisation_summary(
        greedy_score,
        optimised_score
    )

    assert summary["greedy_total_penalty"] == 300
    assert summary["optimised_total_penalty"] == 100
    assert summary["total_improvement"] == 200
    assert (
        "No further one-player moves or two-player swaps improved the score."
        in summary["message"]
    )
    assert {
        "missing raid player",
        "raid score"
    }.issubset(
        {
            area["label"]
            for area in summary["changed_areas"]
        }
    )


def test_build_balanced_teams_includes_optimisation_summary():
    raid_player_one = make_player(
        "Raid Player One",
        2100,
        126
    )
    raid_player_one["latestSnapshot"]["data"]["bosses"] = {
        "tombs_of_amascut": {
            "kills": 151
        }
    }

    raid_player_two = make_player(
        "Raid Player Two",
        2100,
        126
    )
    raid_player_two["latestSnapshot"]["data"]["bosses"] = {
        "chambers_of_xeric": {
            "kills": 151
        }
    }

    non_raid_player_one = make_player(
        "Non Raid Player One",
        2100,
        126
    )

    non_raid_player_two = make_player(
        "Non Raid Player Two",
        2100,
        126
    )

    result = team_balancing.build_balanced_teams(
        [
            raid_player_one,
            raid_player_two,
            non_raid_player_one,
            non_raid_player_two
        ],
        team_count=2
    )

    summary = result[0]["optimisation_summary"]

    assert summary["optimised_total_penalty"] <= summary["greedy_total_penalty"]
    assert "message" in summary
    assert all(
        team["optimisation_summary"] == summary
        for team in result
    )
