from utils.osrs_drop_group_data import DROP_GROUP_DATA


def get_group(group_id):
    return next(
        group
        for group in DROP_GROUP_DATA
        if group["drop_group_id"] == group_id
    )


def test_generated_drop_group_data_has_valid_shape():
    assert DROP_GROUP_DATA

    group_ids = tuple(
        group["drop_group_id"]
        for group in DROP_GROUP_DATA
    )

    assert len(
        set(
            group_ids
        )
    ) == len(
        group_ids
    )

    assert group_ids == tuple(
        sorted(
            group_ids
        )
    )

    for group in DROP_GROUP_DATA:
        assert group["drop_group_id"]
        assert group["display_name"]
        assert group["source_ids"]
        assert group["source_names"]
        assert group["drop_ids"]
        assert group["drop_names"]
        assert len(
            group["drop_ids"]
        ) == len(
            group["drop_names"]
        )
        assert len(
            set(
                group["drop_ids"]
            )
        ) == len(
            group["drop_ids"]
        )


def test_generated_drop_group_data_contains_expected_key_groups():
    group_ids = {
        group["drop_group_id"]
        for group in DROP_GROUP_DATA
    }

    assert "fashionscape_item" in group_ids
    assert "raids_purple" in group_ids
    assert "master_clue_scroll_unique" in group_ids
    assert "dagannoth_rex_uniques" in group_ids


def test_generated_drop_group_data_contains_dagannoth_rex_uniques():
    group = get_group(
        "dagannoth_rex_uniques"
    )

    assert group["display_name"].lower() == "dagannoth rex uniques"
    assert group["source_ids"] == (
        "dagannoth_rex",
    )
    assert {
        "berserker_ring",
        "warrior_ring",
    }.issubset(
        set(
            group["drop_ids"]
        )
    )
    assert group["include_pet"] is False
