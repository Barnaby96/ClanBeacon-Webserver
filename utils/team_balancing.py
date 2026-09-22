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

    for team in teams:
        team["reasons"] = _build_team_reasons(
            team
        )

    return teams


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
