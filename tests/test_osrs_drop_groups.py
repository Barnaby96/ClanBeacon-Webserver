from utils.osrs_drop_group_data import DROP_GROUP_DATA
from utils.osrs_drop_groups import (
    DROP_GROUP_DEFINITIONS,
    filter_valid_drop_target_by_point_value,
    get_drop_group_definition,
    get_drop_group_overlap_family_ids,
    get_drop_group_overlap_hard_unique_tags,
    get_max_distinct_drop_count,
)


def test_drop_group_definitions_are_loaded_from_generated_data():
    assert len(
        DROP_GROUP_DEFINITIONS
    ) == len(
        DROP_GROUP_DATA
    )

    assert get_drop_group_definition(
        "raids_purple"
    ).max_distinct_drop_count == 26

    assert get_drop_group_definition(
        "fashionscape_item"
    ).max_distinct_drop_count >= 1


def test_dagannoth_rex_drop_group_caps_relevant_unique_count():
    definition = get_drop_group_definition(
        "Dagannoth Rex uniques"
    )

    assert definition.drop_group_id == "dagannoth_rex_uniques"
    assert definition.display_name.lower() == "dagannoth rex uniques"
    assert definition.source_id == "dagannoth_rex"
    assert definition.source_ids == (
        "dagannoth_rex",
    )
    assert {
        "berserker_ring",
        "warrior_ring",
    }.issubset(
        set(
            definition.drop_ids
        )
    )
    assert definition.max_distinct_drop_count >= 2
    assert definition.include_pet is False


def test_get_max_distinct_drop_count_for_known_group():
    assert get_max_distinct_drop_count(
        "dagannoth_rex_uniques"
    ) >= 2


def test_get_max_distinct_drop_count_for_unknown_group():
    assert get_max_distinct_drop_count(
        "unknown_group"
    ) is None


def test_filter_valid_drop_target_by_point_value_caps_known_group():
    max_count = get_max_distinct_drop_count(
        "dagannoth_rex_uniques"
    )

    assert max_count >= 2

    targets = {
        point_value: point_value
        for point_value in range(
            1,
            max_count + 2,
        )
    }

    assert filter_valid_drop_target_by_point_value(
        "dagannoth_rex_uniques",
        targets,
    ) == {
        point_value: point_value
        for point_value in range(
            1,
            max_count + 1,
        )
    }


def test_filter_valid_drop_target_by_point_value_uses_large_generated_groups():
    assert filter_valid_drop_target_by_point_value(
        "raids_purple",
        {
            1: 1,
            2: 5,
            3: 10,
            4: 20,
            5: 30,
        },
    ) == {
        1: 1,
        2: 5,
        3: 10,
        4: 20,
    }


def test_filter_valid_drop_target_by_point_value_preserves_unknown_group():
    assert filter_valid_drop_target_by_point_value(
        "unknown_group",
        {
            1: 1,
            2: 2,
            3: 3,
        },
    ) == {
        1: 1,
        2: 2,
        3: 3,
    }


def test_wilderness_drop_groups_share_overlap_family_tag():
    assert get_drop_group_overlap_family_ids(
        "wilderness_unique"
    ) == (
        "wilderness_unique",
    )
    assert get_drop_group_overlap_family_ids(
        "wilderness_ring"
    ) == (
        "wilderness_unique",
    )
    assert get_drop_group_overlap_family_ids(
        "zulrah_uniques"
    ) == ()

    assert get_drop_group_overlap_hard_unique_tags(
        "wilderness_unique"
    ) == frozenset(
        {
            "drop_group_family:wilderness_unique",
        }
    )
    assert get_drop_group_overlap_hard_unique_tags(
        "wilderness_ring"
    ) == frozenset(
        {
            "drop_group_family:wilderness_unique",
        }
    )


def test_drop_group_definition_loads_optional_drop_metadata():
    from utils.osrs_drop_groups import DropGroupDefinition

    definition = DropGroupDefinition.from_data_record(
        {
            "drop_group_id": "giant_mole_unique",
            "display_name": "Giant Mole Unique",
            "source_ids": (
                "giant_mole",
            ),
            "drop_ids": (
                "mole_skin",
            ),
            "drop_names": (
                "Mole skin",
            ),
            "drop_rates": (
                "Always",
            ),
            "drop_counting_modes": (
                "item_quantity",
            ),
            "drop_quantities": (
                "1-3",
            ),
            "access_notes": (
                "Falador hard diary useful.",
            ),
            "notes": (
                "Quantity drop, not N-of-set by default.",
            ),
        }
    )

    assert definition.drop_rates == (
        "Always",
    )
    assert definition.drop_counting_modes == (
        "item_quantity",
    )
    assert definition.drop_quantities == (
        "1-3",
    )
    assert definition.access_notes == (
        "Falador hard diary useful.",
    )
    assert definition.notes == (
        "Quantity drop, not N-of-set by default.",
    )


def test_giant_mole_distinct_drop_count_ignores_item_quantity_rows():
    definition = get_drop_group_definition(
        "giant_mole_unique"
    )

    assert definition.drop_names == (
        "Immaculate mole skin",
        "Mole skin",
    )
    assert definition.drop_counting_modes == (
        "distinct_drops",
        "item_quantity",
    )
    assert definition.distinct_drop_names == (
        "Immaculate mole skin",
    )
    assert definition.max_distinct_drop_count == 1
