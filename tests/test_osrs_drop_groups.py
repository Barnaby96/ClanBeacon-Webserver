from utils.osrs_drop_groups import (
    filter_valid_drop_target_by_point_value,
    get_drop_group_definition,
    get_max_distinct_drop_count,
)


def test_dagannoth_rex_drop_group_caps_relevant_unique_count():
    definition = get_drop_group_definition(
        "Dagannoth Rex uniques"
    )

    assert definition.drop_group_id == "dagannoth_rex_uniques"
    assert definition.source_id == "dagannoth_rex"
    assert definition.drop_ids == (
        "berserker_ring",
        "warrior_ring",
    )
    assert definition.max_distinct_drop_count == 2
    assert definition.include_pet is False


def test_get_max_distinct_drop_count_for_known_group():
    assert get_max_distinct_drop_count(
        "dagannoth_rex_uniques"
    ) == 2


def test_get_max_distinct_drop_count_for_unknown_group():
    assert get_max_distinct_drop_count(
        "unknown_group"
    ) is None


def test_filter_valid_drop_target_by_point_value_caps_known_group():
    assert filter_valid_drop_target_by_point_value(
        "dagannoth_rex_uniques",
        {
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
        },
    ) == {
        1: 1,
        2: 2,
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
