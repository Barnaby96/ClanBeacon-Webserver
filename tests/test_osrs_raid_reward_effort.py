import pytest

def test_raid_reward_expected_completions_distinguishes_specific_items():
    from utils.osrs_drop_tile_effort import estimate_raid_reward_expected_completions
    assert estimate_raid_reward_expected_completions(0.20, 3) == pytest.approx(15.0)
    assert estimate_raid_reward_expected_completions(0.20, 3, conditional_reward_probability=0.10) == pytest.approx(150.0)
    with pytest.raises(ValueError):
        estimate_raid_reward_expected_completions(0, 3)

def test_raid_reward_completion_probability():
    from utils.osrs_drop_tile_effort import estimate_raid_reward_completion_probability
    calculate = estimate_raid_reward_completion_probability
    assert calculate(0.20, 1, 5) == pytest.approx(0.67232)
    assert calculate(0.20, 3, 10) == pytest.approx(0.3222004736)
    assert calculate(0.20, 1, 5, conditional_reward_probability=0.10) == pytest.approx(1 - 0.98**5)
    assert calculate(0.20, 3, 2) == 0
    assert calculate(1.0, 3, 3) == 1
    with pytest.raises(ValueError):
        calculate(0.20, 1, -1)

def test_raid_reward_probability_from_playtime():
    from utils.osrs_drop_tile_effort import estimate_raid_reward_probability_from_playtime
    calculate = estimate_raid_reward_probability_from_playtime
    assert calculate(0.20, 3, 2.5, 3) == pytest.approx(0.148032)
    assert calculate(0.20, 1, 2.5, 3, conditional_reward_probability=0.10) == pytest.approx(1 - 0.98**7)
    assert calculate(0.20, 1, 2.5, 0) == 0
    with pytest.raises(ValueError):
        calculate(0.20, 1, -2.5, 3)

def test_raid_reward_probability_checks_shared_character_budgets():
    from utils.osrs_drop_tile_effort import estimate_raid_reward_probability_with_character_budgets
    calculate = estimate_raid_reward_probability_with_character_budgets
    budgets = {"a": 2, "b": 2, "c": 2, "d": 2}
    previous = {"other_tile": {"a": 1}}
    participants = ("a", "b", "c", "d")
    result = calculate(0.20, 1, 3, 1, budgets, previous, participants)
    assert result == pytest.approx(1 - 0.8**3)
    with pytest.raises(ValueError, match="budget"):
        calculate(0.20, 1, 3, 1.25, budgets, previous, participants)
    assert previous == {"other_tile": {"a": 1}}

def test_raid_performance_profile_probability():
    from utils.osrs_raid_performance import RaidPerformanceProfile, estimate_raid_reward_probability_for_profile
    profile = RaidPerformanceProfile(source_id="tombs_of_amascut", scenario="Illustrative four-player raid", raids_per_hour=2, purple_probability=0.20)
    assert profile.source_id == "tombs_of_amascut"
    assert estimate_raid_reward_probability_for_profile(profile, target=1, allocated_hours=2) == pytest.approx(0.5904)
    with pytest.raises(ValueError):
        RaidPerformanceProfile(source_id="tombs_of_amascut", scenario="Invalid rate", raids_per_hour=0, purple_probability=0.20)
    with pytest.raises(ValueError):
        RaidPerformanceProfile(source_id="tombs_of_amascut", scenario="Unknown chance", raids_per_hour=2, purple_probability=None)

def test_compare_raid_reward_profiles():
    from utils.osrs_raid_performance import RaidPerformanceProfile, compare_raid_reward_profiles
    profiles = (
        RaidPerformanceProfile("chambers_of_xeric", "Illustrative CoX", 3, 0.08),
        RaidPerformanceProfile("tombs_of_amascut", "Illustrative ToA", 2, 0.20),
    )
    results = compare_raid_reward_profiles(profiles, target=1, allocated_hours=2)
    assert [source for source, probability in results] == ["tombs_of_amascut", "chambers_of_xeric"]
    assert dict(results)["tombs_of_amascut"] == pytest.approx(1 - 0.8**4)
    assert dict(results)["chambers_of_xeric"] == pytest.approx(1 - 0.92**6)
    single = compare_raid_reward_profiles(profiles[:1], target=1, allocated_hours=2)
    assert len(single) == 1 and single[0][0] == "chambers_of_xeric"
