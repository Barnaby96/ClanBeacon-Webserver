import pytest

from utils.board_generation import (
    PetRole,
    TileCategory,
    TrackingSource,
)
from utils.osrs_tile_templates import (
    make_drop_candidate,
    make_killcount_candidate,
    make_pet_candidate,
    make_skill_xp_candidate,
    make_skill_xp_or_pet_candidate,
)


def test_make_zulrah_killcount_candidate_uses_content_access_profile():
    candidate = make_killcount_candidate(
        title="Complete 150 Zulrah KC",
        point_value=3,
        boss_id="Zulrah",
        target=150,
        content_id="zulrah",
    )

    assert candidate.primary_category == TileCategory.KILLCOUNT
    assert candidate.point_value == 3
    assert candidate.routes[0].display_text == "Complete 150 Zulrah KC"
    assert candidate.routes[0].tracking_source == TrackingSource.WOM

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "boss:zulrah",
            "source:zulrah",
            "metric:boss_zulrah_kc",
        }
    )

    assert candidate.access_profile.effective_skill_requirements == {
        "agility": 56,
        "ranged": 25,
        "crafting": 10,
    }


def test_make_drop_candidate_requires_drop_or_drop_group():
    with pytest.raises(
        ValueError,
        match="Drop candidates require either drop_id or drop_group_id"
    ):
        make_drop_candidate(
            title="Bad drop tile",
            point_value=1,
            source_id="zulrah",
        )


def test_make_zulrah_drop_group_candidate_uses_drop_group_and_content_profile():
    candidate = make_drop_candidate(
        title="Obtain any Zulrah unique",
        point_value=3,
        source_id="zulrah",
        boss_id="zulrah",
        drop_group_id="zulrah_uniques",
        content_id="zulrah",
        display_text="Obtain any Zulrah unique",
    )

    assert candidate.primary_category == TileCategory.DROP
    assert candidate.routes[0].display_text == "Obtain any Zulrah unique"

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "boss:zulrah",
            "source:zulrah",
            "metric:drop_group_zulrah_uniques",
            "drop_group:zulrah_uniques",
        }
    )

    assert candidate.access_profile.effective_skill_requirements == {
        "agility": 56,
        "ranged": 25,
        "crafting": 10,
    }


def test_make_skill_xp_or_pet_candidate_builds_secondary_pet_route():
    candidate = make_skill_xp_or_pet_candidate(
        title="Gain 1,000,000 Thieving XP OR obtain Rocky",
        point_value=3,
        skill_id="Thieving",
        xp_target=1_000_000,
        pet_id="Rocky",
    )

    assert candidate.primary_category == TileCategory.SKILL
    assert candidate.secondary_categories == frozenset(
        {
            TileCategory.PET
        }
    )
    assert candidate.pet_role == PetRole.SECONDARY
    assert candidate.has_fallback is True
    assert len(candidate.routes) == 2
    assert candidate.routes[0].metric_id == "thieving"

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "skill:thieving",
            "metric:thieving",
            "metric:pet_rocky",
            "source:thieving",
            "pet:rocky",
        }
    )


def test_make_skill_xp_or_pet_candidate_uses_runecrafting_wom_metric():
    candidate = make_skill_xp_or_pet_candidate(
        title=(
            "Gain 1,000,000 Runecraft XP "
            "OR obtain Rift guardian"
        ),
        point_value=4,
        skill_id="Runecraft",
        xp_target=1_000_000,
        pet_id="Rift guardian",
    )

    assert candidate.routes[0].skill_id == "runecraft"
    assert candidate.routes[0].metric_id == "runecrafting"


def test_make_killcount_candidate_without_content_has_empty_access_profile():
    candidate = make_killcount_candidate(
        title="Complete 50 Barrows KC",
        point_value=1,
        boss_id="barrows",
        target=50,
    )

    assert candidate.access_profile.effective_skill_requirements == {}
    assert candidate.access_profile.recommended_skill_requirements == {}
    assert candidate.access_profile.access_flags == frozenset()


def test_make_skill_xp_candidate_builds_wom_tracked_skill_tile():
    candidate = make_skill_xp_candidate(
        title="Gain 500,000 Cooking XP",
        point_value=1,
        skill_id="Cooking",
        xp_target=500_000,
    )

    assert candidate.primary_category == TileCategory.SKILL
    assert candidate.point_value == 1
    assert candidate.pet_role == PetRole.NONE
    assert candidate.routes[0].display_text == "Gain 500,000 Cooking XP"
    assert candidate.routes[0].tracking_source == TrackingSource.WOM
    assert candidate.routes[0].metric_id == "cooking"

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "skill:cooking",
            "metric:cooking",
            "source:cooking",
        }
    )


def test_make_pet_candidate_builds_primary_pet_group_tile():
    candidate = make_pet_candidate(
        title="Obtain any skilling pet",
        point_value=4,
        pet_group_id="skilling_pets",
        source_id="skilling_pets",
        display_text="Obtain any skilling pet",
        additional_hard_unique_tags=(
            "source:any_pet",
        ),
    )

    assert candidate.primary_category == TileCategory.PET
    assert candidate.pet_role == PetRole.PRIMARY
    assert candidate.routes[0].tracking_source == TrackingSource.DINK

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "metric:pet_group_skilling_pets",
            "source:skilling_pets",
            "pet_group:skilling_pets",
            "source:any_pet",
        }
    )


def test_make_pet_candidate_requires_pet_or_pet_group():
    with pytest.raises(
        ValueError,
        match="Pet candidates require either pet_id or pet_group_id"
    ):
        make_pet_candidate(
            title="Bad pet tile",
            point_value=5,
        )
