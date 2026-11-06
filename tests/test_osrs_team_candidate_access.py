"""Team-level route access assessment regressions."""

from dataclasses import replace

from utils.board_generation import (
    AccessProfile,
    RouteMode,
)
from utils.osrs_capability_profiles import (
    build_capability_profiles_from_rostered_players,
)
from utils.osrs_tile_catalogue import (
    get_curated_tile_generation_candidates,
)


def _candidate(mode):
    return next(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if candidate.route_mode == mode
    )


def _route_profiles(*requirements):
    return tuple(
        {
            "access_profile": AccessProfile(
                effective_skill_requirements={
                    skill: minimum,
                }
            ),
            "requirements_verified": True,
        }
        for skill, minimum in requirements
    )


def _roster(players_by_team, levels_by_name, failed_names=()):
    fetched = []

    def fetch_player(name):
        fetched.append(name)

        if name in failed_names:
            raise RuntimeError("WOM unavailable")

        result = {"displayName": name}
        levels = levels_by_name.get(name)

        if levels is not None:
            result["latestSnapshot"] = {
                "data": {
                    "skills": {
                        skill: {"level": level}
                        for skill, level in levels.items()
                    }
                }
            }

        return result

    def score_player(data):
        return {
            "player_name": data["displayName"],
            "skilling_score": 1,
        }

    result = build_capability_profiles_from_rostered_players(
        players_by_team,
        fetch_player=fetch_player,
        score_player=score_player,
    )

    return result, fetched


def test_team_can_split_and_routes_between_different_players():
    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )

    or_candidate = _candidate(RouteMode.OR)
    and_candidate = replace(
        or_candidate,
        route_mode=RouteMode.AND,
    )

    assert len(and_candidate.routes) == 2

    profiles = _route_profiles(
        ("thieving", 60),
        ("fishing", 60),
    )

    result, fetched = _roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Bob"),
            ),
            "Saradomin": (
                (3, "Charlie"),
            ),
        },
        {
            "Alice": {"thieving": 70, "fishing": 10},
            "Bob": {"thieving": 10, "fishing": 70},
            "Charlie": {"thieving": 10, "fishing": 10},
        },
    )

    def assess(candidate, team):
        return assess_team_candidate_route_access(
            candidate,
            team_name=team,
            capability_result=result,
            route_access_profiles=profiles,
        )

    # Alice and Bob each unlock a different route.
    assert assess(and_candidate, "Zamorak") == "accessible"
    assert assess(or_candidate, "Zamorak") == "accessible"

    # Charlie cannot access either route.
    assert assess(and_candidate, "Saradomin") == "inaccessible"
    assert assess(or_candidate, "Saradomin") == "inaccessible"

    # No additional WOM lookups during assessment.
    assert fetched == ["Alice", "Bob", "Charlie"]


def test_team_n_of_combines_access_across_members():
    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )

    candidate = _candidate(RouteMode.N_OF)

    assert len(candidate.routes) == 3
    assert candidate.required_route_count == 2

    profiles = _route_profiles(
        ("mining", 60),
        ("fishing", 60),
        ("thieving", 60),
    )

    result, fetched = _roster(
        {
            "Armadyl": (
                (1, "Alice"),
                (2, "Bob"),
            ),
            "Saradomin": (
                (3, "Charlie"),
            ),
        },
        {
            "Alice": {
                "mining": 70,
                "fishing": 10,
                "thieving": 10,
            },
            "Bob": {
                "mining": 10,
                "fishing": 70,
                "thieving": 10,
            },
            "Charlie": {
                "mining": 70,
                "fishing": 10,
                "thieving": 10,
            },
        },
    )

    def assess(team):
        return assess_team_candidate_route_access(
            candidate,
            team_name=team,
            capability_result=result,
            route_access_profiles=profiles,
        )

    # Two accessible routes, unlocked by different players.
    assert assess("Armadyl") == "accessible"

    # Only one of three routes accessible; two required.
    assert assess("Saradomin") == "inaccessible"

    assert fetched == ["Alice", "Bob", "Charlie"]


def test_team_candidate_access_preserves_missing_evidence():
    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )

    candidate = replace(
        _candidate(RouteMode.OR),
        route_mode=RouteMode.AND,
    )

    profiles = _route_profiles(
        ("thieving", 60),
        ("fishing", 60),
    )

    result, fetched = _roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Broken"),
            ),
            "Saradomin": (
                (3, "Charlie"),
            ),
        },
        {
            "Alice": {"thieving": 70, "fishing": 10},
            "Charlie": {"thieving": 10, "fishing": 10},
        },
        failed_names=("Broken",),
    )

    def assess(team, metadata=profiles):
        return assess_team_candidate_route_access(
            candidate,
            team_name=team,
            capability_result=result,
            route_access_profiles=metadata,
        )

    # Broken may have access to the second route.
    # His failed WOM lookup cannot become inaccessibility.
    assert assess("Zamorak") == "unknown"

    # A failed player on another team does not affect
    # Saradomin's known inability to access either route.
    assert assess("Saradomin") == "inaccessible"

    # No roster or missing route metadata cannot prove access.
    assert assess("Nonexistent") == "unknown"
    assert assess("Zamorak", metadata=profiles[:1]) == "unknown"

    unreviewed = (
        profiles[0],
        {
            **profiles[1],
            "requirements_verified": False,
        },
    )

    assert assess("Zamorak", metadata=unreviewed) == "unknown"

    assert fetched == ["Alice", "Broken", "Charlie"]


def test_candidate_access_map_filters_per_team():
    from utils.osrs_generated_board_preview import (
        build_candidate_access_by_team,
        build_access_filtered_generation_candidates,
        build_generated_board_candidate_key,
    )

    candidates = tuple(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if candidate.route_mode == RouteMode.SINGLE
    )[:2]

    assert len(candidates) == 2

    restricted, shared = candidates

    restricted_key = build_generated_board_candidate_key(
        restricted
    )
    shared_key = build_generated_board_candidate_key(
        shared
    )

    result, fetched = _roster(
        {
            "Zamorak": ((1, "Alice"),),
            "Saradomin": ((2, "Bob"),),
        },
        {
            "Alice": {"slayer": 80},
            "Bob": {"slayer": 20},
        },
    )

    assessments = build_candidate_access_by_team(
        candidates,
        capability_result=result,
        participating_team_names=("Zamorak", "Saradomin"),
        route_access_profiles_by_candidate={
            restricted_key: _route_profiles(("slayer", 72)),
            shared_key: _route_profiles(("slayer", 10)),
        },
    )

    assert assessments == {
        "Zamorak": {
            restricted_key: "accessible",
            shared_key: "accessible",
        },
        "Saradomin": {
            restricted_key: "inaccessible",
            shared_key: "accessible",
        },
    }

    filtered = build_access_filtered_generation_candidates(
        candidates,
        candidate_access_by_team=assessments,
    )

    assert filtered == (shared,)
    assert fetched == ["Alice", "Bob"]


def test_candidate_access_map_supports_collective_routes():
    from utils.osrs_generated_board_preview import (
        build_candidate_access_by_team,
        build_access_filtered_generation_candidates,
        build_generated_board_candidate_key,
    )

    and_candidate = replace(
        _candidate(RouteMode.OR),
        route_mode=RouteMode.AND,
    )
    n_of_candidate = _candidate(RouteMode.N_OF)

    candidates = (and_candidate, n_of_candidate)

    and_key = build_generated_board_candidate_key(
        and_candidate
    )
    n_of_key = build_generated_board_candidate_key(
        n_of_candidate
    )

    result, fetched = _roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Bob"),
            ),
            "Saradomin": (
                (3, "Charlie"),
            ),
        },
        {
            "Alice": {
                "thieving": 70,
                "fishing": 10,
                "mining": 70,
            },
            "Bob": {
                "thieving": 10,
                "fishing": 70,
                "mining": 10,
            },
            "Charlie": {
                "thieving": 70,
                "fishing": 70,
                "mining": 70,
            },
        },
    )

    assessments = build_candidate_access_by_team(
        candidates,
        capability_result=result,
        participating_team_names=("Zamorak", "Saradomin"),
        route_access_profiles_by_candidate={
            and_key: _route_profiles(
                ("thieving", 60),
                ("fishing", 60),
            ),
            n_of_key: _route_profiles(
                ("mining", 60),
                ("fishing", 60),
                ("thieving", 60),
            ),
        },
    )

    for team in ("Zamorak", "Saradomin"):
        assert assessments[team][and_key] == "accessible"
        assert assessments[team][n_of_key] == "accessible"

    assert build_access_filtered_generation_candidates(
        candidates,
        candidate_access_by_team=assessments,
    ) == candidates

    assert fetched == ["Alice", "Bob", "Charlie"]


def test_candidate_access_map_preserves_missing_evidence():
    from utils.osrs_generated_board_preview import (
        build_candidate_access_by_team,
        build_access_filtered_generation_candidates,
        build_generated_board_candidate_key,
    )

    candidate = _candidate(RouteMode.SINGLE)
    key = build_generated_board_candidate_key(candidate)

    result, fetched = _roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Broken"),
            ),
            "Saradomin": (
                (3, "Charlie"),
            ),
        },
        {
            "Alice": {"slayer": 10},
            "Charlie": {"slayer": 80},
        },
        failed_names=("Broken",),
    )

    def build(metadata):
        return build_candidate_access_by_team(
            (candidate,),
            capability_result=result,
            participating_team_names=("Zamorak", "Saradomin"),
            route_access_profiles_by_candidate=metadata,
        )

    assessments = build({
        key: _route_profiles(("slayer", 72)),
    })

    assert assessments["Zamorak"][key] == "unknown"
    assert assessments["Saradomin"][key] == "accessible"

    assert build_access_filtered_generation_candidates(
        (candidate,),
        candidate_access_by_team=assessments,
    ) == ()

    missing_metadata = build({})

    assert missing_metadata["Zamorak"][key] == "unknown"
    assert missing_metadata["Saradomin"][key] == "unknown"

    assert build_access_filtered_generation_candidates(
        (candidate,),
        candidate_access_by_team=missing_metadata,
    ) == ()

    # Without identified participating teams, there must
    # be no vacuous approval of all candidates.
    no_teams = build_candidate_access_by_team(
        (candidate,),
        capability_result=result,
        participating_team_names=(),
        route_access_profiles_by_candidate={
            key: _route_profiles(("slayer", 1)),
        },
    )

    assert build_access_filtered_generation_candidates(
        (candidate,),
        candidate_access_by_team=no_teams,
    ) == ()

    assert fetched == ["Alice", "Broken", "Charlie"]


def test_candidate_access_map_does_not_approve_drop_routes():
    from utils.board_generation import TileCategory
    from utils.osrs_generated_board_preview import (
        build_candidate_access_by_team,
        build_access_filtered_generation_candidates,
        build_generated_board_candidate_key,
    )

    candidate = next(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if any(
            route.route_type == TileCategory.DROP
            for route in candidate.routes
        )
    )

    key = build_generated_board_candidate_key(candidate)

    result, fetched = _roster(
        {"Zamorak": ((1, "Alice"),)},
        {"Alice": {"slayer": 99}},
    )

    # Generic skill profiles must not substitute for
    # verified drop-source coverage.
    metadata = _route_profiles(
        *([("slayer", 1)] * len(candidate.routes))
    )

    assessments = build_candidate_access_by_team(
        (candidate,),
        capability_result=result,
        participating_team_names=("Zamorak",),
        route_access_profiles_by_candidate={
            key: metadata,
        },
    )

    assert assessments["Zamorak"][key] == "unknown"

    assert build_access_filtered_generation_candidates(
        (candidate,),
        candidate_access_by_team=assessments,
    ) == ()

    assert fetched == ["Alice"]


def _synthetic_verified_drop_candidate():
    from utils.board_generation import TileCategory

    base = next(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if (
            candidate.primary_category == TileCategory.DROP
            and candidate.route_mode == RouteMode.SINGLE
            and len(candidate.routes) == 1
        )
    )

    route = replace(
        base.routes[0],
        route_type=TileCategory.DROP,
        display_text="Obtain synthetic rare drop",
        source_id=None,
        metric_id=None,
        boss_id=None,
        drop_id="synthetic_rare_drop",
        drop_group_id=None,
        pet_id=None,
        pet_group_id=None,
        hard_unique_tags=frozenset(),
    )

    return replace(
        base,
        title="Obtain synthetic rare drop",
        routes=(route,),
        hard_unique_tags=frozenset(),
    )


def _synthetic_verified_drop_metadata():
    from utils.osrs_content_access import (
        build_access_profile_for_content,
    )

    rows = (
        {
            "drop_id": "synthetic_rare_drop",
            "source_ids": ("vorkath",),
            "include_in_unique_group": False,
        },
        {
            "drop_id": "synthetic_rare_drop",
            "source_ids": ("synthetic_cave",),
            "include_in_unique_group": False,
        },
    )

    records = (
        {
            "drop_id": "synthetic_rare_drop",
            "source_ids": ("vorkath", "synthetic_cave"),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:synthetic-source-review",),
        },
    )

    profiles = {
        "vorkath": {
            "access_profile": build_access_profile_for_content(
                "vorkath"
            ),
            "requirements_verified": True,
        },
        "synthetic_cave": {
            "access_profile": AccessProfile(
                effective_skill_requirements={"slayer": 72},
            ),
            "requirements_verified": True,
        },
    }

    return {
        "drop_rows": rows,
        "verification_records": records,
        "source_access_profiles": profiles,
    }


def test_verified_drop_route_accepts_alternative_source():
    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )
    from utils.osrs_generated_board_preview import (
        build_candidate_access_by_team,
        build_access_filtered_generation_candidates,
        build_generated_board_candidate_key,
    )

    candidate = _synthetic_verified_drop_candidate()
    metadata = _synthetic_verified_drop_metadata()

    result, fetched = _roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Bob"),
            ),
            "Saradomin": (
                (3, "Charlie"),
            ),
        },
        {
            "Alice": {"magic": 1, "slayer": 40},
            "Bob": {"magic": 1, "slayer": 80},
            "Charlie": {"magic": 1, "slayer": 20},
        },
    )

    def assess(team):
        return assess_team_candidate_route_access(
            candidate,
            team_name=team,
            capability_result=result,
            route_access_profiles=(metadata,),
        )

    # Bob cannot access Vorkath, but can access the
    # verified synthetic alternative source.
    assert assess("Zamorak") == "accessible"

    # Charlie cannot access either source.
    assert assess("Saradomin") == "inaccessible"

    key = build_generated_board_candidate_key(candidate)

    assessments = build_candidate_access_by_team(
        (candidate,),
        capability_result=result,
        participating_team_names=("Zamorak", "Saradomin"),
        route_access_profiles_by_candidate={
            key: (metadata,),
        },
    )

    assert assessments == {
        "Zamorak": {key: "accessible"},
        "Saradomin": {key: "inaccessible"},
    }

    # The candidate cannot be included for both teams.
    assert build_access_filtered_generation_candidates(
        (candidate,),
        candidate_access_by_team=assessments,
    ) == ()

    # It can be included when only the eligible team
    # is participating.
    assert build_access_filtered_generation_candidates(
        (candidate,),
        candidate_access_by_team={
            "Zamorak": assessments["Zamorak"],
        },
    ) == (candidate,)

    assert fetched == ["Alice", "Bob", "Charlie"]


def test_verified_drop_route_presumes_quest_completion():
    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )

    candidate = _synthetic_verified_drop_candidate()
    metadata = _synthetic_verified_drop_metadata()

    quest_requirements = dict(
        metadata["source_access_profiles"]["vorkath"][
            "access_profile"
        ].effective_skill_requirements
    )

    assert len(quest_requirements) == 18

    # Quest completion is presumed from the full
    # prerequisite skill chain; no quest log is checked.
    result, fetched = _roster(
        {"Zamorak": ((1, "Alice"),)},
        {"Alice": quest_requirements},
    )

    assert assess_team_candidate_route_access(
        candidate,
        team_name="Zamorak",
        capability_result=result,
        route_access_profiles=(metadata,),
    ) == "accessible"

    assert fetched == ["Alice"]


def test_verified_drop_route_preserves_unknown_and_source_scope():
    from utils.osrs_player_access import (
        assess_team_candidate_route_access,
    )

    candidate = _synthetic_verified_drop_candidate()
    metadata = _synthetic_verified_drop_metadata()

    result, fetched = _roster(
        {
            "Armadyl": (
                (1, "Alice"),
                (2, "Broken"),
            ),
            "Zamorak": (
                (3, "Bob"),
                (4, "Unavailable"),
            ),
        },
        {
            "Alice": {"magic": 1, "slayer": 40},
            "Bob": {"magic": 1, "slayer": 80},
        },
        failed_names=("Broken", "Unavailable"),
    )

    def assess(team, candidate_override=None, metadata_override=None):
        return assess_team_candidate_route_access(
            candidate if candidate_override is None else candidate_override,
            team_name=team,
            capability_result=result,
            route_access_profiles=(
                metadata if metadata_override is None else metadata_override,
            ),
        )

    # An unavailable player could provide missing access.
    assert assess("Armadyl") == "unknown"

    # A confirmed accessible player takes precedence
    # over another player's failed WOM lookup.
    assert assess("Zamorak") == "accessible"

    # No source verification means no approval.
    assert assess(
        "Zamorak",
        metadata_override={
            **metadata,
            "verification_records": (),
        },
    ) == "unknown"

    # Generic skill metadata is not sufficient
    # for a DROP route.
    assert assess(
        "Zamorak",
        metadata_override={
            "access_profile": AccessProfile(
                effective_skill_requirements={"slayer": 1},
            ),
            "requirements_verified": True,
        },
    ) == "unknown"

    # An explicitly source-specific route must not be
    # widened into an any-source DROP objective.
    restricted_route = replace(
        candidate.routes[0],
        source_id="vorkath",
    )

    restricted_candidate = replace(
        candidate,
        routes=(restricted_route,),
    )

    assert assess(
        "Zamorak",
        candidate_override=restricted_candidate,
    ) == "unknown"

    # A DROP-group route is not a verified nonunique
    # specific-item objective.
    group_route = replace(
        candidate.routes[0],
        drop_id=None,
        drop_group_id="synthetic_group",
    )

    group_candidate = replace(
        candidate,
        routes=(group_route,),
    )

    assert assess(
        "Zamorak",
        candidate_override=group_candidate,
    ) == "unknown"

    assert fetched == [
        "Alice",
        "Broken",
        "Bob",
        "Unavailable",
    ]
