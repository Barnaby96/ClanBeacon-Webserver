import pytest

from utils.osrs_drop_database_import import (
    normalise_drop_database_row,
    normalise_drop_database_rows,
    parse_yes_no,
    split_semicolon_values,
)


def test_split_semicolon_values_removes_empty_parts_and_whitespace():
    assert split_semicolon_values(
        "Chambers of Xeric Uniques; Raids Purple; Ancestral Set"
    ) == (
        "Chambers of Xeric Uniques",
        "Raids Purple",
        "Ancestral Set",
    )


def test_parse_yes_no_handles_blank_values_with_default():
    assert parse_yes_no(
        "Yes"
    ) is True
    assert parse_yes_no(
        "No"
    ) is False
    assert parse_yes_no(
        None,
        default=False,
    ) is False
    assert parse_yes_no(
        "",
        default=True,
    ) is True


def test_normalise_drop_database_row_generates_blank_ids():
    row = normalise_drop_database_row(
        {
            "Source Name(s)": "Chambers of Xeric",
            "Source ID(s)": "",
            "Group Name(s)": "Chambers of Xeric Uniques; Raids Purple; Ancestral Set",
            "Group ID(s)": "",
            "Drop Name": "Ancestral hat",
            "Drop ID": "",
            "Drop Rate(s)": "1/15; 1/14",
            "Include In Unique Group?": "Yes",
            "Include Pet?": "",
            "Requirements / Access Notes": "Chance of any unique scales with performance",
            "Notes": "Drop rate is shown as Normal; Challenge Mode",
        }
    )

    assert row.source_names == (
        "Chambers of Xeric",
    )
    assert row.source_ids == (
        "chambers_of_xeric",
    )
    assert row.group_names == (
        "Chambers of Xeric Uniques",
        "Raids Purple",
        "Ancestral Set",
    )
    assert row.group_ids == (
        "chambers_of_xeric_uniques",
        "raids_purple",
        "ancestral_set",
    )
    assert row.drop_name == "Ancestral hat"
    assert row.drop_id == "ancestral_hat"
    assert row.drop_rates == (
        "1/15",
        "1/14",
    )
    assert row.include_in_unique_group is True
    assert row.include_pet is False
    assert row.access_notes == "Chance of any unique scales with performance"


def test_normalise_drop_database_row_uses_supplied_ids():
    row = normalise_drop_database_row(
        {
            "Source Name(s)": "Dagannoth Rex",
            "Source ID(s)": "dk_rex",
            "Group Name(s)": "Dagannoth Rex uniques",
            "Group ID(s)": "rex_uniques",
            "Drop Name": "Berserker ring",
            "Drop ID": "b_ring",
            "Drop Rate(s)": "1/128",
            "Include In Unique Group?": "Yes",
            "Include Pet?": "No",
            "Requirements / Access Notes": "",
            "Notes": "",
        }
    )

    assert row.source_ids == (
        "dk_rex",
    )
    assert row.group_ids == (
        "rex_uniques",
    )
    assert row.drop_id == "b_ring"


def test_normalise_drop_database_rows_builds_group_memberships_only_from_yes_rows():
    database = normalise_drop_database_rows(
        (
            {
                "Source Name(s)": "Dagannoth Rex",
                "Group Name(s)": "Dagannoth Rex uniques",
                "Drop Name": "Berserker ring",
                "Drop Rate(s)": "1/128",
                "Include In Unique Group?": "Yes",
            },
            {
                "Source Name(s)": "Dagannoth Rex",
                "Group Name(s)": "Dagannoth Rex uniques",
                "Drop Name": "Ring of wealth",
                "Drop Rate(s)": "1/128",
                "Include In Unique Group?": "No",
            },
            {
                "Source Name(s)": "Dagannoth Rex",
                "Group Name(s)": "Dagannoth Rex uniques",
                "Drop Name": "Warrior ring",
                "Drop Rate(s)": "1/128",
                "Include In Unique Group?": "Yes",
            },
        )
    )

    group = database.groups_by_id[
        "dagannoth_rex_uniques"
    ]

    assert group.source_ids == (
        "dagannoth_rex",
    )
    assert group.drop_ids == (
        "berserker_ring",
        "warrior_ring",
    )
    assert group.drop_names == (
        "Berserker ring",
        "Warrior ring",
    )
    assert group.max_distinct_drop_count == 2


def test_normalise_drop_database_rows_supports_cross_source_groups():
    database = normalise_drop_database_rows(
        (
            {
                "Source Name(s)": "Chambers of Xeric",
                "Group Name(s)": "Raids Purple",
                "Drop Name": "Twisted bow",
                "Include In Unique Group?": "Yes",
            },
            {
                "Source Name(s)": "Theatre of Blood",
                "Group Name(s)": "Raids Purple",
                "Drop Name": "Scythe of vitur",
                "Include In Unique Group?": "Yes",
            },
        )
    )

    group = database.groups_by_id[
        "raids_purple"
    ]

    assert group.source_ids == (
        "chambers_of_xeric",
        "theatre_of_blood",
    )
    assert group.drop_ids == (
        "twisted_bow",
        "scythe_of_vitur",
    )


def test_normalise_drop_database_row_rejects_mismatched_group_ids():
    with pytest.raises(
        ValueError,
        match="Group ID count must match Group name count",
    ):
        normalise_drop_database_row(
            {
                "Source Name(s)": "Chambers of Xeric",
                "Group Name(s)": "Chambers of Xeric Uniques; Raids Purple",
                "Group ID(s)": "cox_uniques",
                "Drop Name": "Twisted bow",
                "Include In Unique Group?": "Yes",
            }
        )


def test_normalise_drop_database_row_imports_drop_metadata():
    from utils.osrs_drop_database_import import normalise_drop_database_row

    row = normalise_drop_database_row(
        {
            "Source Name(s)": "Giant Mole",
            "Group Name(s)": "Giant Mole Unique",
            "Drop Name": "Mole skin",
            "Drop Rate(s)": "Always",
            "Drop Counting Mode": "Item Quantity",
            "Drop Quantity": "1-3",
            "Include In Unique Group?": "Yes",
        }
    )

    assert row.drop_rates == (
        "Always",
    )
    assert row.drop_counting_mode == "item_quantity"
    assert row.drop_quantity == "1-3"


def test_normalise_drop_database_rows_carries_group_metadata():
    from utils.osrs_drop_database_import import normalise_drop_database_rows

    database = normalise_drop_database_rows(
        (
            {
                "Source Name(s)": "Giant Mole",
                "Group Name(s)": "Giant Mole Unique",
                "Drop Name": "Mole skin",
                "Drop Rate(s)": "Always",
                "Drop Counting Mode": "Item Quantity",
                "Drop Quantity": "1-3",
                "Requirements / Access Notes": "Falador hard diary useful.",
                "Notes": "Quantity drop, not N-of-set by default.",
                "Include In Unique Group?": "Yes",
            },
        )
    )

    group = database.groups_by_id[
        "giant_mole_unique"
    ]

    assert group.drop_rates == (
        "Always",
    )
    assert group.drop_counting_modes == (
        "item_quantity",
    )
    assert group.drop_quantities == (
        "1-3",
    )
    assert group.access_notes == (
        "Falador hard diary useful.",
    )
    assert group.notes == (
        "Quantity drop, not N-of-set by default.",
    )
