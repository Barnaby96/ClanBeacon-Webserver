"""Helpers for expanding atomic components into tile candidates."""

from dataclasses import dataclass

from utils.osrs_generation_recipes import (
    StaticPointTargetModel,
    build_single_tile_candidate,
)


@dataclass(frozen=True)
class SingleComponentExpansion:
    component: object
    target_model: StaticPointTargetModel
    title_formatter: object
    display_text_formatter: object
    explanation_formatter: object
    include_generation_note: bool = False

    def expand(self):
        return expand_single_component(
            component=self.component,
            target_model=self.target_model,
            title_formatter=self.title_formatter,
            display_text_formatter=self.display_text_formatter,
            explanation_formatter=self.explanation_formatter,
            include_generation_note=self.include_generation_note,
        )


def expand_single_component(
    component,
    target_model,
    title_formatter,
    display_text_formatter=None,
    explanation_formatter=None,
    include_generation_note=False,
):
    display_text_formatter = display_text_formatter or title_formatter

    if explanation_formatter is None:
        explanation_formatter = lambda point_value, target: ()

    return tuple(
        build_single_tile_candidate(
            component,
            point_value,
            target_model,
            title=title_formatter(
                point_value,
                target,
            ),
            display_text=display_text_formatter(
                point_value,
                target,
            ),
            explanation=tuple(
                explanation_formatter(
                    point_value,
                    target,
                )
            ),
            include_generation_note=include_generation_note,
        )
        for point_value, target in target_model.target_by_point_value
    )
