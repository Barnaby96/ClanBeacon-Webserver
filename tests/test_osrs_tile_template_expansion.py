import pytest

from utils.board_generation import TileCategory, TrackingSource
from utils.osrs_tile_template_expansion import (
    DropTileTemplate,
    KillcountTileTemplate,
    STATIC_DROP_TEMPLATES,
    STATIC_KILLCOUNT_TEMPLATES,
    STATIC_METRIC_TEMPLATES,
    STATIC_SKILL_XP_TEMPLATES,
    MetricTileTemplate,
    SkillXpTileTemplate,
    expand_drop_template,
    expand_killcount_template,
    expand_metric_template,
    expand_skill_xp_template,
    get_static_drop_candidates,
    get_static_killcount_candidates,
    get_static_metric_candidates,
    get_static_skill_xp_candidates,
)


def test_expand_killcount_template_builds_point_variants():
    template = KillcountTileTemplate(
        source_name="Zulrah",
        boss_id="zulrah",
        content_id="zulrah",
        target_by_point_value={
            1: 50,
            3: 150,
        },
    )

    candidates = expand_killcount_template(
        template
    )

    assert [
        candidate.title
        for candidate in candidates
    ] == [
        "Complete 50 Zulrah KC",
        "Complete 150 Zulrah KC",
    ]

    assert [
        candidate.point_value
        for candidate in candidates
    ] == [
        1,
        3,
    ]

    assert all(
        candidate.primary_category == TileCategory.KILLCOUNT
        for candidate in candidates
    )
    assert all(
        candidate.routes[0].tracking_source == TrackingSource.WOM
        for candidate in candidates
    )
    assert all(
        "boss:zulrah" in candidate.all_hard_unique_tags
        for candidate in candidates
    )
    assert all(
        "source:zulrah" in candidate.all_hard_unique_tags
        for candidate in candidates
    )


def test_killcount_template_validates_point_values():
    with pytest.raises(
        ValueError,
        match="between 1 and 5"
    ):
        KillcountTileTemplate(
            source_name="Bad",
            boss_id="bad",
            target_by_point_value={
                0: 10,
            },
        )


def test_killcount_template_validates_targets():
    with pytest.raises(
        ValueError,
        match="positive"
    ):
        KillcountTileTemplate(
            source_name="Bad",
            boss_id="bad",
            target_by_point_value={
                1: 0,
            },
        )


def test_static_killcount_candidates_cover_each_point_tier():
    candidates = get_static_killcount_candidates()

    assert len(candidates) == len(STATIC_KILLCOUNT_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in candidates
    } >= {
        "Complete 50 Zulrah KC",
        "Complete 400 Zulrah KC",
        "Complete 25 Vorkath KC",
        "Complete 400 Vorkath KC",
        "Complete 25 Giant Mole KC",
        "Complete 500 Scurrius KC",
    }


def test_expand_drop_template_builds_point_variants():
    template = DropTileTemplate(
        source_name="Zulrah",
        source_id="zulrah",
        boss_id="zulrah",
        content_id="zulrah",
        drop_group_id="zulrah_uniques",
        target_by_point_value={
            1: 1,
            3: 3,
        },
    )

    candidates = expand_drop_template(
        template
    )

    assert [
        candidate.title
        for candidate in candidates
    ] == [
        "Obtain 1 Zulrah unique",
        "Obtain 3 Zulrah uniques",
    ]

    assert [
        candidate.point_value
        for candidate in candidates
    ] == [
        1,
        3,
    ]

    assert all(
        candidate.primary_category == TileCategory.DROP
        for candidate in candidates
    )
    assert all(
        candidate.routes[0].tracking_source == TrackingSource.DINK
        for candidate in candidates
    )
    assert all(
        "boss:zulrah" in candidate.all_hard_unique_tags
        for candidate in candidates
    )
    assert all(
        "source:zulrah" in candidate.all_hard_unique_tags
        for candidate in candidates
    )
    assert all(
        "drop_group:zulrah_uniques" in candidate.all_hard_unique_tags
        for candidate in candidates
    )


def test_static_drop_candidates_cover_each_point_tier():
    candidates = get_static_drop_candidates()

    assert len(candidates) == len(STATIC_DROP_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in candidates
    } >= {
        "Obtain 1 Zulrah unique",
        "Obtain 5 Zulrah uniques",
        "Obtain 1 Vorkath unique",
        "Obtain 5 Vorkath uniques",
        "Obtain 1 Giant Mole unique",
        "Obtain 5 Scurrius uniques",
    }


def test_expand_skill_xp_template_builds_point_variants():
    template = SkillXpTileTemplate(
        skill_name="Cooking",
        skill_id="cooking",
        target_by_point_value={
            1: 250_000,
            3: 750_000,
        },
    )

    candidates = expand_skill_xp_template(
        template
    )

    assert [
        candidate.title
        for candidate in candidates
    ] == [
        "Gain 250,000 Cooking XP",
        "Gain 750,000 Cooking XP",
    ]

    assert [
        candidate.point_value
        for candidate in candidates
    ] == [
        1,
        3,
    ]

    assert all(
        candidate.primary_category == TileCategory.SKILL
        for candidate in candidates
    )
    assert all(
        candidate.routes[0].tracking_source == TrackingSource.WOM
        for candidate in candidates
    )
    assert all(
        "skill:cooking" in candidate.all_hard_unique_tags
        for candidate in candidates
    )
    assert all(
        "source:cooking" in candidate.all_hard_unique_tags
        for candidate in candidates
    )


def test_static_skill_xp_candidates_cover_each_point_tier():
    candidates = get_static_skill_xp_candidates()

    assert len(candidates) == len(STATIC_SKILL_XP_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in candidates
    } >= {
        "Gain 250,000 Cooking XP",
        "Gain 1,500,000 Cooking XP",
        "Gain 250,000 Hunter XP",
        "Gain 1,500,000 Hunter XP",
        "Gain 250,000 Agility XP",
        "Gain 1,500,000 Sailing XP",
    }


def test_expand_metric_template_builds_wom_activity_candidates():
    template = MetricTileTemplate(
        display_name="medium-or-harder clue scrolls",
        metric_id="clue_scrolls_medium_plus_completed",
        source_id="clue_scrolls_medium_plus",
        activity_group_id="clue_scrolls",
        target_by_point_value={
            1: 10,
            3: 50,
        },
    )

    candidates = expand_metric_template(
        template
    )

    assert [
        candidate.title
        for candidate in candidates
    ] == [
        "Complete 10 medium-or-harder clue scrolls",
        "Complete 50 medium-or-harder clue scrolls",
    ]

    assert all(
        candidate.primary_category == TileCategory.HYBRID
        for candidate in candidates
    )
    assert all(
        candidate.routes[0].tracking_source == TrackingSource.WOM
        for candidate in candidates
    )
    assert all(
        "activity_group:clue_scrolls" in candidate.all_hard_unique_tags
        for candidate in candidates
    )


def test_static_metric_candidates_cover_each_point_tier_and_clue_group():
    candidates = get_static_metric_candidates()

    assert len(candidates) == len(STATIC_METRIC_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    titles = {
        candidate.title
        for candidate in candidates
    }

    assert "Complete 25 Guardians of the Rift completions" in titles
    assert "Complete 50 medium-or-harder clue scrolls" in titles

    clue_candidates = [
        candidate
        for candidate in candidates
        if "clue scrolls" in candidate.title
    ]

    assert clue_candidates
    assert all(
        "activity_group:clue_scrolls" in candidate.all_hard_unique_tags
        for candidate in clue_candidates
    )
