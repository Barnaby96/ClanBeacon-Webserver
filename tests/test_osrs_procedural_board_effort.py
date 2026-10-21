import pytest
from utils.osrs_procedural_effort_budget import remaining_board_character_hours

def test_character_hours_are_shared_across_tiles():
    budget = {"main": 16}
    assert remaining_board_character_hours(budget, {"tile_a": {"main": 10}, "tile_b": {"main": 6}}) == {"main": 0}
    with pytest.raises(ValueError, match="exceeds"):
        remaining_board_character_hours(budget, {"tile_a": {"main": 10}, "tile_b": {"main": 7}})

def test_board_planning_maximises_points_with_shared_hours():
    from utils.osrs_procedural_board_planning import maximise_board_points_from_plans
    plans = ({"tile_id": "easy", "points": 1, "options": ({"main": 6},)}, {"tile_id": "hard", "points": 5, "options": ({"main": 8},)})
    assert maximise_board_points_from_plans({"main": 8}, plans) == 5
