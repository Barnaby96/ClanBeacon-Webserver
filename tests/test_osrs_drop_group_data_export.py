from utils.osrs_drop_database_import import normalise_drop_database_rows
from utils.osrs_drop_group_data_export import (
    build_drop_group_data_records,
    format_drop_group_data_module,
    write_drop_group_data_module,
)


def build_sample_database():
    return normalise_drop_database_rows(
        (
            {
                "Source Name(s)": "Chambers of Xeric",
                "Group Name(s)": "Raids Purple; FashionScape Item",
                "Drop Name": "Ancestral hat",
                "Include In Unique Group?": "Yes",
            },
            {
                "Source Name(s)": "Theatre of Blood",
                "Group Name(s)": "Raids Purple",
                "Drop Name": "Scythe of vitur",
                "Include In Unique Group?": "Yes",
            },
            {
                "Source Name(s)": "Dagannoth Rex",
                "Group Name(s)": "Dagannoth Rex uniques",
                "Drop Name": "Ring of wealth",
                "Include In Unique Group?": "No",
            },
        )
    )


def test_build_drop_group_data_records_exports_in_id_order():
    database = build_sample_database()

    records = build_drop_group_data_records(
        database
    )

    assert tuple(
        record["drop_group_id"]
        for record in records
    ) == (
        "fashionscape_item",
        "raids_purple",
    )

    raids_record = records[1]

    assert raids_record == {
        "drop_group_id": "raids_purple",
        "display_name": "Raids Purple",
        "source_ids": (
            "chambers_of_xeric",
            "theatre_of_blood",
        ),
        "source_names": (
            "Chambers of Xeric",
            "Theatre of Blood",
        ),
        "drop_ids": (
            "ancestral_hat",
            "scythe_of_vitur",
        ),
        "drop_names": (
            "Ancestral hat",
            "Scythe of vitur",
        ),
        "drop_rates": (
            "",
            "",
        ),
        "drop_counting_modes": (
            "distinct_drops",
            "distinct_drops",
        ),
        "drop_quantities": (
            "",
            "",
        ),
        "access_notes": (),
        "notes": (),
        "include_pet": False,
    }


def test_format_drop_group_data_module_outputs_importable_python():
    database = build_sample_database()

    module_text = format_drop_group_data_module(
        database
    )

    namespace = {}

    exec(
        module_text,
        namespace,
    )

    records = namespace[
        "DROP_GROUP_DATA"
    ]

    assert records[0]["drop_group_id"] == "fashionscape_item"
    assert records[0]["drop_ids"] == (
        "ancestral_hat",
    )
    assert records[1]["drop_group_id"] == "raids_purple"


def test_write_drop_group_data_module(tmp_path):
    database = build_sample_database()
    output_path = tmp_path / "osrs_drop_group_data.py"

    write_drop_group_data_module(
        database,
        output_path,
    )

    module_text = output_path.read_text(
        encoding="utf-8"
    )

    assert "Generated OSRS drop group data" in module_text
    assert "DROP_GROUP_DATA" in module_text
    assert "fashionscape_item" in module_text
    assert "raids_purple" in module_text


def test_build_drop_group_data_records_exports_drop_metadata():
    from utils.osrs_drop_database_import import normalise_drop_database_rows
    from utils.osrs_drop_group_data_export import build_drop_group_data_records

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

    records = build_drop_group_data_records(
        database
    )

    assert records[0]["drop_rates"] == (
        "Always",
    )
    assert records[0]["drop_counting_modes"] == (
        "item_quantity",
    )
    assert records[0]["drop_quantities"] == (
        "1-3",
    )
    assert records[0]["access_notes"] == (
        "Falador hard diary useful.",
    )
    assert records[0]["notes"] == (
        "Quantity drop, not N-of-set by default.",
    )
