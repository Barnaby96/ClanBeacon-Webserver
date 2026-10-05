from utils.osrs_drop_tile_effort import (
    DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
    DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
)
from utils.osrs_drop_tile_effort_preview import (
    build_drop_tile_effort_preview_rows,
)


def test_drop_tile_effort_preview_builds_group_rows():
    rows = build_drop_tile_effort_preview_rows()

    group_rows = [
        row
        for row in rows
        if row.tile_mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        and row.drop_group_id == "dagannoth_prime_uniques"
    ]

    assert group_rows
    assert all(
        row.target is not None
        for row in group_rows
    )
    assert all(
        row.suggested_point_value in {1, 2, 3, 4, 5}
        for row in group_rows
        if row.parseable
    )


def test_drop_tile_effort_preview_builds_specific_drop_rows():
    rows = build_drop_tile_effort_preview_rows()

    specific_rows = [
        row
        for row in rows
        if row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
        and row.drop_group_id == "dagannoth_prime_uniques"
    ]

    assert len(specific_rows) == 4
    assert all(
        row.source_id == "dagannoth_prime"
        for row in specific_rows
    )
    assert all(
        row.drop_name
        for row in specific_rows
    )
    assert all(
        row.suggested_point_value in {1, 2, 3, 4, 5}
        for row in specific_rows
        if row.parseable
    )


def test_drop_tile_effort_preview_can_build_specific_only_rows():
    rows = build_drop_tile_effort_preview_rows(
        include_group_unique_tiles=False,
        include_specific_drop_tiles=True,
    )

    assert rows
    assert {
        row.tile_mode
        for row in rows
    } == {DROP_TILE_EFFORT_MODE_SPECIFIC_DROP}


def test_drop_tile_effort_preview_applies_unsired_source_effort():
    rows = build_drop_tile_effort_preview_rows()

    first_bludgeon_group_row = next(
        row
        for row in rows
        if row.tile_mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        and row.drop_group_id == "abyssal_bludgeon_part"
        and row.target == 1
    )

    assert first_bludgeon_group_row.suggested_point_value >= 2


def test_drop_tile_effort_preview_applies_raid_source_effort():
    rows = build_drop_tile_effort_preview_rows()

    ancestral_hat = next(
        row
        for row in rows
        if row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
        and row.drop_group_id == "ancestral_set"
        and row.drop_name == "Ancestral hat"
    )

    assert ancestral_hat.suggested_point_value >= 4


def test_drop_tile_effort_preview_applies_fortis_colosseum_source_effort():
    rows = build_drop_tile_effort_preview_rows()

    quiver = next(
        row
        for row in rows
        if row.drop_group_id == "fortis_colosseum_wave_12"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
    )

    assert "Dizana" in quiver.drop_name
    assert "quiver" in quiver.drop_name
    assert quiver.expected_rolls == 1
    assert quiver.suggested_point_value == 5
