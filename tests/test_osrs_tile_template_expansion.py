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
    from utils.osrs_tile_template_expansion import (
        build_drop_target_model_from_template,
    )

    candidates = get_static_drop_candidates()

    expected_candidate_count = sum(
        len(
            dict(
                build_drop_target_model_from_template(
                    template
                ).target_by_point_value
            )
        )
        for template in STATIC_DROP_TEMPLATES
    )

    assert len(candidates) == expected_candidate_count

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

    assert "Obtain 1 Zulrah unique" in titles
    assert "Obtain 1 Vorkath unique" in titles
    assert "Obtain 1 Giant Mole unique" in titles
    assert "Obtain 1 Scurrius unique" in titles


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


def test_killcount_template_expands_via_component_single_recipe():
    from utils.board_generation import TrackingSource
    from utils.osrs_tile_template_expansion import (
        KillcountTileTemplate,
        expand_killcount_template,
    )

    template = KillcountTileTemplate(
        source_name="Callisto",
        boss_id="callisto",
        target_by_point_value={
            3: 35,
        },
        explanation=(
            "Prototype source.",
        ),
    )

    candidate = expand_killcount_template(
        template
    )[0]
    route = candidate.routes[0]

    assert candidate.title == "Complete 35 Callisto KC"
    assert candidate.point_value == 3
    assert route.display_text == "Complete 35 Callisto KC"
    assert route.target == 35
    assert route.tracking_source == TrackingSource.WOM
    assert route.metric_id == "boss_callisto_kc"
    assert route.source_id == "callisto"
    assert route.boss_id == "callisto"
    assert candidate.explanation == (
        "Prototype source.",
        "Generated 3-point killcount target from the Callisto template.",
    )
    assert "component:callisto_killcount" in candidate.all_hard_unique_tags
    assert all(
        not tag.startswith("target_model:")
        for tag in candidate.all_hard_unique_tags
    )


def test_skill_xp_template_expands_via_component_single_recipe():
    from utils.board_generation import TrackingSource
    from utils.osrs_tile_template_expansion import (
        SkillXpTileTemplate,
        expand_skill_xp_template,
    )

    template = SkillXpTileTemplate(
        skill_name="Magic",
        skill_id="magic",
        target_by_point_value={
            2: 500000,
        },
        explanation=(
            "Prototype skill source.",
        ),
    )

    candidate = expand_skill_xp_template(
        template
    )[0]
    route = candidate.routes[0]

    assert candidate.title == "Gain 500,000 Magic XP"
    assert candidate.point_value == 2
    assert route.display_text == "Gain 500,000 Magic XP"
    assert route.target == 500000
    assert route.tracking_source == TrackingSource.WOM
    assert route.metric_id == "skill_magic_xp"
    assert route.source_id == "magic"
    assert route.skill_id == "magic"
    assert candidate.explanation == (
        "Prototype skill source.",
        "Generated 2-point skill XP target from the Magic template.",
    )
    assert "component:magic_experience" in candidate.all_hard_unique_tags
    assert "skill:magic" in candidate.all_hard_unique_tags


def test_metric_template_expands_via_component_single_recipe():
    from utils.board_generation import TrackingSource
    from utils.osrs_tile_template_expansion import (
        MetricTileTemplate,
        expand_metric_template,
    )

    template = MetricTileTemplate(
        display_name="medium clue scrolls",
        metric_id="clue_scrolls_medium_completed",
        source_id="clue_scrolls_medium",
        target_by_point_value={
            2: 25,
        },
        activity_group_id="clue_scrolls",
        explanation=(
            "Prototype metric source.",
        ),
    )

    candidate = expand_metric_template(
        template
    )[0]
    route = candidate.routes[0]

    assert candidate.title == "Complete 25 medium clue scrolls"
    assert candidate.point_value == 2
    assert route.display_text == "Complete 25 medium clue scrolls"
    assert route.target == 25
    assert route.tracking_source == TrackingSource.WOM
    assert route.metric_id == "clue_scrolls_medium_completed"
    assert route.source_id == "clue_scrolls_medium"
    assert candidate.explanation == (
        "Prototype metric source.",
        "Generated 2-point WOM metric target from the medium clue scrolls template.",
    )
    assert "component:clue_scrolls_medium_completed_metric" in candidate.all_hard_unique_tags
    assert "metric:clue_scrolls_medium_completed" in candidate.all_hard_unique_tags
    assert "source:clue_scrolls_medium" in candidate.all_hard_unique_tags
    assert "activity_group:clue_scrolls" in candidate.all_hard_unique_tags


def test_drop_template_expands_via_component_single_recipe():
    from utils.board_generation import TrackingSource
    from utils.osrs_tile_template_expansion import (
        DropTileTemplate,
        expand_drop_template,
    )

    template = DropTileTemplate(
        source_name="Zulrah",
        source_id="zulrah",
        boss_id="zulrah",
        drop_group_id="zulrah_uniques",
        target_by_point_value={
            3: 1,
        },
        explanation=(
            "Prototype drop source.",
        ),
    )

    candidate = expand_drop_template(
        template
    )[0]
    route = candidate.routes[0]

    assert candidate.title == "Obtain 1 Zulrah unique"
    assert candidate.point_value == 3
    assert route.display_text == "Obtain 1 Zulrah unique"
    assert route.target == 1
    assert route.tracking_source == TrackingSource.DINK
    assert route.source_id == "zulrah"
    assert route.boss_id == "zulrah"
    assert route.drop_group_id == "zulrah_uniques"
    assert candidate.explanation == (
        "Prototype drop source.",
        "Generated 3-point drop target from the Zulrah template.",
    )
    assert "component:zulrah_drop" in candidate.all_hard_unique_tags
    assert "source:zulrah" in candidate.all_hard_unique_tags
    assert "boss:zulrah" in candidate.all_hard_unique_tags
    assert "drop_group:zulrah_uniques" in candidate.all_hard_unique_tags


def test_template_expansion_uses_shared_single_component_expansion_helper(monkeypatch):
    import utils.osrs_tile_template_expansion as expansion

    captured = {}

    def fake_expand_single_component(**kwargs):
        captured["component"] = kwargs["component"]
        captured["target_model"] = kwargs["target_model"]
        captured["include_generation_note"] = kwargs["include_generation_note"]
        return (
            "candidate",
        )

    monkeypatch.setattr(
        expansion,
        "expand_single_component",
        fake_expand_single_component,
    )

    template = expansion.KillcountTileTemplate(
        source_name="Callisto",
        boss_id="callisto",
        target_by_point_value={
            3: 35,
        },
    )

    assert expansion.expand_killcount_template(
        template
    ) == (
        "candidate",
    )
    assert captured["component"].component_id == "callisto_killcount"
    assert captured["target_model"].target_model_id == "callisto_static_killcount"
    assert captured["include_generation_note"] is False


def test_skilling_minigame_metric_templates_support_n_of_recipe():
    from utils.osrs_tile_template_expansion import (
        STATIC_METRIC_TEMPLATES,
        build_metric_component_from_template,
    )

    components_by_metric = {
        template.metric_id: build_metric_component_from_template(
            template
        )
        for template in STATIC_METRIC_TEMPLATES
    }

    assert components_by_metric[
        "guardians_of_the_rift_completions"
    ].groups == (
        "skilling_minigames",
    )
    assert components_by_metric[
        "guardians_of_the_rift_completions"
    ].supports_recipe(
        "N_OF"
    )
    assert components_by_metric[
        "tempoross_completions"
    ].supports_recipe(
        "N_OF"
    )
    assert components_by_metric[
        "wintertodt_kills"
    ].supports_recipe(
        "N_OF"
    )


def test_dagannoth_rex_drop_template_targets_do_not_exceed_defined_drop_group():
    from utils.osrs_tile_template_expansion import (
        STATIC_DROP_TEMPLATES,
        build_drop_target_model_from_template,
    )

    template = next(
        template
        for template in STATIC_DROP_TEMPLATES
        if template.drop_group_id == "dagannoth_rex_uniques"
    )

    target_model = build_drop_target_model_from_template(
        template
    )

    max_target = max(
        dict(
            target_model.target_by_point_value
        ).values()
    )

    assert max_target <= 5
    assert max_target == len(
        target_model.target_by_point_value
    )
