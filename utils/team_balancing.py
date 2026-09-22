COMBAT_SKILLS = (
    "attack",
    "strength",
    "defence",
    "ranged",
    "prayer",
    "magic",
    "slayer"
)


SOLO_BOSS_METRICS = (
    "vorkath",
    "zulrah",
    "phantom_muspah",
    "the_gauntlet",
    "the_corrupted_gauntlet",
    "amoxliatl",
    "doom_of_mokhaiotl",
    "mad_angel",
    "maggot_king",
    "shellbane_gryphon"
)


SLAYER_BOSS_METRICS = (
    "alchemical_hydra",
    "cerberus",
    "grotesque_guardians",
    "abyssal_sire",
    "thermonuclear_smoke_devil",
    "kraken",
    "araxxor"
)


DT2_BOSS_METRICS = (
    "duke_sucellus",
    "vardorvis",
    "the_leviathan",
    "the_whisperer"
)


ENDGAME_BOSS_METRICS = (
    "tzkal_zuk",
    "sol_heredit"
)


GROUP_BOSS_METRICS = (
    "nex",
    "commander_zilyana",
    "general_graardor",
    "kreearra",
    "kril_tsutsaroth",
    "nightmare",
    "phosanis_nightmare",
    "corporeal_beast",
    "yama",
    "the_hueycoatl",
    "the_royal_titans"
)


RAID_METRICS = (
    "chambers_of_xeric",
    "chambers_of_xeric_challenge_mode",
    "theatre_of_blood",
    "theatre_of_blood_hard_mode",
    "tombs_of_amascut",
    "tombs_of_amascut_expert"
)


WILDERNESS_BOSS_METRICS = (
    "callisto",
    "venenatis",
    "vetion",
    "artio",
    "spindel",
    "calvarion",
    "chaos_elemental",
    "chaos_fanatic",
    "crazy_archaeologist",
    "scorpia"
)


MIDGAME_BOSS_METRICS = (
    "barrows_chests",
    "sarachnis",
    "giant_mole",
    "king_black_dragon",
    "kalphite_queen",
    "dagannoth_prime",
    "dagannoth_rex",
    "dagannoth_supreme",
    "scurrius",
    "lunar_chests",
    "hespori",
    "skotizo",
    "bryophyta",
    "obor",
    "brutus",
    "tztok_jad",
    "deranged_archaeologist"
)


ACTIVITY_BOSS_METRICS = (
    "wintertodt",
    "tempoross",
    "zalcano",
    "guardians_of_the_rift"
)


CLUE_ACTIVITY_BOSS_METRICS = (
    "mimic",
)


CLUE_ACTIVITY_METRICS = (
    "clue_scrolls_all",
    "clue_scrolls_elite",
    "clue_scrolls_master"
)


BOSS_SCORE_FIELDS = (
    "solo_boss_score",
    "slayer_boss_score",
    "dt2_boss_score",
    "endgame_boss_score",
    "group_boss_score",
    "raid_score",
    "wilderness_boss_score",
    "midgame_boss_score",
    "activity_boss_score",
    "clue_activity_score"
)


BALANCE_GAP_WEIGHTS = {
    "player_count": 10000,
    "raid_score": 90,
    "endgame_boss_score": 85,
    "group_boss_score": 65,
    "combat_level": 55,
    "combat_skill_total": 50,
    "dt2_boss_score": 50,
    "solo_boss_score": 40,
    "slayer_boss_score": 40,
    "skilling_score": 30,
    "activity_boss_score": 30,
    "total_level": 25,
    "wilderness_boss_score": 20,
    "midgame_boss_score": 15,
    "clue_activity_score": 10
}


BALANCE_GAP_SCALES = {
    "player_count": 1,
    "raid_score": 1,
    "endgame_boss_score": 1,
    "group_boss_score": 1,
    "combat_level": 5,
    "combat_skill_total": 25,
    "dt2_boss_score": 1,
    "solo_boss_score": 1,
    "slayer_boss_score": 1,
    "skilling_score": 100,
    "activity_boss_score": 1,
    "total_level": 100,
    "wilderness_boss_score": 1,
    "midgame_boss_score": 1,
    "clue_activity_score": 1
}


COVERAGE_PENALTY_WEIGHTS = {
    "missing_strong_pvmer": 1200,
    "missing_group_pvmer": 900,
    "missing_raid_player": 1500,
    "missing_extra_raid_player": 400,
    "missing_strong_skiller": 800,
    "keep_apart_conflict": 100000
}


def _safe_int(value, default=0):
    try:
        return int(value)
    except (
        TypeError,
        ValueError
    ):
        return default


def _get_snapshot_data(player_data):
    snapshot = player_data.get("latestSnapshot") or {}
    return snapshot.get("data") or {}


def _get_skill_level(player_data, skill_name):
    snapshot_data = _get_snapshot_data(
        player_data
    )
    skills = snapshot_data.get("skills") or {}
    skill = skills.get(skill_name) or {}

    return _safe_int(
        skill.get("level")
    )


def _get_metric_value(
    player_data,
    section_name,
    metric_name
):
    snapshot_data = _get_snapshot_data(
        player_data
    )
    section = snapshot_data.get(
        section_name
    ) or {}
    metric = section.get(
        metric_name
    ) or {}

    value = metric.get(
        "kills"
    )

    if value is None:
        value = metric.get(
            "score"
        )

    return _safe_int(
        value
    )


def _tiered_score(
    value,
    tiers
):
    value = _safe_int(
        value
    )

    for minimum_value, score in tiers:
        if value >= minimum_value:
            return score

    return 0


def _normal_boss_score(value):
    return _tiered_score(
        value,
        (
            (501, 5),
            (151, 4),
            (51, 3),
            (11, 2),
            (1, 1)
        )
    )


def _raid_score(value):
    return _tiered_score(
        value,
        (
            (151, 10),
            (76, 8),
            (26, 6),
            (6, 4),
            (1, 2)
        )
    )


def _endgame_score(value):
    return _tiered_score(
        value,
        (
            (21, 10),
            (6, 9),
            (2, 7),
            (1, 5)
        )
    )


def _wilderness_boss_score(value):
    return _tiered_score(
        value,
        (
            (3001, 5),
            (1501, 4),
            (501, 3),
            (101, 2),
            (1, 1)
        )
    )


def _calculate_metric_group_score(
    player_data,
    section_name,
    metric_names,
    score_function
):
    return sum(
        score_function(
            _get_metric_value(
                player_data,
                section_name,
                metric_name
            )
        )
        for metric_name in metric_names
    )


def _calculate_clue_activity_score(player_data):
    boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        CLUE_ACTIVITY_BOSS_METRICS,
        _normal_boss_score
    )

    activity_score = _calculate_metric_group_score(
        player_data,
        "activities",
        CLUE_ACTIVITY_METRICS,
        _normal_boss_score
    )

    return boss_score + activity_score


def calculate_player_balance_scores(player_data):
    total_level = _get_skill_level(
        player_data,
        "overall"
    )

    combat_level = _safe_int(
        player_data.get("combatLevel")
    )

    combat_skill_total = sum(
        _get_skill_level(
            player_data,
            skill_name
        )
        for skill_name in COMBAT_SKILLS
    )

    skilling_score = max(
        total_level - combat_skill_total,
        0
    )

    display_name = str(
        player_data.get("displayName")
        or player_data.get("username")
        or ""
    ).strip()

    solo_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        SOLO_BOSS_METRICS,
        _normal_boss_score
    )

    slayer_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        SLAYER_BOSS_METRICS,
        _normal_boss_score
    )

    dt2_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        DT2_BOSS_METRICS,
        _normal_boss_score
    )

    endgame_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        ENDGAME_BOSS_METRICS,
        _endgame_score
    )

    group_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        GROUP_BOSS_METRICS,
        _normal_boss_score
    )

    raid_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        RAID_METRICS,
        _raid_score
    )

    wilderness_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        WILDERNESS_BOSS_METRICS,
        _wilderness_boss_score
    )

    midgame_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        MIDGAME_BOSS_METRICS,
        _normal_boss_score
    )

    activity_boss_score = _calculate_metric_group_score(
        player_data,
        "bosses",
        ACTIVITY_BOSS_METRICS,
        _normal_boss_score
    )

    activity_boss_score += _calculate_metric_group_score(
        player_data,
        "activities",
        ("guardians_of_the_rift",),
        _normal_boss_score
    )

    clue_activity_score = _calculate_clue_activity_score(
        player_data
    )

    return {
        "player_id": player_data.get("id"),
        "player_name": display_name,
        "player_key": display_name.casefold(),
        "total_level": total_level,
        "combat_level": combat_level,
        "combat_skill_total": combat_skill_total,
        "skilling_score": skilling_score,
        "overall_score": total_level,
        "solo_boss_score": solo_boss_score,
        "slayer_boss_score": slayer_boss_score,
        "dt2_boss_score": dt2_boss_score,
        "endgame_boss_score": endgame_boss_score,
        "group_boss_score": group_boss_score,
        "raid_score": raid_score,
        "wilderness_boss_score": wilderness_boss_score,
        "midgame_boss_score": midgame_boss_score,
        "activity_boss_score": activity_boss_score,
        "clue_activity_score": clue_activity_score
    }


def _normalise_keep_apart_groups(keep_apart_groups):
    normalised_groups = []

    for group in keep_apart_groups or []:
        normalised_group = {
            str(player_name).strip().casefold()
            for player_name in group
            if str(player_name).strip()
        }

        if len(normalised_group) > 1:
            normalised_groups.append(
                normalised_group
            )

    return normalised_groups


def parse_keep_apart_text(keep_apart_text):
    groups = []

    for line in str(
        keep_apart_text or ""
    ).splitlines():
        group = []
        seen_players = set()

        for player_name in line.split(","):
            player_name = player_name.strip()

            if not player_name:
                continue

            player_key = player_name.casefold()

            if player_key in seen_players:
                continue

            seen_players.add(
                player_key
            )

            group.append(
                player_name
            )

        if len(group) > 1:
            groups.append(
                group
            )

    return groups


def _find_keep_apart_conflicts(
    team,
    player,
    keep_apart_groups
):
    conflicts = []

    for group in keep_apart_groups:
        if player["player_key"] not in group:
            continue

        for team_player in team["players"]:
            if team_player["player_key"] in group:
                conflicts.append(
                    team_player["player_name"]
                )

    return sorted(
        set(conflicts),
        key=str.casefold
    )


def build_balanced_teams(
    players,
    team_count,
    keep_apart_groups=None
):
    team_count = _safe_int(
        team_count
    )

    if team_count <= 0:
        raise ValueError(
            "Team count must be greater than zero."
        )

    normalised_keep_apart_groups = _normalise_keep_apart_groups(
        keep_apart_groups
    )

    scored_players = [
        calculate_player_balance_scores(
            player
        )
        for player in players
    ]

    teams = [
        {
            "team_number": team_number,
            "players": [],
            "player_count": 0,
            "total_level": 0,
            "combat_level": 0,
            "skilling_score": 0,
            **{
                score_field: 0
                for score_field in BOSS_SCORE_FIELDS
            },
            "keep_apart_conflicts": []
        }
        for team_number in range(
            1,
            team_count + 1
        )
    ]

    sorted_players = sorted(
        scored_players,
        key=lambda player: (
            player["overall_score"],
            player["combat_level"],
            player["skilling_score"],
            max(
                player[score_field]
                for score_field in BOSS_SCORE_FIELDS
            ),
            player["player_name"].casefold()
        ),
        reverse=True
    )

    for player in sorted_players:
        target_team = min(
            teams,
            key=lambda team: (
                len(
                    _find_keep_apart_conflicts(
                        team,
                        player,
                        normalised_keep_apart_groups
                    )
                ),
                team["player_count"],
                team["total_level"],
                team["combat_level"],
                team["skilling_score"],
                *(
                    team[score_field]
                    for score_field in BOSS_SCORE_FIELDS
                )
            )
        )

        conflicts = _find_keep_apart_conflicts(
            target_team,
            player,
            normalised_keep_apart_groups
        )

        if conflicts:
            target_team["keep_apart_conflicts"].append(
                {
                    "player_name": player["player_name"],
                    "conflicts_with": conflicts
                }
            )

        target_team["players"].append(
            player
        )
        target_team["player_count"] += 1
        target_team["total_level"] += player["total_level"]
        target_team["combat_level"] += player["combat_level"]
        target_team["skilling_score"] += player["skilling_score"]

        for score_field in BOSS_SCORE_FIELDS:
            target_team[score_field] += player[score_field]

    greedy_teams = _clone_team_layout(
        teams,
        normalised_keep_apart_groups
    )
    greedy_score = score_team_layout(
        greedy_teams
    )

    teams = _optimise_team_layout(
        teams,
        normalised_keep_apart_groups
    )
    optimised_score = score_team_layout(
        teams
    )
    optimisation_summary = _build_optimisation_summary(
        greedy_score,
        optimised_score
    )

    _add_player_placement_notes(
        teams
    )

    for team in teams:
        team["optimisation_summary"] = optimisation_summary
        team["reasons"] = _build_team_reasons(
            team
        )

    return teams




def _find_team_keep_apart_conflicts(
    team,
    keep_apart_groups
):
    conflicts = []

    for player_index, player in enumerate(
        team.get(
            "players",
            []
        )
    ):
        comparison_team = {
            "players": team.get(
                "players",
                []
            )[:player_index]
        }

        player_conflicts = _find_keep_apart_conflicts(
            comparison_team,
            player,
            keep_apart_groups
        )

        if player_conflicts:
            conflicts.append(
                {
                    "player_name": player["player_name"],
                    "conflicts_with": player_conflicts
                }
            )

    return conflicts


def _recalculate_team_totals(
    team,
    keep_apart_groups
):
    players = team.get(
        "players",
        []
    )

    team["player_count"] = len(
        players
    )
    team["total_level"] = sum(
        player["total_level"]
        for player in players
    )
    team["combat_level"] = sum(
        player["combat_level"]
        for player in players
    )
    team["combat_skill_total"] = sum(
        player["combat_skill_total"]
        for player in players
    )
    team["skilling_score"] = sum(
        player["skilling_score"]
        for player in players
    )

    for score_field in BOSS_SCORE_FIELDS:
        team[score_field] = sum(
            player[score_field]
            for player in players
        )

    team["keep_apart_conflicts"] = _find_team_keep_apart_conflicts(
        team,
        keep_apart_groups
    )

    return team


def _recalculate_layout_totals(
    teams,
    keep_apart_groups
):
    for team in teams:
        _recalculate_team_totals(
            team,
            keep_apart_groups
        )

    return teams


def _clone_team_layout(
    teams,
    keep_apart_groups
):
    cloned_teams = [
        {
            "team_number": team["team_number"],
            "players": list(
                team.get(
                    "players",
                    []
                )
            ),
            "keep_apart_conflicts": []
        }
        for team in teams
    ]

    return _recalculate_layout_totals(
        cloned_teams,
        keep_apart_groups
    )


def _layout_total_penalty(teams):
    return score_team_layout(
        teams
    )["total_penalty"]




def _penalty_change(
    label,
    before,
    after
):
    improvement = before - after

    return {
        "label": label,
        "before": before,
        "after": after,
        "improvement": improvement,
        "direction": "improved" if improvement > 0 else "worsened"
    }


def _build_optimisation_summary(
    greedy_score,
    optimised_score
):
    changed_areas = []

    for stat_name in BALANCE_GAP_WEIGHTS:
        before = greedy_score["gap_penalties"][stat_name]["penalty"]
        after = optimised_score["gap_penalties"][stat_name]["penalty"]

        if before == after:
            continue

        changed_areas.append(
            _penalty_change(
                stat_name.replace(
                    "_",
                    " "
                ),
                before,
                after
            )
        )

    for penalty_name in COVERAGE_PENALTY_WEIGHTS:
        before = greedy_score["coverage"]["penalties"][penalty_name]
        after = optimised_score["coverage"]["penalties"][penalty_name]

        if before == after:
            continue

        changed_areas.append(
            _penalty_change(
                penalty_name.replace(
                    "_",
                    " "
                ),
                before,
                after
            )
        )

    total_improvement = (
        greedy_score["total_penalty"]
        - optimised_score["total_penalty"]
    )

    changed_areas.sort(
        key=lambda area: (
            abs(
                area["improvement"]
            ),
            area["label"]
        ),
        reverse=True
    )

    if total_improvement > 0:
        message = (
            "The optimiser improved the greedy layout. No further "
            "one-player moves or two-player swaps improved the score."
        )
    else:
        message = (
            "The greedy layout was already the best layout found by "
            "one-player moves and two-player swaps."
        )

    return {
        "greedy_total_penalty": greedy_score["total_penalty"],
        "optimised_total_penalty": optimised_score["total_penalty"],
        "total_improvement": total_improvement,
        "changed_areas": changed_areas,
        "message": message
    }




def _player_has_keep_apart_conflict(player, team):
    return any(
        conflict["player_name"] == player["player_name"]
        for conflict in team.get(
            "keep_apart_conflicts",
            []
        )
    )


def _build_player_placement_notes(
    player,
    team,
    strong_skiller_threshold
):
    notes = [
        (
            f"Placed on Team {team['team_number']} after the optimiser "
            "compared one-player moves and two-player swaps."
        )
    ]

    if _player_is_raid_player(
        player
    ):
        notes.append(
            f"Contributes raid coverage with raid score {player['raid_score']}."
        )

    if _player_is_strong_pvmer(
        player
    ):
        notes.append(
            "Counts towards this team's strong PvMer coverage."
        )

    if _player_is_group_pvmer(
        player
    ):
        notes.append(
            "Counts towards this team's group PvM coverage."
        )

    if _player_is_strong_skiller(
        player,
        strong_skiller_threshold
    ):
        notes.append(
            "Counts towards this team's strong skiller coverage."
        )

    if player["activity_boss_score"] > 0:
        notes.append(
            (
                "Adds activity score for skilling-style tiles such as "
                "Wintertodt, Tempoross, Zalcano, or Guardians of the Rift."
            )
        )

    if _player_has_keep_apart_conflict(
        player,
        team
    ):
        notes.append(
            "Warning: this player is involved in a keep-apart conflict on this team."
        )

    if len(
        notes
    ) == 1:
        notes.append(
            "Provides general team depth through account and score balance."
        )

    return notes


def _add_player_placement_notes(teams):
    strong_skiller_threshold = _strong_skiller_threshold(
        teams
    )

    for team in teams:
        for player in team.get(
            "players",
            []
        ):
            player["placement_notes"] = _build_player_placement_notes(
                player,
                team,
                strong_skiller_threshold
            )

    return teams


def _candidate_with_player_move(
    teams,
    source_team_index,
    player_index,
    target_team_index,
    keep_apart_groups
):
    candidate = _clone_team_layout(
        teams,
        keep_apart_groups
    )

    player = candidate[source_team_index]["players"].pop(
        player_index
    )
    candidate[target_team_index]["players"].append(
        player
    )

    return _recalculate_layout_totals(
        candidate,
        keep_apart_groups
    )


def _candidate_with_player_swap(
    teams,
    first_team_index,
    first_player_index,
    second_team_index,
    second_player_index,
    keep_apart_groups
):
    candidate = _clone_team_layout(
        teams,
        keep_apart_groups
    )

    first_player = candidate[first_team_index]["players"][first_player_index]
    second_player = candidate[second_team_index]["players"][second_player_index]

    candidate[first_team_index]["players"][first_player_index] = second_player
    candidate[second_team_index]["players"][second_player_index] = first_player

    return _recalculate_layout_totals(
        candidate,
        keep_apart_groups
    )


def _iter_player_move_candidates(
    teams,
    keep_apart_groups
):
    for source_team_index, source_team in enumerate(
        teams
    ):
        for player_index in range(
            len(
                source_team.get(
                    "players",
                    []
                )
            )
        ):
            for target_team_index, target_team in enumerate(
                teams
            ):
                if source_team_index == target_team_index:
                    continue

                yield _candidate_with_player_move(
                    teams,
                    source_team_index,
                    player_index,
                    target_team_index,
                    keep_apart_groups
                )


def _iter_player_swap_candidates(
    teams,
    keep_apart_groups
):
    for first_team_index in range(
        len(
            teams
        )
    ):
        for second_team_index in range(
            first_team_index + 1,
            len(
                teams
            )
        ):
            first_team = teams[first_team_index]
            second_team = teams[second_team_index]

            for first_player_index in range(
                len(
                    first_team.get(
                        "players",
                        []
                    )
                )
            ):
                for second_player_index in range(
                    len(
                        second_team.get(
                            "players",
                            []
                        )
                    )
                ):
                    yield _candidate_with_player_swap(
                        teams,
                        first_team_index,
                        first_player_index,
                        second_team_index,
                        second_player_index,
                        keep_apart_groups
                    )


def _select_improved_layout(
    current_teams,
    candidate_layouts
):
    current_score = _layout_total_penalty(
        current_teams
    )

    for candidate in candidate_layouts:
        candidate_score = _layout_total_penalty(
            candidate
        )

        if candidate_score < current_score:
            return candidate, True

    return current_teams, False


def _optimise_team_layout(
    teams,
    keep_apart_groups
):
    best_teams = _clone_team_layout(
        teams,
        keep_apart_groups
    )

    improved = True

    while improved:
        best_teams, improved = _select_improved_layout(
            best_teams,
            _iter_player_move_candidates(
                best_teams,
                keep_apart_groups
            )
        )

        if improved:
            continue

        best_teams, improved = _select_improved_layout(
            best_teams,
            _iter_player_swap_candidates(
                best_teams,
                keep_apart_groups
            )
        )

    return best_teams


def _team_stat_total(team, stat_name):
    if stat_name in team:
        return _safe_int(
            team.get(
                stat_name
            )
        )

    return sum(
        _safe_int(
            player.get(
                stat_name
            )
        )
        for player in team.get(
            "players",
            []
        )
    )


def _calculate_gap_penalty(teams, stat_name):
    values = [
        _team_stat_total(
            team,
            stat_name
        )
        for team in teams
    ]

    if not values:
        return {
            "gap": 0,
            "scaled_gap": 0,
            "penalty": 0
        }

    gap = max(
        values
    ) - min(
        values
    )

    scale = BALANCE_GAP_SCALES[
        stat_name
    ]

    scaled_gap = gap / scale

    return {
        "gap": gap,
        "scaled_gap": scaled_gap,
        "penalty": scaled_gap * BALANCE_GAP_WEIGHTS[stat_name]
    }


def _player_is_strong_pvmer(player):
    return (
        player["raid_score"] > 0
        or player["endgame_boss_score"] > 0
        or player["dt2_boss_score"] >= 4
        or player["solo_boss_score"] >= 8
        or player["slayer_boss_score"] >= 8
    )


def _player_is_group_pvmer(player):
    return (
        player["group_boss_score"] >= 5
        or player["raid_score"] > 0
    )


def _player_is_raid_player(player):
    return player["raid_score"] > 0


def _player_skilling_coverage_score(player):
    return (
        player["skilling_score"]
        + (
            player["activity_boss_score"] * 100
        )
    )


def _strong_skiller_threshold(teams):
    players = [
        player
        for team in teams
        for player in team.get(
            "players",
            []
        )
    ]

    if not players:
        return 0

    scores = sorted(
        (
            _player_skilling_coverage_score(
                player
            )
            for player in players
        ),
        reverse=True
    )

    threshold_index = min(
        len(
            scores
        ) - 1,
        max(
            len(
                teams
            ) - 1,
            0
        )
    )

    return scores[
        threshold_index
    ]


def _player_is_strong_skiller(player, threshold):
    return _player_skilling_coverage_score(
        player
    ) >= threshold


def _calculate_team_coverage(team, strong_skiller_threshold):
    players = team.get(
        "players",
        []
    )

    raid_player_count = sum(
        1
        for player in players
        if _player_is_raid_player(
            player
        )
    )

    return {
        "team_number": team["team_number"],
        "has_strong_pvmer": any(
            _player_is_strong_pvmer(
                player
            )
            for player in players
        ),
        "has_group_pvmer": any(
            _player_is_group_pvmer(
                player
            )
            for player in players
        ),
        "has_strong_skiller": any(
            _player_is_strong_skiller(
                player,
                strong_skiller_threshold
            )
            for player in players
        ),
        "raid_player_count": raid_player_count
    }


def _calculate_coverage_penalties(teams):
    strong_skiller_threshold = _strong_skiller_threshold(
        teams
    )

    team_coverage = [
        _calculate_team_coverage(
            team,
            strong_skiller_threshold
        )
        for team in teams
    ]

    penalties = {
        "missing_strong_pvmer": 0,
        "missing_group_pvmer": 0,
        "missing_raid_player": 0,
        "missing_extra_raid_player": 0,
        "missing_strong_skiller": 0,
        "keep_apart_conflict": 0
    }

    for coverage in team_coverage:
        if not coverage["has_strong_pvmer"]:
            penalties["missing_strong_pvmer"] += (
                COVERAGE_PENALTY_WEIGHTS["missing_strong_pvmer"]
            )

        if not coverage["has_group_pvmer"]:
            penalties["missing_group_pvmer"] += (
                COVERAGE_PENALTY_WEIGHTS["missing_group_pvmer"]
            )

        if coverage["raid_player_count"] == 0:
            penalties["missing_raid_player"] += (
                COVERAGE_PENALTY_WEIGHTS["missing_raid_player"]
            )

        if coverage["raid_player_count"] < 2:
            penalties["missing_extra_raid_player"] += (
                COVERAGE_PENALTY_WEIGHTS["missing_extra_raid_player"]
            )

        if not coverage["has_strong_skiller"]:
            penalties["missing_strong_skiller"] += (
                COVERAGE_PENALTY_WEIGHTS["missing_strong_skiller"]
            )

    penalties["keep_apart_conflict"] = sum(
        len(
            team.get(
                "keep_apart_conflicts",
                []
            )
        )
        * COVERAGE_PENALTY_WEIGHTS["keep_apart_conflict"]
        for team in teams
    )

    return {
        "team_coverage": team_coverage,
        "strong_skiller_threshold": strong_skiller_threshold,
        "penalties": penalties,
        "total_penalty": sum(
            penalties.values()
        )
    }


def score_team_layout(teams):
    gap_penalties = {
        stat_name: _calculate_gap_penalty(
            teams,
            stat_name
        )
        for stat_name in BALANCE_GAP_WEIGHTS
    }

    coverage = _calculate_coverage_penalties(
        teams
    )

    gap_penalty_total = sum(
        gap_penalty["penalty"]
        for gap_penalty in gap_penalties.values()
    )

    total_penalty = (
        gap_penalty_total
        + coverage["total_penalty"]
    )

    return {
        "total_penalty": total_penalty,
        "gap_penalty_total": gap_penalty_total,
        "coverage_penalty_total": coverage["total_penalty"],
        "gap_penalties": gap_penalties,
        "coverage": coverage
    }


def _build_team_reasons(team):
    reasons = []

    if not team["players"]:
        reasons.append(
            "No players assigned yet."
        )
        return reasons

    strongest_combat_player = max(
        team["players"],
        key=lambda player: (
            player["combat_level"],
            player["overall_score"],
            player["player_name"].casefold()
        )
    )

    strongest_skilling_player = max(
        team["players"],
        key=lambda player: (
            player["skilling_score"],
            player["overall_score"],
            player["player_name"].casefold()
        )
    )

    reasons.append(
        f"{strongest_combat_player['player_name']} is this team's "
        f"highest combat-level player."
    )

    reasons.append(
        f"{strongest_skilling_player['player_name']} is this team's "
        f"strongest non-combat skiller by level total."
    )

    if team["keep_apart_conflicts"]:
        for conflict in team["keep_apart_conflicts"]:
            conflicts_with = ", ".join(
                conflict["conflicts_with"]
            )

            reasons.append(
                f"Keep-apart conflict: {conflict['player_name']} "
                f"was placed with {conflicts_with}."
            )
    else:
        reasons.append(
            "No keep-apart conflicts in this suggested team."
        )

    reasons.append(
        "Players were assigned to keep team size, total level, "
        "combat level, skilling score, and bossing categories close."
    )

    return reasons
