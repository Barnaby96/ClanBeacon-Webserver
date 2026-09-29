import pytest

from utils.board_generation import (
    PetRole,
    TileCategory,
    TrackingSource,
)
from utils.osrs_tile_templates import (
    make_drop_candidate,
    make_killcount_candidate,
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

    assert candidate.all_hard_unique_tags == frozenset(
        {
            "skill:thieving",
            "metric:skill_thieving_xp",
            "metric:pet_rocky",
            "source:thieving",
            "pet:rocky",
        }
    )


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
