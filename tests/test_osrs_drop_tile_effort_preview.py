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


def test_drop_tile_effort_preview_formats_decimal_values_for_display():
    rows = build_drop_tile_effort_preview_rows()

    row = next(
        row
        for row in rows
        if row.drop_group_id == "abyssal_bludgeon_part"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        and row.target == 1
    )

    assert row.expected_rolls_display == "67.33"
    assert row.total_effort_display == "202"


def test_drop_tile_effort_preview_exposes_source_effort_reason():
    rows = build_drop_tile_effort_preview_rows()

    quiver = next(
        row
        for row in rows
        if row.drop_group_id == "fortis_colosseum_wave_12"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
    )

    assert quiver.access_requirement_multiplier_display == "5"
    assert quiver.source_difficulty_multiplier_display == "500"
    assert "Wave 12" in quiver.source_effort_reason


def test_drop_tile_effort_preview_applies_slayer_boss_source_effort():
    rows = build_drop_tile_effort_preview_rows()

    hydra_leather = next(
        row
        for row in rows
        if row.drop_group_id == "alchemical_hydra_unique"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
        and row.drop_name == "Hydra leather"
    )

    araxxor_one_unique = next(
        row
        for row in rows
        if row.drop_group_id == "araxxor_uniques"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        and row.target == 1
    )

    assert hydra_leather.access_requirement_multiplier_display == "2"
    assert hydra_leather.source_difficulty_multiplier_display == "1.5"
    assert "Slayer" in hydra_leather.source_effort_reason
    assert hydra_leather.suggested_point_value >= 4

    assert araxxor_one_unique.access_requirement_multiplier_display == "2"
    assert araxxor_one_unique.source_difficulty_multiplier_display == "1.75"
    assert "Slayer" in araxxor_one_unique.source_effort_reason
    assert araxxor_one_unique.suggested_point_value >= 2


def test_drop_tile_effort_preview_applies_boss_source_effort():
    rows = build_drop_tile_effort_preview_rows()

    nex_row = next(
        row
        for row in rows
        if row.source_id == "nex"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        and row.target == 1
    )
    vorkath_row = next(
        row
        for row in rows
        if row.drop_group_id == "vorkath_uniques"
        and row.tile_mode == DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        and row.target == 1
    )

    assert nex_row.access_requirement_multiplier_display == "2"
    assert nex_row.source_difficulty_multiplier_display == "25"
    assert "group-boss" in nex_row.source_effort_reason
    assert nex_row.suggested_point_value >= 4

    assert vorkath_row.access_requirement_multiplier_display == "1.5"
    assert vorkath_row.source_difficulty_multiplier_display == "1.5"
    assert "quest access" in vorkath_row.source_effort_reason
    assert vorkath_row.suggested_point_value >= 3
