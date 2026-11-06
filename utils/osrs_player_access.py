"""Player-level evidence for OSRS activity access assessment.

Unknown or invalid skill information must not be interpreted
as evidence of an unmet requirement or a completed unlock.
"""

from collections.abc import Mapping


def extract_player_access_skill_levels(player_data):
    """Extract confirmed individual skill levels from a WOM snapshot.

    Returns only valid, positive integer levels.
    Absent or malformed skill records remain unknown.
    """
    if not isinstance(player_data, Mapping):
        return {}

    snapshot = player_data.get("latestSnapshot")

    if not isinstance(snapshot, Mapping):
        return {}

    data = snapshot.get("data")

    if not isinstance(data, Mapping):
        return {}

    skills = data.get("skills")

    if not isinstance(skills, Mapping):
        return {}

    levels = {}

    for skill_name, skill_record in skills.items():
        if not isinstance(skill_name, str):
            continue

        if (
            not skill_name
            or skill_name != skill_name.strip()
            or skill_name == "overall"
        ):
            continue

        if not isinstance(skill_record, Mapping):
            continue

        level = skill_record.get("level")

        # Reject booleans, numeric strings, None and invalid levels.
        # type() is intentional: bool is a subclass of int.
        if type(level) is not int or level < 1:
            continue

        levels[skill_name] = level

    return levels


def assess_player_source_access(
    profile,
    skill_levels,
    *,
    source_id=None,
    requirements_verified=False,
):
    """Assess acquisition-source access using known player skill levels.

    For quest-locked content, completion is presumed when all
    effective requirements, including prerequisite quest skills,
    are satisfied.

    No quest-log verification or organiser confirmation is needed.

    Unknown evidence must not be treated as confirmed access.
    """
    from utils.board_generation import (
        AccessFlag,
        AccessProfile,
    )

    if requirements_verified is not True:
        return "unknown"

    if not isinstance(profile, AccessProfile):
        return "unknown"

    if (
        not isinstance(source_id, str)
        or not source_id
        or source_id != source_id.strip()
    ):
        return "unknown"

    if not isinstance(skill_levels, Mapping):
        skill_levels = {}

    missing_skill_evidence = False
    boost_required_unconfirmed = False

    for skill, required_level in (
        profile.effective_skill_requirements.items()
    ):
        player_level = skill_levels.get(skill)

        if type(player_level) is not int or player_level < 1:
            missing_skill_evidence = True
            continue

        if player_level >= required_level:
            continue

        thresholds = (
            profile.skill_boostability_thresholds.get(
                skill,
                {}
            )
        )

        # An unmet confirmed unboostable requirement
        # makes the source inaccessible, regardless of
        # other potentially boostable requirements.
        nonboostable_level = thresholds.get("no", 0)

        if player_level < nonboostable_level:
            return "inaccessible"

        # A requirement with unverified boostability
        # retains its existing strict-level behaviour.
        # A separate, lower boostable requirement must
        # not hide an unmet stricter requirement.
        unknown_boostability_level = thresholds.get(
            "unknown", 0
        )

        if player_level < unknown_boostability_level:
            return "inaccessible"

        # A confirmed boostable threshold is not an
        # automatic failure. We cannot assume that the
        # player has a suitable temporary boost.
        boostable_level = thresholds.get("yes", 0)

        if player_level < boostable_level:
            boost_required_unconfirmed = True
            continue

        # Preserve legacy strict-level behaviour when
        # boostability has not been established, or when
        # the remaining unmet threshold is not covered
        # by a confirmed boostable requirement.
        return "inaccessible"

    if missing_skill_evidence or boost_required_unconfirmed:
        return "unknown"

    # Planning assumptions are not verified player evidence.
    # However, a verified OR requirement is satisfied when
    # the player's measured skill meets its original route.
    # Item ownership or travel access remains unverified
    # when that numerical alternative is not satisfied.
    #
    # Other measurable mandatory skills have already been
    # evaluated above. Partial quest progression cannot be
    # established using WOM skill evidence.
    for condition in profile.non_skill_conditions:
        if (
            condition.condition_kind
            == "ALTERNATIVE_SKILL_OR_NON_SKILL"
        ):
            skill, level, boostability = (
                condition.alternative_skill_route
            )

            observed_level = skill_levels.get(skill)

            if (
                type(observed_level) is int
                and observed_level >= level
            ):
                # The skill route is independently satisfied.
                # This does not establish item ownership or
                # access to the alternative non-skill route.
                continue

        # A genuine requirement remains unmeasured.
        return "unknown"

    # QUEST_LOCKED is satisfied by the skill-based presumption
    # after all effective requirements have been checked.
    #
    # Wilderness and dangerous-death flags describe risk;
    # they do not themselves prevent entry.
    resolved_flags = frozenset({
        AccessFlag.QUEST_LOCKED,
        AccessFlag.WILDERNESS,
        AccessFlag.DANGEROUS_DEATH,
    })

    unresolved_flags = (
        profile.access_flags - resolved_flags
    )

    if unresolved_flags:
        return "unknown"

    return "accessible"


def assess_player_nonunique_drop_access(
    *,
    drop_id,
    drop_rows,
    verification_records=(),
    source_access_profiles=None,
    skill_levels=None,
):
    """Assess access to any verified acquisition source for an item.

    Source coverage must be verified before individual sources
    are considered. A player needs one accessible source.

    Quest completion is presumed from the effective skill
    requirements already resolved through prerequisite quests.
    """
    from utils.osrs_drop_source_coverage import (
        build_verified_drop_source_id_map,
        select_source_verified_nonunique_drops,
    )

    if (
        not isinstance(drop_id, str)
        or not drop_id
        or drop_id != drop_id.strip()
    ):
        return "unknown"

    if not isinstance(source_access_profiles, Mapping):
        source_access_profiles = {}

    # Preserve the complete set of verification records for
    # both validation operations.
    try:
        records = tuple(verification_records or ())
        rows = tuple(drop_rows or ())

        eligible_drop_ids = (
            select_source_verified_nonunique_drops(
                rows,
                verification_records=records,
            )
        )

        if drop_id not in eligible_drop_ids:
            return "unknown"

        verified_source_map = (
            build_verified_drop_source_id_map(records)
        )

        verified_source_ids = verified_source_map.get(
            drop_id
        )

    except (TypeError, ValueError, KeyError, AttributeError):
        # Invalid verification data cannot establish access.
        return "unknown"

    if (
        not isinstance(
            verified_source_ids,
            (tuple, list, set, frozenset),
        )
        or not verified_source_ids
    ):
        return "unknown"

    source_ids = tuple(verified_source_ids)

    if any(
        not isinstance(source_id, str)
        or not source_id
        or source_id != source_id.strip()
        for source_id in source_ids
    ):
        return "unknown"

    statuses = []

    for source_id in source_ids:
        metadata = source_access_profiles.get(source_id)

        if not isinstance(metadata, Mapping):
            statuses.append("unknown")
            continue

        status = assess_player_source_access(
            metadata.get("access_profile"),
            skill_levels,
            source_id=source_id,
            requirements_verified=metadata.get(
                "requirements_verified",
                False,
            ),
        )

        if status == "accessible":
            return "accessible"

        statuses.append(status)

    if statuses and all(
        status == "inaccessible"
        for status in statuses
    ):
        return "inaccessible"

    return "unknown"


def assess_team_nonunique_drop_access(
    *,
    team_name,
    capability_result,
    drop_id,
    drop_rows,
    verification_records=(),
    source_access_profiles=None,
):
    """Assess whether any rostered team member can obtain a drop.

    Reuses individual WOM skill evidence collected during roster
    loading. No additional player lookups or quest-log checks.

    An accessible player establishes team access. Otherwise,
    missing evidence or a failed WOM lookup keeps access unknown.
    """
    if (
        not isinstance(team_name, str)
        or not team_name
        or team_name != team_name.strip()
    ):
        return "unknown"

    if capability_result is None:
        return "unknown"

    player_evidence = getattr(
        capability_result,
        "player_access_evidence",
        None,
    )

    failed_players = getattr(
        capability_result,
        "failed_players",
        None,
    )

    if (
        not isinstance(player_evidence, (tuple, list))
        or not isinstance(failed_players, (tuple, list))
    ):
        return "unknown"

    # A failed lookup cannot demonstrate inaccessibility.
    team_has_failed_lookup = False

    for failure in failed_players:
        if not isinstance(failure, Mapping):
            return "unknown"

        if failure.get("team_name") == team_name:
            team_has_failed_lookup = True

    statuses = []

    for player in player_evidence:
        if not isinstance(player, Mapping):
            return "unknown"

        if player.get("team_name") != team_name:
            continue

        skill_levels = player.get("skill_levels")

        status = assess_player_nonunique_drop_access(
            drop_id=drop_id,
            drop_rows=drop_rows,
            verification_records=verification_records,
            source_access_profiles=source_access_profiles,
            skill_levels=skill_levels,
        )

        if status == "accessible":
            return "accessible"

        statuses.append(status)

    if team_has_failed_lookup:
        return "unknown"

    # An empty team, or a team absent from this roster,
    # does not establish an unmet access requirement.
    if not statuses:
        return "unknown"

    if all(status == "inaccessible" for status in statuses):
        return "inaccessible"

    return "unknown"


def assess_candidate_route_access(
    candidate,
    route_access_statuses,
):
    """Combine route-level access into candidate-level access.

    Assessments must cover every route in the same order.

    This function assumes that SUM routes permit repeatable
    contributions towards the shared target, as they do in
    the current curated clue-scroll catalogue.

    It does not infer access from the candidate's overall
    access_profile or make additional WOM requests.
    """
    from utils.board_generation import (
        RouteMode,
        TileCandidate,
    )

    if not isinstance(candidate, TileCandidate):
        return "unknown"

    if not isinstance(
        route_access_statuses,
        (tuple, list),
    ):
        return "unknown"

    statuses = tuple(route_access_statuses)

    if len(statuses) != len(candidate.routes):
        return "unknown"

    valid_statuses = frozenset({
        "accessible",
        "inaccessible",
        "unknown",
    })

    # Reject invalid evidence before aggregating routes.
    if any(
        not isinstance(status, str)
        or status not in valid_statuses
        for status in statuses
    ):
        return "unknown"

    accessible_count = statuses.count("accessible")
    unknown_count = statuses.count("unknown")
    route_count = len(statuses)

    if candidate.route_mode == RouteMode.SINGLE:
        if route_count != 1:
            return "unknown"

        return statuses[0]

    if candidate.route_mode in (
        RouteMode.OR,
        RouteMode.SUM,
    ):
        # OR: one complete alternative is sufficient.
        # SUM: one repeatable contribution route is sufficient.
        if accessible_count >= 1:
            return "accessible"

        if unknown_count >= 1:
            return "unknown"

        return "inaccessible"

    if candidate.route_mode == RouteMode.AND:
        if "inaccessible" in statuses:
            return "inaccessible"

        if unknown_count >= 1:
            return "unknown"

        return "accessible"

    if candidate.route_mode == RouteMode.N_OF:
        required = candidate.required_route_count

        if (
            type(required) is not int
            or required < 1
            or required > route_count
        ):
            return "unknown"

        if accessible_count >= required:
            return "accessible"

        # Unknown routes might supply enough completions.
        if accessible_count + unknown_count >= required:
            return "unknown"

        # Even resolving every unknown route positively
        # would leave too few available completions.
        return "inaccessible"

    return "unknown"


def assess_team_candidate_route_access(
    candidate,
    *,
    team_name,
    capability_result,
    route_access_profiles,
):
    """Assess every candidate route using a team's WOM evidence.

    Different team members may establish access to different
    completion routes.

    The resulting route assessments are combined according to
    the candidate's SINGLE, OR, AND, SUM or N_OF mode.

    Quest completion is presumed from the effective skill
    requirements already resolved through prerequisite quests.

    No additional WOM requests or quest-log checks are made.
    """
    from utils.board_generation import (
        TileCandidate,
        TileCategory,
    )

    if not isinstance(candidate, TileCandidate):
        return "unknown"

    if (
        not isinstance(team_name, str)
        or not team_name
        or team_name != team_name.strip()
    ):
        return "unknown"

    if capability_result is None:
        return "unknown"

    if not isinstance(route_access_profiles, (tuple, list)):
        return "unknown"

    if len(route_access_profiles) != len(candidate.routes):
        return "unknown"

    player_evidence = getattr(
        capability_result,
        "player_access_evidence",
        None,
    )

    failed_players = getattr(
        capability_result,
        "failed_players",
        None,
    )

    if (
        not isinstance(player_evidence, (tuple, list))
        or not isinstance(failed_players, (tuple, list))
    ):
        return "unknown"

    team_has_failed_lookup = False

    for failure in failed_players:
        if not isinstance(failure, Mapping):
            return "unknown"

        if failure.get("team_name") == team_name:
            team_has_failed_lookup = True

    team_players = []

    for player in player_evidence:
        if not isinstance(player, Mapping):
            return "unknown"

        if player.get("team_name") == team_name:
            team_players.append(player)

    if not team_players and not team_has_failed_lookup:
        return "unknown"

    route_statuses = []

    for route, metadata in zip(
        candidate.routes,
        route_access_profiles,
    ):
        # Specific-item DROP routes can use alternative
        # acquisition sources only when the objective
        # itself is source-independent.
        #
        # Source-specific routes and DROP groups require
        # separate access assessment and remain unknown.
        if (
            route.route_type == TileCategory.DROP
            or route.drop_id is not None
            or route.drop_group_id is not None
        ):
            source_independent_item = (
                route.route_type == TileCategory.DROP
                and isinstance(route.drop_id, str)
                and bool(route.drop_id)
                and route.drop_id == route.drop_id.strip()
                and route.source_id is None
                and route.drop_group_id is None
                and route.boss_id is None
                and route.pet_id is None
                and route.pet_group_id is None
                and route.metric_id is None
            )

            if (
                source_independent_item
                and isinstance(metadata, Mapping)
            ):
                status = assess_team_nonunique_drop_access(
                    team_name=team_name,
                    capability_result=capability_result,
                    drop_id=route.drop_id,
                    drop_rows=metadata.get(
                        "drop_rows",
                        (),
                    ),
                    verification_records=metadata.get(
                        "verification_records",
                        (),
                    ),
                    source_access_profiles=metadata.get(
                        "source_access_profiles",
                    ),
                )

                route_statuses.append(status)

            else:
                route_statuses.append("unknown")

            continue

        if not isinstance(metadata, Mapping):
            route_statuses.append("unknown")
            continue

        profile = metadata.get("access_profile")
        requirements_verified = metadata.get(
            "requirements_verified",
            False,
        )

        player_statuses = []

        for player in team_players:
            skill_levels = player.get("skill_levels")

            player_status = assess_player_source_access(
                profile,
                skill_levels,
                source_id=route.source_id,
                requirements_verified=requirements_verified,
            )

            if player_status == "accessible":
                player_statuses.append("accessible")
                break

            player_statuses.append(player_status)

        if "accessible" in player_statuses:
            route_statuses.append("accessible")

        elif team_has_failed_lookup:
            # An unavailable player might be able to
            # complete this route.
            route_statuses.append("unknown")

        elif (
            not player_statuses
            or "unknown" in player_statuses
        ):
            route_statuses.append("unknown")

        elif all(
            status == "inaccessible"
            for status in player_statuses
        ):
            route_statuses.append("inaccessible")

        else:
            route_statuses.append("unknown")

    return assess_candidate_route_access(
        candidate,
        tuple(route_statuses),
    )
