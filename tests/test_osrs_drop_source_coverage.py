def test_recorded_drop_source_map_preserves_shared_sources():
    from utils.osrs_drop_group_data import DROP_ROW_DATA
    from utils.osrs_drop_source_coverage import (
        build_recorded_drop_source_id_map,
    )

    sample_rows = (
        {
            "drop_id": "shared_rare",
            "source_ids": ("vorkath", "king_black_dragon"),
        },
        {
            "drop_id": "shared_rare",
            "source_ids": ("vorkath", "steel_dragon"),
        },
        {
            "drop_id": "other_drop",
            "source_ids": ("giant_mole",),
        },
    )

    sample_map = build_recorded_drop_source_id_map(sample_rows)

    assert sample_map["shared_rare"] == frozenset({
        "vorkath",
        "king_black_dragon",
        "steel_dragon",
    })

    assert sample_map["other_drop"] == frozenset({
        "giant_mole",
    })

    recorded_map = build_recorded_drop_source_id_map(
        DROP_ROW_DATA
    )

    visage_sources = recorded_map["draconic_visage"]

    assert len(visage_sources) == 15
    assert "vorkath" in visage_sources
    assert "king_black_dragon" in visage_sources
    assert "skeletal_wyvern" in visage_sources
    assert "rune_dragon" in visage_sources

    assert isinstance(visage_sources, frozenset)


def test_verified_source_map_requires_complete_evidence():
    from utils.osrs_drop_source_coverage import (
        build_verified_drop_source_id_map,
    )

    records = (
        {
            "drop_id": "test_verified_drop",
            "source_ids": ("vorkath", "king_black_dragon"),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:review-001",),
        },
        {
            "drop_id": "test_unverified_drop",
            "source_ids": ("giant_mole",),
            "verification_status": "implemented",
            "coverage_complete": True,
            "evidence_refs": ("test:review-002",),
        },
        {
            "drop_id": "test_incomplete_drop",
            "source_ids": ("zulrah",),
            "verification_status": "verified",
            "coverage_complete": False,
            "evidence_refs": ("test:review-003",),
        },
        {
            "drop_id": "test_unproven_drop",
            "source_ids": ("nex",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": (),
        },
        {
            "drop_id": "test_no_source_drop",
            "source_ids": (),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:review-004",),
        },
    )

    verified = build_verified_drop_source_id_map(records)

    assert verified == {
        "test_verified_drop": frozenset({
            "vorkath",
            "king_black_dragon",
        }),
    }


def test_verified_source_map_never_auto_approves_spreadsheet_rows():
    from utils.osrs_drop_group_data import DROP_ROW_DATA
    from utils.osrs_drop_source_coverage import (
        build_verified_drop_source_id_map,
        build_recorded_drop_source_id_map,
    )

    recorded = build_recorded_drop_source_id_map(DROP_ROW_DATA)

    assert len(recorded["draconic_visage"]) == 15

    # No explicit verification records means no approved sources.
    assert build_verified_drop_source_id_map() == {}


def test_verified_source_map_rejects_duplicate_verification_records():
    import pytest

    from utils.osrs_drop_source_coverage import (
        build_verified_drop_source_id_map,
    )

    records = (
        {
            "drop_id": "test_shared_drop",
            "source_ids": ("vorkath",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:review-a",),
        },
        {
            "drop_id": "test_shared_drop",
            "source_ids": ("king_black_dragon",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:review-b",),
        },
    )

    with pytest.raises(ValueError, match="Duplicate"):
        build_verified_drop_source_id_map(records)


def _make_source_coverage_test_candidate():
    from utils.board_generation import (
        ContributionMode,
        Route,
        RouteMode,
        TileCandidate,
        TileCategory,
        TrackingSource,
    )

    return TileCandidate(
        title="Test Draconic visage objective",
        point_value=5,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            Route(
                route_type=TileCategory.DROP,
                display_text="Obtain Draconic visage",
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.TEAM_SUM,
                source_id="vorkath",
                drop_id="draconic_visage",
            ),
        ),
    )


def test_verified_drop_tags_reserve_all_acquisition_sources():
    import pytest

    from utils.board_generation import (
        find_conflicting_tags,
        reserve_candidate_tags,
    )
    from utils.osrs_drop_source_coverage import (
        apply_verified_drop_source_tags,
    )

    candidate = _make_source_coverage_test_candidate()

    # Synthetic verification data for testing only.
    verification_records = (
        {
            "drop_id": "draconic_visage",
            "source_ids": (
                "vorkath",
                "king_black_dragon",
            ),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:source-review",),
        },
    )

    verified_candidate = apply_verified_drop_source_tags(
        candidate,
        verification_records,
    )

    assert {
        "source:vorkath",
        "source:king_black_dragon",
        "drop:draconic_visage",
    }.issubset(verified_candidate.all_hard_unique_tags)

    assert (
        "source:king_black_dragon"
        not in candidate.all_hard_unique_tags
    )

    assert find_conflicting_tags(
        verified_candidate,
        {"source:king_black_dragon"},
    ) == frozenset({"source:king_black_dragon"})

    assert find_conflicting_tags(
        verified_candidate,
        {"source:vorkath"},
    ) == frozenset({"source:vorkath"})

    with pytest.raises(ValueError, match="conflicts"):
        reserve_candidate_tags(
            verified_candidate,
            {"source:king_black_dragon"},
        )


def test_verified_drop_tags_fail_closed_without_complete_verification():
    import pytest

    from utils.osrs_drop_source_coverage import (
        apply_verified_drop_source_tags,
    )

    candidate = _make_source_coverage_test_candidate()

    # No approved records.
    with pytest.raises(ValueError):
        apply_verified_drop_source_tags(candidate, ())

    # A spreadsheet-style record is not verification.
    with pytest.raises(ValueError):
        apply_verified_drop_source_tags(
            candidate,
            (
                {
                    "drop_id": "draconic_visage",
                    "source_ids": ("vorkath",),
                },
            ),
        )

    # Verified coverage must include the candidate's source.
    with pytest.raises(ValueError):
        apply_verified_drop_source_tags(
            candidate,
            (
                {
                    "drop_id": "draconic_visage",
                    "source_ids": ("king_black_dragon",),
                    "verification_status": "verified",
                    "coverage_complete": True,
                    "evidence_refs": ("test:source-review",),
                },
            ),
        )

    # An incomplete source list cannot be approved.
    with pytest.raises(ValueError):
        apply_verified_drop_source_tags(
            candidate,
            (
                {
                    "drop_id": "draconic_visage",
                    "source_ids": ("vorkath",),
                    "verification_status": "verified",
                    "coverage_complete": False,
                    "evidence_refs": ("test:incomplete-review",),
                },
            ),
        )


def test_nonunique_drop_eligibility_requires_complete_source_coverage():
    from utils.osrs_drop_source_coverage import (
        select_source_verified_nonunique_drops,
    )

    rows = (
        {
            "drop_id": "test_shared_drop",
            "source_ids": ("boss_a",),
            "include_in_unique_group": False,
        },
        {
            "drop_id": "test_shared_drop",
            "source_ids": ("boss_b",),
            "include_in_unique_group": False,
        },
        {
            "drop_id": "test_unique_drop",
            "source_ids": ("boss_c",),
            "include_in_unique_group": True,
        },
        {
            "drop_id": "test_mixed_drop",
            "source_ids": ("boss_d",),
            "include_in_unique_group": True,
        },
        {
            "drop_id": "test_mixed_drop",
            "source_ids": ("boss_e",),
            "include_in_unique_group": False,
        },
    )

    verification_records = (
        {
            "drop_id": "test_shared_drop",
            "source_ids": ("boss_a", "boss_b"),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:shared-review",),
        },
        {
            "drop_id": "test_unique_drop",
            "source_ids": ("boss_c",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:unique-review",),
        },
        {
            "drop_id": "test_mixed_drop",
            "source_ids": ("boss_d", "boss_e"),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:mixed-review",),
        },
    )

    eligible = select_source_verified_nonunique_drops(
        rows,
        verification_records,
    )

    assert eligible == {
        "test_shared_drop": frozenset({
            "boss_a",
            "boss_b",
        }),
    }


def test_nonunique_drop_eligibility_fails_closed_for_draconic_visage():
    from utils.osrs_drop_group_data import DROP_ROW_DATA
    from utils.osrs_drop_source_coverage import (
        select_source_verified_nonunique_drops,
    )

    # Nothing from the spreadsheet is automatically source-verified.
    assert select_source_verified_nonunique_drops(
        DROP_ROW_DATA,
    ) == {}

    # Synthetic verification deliberately omits 14 recorded sources.
    incomplete_records = (
        {
            "drop_id": "draconic_visage",
            "source_ids": ("vorkath",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:incomplete-source-list",),
        },
    )

    eligible = select_source_verified_nonunique_drops(
        DROP_ROW_DATA,
        incomplete_records,
    )

    assert "draconic_visage" not in eligible
