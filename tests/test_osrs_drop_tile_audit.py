from collections import Counter

from utils.osrs_tile_template_expansion import (
    DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED,
    DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE,
    DROP_GROUP_TILE_AUDIT_REVIEW_MULTI_SOURCE,
    build_drop_group_tile_audit_rows,
    classify_drop_group_for_tile_audit,
)


def test_drop_group_tile_audit_marks_existing_static_templates():
    rows = build_drop_group_tile_audit_rows()

    classifications_by_group_id = {
        row.drop_group_id: row.classification
        for row in rows
    }

    assert classifications_by_group_id["zulrah_uniques"] == (
        DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED
    )
    assert classifications_by_group_id["dagannoth_rex_uniques"] == (
        DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED
    )


def test_drop_group_tile_audit_identifies_single_source_candidates():
    rows = build_drop_group_tile_audit_rows()

    classifications_by_group_id = {
        row.drop_group_id: row.classification
        for row in rows
    }

    assert classifications_by_group_id["dagannoth_prime_uniques"] == (
        DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE
    )
    assert classifications_by_group_id["dagannoth_supreme_uniques"] == (
        DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE
    )


def test_drop_group_tile_audit_marks_multi_source_groups_for_review():
    classification, reason = classify_drop_group_for_tile_audit(
        {
            "drop_group_id": "multi_source_test",
            "display_name": "Multi Source Test",
            "source_ids": (
                "source_one",
                "source_two",
            ),
            "source_names": (
                "Source One",
                "Source Two",
            ),
            "drop_ids": (
                "drop_one",
            ),
        },
        templated_group_ids=frozenset(),
    )

    assert classification == DROP_GROUP_TILE_AUDIT_REVIEW_MULTI_SOURCE
    assert "Multiple sources" in reason


def test_drop_group_tile_audit_has_expected_total_shape():
    rows = build_drop_group_tile_audit_rows()

    counts = Counter(
        row.classification
        for row in rows
    )

    assert len(rows) == 109
    assert counts[DROP_GROUP_TILE_AUDIT_ALREADY_TEMPLATED] == 10
    assert counts[DROP_GROUP_TILE_AUDIT_ELIGIBLE_SINGLE_SOURCE] > 0


def test_drop_group_tile_audit_counts_specific_drop_tile_candidates():
    rows = build_drop_group_tile_audit_rows()

    rows_by_group_id = {
        row.drop_group_id: row
        for row in rows
    }

    dagannoth_prime = rows_by_group_id["dagannoth_prime_uniques"]

    assert dagannoth_prime.supports_group_unique_tiles is True
    assert dagannoth_prime.supports_specific_drop_tiles is True
    assert dagannoth_prime.specific_drop_tile_count == 4


def test_drop_group_tile_audit_rejects_specific_drops_from_multi_source_groups():
    rows = build_drop_group_tile_audit_rows(
        drop_groups=(
            {
                "drop_group_id": "shared_group",
                "display_name": "Shared Group",
                "source_ids": (
                    "source_one",
                    "source_two",
                ),
                "source_names": (
                    "Source One",
                    "Source Two",
                ),
                "drop_ids": (
                    "shared_drop",
                ),
            },
        )
    )

    assert rows[0].supports_group_unique_tiles is False
    assert rows[0].supports_specific_drop_tiles is False
    assert rows[0].specific_drop_tile_count == 0


def test_drop_group_tile_audit_blocks_individual_clue_drop_tiles():
    rows = build_drop_group_tile_audit_rows()

    rows_by_group_id = {
        row.drop_group_id: row
        for row in rows
    }

    third_age = rows_by_group_id["3rd_age_unique"]

    assert third_age.supports_specific_drop_tiles is False
    assert third_age.specific_drop_tile_count == 0
