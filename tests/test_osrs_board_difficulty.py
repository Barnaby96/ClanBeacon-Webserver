import pytest
from utils.board_generation import TileCategory
from utils.osrs_board_difficulty import build_board_generation_rules_for_difficulty

@pytest.mark.parametrize("mode, primary, secondary", [
    ("relaxed", 0, (0, 1, 2)),
    ("standard", 0, (1, 2, 3)),
    ("competitive", 1, (2, 4, 6)),
    ("brutal", 3, (3, 5, 7)),
])
def test_difficulty_mode_pet_rules(mode, primary, secondary):
    rules = build_board_generation_rules_for_difficulty(mode)
    assert rules.board_size == 25
    assert rules.points_distribution == {tier: 5 for tier in range(1, 6)}
    assert (rules.primary_pet_tiles_min, rules.primary_pet_tiles_target, rules.primary_pet_tiles_max) == (primary,) * 3
    assert (rules.secondary_pet_routes_min, rules.secondary_pet_routes_target, rules.secondary_pet_routes_max) == secondary
    assert sum(slot.required_category == TileCategory.PET for slot in rules.build_slots()) == primary

def test_default_difficulty_is_competitive():
    assert build_board_generation_rules_for_difficulty() == build_board_generation_rules_for_difficulty("competitive")

def test_unknown_difficulty_is_rejected():
    with pytest.raises(ValueError):
        build_board_generation_rules_for_difficulty("impossible")

def test_primary_pet_subtypes():
    from utils.osrs_board_difficulty import classify_primary_pet_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    candidates = {tile.title: tile for tile in get_curated_tile_generation_candidates()}
    assert classify_primary_pet_candidate(candidates["Obtain Beaver"]) == "skilling"
    assert classify_primary_pet_candidate(candidates["Obtain Baby chinchompa"]) == "skilling"
    assert classify_primary_pet_candidate(candidates["Obtain Abyssal orphan"]) == "boss"
    assert classify_primary_pet_candidate(candidates["Obtain Abyssal protector"]) == "other"

@pytest.mark.parametrize("mode", ["relaxed", "standard", "competitive", "brutal"])
def test_approved_category_distribution(mode):
    rules = build_board_generation_rules_for_difficulty(mode)
    assert rules.minimum_primary_categories_per_tier == 2
    assert rules.target_primary_categories_per_tier == 3
    assert rules.maximum_primary_category_tiles_per_tier == 3
    assert rules.minimum_primary_category_counts == {
        TileCategory.SKILL: 4,
        TileCategory.KILLCOUNT: 4,
        TileCategory.DROP: 4,
    }
    for tier in range(1, 6):
        required = rules.required_categories_by_point.get(tier, ())
        assert not set(required) & {TileCategory.SKILL, TileCategory.KILLCOUNT, TileCategory.DROP}
        assert len(required) + rules.flex_slots_by_point[tier] == 5

def test_assembler_enforces_per_tier_category_variety():
    from dataclasses import replace
    from collections import Counter
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={})
    pool = get_curated_tile_generation_candidates()
    skills = [t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.SKILL][:5]
    alternatives = [t for t in pool if t.point_value == 1 and t.primary_category in (TileCategory.KILLCOUNT, TileCategory.DROP)][:20]
    assert len(skills) == 5 and len(alternatives) >= 2
    board = assemble_board_candidates((*skills, *alternatives), rules=rules)
    counts = Counter(t.primary_category for t in board.candidates)
    assert len(board.candidates) == 5
    assert len(counts) >= 2
    assert max(counts.values()) <= 3

def test_per_tier_variety_rejects_five_kept_skills():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates, BoardAssemblyError
    from utils.osrs_tile_templates import make_skill_xp_candidate
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("agility", "cooking", "fishing", "mining", "woodcutting"))
    with pytest.raises(BoardAssemblyError):
        assemble_board_candidates(skills, rules=rules, preselected_candidates=skills)

def test_per_tier_variety_rejects_five_generated_skills():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates, BoardAssemblyError
    from utils.osrs_tile_templates import make_skill_xp_candidate
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("agility", "cooking", "fishing", "mining", "woodcutting"))
    with pytest.raises(BoardAssemblyError):
        assemble_board_candidates(skills, rules=rules)

def test_per_tier_category_limit_selects_alternatives():
    from collections import Counter
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("agility", "cooking", "fishing", "mining", "woodcutting"))
    pool = get_curated_tile_generation_candidates()
    killcount = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT)
    drop = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.DROP)
    board = assemble_board_candidates((*skills, killcount, drop), rules=rules)
    counts = Counter(t.primary_category for t in board.candidates)
    assert counts == {TileCategory.SKILL: 3, TileCategory.KILLCOUNT: 1, TileCategory.DROP: 1}
    assert killcount in board.candidates and drop in board.candidates

def test_assembler_enforces_whole_board_category_minimums():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates, BoardAssemblyError
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    pool = get_curated_tile_generation_candidates()
    skill = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.SKILL)
    others = tuple(t for t in pool if t.point_value == 1 and t.primary_category in (TileCategory.KILLCOUNT, TileCategory.DROP))
    candidates = (skill, *others)
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={})
    assert len(assemble_board_candidates(candidates, rules=rules).candidates) == 5
    rules = replace(rules, minimum_primary_category_counts={TileCategory.SKILL: 2})
    with pytest.raises(BoardAssemblyError, match="category"):
        assemble_board_candidates(candidates, rules=rules)

def test_validator_enforces_per_tier_category_limits():
    from dataclasses import replace
    from utils.board_generation import validate_generated_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("agility", "cooking", "fishing", "mining", "woodcutting"))
    killcount = next(t for t in get_curated_tile_generation_candidates() if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT)
    for candidates in ((*skills[:4], killcount), skills):
        errors = validate_generated_board_candidates(candidates, rules=rules)
        assert any("category" in error.lower() for error in errors)

def test_assembler_reserves_whole_board_category_minimums():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={TileCategory.SKILL: 2})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("cooking", "agility"))
    pool = get_curated_tile_generation_candidates()
    others = tuple(t for t in pool if t.point_value == 1 and t.primary_category in (TileCategory.KILLCOUNT, TileCategory.DROP))
    assert len(others) >= 5
    candidates = (*others, *skills)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=skills)
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 5
    assert sum(t.primary_category == TileCategory.SKILL for t in board.candidates) >= 2

def test_assembler_reserves_all_category_minimums_together():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={TileCategory.SKILL: 2, TileCategory.KILLCOUNT: 2, TileCategory.DROP: 1})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("cooking", "agility", "fishing"))
    pool = get_curated_tile_generation_candidates()
    kills = tuple(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT)[:2]
    drops = tuple(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.DROP)[:3]
    assert len(kills) == 2 and len(drops) == 3
    candidates = (*skills, *kills, *drops)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=(*skills[:2], *kills))
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 5
    for category, minimum in rules.minimum_primary_category_counts.items():
        assert sum(t.primary_category == category for t in board.candidates) >= minimum

def test_assembler_reserves_category_in_eligible_point_tier():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 3, 2: 2}, required_categories_by_point={1: (TileCategory.DROP,)}, flex_slots_by_point={1: 2, 2: 2}, minimum_primary_category_counts={TileCategory.SKILL: 2, TileCategory.KILLCOUNT: 1, TileCategory.DROP: 1})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("cooking", "agility"))
    pool = get_curated_tile_generation_candidates()
    kill_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT)
    drop_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.DROP)
    kill_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.KILLCOUNT)
    drop_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.DROP)
    candidates = (kill_1, *skills, drop_1, kill_2, drop_2)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=skills)
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules, preselected_candidates=skills[:1])
    assert len(board.candidates) == 5
    assert sum(t.primary_category == TileCategory.SKILL for t in board.candidates) == 2

def test_assembler_reserves_competing_category_slots():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 3, 2: 2}, required_categories_by_point={1: (TileCategory.SKILL,)}, flex_slots_by_point={1: 2, 2: 2}, minimum_primary_category_counts={TileCategory.SKILL: 1, TileCategory.KILLCOUNT: 1, TileCategory.DROP: 1})
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("cooking", "agility"))
    skill_2 = make_skill_xp_candidate(title="Gain 2,000 Woodcutting XP", point_value=2, skill_id="woodcutting", xp_target=2000)
    pool = get_curated_tile_generation_candidates()
    kill_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT)
    drop_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.DROP)
    hybrid_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.HYBRID)
    candidates = (skills[0], skills[1], kill_1, drop_1, skill_2, hybrid_2)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=(skills[0], kill_1, drop_1))
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 5
    for category, minimum in rules.minimum_primary_category_counts.items():
        assert sum(t.primary_category == category for t in board.candidates) >= minimum

def test_assembler_reserves_distinct_future_candidates():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 3, 2: 2}, required_categories_by_point={1: (TileCategory.DROP,)}, flex_slots_by_point={1: 2, 2: 2}, minimum_primary_category_counts={TileCategory.SKILL: 2, TileCategory.KILLCOUNT: 1, TileCategory.DROP: 1})
    skill_1 = make_skill_xp_candidate(title="Gain 1,000 Cooking XP", point_value=1, skill_id="cooking", xp_target=1000)
    skill_2 = make_skill_xp_candidate(title="Gain 2,000 Woodcutting XP", point_value=2, skill_id="woodcutting", xp_target=2000)
    pool = get_curated_tile_generation_candidates()
    drop_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.DROP)
    kill_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT and not (t.all_hard_unique_tags & drop_1.all_hard_unique_tags))
    kill_extra = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT and t != kill_1 and not (t.all_hard_unique_tags & (drop_1.all_hard_unique_tags | kill_1.all_hard_unique_tags)))
    hybrid_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.HYBRID)
    candidates = (drop_1, kill_1, kill_extra, skill_1, skill_2, hybrid_2)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=(drop_1, kill_1, skill_1))
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 5
    assert sum(t.primary_category == TileCategory.SKILL for t in board.candidates) == 2

def test_assembler_reserves_nonconflicting_future_candidates():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 3, 2: 2}, required_categories_by_point={1: (TileCategory.DROP,)}, flex_slots_by_point={1: 2, 2: 2}, minimum_primary_category_counts={TileCategory.SKILL: 2, TileCategory.KILLCOUNT: 1, TileCategory.DROP: 1})
    skill_1 = make_skill_xp_candidate(title="Gain 1,000 Cooking XP", point_value=1, skill_id="cooking", xp_target=1000)
    skill_2a = make_skill_xp_candidate(title="Gain 2,000 Woodcutting XP", point_value=2, skill_id="woodcutting", xp_target=2000)
    skill_2b = make_skill_xp_candidate(title="Gain 2,000 Mining XP", point_value=2, skill_id="mining", xp_target=2000)
    shared = frozenset({"test:future_skill_conflict"})
    skill_2a = replace(skill_2a, hard_unique_tags=skill_2a.hard_unique_tags | shared)
    skill_2b = replace(skill_2b, hard_unique_tags=skill_2b.hard_unique_tags | shared)
    assert skill_2a.all_hard_unique_tags & skill_2b.all_hard_unique_tags
    pool = get_curated_tile_generation_candidates()
    drop_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.DROP)
    kill_1 = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT and not (t.all_hard_unique_tags & drop_1.all_hard_unique_tags))
    kill_extra = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT and t != kill_1 and not (t.all_hard_unique_tags & (drop_1.all_hard_unique_tags | kill_1.all_hard_unique_tags)))
    hybrid_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.HYBRID)
    candidates = (drop_1, kill_1, kill_extra, skill_1, skill_2a, skill_2b, hybrid_2)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=(drop_1, kill_1, skill_1))
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 5
    assert sum(t.primary_category == TileCategory.SKILL for t in board.candidates) == 2

def test_assembler_reserves_nonconflicting_cross_category_candidates():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("relaxed")
    rules = replace(base, board_size=5, points_distribution={1: 3, 2: 2}, required_categories_by_point={1: (TileCategory.DROP,)}, flex_slots_by_point={1: 2, 2: 2}, minimum_primary_category_counts={TileCategory.SKILL: 1, TileCategory.KILLCOUNT: 1, TileCategory.DROP: 1})
    skill_1 = make_skill_xp_candidate(title="Gain 1,000 Cooking XP", point_value=1, skill_id="cooking", xp_target=1000)
    skill_2 = make_skill_xp_candidate(title="Gain 2,000 Woodcutting XP", point_value=2, skill_id="woodcutting", xp_target=2000)
    pool = get_curated_tile_generation_candidates()
    kill_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.KILLCOUNT)
    hybrid_2 = next(t for t in pool if t.point_value == 2 and t.primary_category == TileCategory.HYBRID and not (t.all_hard_unique_tags & kill_2.all_hard_unique_tags))
    shared = frozenset({"test:cross_category_future_conflict"})
    skill_2 = replace(skill_2, hard_unique_tags=skill_2.hard_unique_tags | shared)
    kill_2 = replace(kill_2, hard_unique_tags=kill_2.hard_unique_tags | shared)
    drops = []
    used = skill_1.all_hard_unique_tags | skill_2.all_hard_unique_tags | kill_2.all_hard_unique_tags | hybrid_2.all_hard_unique_tags
    for t in pool:
        if t.point_value == 1 and t.primary_category == TileCategory.DROP and not (t.all_hard_unique_tags & used):
            drops.append(t)
            used = used | t.all_hard_unique_tags
            if len(drops) == 3:
                break
    assert len(drops) == 3
    assert skill_2.all_hard_unique_tags & kill_2.all_hard_unique_tags
    candidates = (*drops, skill_1, skill_2, kill_2, hybrid_2)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=(drops[0], skill_1, kill_2))
    assert len(control.candidates) == 5
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 5
    for category, minimum in rules.minimum_primary_category_counts.items():
        assert sum(t.primary_category == category for t in board.candidates) >= minimum

def test_assembler_reserves_categories_across_tier_caps():
    import random
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    from utils.osrs_board_difficulty import build_board_generation_rules_for_difficulty
    candidates = list(get_curated_tile_generation_candidates())
    random.Random(8).shuffle(candidates)
    rules = build_board_generation_rules_for_difficulty("relaxed")
    board = assemble_board_candidates(candidates, rules=rules)
    assert len(board.candidates) == 25
    for category, minimum in rules.minimum_primary_category_counts.items():
        assert sum(t.primary_category == category for t in board.candidates) >= minimum

def test_assembler_reserves_pet_routes_and_category_minimums_together():
    import random
    from utils.board_generation import assemble_board_candidates, count_secondary_pet_routes
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    from utils.osrs_board_difficulty import build_board_generation_rules_for_difficulty
    candidates = get_curated_tile_generation_candidates()
    rules = build_board_generation_rules_for_difficulty("standard")
    control_pool = list(candidates)
    random.Random(0).shuffle(control_pool)
    control = assemble_board_candidates(control_pool, rules=rules)
    assert len(control.candidates) == 25
    failing_pool = list(candidates)
    random.Random(8).shuffle(failing_pool)
    board = assemble_board_candidates(failing_pool, rules=rules)
    assert len(board.candidates) == 25
    assert count_secondary_pet_routes(board.candidates) >= rules.secondary_pet_routes_min
    for category, minimum in rules.minimum_primary_category_counts.items():
        assert sum(t.primary_category == category for t in board.candidates) >= minimum

def test_standard_prefers_secondary_pet_route_target_when_feasible():
    import random
    from utils.board_generation import assemble_board_candidates, count_secondary_pet_routes, secondary_pet_route_count
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    from utils.osrs_board_difficulty import build_board_generation_rules_for_difficulty
    candidates = list(get_curated_tile_generation_candidates())
    rules = build_board_generation_rules_for_difficulty("standard")
    pet_tiles = [t for t in candidates if secondary_pet_route_count(t) > 0]
    assert len(pet_tiles) >= rules.secondary_pet_routes_target
    random.Random(0).shuffle(candidates)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=tuple(pet_tiles[:2]))
    assert count_secondary_pet_routes(control.candidates) >= rules.secondary_pet_routes_target
    board = assemble_board_candidates(candidates, rules=rules)
    assert count_secondary_pet_routes(board.candidates) >= rules.secondary_pet_routes_target

def test_standard_prefers_three_primary_categories_when_feasible():
    from dataclasses import replace
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_templates import make_skill_xp_candidate
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    base = build_board_generation_rules_for_difficulty("standard")
    rules = replace(base, board_size=5, points_distribution={1: 5}, required_categories_by_point={1: ()}, flex_slots_by_point={1: 5}, minimum_primary_category_counts={}, secondary_pet_routes_min=0, secondary_pet_routes_target=0, secondary_pet_routes_max=0)
    assert rules.target_primary_categories_per_tier == 3
    skills = tuple(make_skill_xp_candidate(title=f"Gain 1,000 {skill.title()} XP", point_value=1, skill_id=skill, xp_target=1000) for skill in ("cooking", "agility", "fishing"))
    pool = get_curated_tile_generation_candidates()
    kill = next(t for t in pool if t.point_value == 1 and t.primary_category == TileCategory.KILLCOUNT)
    used = frozenset().union(*(t.all_hard_unique_tags for t in (*skills, kill)))
    drops = []
    for tile in pool:
        if tile.point_value == 1 and tile.primary_category == TileCategory.DROP and not (tile.all_hard_unique_tags & used):
            drops.append(tile)
            used = used | tile.all_hard_unique_tags
            if len(drops) == 2:
                break
    assert len(drops) == 2
    candidates = (*skills, *drops, kill)
    control = assemble_board_candidates(candidates, rules=rules, preselected_candidates=(skills[0], drops[0], kill))
    assert len({t.primary_category for t in control.candidates}) >= 3
    board = assemble_board_candidates(candidates, rules=rules)
    assert len({t.primary_category for t in board.candidates}) >= rules.target_primary_categories_per_tier

@pytest.mark.parametrize("seed", [29, 72])
def test_standard_pet_target_for_known_feasible_seeds(seed):
    import random
    from utils.board_generation import assemble_board_candidates, count_secondary_pet_routes, secondary_pet_route_count
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates
    from utils.osrs_board_difficulty import build_board_generation_rules_for_difficulty
    pool = list(get_curated_tile_generation_candidates())
    rules = build_board_generation_rules_for_difficulty("standard")
    pet_tiles = [t for t in pool if secondary_pet_route_count(t) > 0]
    random.Random(seed).shuffle(pool)
    control = assemble_board_candidates(pool, rules=rules, preselected_candidates=tuple(pet_tiles[:2]))
    assert count_secondary_pet_routes(control.candidates) >= rules.secondary_pet_routes_target
    board = assemble_board_candidates(pool, rules=rules)
    assert count_secondary_pet_routes(board.candidates) >= rules.secondary_pet_routes_target
