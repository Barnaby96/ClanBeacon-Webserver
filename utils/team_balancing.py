COMBAT_SKILLS = (
    "attack",
    "strength",
    "defence",
    "ranged",
    "prayer",
    "magic",
    "slayer"
)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (
        TypeError,
        ValueError
    ):
        return default


def _get_skill_level(player_data, skill_name):
    snapshot = player_data.get("latestSnapshot") or {}
    snapshot_data = snapshot.get("data") or {}
    skills = snapshot_data.get("skills") or {}
    skill = skills.get(skill_name) or {}

    return _safe_int(
        skill.get("level")
    )


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

    return {
        "player_id": player_data.get("id"),
        "player_name": display_name,
        "player_key": display_name.casefold(),
        "total_level": total_level,
        "combat_level": combat_level,
        "combat_skill_total": combat_skill_total,
        "skilling_score": skilling_score,
        "overall_score": total_level
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
                team["skilling_score"]
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
        "Players were assigned to keep team size and total level close."
    )

    return reasons