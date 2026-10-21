import pytest
from decimal import Decimal

def test_skill_rate_selection_respects_skill_level_and_unknown():
    from utils.osrs_procedural_skill_rates import resolve_skill_xp_rate
    rates = {"fishing": {1: 10000, 70: 40000}, "cooking": {1: 80000}}
    assert resolve_skill_xp_rate("fishing", 50, rates) == Decimal("10000")
    assert resolve_skill_xp_rate("fishing", 80, rates) == Decimal("40000")
    assert resolve_skill_xp_rate("cooking", 80, rates) == Decimal("80000")
    assert resolve_skill_xp_rate("fishing", None, rates) is None
    assert resolve_skill_xp_rate("mining", 80, rates) is None

def test_locked_method_access_remains_unknown():
    from utils.board_generation import AccessProfile, AccessFlag
    from utils.osrs_procedural_skill_rates import assess_training_method_access
    profile = AccessProfile(effective_skill_requirements={"agility": 70}, access_flags={AccessFlag.QUEST_LOCKED})
    assert assess_training_method_access(profile, {"agility": 80}) == "unknown"

@pytest.mark.parametrize("level,locked,confirmed,expected", [(80,False,False,"accessible"),(60,False,False,"inaccessible"),(None,False,False,"unknown"),(80,True,True,"accessible"),(60,True,False,"inaccessible")])
def test_training_method_access_states(level, locked, confirmed, expected):
    from utils.board_generation import AccessFlag, AccessProfile
    from utils.osrs_procedural_skill_rates import assess_training_method_access
    flags = {AccessFlag.QUEST_LOCKED} if locked else set()
    profile = AccessProfile(effective_skill_requirements={"agility": 70}, access_flags=flags)
    actual = assess_training_method_access(profile, {"agility": level}, flags if confirmed else ())
    assert actual == expected

def test_unlock_evidence_is_method_specific():
    from utils.board_generation import AccessProfile, AccessFlag
    from utils.osrs_procedural_skill_rates import assess_training_method_access
    profile = AccessProfile(effective_skill_requirements={"agility": 70}, access_flags={AccessFlag.QUEST_LOCKED})
    confirmed = {"course_a"}
    assert assess_training_method_access(profile, {"agility": 80}, method_id="course_a", confirmed_method_ids=confirmed) == "accessible"
    assert assess_training_method_access(profile, {"agility": 80}, method_id="course_b", confirmed_method_ids=confirmed) == "unknown"

def test_rate_selection_tracks_unknown_methods():
    from utils.board_generation import AccessFlag, AccessProfile
    from utils.osrs_procedural_skill_rates import select_training_method_rate
    basic = ("basic", 25000, AccessProfile(effective_skill_requirements={"agility": 40}))
    locked = ("quest_course", 70000, AccessProfile(effective_skill_requirements={"agility": 70}, access_flags={AccessFlag.QUEST_LOCKED}))
    selected, unknown = select_training_method_rate((basic, locked), {"agility": 80})
    assert selected == ("basic", Decimal("25000"))
    assert unknown == ("quest_course",)

def test_fly_fishing_reference_rates_and_access():
    from utils.osrs_procedural_training_methods import FLY_FISHING_METHOD
    from utils.osrs_procedural_skill_rates import resolve_skill_xp_rate
    rates = {"fishing": FLY_FISHING_METHOD["xp_per_hour_by_level"]}
    assert FLY_FISHING_METHOD["access_profile"].effective_skill_requirements == {"fishing": 20}
    assert resolve_skill_xp_rate("fishing", 19, rates) is None
    assert resolve_skill_xp_rate("fishing", 20, rates) == Decimal("13000")
    assert resolve_skill_xp_rate("fishing", 80, rates) == Decimal("44000")
    assert FLY_FISHING_METHOD["source_url"].startswith("https://oldschool.runescape.wiki/")

def test_catalogue_method_selection_uses_character_level():
    from utils.osrs_procedural_training_methods import FLY_FISHING_METHOD
    from utils.osrs_procedural_skill_rates import select_training_method_rate_from_catalogue
    methods = (FLY_FISHING_METHOD,)
    selected, unknown = select_training_method_rate_from_catalogue(methods, {"fishing": 80})
    assert selected == ("fly_fishing_standard", Decimal("44000"))
    assert unknown == ()
    selected, unknown = select_training_method_rate_from_catalogue(methods, {"fishing": 19})
    assert selected is None
    assert unknown == ()
