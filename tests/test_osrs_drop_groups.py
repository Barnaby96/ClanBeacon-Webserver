from utils.osrs_drop_group_data import DROP_GROUP_DATA
from utils.osrs_drop_groups import (
    DROP_GROUP_DEFINITIONS,
    filter_valid_drop_target_by_point_value,
    get_drop_group_definition,
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
