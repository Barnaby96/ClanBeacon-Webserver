from utils.osrs_pets import get_osrs_pet_options


def test_pet_options_include_drop_obtained_examples():
    options = get_osrs_pet_options()

    assert {
        "label": "Thieving - Rocky",
        "value": "Rocky",
    } in options
    assert {
        "label": "Mad Angel - Aggy",
        "value": "Aggy",
    } in options
    assert {
        "label": "Guardians of the Rift - Abyssal protector",
        "value": "Abyssal protector",
    } in options


def test_pet_options_exclude_generic_follower_pets():
    values = {
        option["value"]
        for option in get_osrs_pet_options()
    }

    assert "Broav" not in values
    assert "Cat" not in values
    assert "Hellcat" not in values
    assert "Pet fish" not in values
    assert "Pet rock" not in values
    assert "Toy cat" not in values


def test_pet_options_have_unique_submitted_values():
    options = get_osrs_pet_options()
    values = [
        option["value"]
        for option in options
    ]

    assert len(values) == 71
    assert len(values) == len(set(values))
