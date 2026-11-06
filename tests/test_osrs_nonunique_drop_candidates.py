"""Regressions for provisional, source-verified non-unique DROP recipes."""


def _sample_drop_rows():
    return (
        {
            "drop_id": "synthetic_shared_drop",
            "drop_name": "Synthetic shared drop",
            "source_ids": ("boss_a",),
            "include_in_unique_group": False,
        },
        {
            "drop_id": "synthetic_shared_drop",
            "drop_name": "Synthetic shared drop",
            "source_ids": ("boss_b",),
            "include_in_unique_group": False,
        },
    )


def _verified_records():
    return (
        {
            "drop_id": "synthetic_shared_drop",
            "source_ids": ("boss_a", "boss_b", "boss_c"),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:synthetic-source-review",),
        },
    )


def test_provisional_nonunique_drop_reserves_every_verified_source():
    from utils.board_generation import (
        ContributionMode,
        RouteMode,
        TileCategory,
        TrackingSource,
        find_conflicting_tags,
    )
    from utils.osrs_generated_drop_tile_candidates import (
        build_provisional_verified_nonunique_drop_candidate,
    )

    candidate = build_provisional_verified_nonunique_drop_candidate(
        drop_id="synthetic_shared_drop",
        source_id="boss_a",
        target=2,
        point_value=3,
        drop_rows=_sample_drop_rows(),
        verification_records=_verified_records(),
    )

    assert candidate.primary_category == TileCategory.DROP
    assert candidate.point_value == 3
    assert candidate.route_mode == RouteMode.SINGLE
    assert len(candidate.routes) == 1

    route = candidate.routes[0]

    assert route.drop_id == "synthetic_shared_drop"
    assert route.target == 2
    assert route.tracking_source == TrackingSource.DINK
    assert route.contribution_mode == ContributionMode.TEAM_SUM

    # Effort has not yet been calibrated.
    assert route.expected_rolls is None

    assert {
        "drop:synthetic_shared_drop",
        "source:boss_a",
        "source:boss_b",
        "source:boss_c",
    }.issubset(candidate.all_hard_unique_tags)

    # Boss C was verified as an additional source despite being
    # absent from the original spreadsheet rows.
    assert find_conflicting_tags(
        candidate,
        {"source:boss_c"},
    ) == frozenset({"source:boss_c"})

    # A source ID may anchor the route's metadata, but must not
    # turn the objective into a boss-specific acquisition rule.
    assert "boss_a" not in candidate.title.casefold()


def test_provisional_nonunique_drop_fails_closed_for_unverified_sources():
    import pytest

    from utils.osrs_generated_drop_tile_candidates import (
        build_provisional_verified_nonunique_drop_candidate,
    )

    base = {
        "drop_id": "synthetic_shared_drop",
        "source_id": "boss_a",
        "target": 2,
        "point_value": 3,
        "drop_rows": _sample_drop_rows(),
    }

    with pytest.raises(ValueError):
        build_provisional_verified_nonunique_drop_candidate(
            **base,
            verification_records=(),
        )

    # A declaration covering only one of two recorded sources
    # cannot qualify, even if its completeness flag says True.
    incomplete_sources = (
        {
            "drop_id": "synthetic_shared_drop",
            "source_ids": ("boss_a",),
            "verification_status": "verified",
            "coverage_complete": True,
            "evidence_refs": ("test:incomplete",),
        },
    )

    with pytest.raises(ValueError):
        build_provisional_verified_nonunique_drop_candidate(
            **base,
            verification_records=incomplete_sources,
        )

    unique_rows = tuple(
        {
            **row,
            "include_in_unique_group": True,
        }
        for row in _sample_drop_rows()
    )

    with pytest.raises(ValueError):
        build_provisional_verified_nonunique_drop_candidate(
            **{**base, "drop_rows": unique_rows},
            verification_records=_verified_records(),
        )


def test_provisional_nonunique_drop_rejects_invalid_recipe_inputs():
    import pytest

    from utils.osrs_generated_drop_tile_candidates import (
        build_provisional_verified_nonunique_drop_candidate,
    )

    base = {
        "drop_id": "synthetic_shared_drop",
        "source_id": "boss_a",
        "target": 2,
        "point_value": 3,
        "drop_rows": _sample_drop_rows(),
        "verification_records": _verified_records(),
    }

    invalid_overrides = (
        {"target": 0},
        {"target": True},
        {"point_value": 0},
        {"point_value": 6},
        {"drop_id": "unknown_drop"},
        {"source_id": "unverified_boss"},
    )

    for override in invalid_overrides:
        with pytest.raises(ValueError):
            build_provisional_verified_nonunique_drop_candidate(
                **{**base, **override},
            )


def test_provisional_nonunique_drop_converts_to_live_dink_condition(
    monkeypatch,
):
    from utils import osrs_generated_board_live_tiles as live_tiles
    from utils.osrs_generated_drop_tile_candidates import (
        build_provisional_verified_nonunique_drop_candidate,
    )

    rows = _sample_drop_rows()

    candidate = build_provisional_verified_nonunique_drop_candidate(
        drop_id="synthetic_shared_drop",
        source_id="boss_a",
        target=2,
        point_value=3,
        drop_rows=rows,
        verification_records=_verified_records(),
    )

    # Supply synthetic imported metadata to the converter.
    # This does not modify the real 435-row database.
    monkeypatch.setattr(
        live_tiles,
        "DROP_ROW_DATA",
        rows,
        raising=False,
    )

    assert candidate.routes[0].source_id is None

    payload = live_tiles.build_live_tile_payload_from_candidate(
        candidate
    )

    assert len(payload["conditions"]) == 1

    condition = payload["conditions"][0]

    assert condition["condition_type"] == "DROP"
    assert condition["condition_trigger"] == "Synthetic shared drop"
    assert condition["target"] == 2

    # Acquisition-source reservation belongs to board generation,
    # not to the Dink item-name matching condition.
    assert "boss_a" not in condition["condition_trigger"]
    assert "boss_b" not in condition["condition_trigger"]


def test_unapproved_draconic_visage_name_resolves_from_imported_rows():
    from utils.osrs_drop_group_data import DROP_ROW_DATA
    from utils.osrs_generated_board_live_tiles import (
        _get_drop_name,
    )

    matches = [
        row
        for row in DROP_ROW_DATA
        if row["drop_id"] == "draconic_visage"
    ]

    assert len(matches) == 15

    # Name resolution must not require source verification.
    # This test does not create or activate any Bingo candidate.
    assert _get_drop_name("draconic_visage") == "Draconic visage"
