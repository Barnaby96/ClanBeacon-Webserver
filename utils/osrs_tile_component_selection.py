"""Selection helpers for atomic OSRS Bingo tile components."""

from dataclasses import dataclass

from utils.board_generation import canonical_id


def normalise_optional_values(values):
    if values is None:
        return None

    return frozenset(
        canonical_id(
            value
        )
        for value in values
    )


def normalise_optional_enum_values(values):
    if values is None:
        return None

    return frozenset(
        getattr(
            value,
            "value",
            value,
        )
        for value in values
    )


@dataclass(frozen=True)
class ComponentSelectionCriteria:
    component_types: frozenset | None = None
    primary_categories: frozenset | None = None
    tracking_sources: frozenset | None = None
    any_groups: frozenset | None = None
    all_groups: frozenset | None = None
    supported_recipe_ids: frozenset | None = None
    include_component_ids: frozenset | None = None
    exclude_component_ids: frozenset | None = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "component_types",
            normalise_optional_enum_values(
                self.component_types
            ),
        )
        object.__setattr__(
            self,
            "primary_categories",
            normalise_optional_enum_values(
                self.primary_categories
            ),
        )
        object.__setattr__(
            self,
            "tracking_sources",
            normalise_optional_enum_values(
                self.tracking_sources
            ),
        )
        object.__setattr__(
            self,
            "any_groups",
            normalise_optional_values(
                self.any_groups
            ),
        )
        object.__setattr__(
            self,
            "all_groups",
            normalise_optional_values(
                self.all_groups
            ),
        )
        object.__setattr__(
            self,
            "supported_recipe_ids",
            frozenset(
                canonical_id(
                    recipe_id
                ).upper()
                for recipe_id in self.supported_recipe_ids
            )
            if self.supported_recipe_ids is not None
            else None,
        )
        object.__setattr__(
            self,
            "include_component_ids",
            normalise_optional_values(
                self.include_component_ids
            ),
        )
        object.__setattr__(
            self,
            "exclude_component_ids",
            normalise_optional_values(
                self.exclude_component_ids
            ),
        )


def component_matches_criteria(component, criteria):
    if criteria.component_types is not None:
        if component.component_type.value not in criteria.component_types:
            return False

    if criteria.primary_categories is not None:
        if component.primary_category.value not in criteria.primary_categories:
            return False

    if criteria.tracking_sources is not None:
        if component.tracking_source.value not in criteria.tracking_sources:
            return False

    if criteria.include_component_ids is not None:
        if component.component_id not in criteria.include_component_ids:
            return False

    if criteria.exclude_component_ids is not None:
        if component.component_id in criteria.exclude_component_ids:
            return False

    component_groups = frozenset(
        component.groups
    )

    if criteria.any_groups is not None:
        if component_groups.isdisjoint(
            criteria.any_groups
        ):
            return False

    if criteria.all_groups is not None:
        if not criteria.all_groups.issubset(
            component_groups
        ):
            return False

    if criteria.supported_recipe_ids is not None:
        if criteria.supported_recipe_ids.isdisjoint(
            frozenset(
                component.compatible_recipe_ids
            )
        ):
            return False

    return True


def select_components(components, criteria):
    return tuple(
        component
        for component in components
        if component_matches_criteria(
            component,
            criteria,
        )
    )


def require_component_count(components, minimum_count, label="components"):
    components = tuple(
        components
    )

    if len(
        components
    ) < minimum_count:
        raise ValueError(
            f"Need at least {minimum_count} {label}; "
            f"found {len(components)}."
        )

    return components
