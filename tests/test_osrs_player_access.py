"""Individual WOM skill evidence for access assessment."""


def test_extract_player_access_skills_preserves_known_levels():
    from utils.osrs_player_access import (
        extract_player_access_skill_levels,
    )

    player_data = {
        "displayName": "Synthetic Tester",
        "latestSnapshot": {
            "data": {
                "skills": {
                    "overall": {"level": 1900},
                    "slayer": {"level": 72},
                    "sailing": {"level": 87},
                    "attack": {"level": 1},
                },
            },
        },
    }

    original_skills = dict(
        player_data["latestSnapshot"]["data"]["skills"]
    )

    levels = extract_player_access_skill_levels(
        player_data
    )

    assert levels == {
        "slayer": 72,
        "sailing": 87,
        "attack": 1,
    }

    assert (
        player_data["latestSnapshot"]["data"]["skills"]
        == original_skills
    )


def test_extract_player_access_skills_keeps_missing_unknown():
    from utils.osrs_player_access import (
        extract_player_access_skill_levels,
    )

    assert extract_player_access_skill_levels({}) == {}

    player_data = {
        "latestSnapshot": {
            "data": {
                "skills": {
                    "slayer": {"level": 1},
                    "sailing": {"level": None},
                    "magic": {"level": True},
                    "hunter": {"level": "85"},
                    "prayer": {"level": 0},
                    "mining": {"level": -1},
                },
            },
        },
    }

    levels = extract_player_access_skill_levels(
        player_data
    )

    assert levels == {"slayer": 1}

    # Missing and invalid evidence must never become level 0.
    for skill in (
        "sailing",
        "magic",
        "hunter",
        "prayer",
        "mining",
        "runecrafting",
    ):
        assert skill not in levels


def test_source_access_presumes_dragon_slayer_ii_completion():
    from utils.board_generation import AccessFlag
    from utils.osrs_content_access import (
        build_access_profile_for_content,
    )
    from utils.osrs_player_access import (
        assess_player_source_access,
    )

    profile = build_access_profile_for_content("vorkath")

    # The curated prerequisite resolver currently produces
    # 18 effective skill requirements for Dragon Slayer II.
    required = dict(profile.effective_skill_requirements)

    assert len(required) == 18
    assert AccessFlag.QUEST_LOCKED in profile.access_flags

    # Meets every direct and prerequisite quest skill requirement.
    assert assess_player_source_access(
        profile,
        required,
        source_id="vorkath",
        requirements_verified=True,
    ) == "accessible"

    # No manual confirmation of quest completion is supplied.


def test_source_access_distinguishes_low_and_unknown_skills():
    from utils.osrs_content_access import (
        build_access_profile_for_content,
    )
    from utils.osrs_player_access import (
        assess_player_source_access,
    )

    profile = build_access_profile_for_content("vorkath")
    required = dict(profile.effective_skill_requirements)

    def assess(levels):
        return assess_player_source_access(
            profile,
            levels,
            source_id="vorkath",
            requirements_verified=True,
        )

    too_low = dict(required)
    too_low["magic"] = required["magic"] - 1

    assert assess(too_low) == "inaccessible"

    missing = dict(required)
    del missing["magic"]

    assert assess(missing) == "unknown"

    malformed = dict(required)
    malformed["magic"] = "99"

    assert assess(malformed) == "unknown"

    # A demonstrated shortfall takes precedence over
    # another missing skill value.
    both = dict(required)
    both["magic"] = required["magic"] - 1
    del both["smithing"]

    assert assess(both) == "inaccessible"


def test_source_access_requires_reviewed_requirements():
    from utils.board_generation import AccessProfile
    from utils.osrs_player_access import (
        assess_player_source_access,
    )

    # Empty requirements do not automatically mean unrestricted.
    assert assess_player_source_access(
        AccessProfile(),
        {},
        source_id="test_source",
    ) == "unknown"

    # A reviewed genuinely unrestricted source is accessible.
    assert assess_player_source_access(
        AccessProfile(),
        {},
        source_id="test_source",
        requirements_verified=True,
    ) == "accessible"

    assert assess_player_source_access(
        None,
        {"slayer": 99},
        source_id="test_source",
        requirements_verified=True,
    ) == "unknown"


def test_source_access_separates_risks_from_unresolved_unlocks():
    from utils.board_generation import AccessFlag, AccessProfile
    from utils.osrs_player_access import (
        assess_player_source_access,
    )

    wilderness_profile = AccessProfile(
        access_flags=frozenset({
            AccessFlag.WILDERNESS,
            AccessFlag.DANGEROUS_DEATH,
        }),
    )

    assert assess_player_source_access(
        wilderness_profile,
        {},
        source_id="test_wilderness_source",
        requirements_verified=True,
    ) == "accessible"

    diary_profile = AccessProfile(
        access_flags=frozenset({
            AccessFlag.DIARY_LOCKED,
        }),
    )

    assert assess_player_source_access(
        diary_profile,
        {},
        source_id="test_diary_source",
        requirements_verified=True,
    ) == "unknown"


def _synthetic_multi_source_drop_access_data():
    from utils.board_generation import AccessProfile
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
            "evidence_refs": ("test:complete-source-review",),
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

    return rows, records, profiles


def test_nonunique_drop_access_accepts_any_accessible_source():
    from utils.osrs_player_access import (
        assess_player_nonunique_drop_access,
    )

    rows, records, profiles = (
        _synthetic_multi_source_drop_access_data()
    )

    # Magic 1 demonstrates that Vorkath is inaccessible,
    # but Slayer 80 allows the synthetic alternative.
    status = assess_player_nonunique_drop_access(
        drop_id="synthetic_rare_drop",
        drop_rows=rows,
        verification_records=records,
        source_access_profiles=profiles,
        skill_levels={
            "magic": 1,
            "slayer": 80,
        },
    )

    assert status == "accessible"

    # The quest source can independently establish access
    # using presumed quest completion from WOM skill levels.
    quest_requirements = dict(
        profiles["vorkath"][
            "access_profile"
        ].effective_skill_requirements
    )

    status = assess_player_nonunique_drop_access(
        drop_id="synthetic_rare_drop",
        drop_rows=rows,
        verification_records=records,
        source_access_profiles={
            "vorkath": profiles["vorkath"],
        },
        skill_levels=quest_requirements,
    )

    assert status == "accessible"


def test_nonunique_drop_access_distinguishes_inaccessible_and_unknown():
    from utils.osrs_player_access import (
        assess_player_nonunique_drop_access,
    )

    rows, records, profiles = (
        _synthetic_multi_source_drop_access_data()
    )

    def assess(levels, metadata=profiles):
        return assess_player_nonunique_drop_access(
            drop_id="synthetic_rare_drop",
            drop_rows=rows,
            verification_records=records,
            source_access_profiles=metadata,
            skill_levels=levels,
        )

    # Both verified acquisition methods are blocked.
    assert assess({
        "magic": 1,
        "slayer": 70,
    }) == "inaccessible"

    # Vorkath is blocked; the alternative has unknown
    # Slayer evidence, so the overall status is unknown.
    assert assess({
        "magic": 1,
    }) == "unknown"

    # Missing source-access metadata must not imply
    # that the source is freely accessible.
    assert assess(
        {"magic": 1},
        metadata={
            "vorkath": profiles["vorkath"],
        },
    ) == "unknown"

    # Unreviewed requirements must not approve a source.
    unreviewed = {
        **profiles,
        "synthetic_cave": {
            **profiles["synthetic_cave"],
            "requirements_verified": False,
        },
    }

    assert assess({
        "magic": 1,
        "slayer": 99,
    }, metadata=unreviewed) == "unknown"


def test_nonunique_drop_access_requires_verified_source_coverage():
    from utils.osrs_player_access import (
        assess_player_nonunique_drop_access,
    )

    rows, records, profiles = (
        _synthetic_multi_source_drop_access_data()
    )

    def assess(verification_records):
        return assess_player_nonunique_drop_access(
            drop_id="synthetic_rare_drop",
            drop_rows=rows,
            verification_records=verification_records,
            source_access_profiles=profiles,
            skill_levels={
                "magic": 99,
                "slayer": 99,
            },
        )

    # Spreadsheet observations alone cannot grant access.
    assert assess(()) == "unknown"

    # A declaration omitting an Excel-recorded source
    # is ineligible even if it claims complete coverage.
    incomplete = (
        {
            "drop_id": "synthetic_rare_drop",
            "source_ids": ("vorkath",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:incomplete-source-review",),
        },
    )

    assert assess(incomplete) == "unknown"

    # A correctly declared verification record is required.
    assert assess(records) == "accessible"


def _build_synthetic_team_access_roster(
    players_by_team,
    levels_by_name,
    failed_names=(),
):
    from utils.osrs_capability_profiles import (
        build_capability_profiles_from_rostered_players,
    )

    fetch_log = []

    def fake_fetch_player(name):
        fetch_log.append(name)

        if name in failed_names:
            raise RuntimeError("WOM failed")

        player_data = {"displayName": name}
        levels = levels_by_name.get(name)

        if levels is not None:
            player_data["latestSnapshot"] = {
                "data": {
                    "skills": {
                        skill: {"level": level}
                        for skill, level in levels.items()
                    },
                },
            }

        return player_data

    def fake_score_player(data):
        return {
            "player_name": data["displayName"],
            "skilling_score": 1,
        }

    result = build_capability_profiles_from_rostered_players(
        players_by_team,
        fetch_player=fake_fetch_player,
        score_player=fake_score_player,
    )

    return result, fetch_log


def _assess_synthetic_team_drop(
    result,
    team_name,
    *,
    verification_records_override=None,
):
    from utils.osrs_player_access import (
        assess_team_nonunique_drop_access,
    )

    rows, records, profiles = (
        _synthetic_multi_source_drop_access_data()
    )

    if verification_records_override is not None:
        records = verification_records_override

    return assess_team_nonunique_drop_access(
        team_name=team_name,
        capability_result=result,
        drop_id="synthetic_rare_drop",
        drop_rows=rows,
        verification_records=records,
        source_access_profiles=profiles,
    )


def test_team_drop_access_accepts_one_eligible_player():
    result, fetch_log = _build_synthetic_team_access_roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Bob"),
            ),
            "Saradomin": (
                (3, "Charlie"),
                (4, "Diana"),
            ),
        },
        {
            "Alice": {"magic": 1, "slayer": 55},
            "Bob": {"magic": 1, "slayer": 80},
            "Charlie": {"magic": 1, "slayer": 50},
            "Diana": {"magic": 1, "slayer": 60},
        },
    )

    assert fetch_log == [
        "Alice",
        "Bob",
        "Charlie",
        "Diana",
    ]

    # Alice cannot access either source, but Bob can
    # access the synthetic Slayer-72 alternative.
    assert _assess_synthetic_team_drop(
        result,
        "Zamorak",
    ) == "accessible"

    # Neither Saradomin player can access either source.
    assert _assess_synthetic_team_drop(
        result,
        "Saradomin",
    ) == "inaccessible"

    # Team assessment must reuse captured WOM evidence,
    # never fetch players again.
    assert fetch_log == [
        "Alice",
        "Bob",
        "Charlie",
        "Diana",
    ]


def test_team_drop_access_preserves_unknown_and_failed_players():
    result, fetch_log = _build_synthetic_team_access_roster(
        {
            "Zamorak": (
                (1, "Alice"),
                (2, "Bob"),
            ),
            "Armadyl": (
                (3, "Charlie"),
                (4, "Broken"),
            ),
            "Saradomin": (
                (5, "Diana"),
            ),
        },
        {
            "Alice": {"magic": 1, "slayer": 55},
            "Bob": None,
            "Charlie": {"magic": 1, "slayer": 40},
            "Diana": {"magic": 1, "slayer": 40},
        },
        failed_names=("Broken",),
    )

    # Bob has no WOM snapshot. His access is unknown.
    assert _assess_synthetic_team_drop(
        result,
        "Zamorak",
    ) == "unknown"

    # A failed WOM lookup must not disappear from the
    # assessment and make the team falsely inaccessible.
    assert len(result.failed_players) == 1

    assert _assess_synthetic_team_drop(
        result,
        "Armadyl",
    ) == "unknown"

    # A failure on another team must not affect this
    # team's demonstrably inaccessible player.
    assert _assess_synthetic_team_drop(
        result,
        "Saradomin",
    ) == "inaccessible"

    assert fetch_log == [
        "Alice",
        "Bob",
        "Charlie",
        "Broken",
        "Diana",
    ]


def test_team_drop_access_fails_closed_without_roster_or_coverage():
    result, fetch_log = _build_synthetic_team_access_roster(
        {
            "Empty": (),
            "Zamorak": ((1, "Alice"),),
        },
        {
            "Alice": {"magic": 1, "slayer": 80},
        },
    )

    # An empty or nonexistent team cannot establish access.
    assert _assess_synthetic_team_drop(
        result,
        "Empty",
    ) == "unknown"

    assert _assess_synthetic_team_drop(
        result,
        "Nonexistent",
    ) == "unknown"

    # Complete source verification remains mandatory,
    # even when a rostered player meets source skills.
    assert _assess_synthetic_team_drop(
        result,
        "Zamorak",
        verification_records_override=(),
    ) == "unknown"

    assert fetch_log == ["Alice"]
