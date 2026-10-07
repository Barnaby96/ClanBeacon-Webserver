from utils.osrs_capability_profiles import (
    CapabilityProfile,
    CapabilityProfileSet,
)
from utils.osrs_generated_board_preview import (
    build_capability_candidate_order_key,
    build_filtered_generation_candidates,
    build_generated_board_candidate_key,
    get_curated_generated_board_preview_summary,
    build_generated_board_preview_summary,
    get_curated_generated_board_preview_summary,
)
from utils.board_generation import (
    BoardAssemblyError,
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
    assemble_board_candidates,
)
from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates


def test_build_generated_board_preview_summary_groups_rows_by_point_value():
    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    summary = build_generated_board_preview_summary(
        board
    )

    assert summary.candidate_count == 25
    assert summary.counts_by_point_value == {
        1: 5,
        2: 5,
        3: 5,
        4: 5,
        5: 5,
    }
    assert set(summary.rows_by_point_value) == {
        1,
        2,
        3,
        4,
        5,
    }
    assert all(
        len(rows) == 5
        for rows in summary.rows_by_point_value.values()
    )


def test_curated_generated_board_preview_summary_includes_tags_and_routes():
    summary = get_curated_generated_board_preview_summary()

    rows = [
        row
        for point_rows in summary.rows_by_point_value.values()
        for row in point_rows
    ]

    assert len(rows) == 25
    assert all(
        row.title
        for row in rows
    )
    assert all(
        row.route_descriptions
        for row in rows
    )
    assert any(
        "source:zulrah" in row.hard_unique_tags
        for row in rows
    )


def test_generated_board_preview_summary_accepts_capability_profiles():
    summary = get_curated_generated_board_preview_summary(
        capability_profiles=CapabilityProfileSet(
            source="teams",
            profiles=(
                CapabilityProfile(
                    profile_id="1",
                    display_name="Team One",
                    player_count=5,
                    scores={
                        "solo_boss_score": 9,
                    },
                ),
                CapabilityProfile(
                    profile_id="2",
                    display_name="Team Two",
                    player_count=5,
                    scores={
                        "solo_boss_score": 0,
                    },
                ),
            ),
        )
    )

    rows = [
        row
        for point_rows in summary.rows_by_point_value.values()
        for row in point_rows
    ]

    zulrah_row = next(
        row
        for row in rows
        if "source:zulrah" in row.hard_unique_tags
    )

    assert zulrah_row.capability_score_field == "solo_boss_score"
    assert zulrah_row.capability_score_field_label == "Solo boss"
    assert zulrah_row.capability_warning_level == "danger"
    assert "Solo boss" in zulrah_row.capability_summary_text


def make_capability_order_test_candidate(title, boss_id):
    return TileCandidate(
        title=title,
        point_value=1,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=next(iter(RouteMode)),
        routes=(
            Route(
                route_type=TileCategory.KILLCOUNT,
                tracking_source=next(iter(TrackingSource)),
                contribution_mode=next(iter(ContributionMode)),
                display_text=title,
                target=1,
                boss_id=boss_id,
                source_id=boss_id,
            ),
        ),
    )


def test_capability_candidate_order_key_prefers_balanced_candidates():
    balanced_candidate = make_capability_order_test_candidate(
        "Balanced Zulrah",
        "zulrah",
    )
    risky_candidate = make_capability_order_test_candidate(
        "Risky Nex",
        "nex",
    )

    capability_profiles = CapabilityProfileSet(
        source="teams",
        profiles=(
            CapabilityProfile(
                profile_id="1",
                display_name="Team One",
                player_count=5,
                scores={
                    "solo_boss_score": 10,
                    "group_boss_score": 10,
                },
            ),
            CapabilityProfile(
                profile_id="2",
                display_name="Team Two",
                player_count=5,
                scores={
                    "solo_boss_score": 10,
                    "group_boss_score": 0,
                },
            ),
        ),
    )

    key = build_capability_candidate_order_key(
        capability_profiles
    )

    assert key(balanced_candidate) < key(risky_candidate)


def test_generated_board_preview_only_uses_capability_order_with_profiles(monkeypatch):
    captured = {}

    def fake_assemble_board_candidates(candidates, candidate_order_key=None):
        captured["candidate_order_key"] = candidate_order_key

        class FakeBoard:
            candidates = ()

        return FakeBoard()

    monkeypatch.setattr(
        "utils.osrs_generated_board_preview.assemble_board_candidates",
        fake_assemble_board_candidates,
    )

    get_curated_generated_board_preview_summary()

    assert captured["candidate_order_key"] is None

    get_curated_generated_board_preview_summary(
        capability_profiles=CapabilityProfileSet(
            source="teams",
            profiles=(),
        )
    )

    assert captured["candidate_order_key"] is not None


def test_generated_board_preview_falls_back_when_capability_order_cannot_assemble_board(
    monkeypatch,
):
    captured_order_keys = []

    class FakeBoard:
        candidates = ()

    def fake_assemble_board_candidates(candidates, candidate_order_key=None):
        captured_order_keys.append(candidate_order_key)

        if candidate_order_key is not None:
            raise BoardAssemblyError("Could not fill generated board.")

        return FakeBoard()

    monkeypatch.setattr(
        "utils.osrs_generated_board_preview.assemble_board_candidates",
        fake_assemble_board_candidates,
    )

    summary = get_curated_generated_board_preview_summary(
        capability_profiles=CapabilityProfileSet(
            source="teams",
            profiles=(),
        )
    )

    assert summary.candidate_count == 0
    assert summary.capability_ordering_applied is True
    assert summary.capability_ordering_fell_back is True
    assert summary.capability_ordering_fallback_reason == (
        "Could not fill generated board."
    )
    assert captured_order_keys[0] is not None
    assert captured_order_keys[1] is None


def test_generated_board_preview_summary_marks_capability_ordering_applied(monkeypatch):
    captured = {}

    def fake_assemble_board_candidates(candidates, candidate_order_key=None):
        captured["candidate_order_key"] = candidate_order_key

        class FakeBoard:
            candidates = ()

        return FakeBoard()

    monkeypatch.setattr(
        "utils.osrs_generated_board_preview.assemble_board_candidates",
        fake_assemble_board_candidates,
    )

    summary = get_curated_generated_board_preview_summary(
        capability_profiles=CapabilityProfileSet(
            source="teams",
            profiles=(),
        )
    )

    assert captured["candidate_order_key"] is not None
    assert summary.capability_ordering_applied is True
    assert summary.capability_ordering_fell_back is False
    assert summary.capability_ordering_fallback_reason is None


def test_generated_board_candidate_key_is_stable():
    candidate = next(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if candidate.title == "Complete 800 Giant Mole KC"
    )

    assert build_generated_board_candidate_key(candidate) == (
        build_generated_board_candidate_key(candidate)
    )
    assert len(build_generated_board_candidate_key(candidate)) == 64


def test_generated_board_candidate_key_distinguishes_point_tiers():
    candidates = get_curated_tile_generation_candidates()

    lower_tier = next(
        candidate
        for candidate in candidates
        if candidate.title == "Complete 500 Giant Mole KC"
    )
    higher_tier = next(
        candidate
        for candidate in candidates
        if candidate.title == "Complete 800 Giant Mole KC"
    )

    assert build_generated_board_candidate_key(lower_tier) != (
        build_generated_board_candidate_key(higher_tier)
    )


def test_generated_board_preview_rows_include_tile_key():
    summary = get_curated_generated_board_preview_summary()
    row = next(iter(summary.rows_by_point_value.values()))[0]

    assert row.tile_key
    assert len(row.tile_key) == 64


def test_build_filtered_generation_candidates_bans_exact_tile_key_only():
    candidates = tuple(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if candidate.title in {
            "Complete 500 Giant Mole KC",
            "Complete 800 Giant Mole KC",
        }
    )

    banned_key = build_generated_board_candidate_key(
        next(
            candidate
            for candidate in candidates
            if candidate.title == "Complete 800 Giant Mole KC"
        )
    )

    filtered = build_filtered_generation_candidates(
        candidates,
        banned_tile_keys=(
            banned_key,
        ),
    )

    assert {
        candidate.title
        for candidate in filtered
    } == {
        "Complete 500 Giant Mole KC",
    }


def test_reroll_summary_keeps_selected_tile_and_excludes_unkept_exact_tile():
    first_summary = get_curated_generated_board_preview_summary()

    first_rows = tuple(
        row
        for rows in first_summary.rows_by_point_value.values()
        for row in rows
    )

    kept_row = first_rows[0]
    banned_row = first_rows[1]

    rerolled_summary = get_curated_generated_board_preview_summary(
        kept_tile_keys=(
            kept_row.tile_key,
        ),
        banned_tile_keys=(
            banned_row.tile_key,
        ),
    )

    rerolled_rows = tuple(
        row
        for rows in rerolled_summary.rows_by_point_value.values()
        for row in rows
    )

    rerolled_keys = {
        row.tile_key
        for row in rerolled_rows
    }

    assert kept_row.tile_key in rerolled_keys
    assert banned_row.tile_key not in rerolled_keys
