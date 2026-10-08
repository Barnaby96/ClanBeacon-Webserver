from routes.admin.tile_routes import _format_admin_tile_condition


def test_admin_tile_condition_formats_experience_trigger_for_display():
    condition = (
        None,
        None,
        None,
        "EXPERIENCE",
        "thieving",
        1_000_000,
    )

    assert _format_admin_tile_condition(condition) == (
        "1,000,000 x Experience: Thieving"
    )


def test_admin_tile_condition_displays_runecrafting_as_runecraft():
    condition = (
        None,
        None,
        None,
        "EXPERIENCE",
        "runecrafting",
        500_000,
    )

    assert _format_admin_tile_condition(condition) == (
        "500,000 x Experience: Runecraft"
    )


def test_admin_tile_condition_formats_killcount_trigger_for_display():
    condition = (
        None,
        None,
        None,
        "KILLCOUNT",
        "giant_mole",
        150,
    )

    assert _format_admin_tile_condition(condition) == (
        "150 x Killcount: Giant Mole"
    )


def test_admin_tile_condition_preserves_drop_name_case():
    condition = (
        None,
        None,
        None,
        "DROP",
        "Bandos chestplate",
        1,
    )

    assert _format_admin_tile_condition(condition) == (
        "1 x Drop: Bandos chestplate"
    )
