from utils.osrs_encounter_groups import (
    MAX_WILDERNESS_KC_TILES,
    get_wilderness_boss_pair_id,
    is_wilderness_drop_group_id,
)
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import FrozenSet, Iterable, Optional, Sequence


class TileCategory(str, Enum):
    SKILL = "SKILL"
    KILLCOUNT = "KILLCOUNT"
    DROP = "DROP"
    PET = "PET"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"


class RouteMode(str, Enum):
    SINGLE = "SINGLE"
    OR = "OR"
    AND = "AND"
    SUM = "SUM"
    N_OF = "N_OF"


class PetRole(str, Enum):
    NONE = "NONE"
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


class TrackingSource(str, Enum):
    WOM = "WOM"
    DINK = "DINK"
    MANUAL = "MANUAL"


class ContributionMode(str, Enum):
    TEAM_SUM = "TEAM_SUM"
    ANY_PLAYER = "ANY_PLAYER"
    N_OF_UNIQUES = "N_OF_UNIQUES"
    UNIQUE_PLAYERS = "UNIQUE_PLAYERS"


class AccessFlag(str, Enum):
    QUEST_LOCKED = "QUEST_LOCKED"
    DIARY_LOCKED = "DIARY_LOCKED"
    MINIGAME_UNLOCK = "MINIGAME_UNLOCK"
    RAID_ACCESS = "RAID_ACCESS"
    WILDERNESS = "WILDERNESS"
    DANGEROUS_DEATH = "DANGEROUS_DEATH"
    MEMBERS_AREA = "MEMBERS_AREA"


class AccessConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class BoardSlot:
    point_value: int
    required_category: Optional[TileCategory] = None

    @property
    def is_flex(self):
        return self.required_category is None

    def matches_candidate(self, candidate):
        if candidate.point_value != self.point_value:
            return False

        if self.is_flex:
            return True

        return candidate.primary_category == self.required_category


def default_points_distribution():
    return {
        1: 5,
        2: 5,
        3: 5,
        4: 5,
        5: 5,
    }


def default_required_categories_by_point():
    return {
        point_value: (
            TileCategory.SKILL,
            TileCategory.KILLCOUNT,
            TileCategory.DROP,
        )
        for point_value in range(1, 6)
    }


def default_flex_slots_by_point():
    return {
        point_value: 2
        for point_value in range(1, 6)
    }


@dataclass(frozen=True)
class BoardGenerationRules:
    board_size: int = 25
    points_distribution: dict[int, int] = field(
        default_factory=default_points_distribution
    )
    required_categories_by_point: dict[int, tuple[TileCategory, ...]] = field(
        default_factory=default_required_categories_by_point
    )
    flex_slots_by_point: dict[int, int] = field(
        default_factory=default_flex_slots_by_point
    )
    primary_pet_tiles_min: int = 1
    primary_pet_tiles_target: int = 1
    primary_pet_tiles_max: int = 1
    secondary_pet_routes_min: int = 2
    secondary_pet_routes_target: int = 4
    secondary_pet_routes_max: int = 6
    minimum_primary_categories_per_tier: int | None = None
    target_primary_categories_per_tier: int | None = None
    maximum_primary_category_tiles_per_tier: int | None = None
    minimum_primary_category_counts: dict[TileCategory, int] = field(default_factory=dict)

    def __post_init__(self):
        errors = self.validation_errors()

        if errors:
            raise ValueError(
                "; ".join(errors)
            )

    def validation_errors(self):
        errors = []

        if self.board_size <= 0:
            errors.append(
                "Board size must be greater than zero."
            )

        if sum(self.points_distribution.values()) != self.board_size:
            errors.append(
                "Points distribution must add up to board size."
            )

        for point_value, tile_count in self.points_distribution.items():
            if point_value < 1 or point_value > 5:
                errors.append(
                    "Point values must be between 1 and 5."
                )

            if tile_count < 0:
                errors.append(
                    "Point distribution counts cannot be negative."
                )

            required_count = len(
                self.required_categories_by_point.get(
                    point_value,
                    ()
                )
            )
            flex_count = self.flex_slots_by_point.get(
                point_value,
                0
            )

            if flex_count < 0:
                errors.append(
                    "Flex slot counts cannot be negative."
                )

            if required_count + flex_count != tile_count:
                errors.append(
                    "Required categories plus flex slots must match "
                    f"the tile count for {point_value}-point tiles."
                )

        if not (
            self.primary_pet_tiles_min
            <= self.primary_pet_tiles_target
            <= self.primary_pet_tiles_max
        ):
            errors.append(
                "Primary pet tile limits must be min <= target <= max."
            )

        if not (
            self.secondary_pet_routes_min
            <= self.secondary_pet_routes_target
            <= self.secondary_pet_routes_max
        ):
            errors.append(
                "Secondary pet route limits must be min <= target <= max."
            )

        return errors

    def build_slots(self):
        required_slots = []
        flex_slots = []

        for point_value in sorted(
            self.points_distribution
        ):
            for required_category in self.required_categories_by_point.get(
                point_value,
                ()
            ):
                required_slots.append(
                    BoardSlot(
                        point_value=point_value,
                        required_category=required_category,
                    )
                )

            for _ in range(
                self.flex_slots_by_point.get(
                    point_value,
                    0
                )
            ):
                flex_slots.append(
                    BoardSlot(
                        point_value=point_value,
                    )
                )

        return tuple(
            [
                *required_slots,
                *flex_slots,
            ]
        )



def canonical_id(value):
    if value is None:
        return None

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def build_tag(tag_type, value):
    canonical_value = canonical_id(value)

    if canonical_value is None or canonical_value == "":
        return None

    return f"{tag_type}:{canonical_value}"


def normalise_skill_requirements(requirements, label):
    normalised_requirements = {}

    for skill_id, level in requirements.items():
        canonical_skill_id = canonical_id(skill_id)

        if canonical_skill_id is None or canonical_skill_id == "":
            raise ValueError(
                f"{label} skill requirement has an empty skill id."
            )

        if isinstance(level, bool):
            raise ValueError(
                f"{label} skill requirement for {canonical_skill_id} "
                "must be a level between 1 and 99."
            )

        try:
            level = int(level)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{label} skill requirement for {canonical_skill_id} "
                "must be a level between 1 and 99."
            ) from error

        if level < 1 or level > 99:
            raise ValueError(
                f"{label} skill requirement for {canonical_skill_id} "
                "must be a level between 1 and 99."
            )

        normalised_requirements[canonical_skill_id] = level

    return normalised_requirements


@dataclass(frozen=True)
class AccessProfile:
    effective_skill_requirements: dict[str, int] = field(default_factory=dict)
    recommended_skill_requirements: dict[str, int] = field(default_factory=dict)
    access_flags: FrozenSet[AccessFlag] = field(default_factory=frozenset)
    access_confidence: AccessConfidence = AccessConfidence.HIGH

    def __post_init__(self):
        object.__setattr__(
            self,
            "effective_skill_requirements",
            normalise_skill_requirements(
                self.effective_skill_requirements,
                "Effective"
            )
        )
        object.__setattr__(
            self,
            "recommended_skill_requirements",
            normalise_skill_requirements(
                self.recommended_skill_requirements,
                "Recommended"
            )
        )
        object.__setattr__(
            self,
            "access_flags",
            frozenset(
                self.access_flags
            )
        )


@dataclass(frozen=True)
class Route:
    route_type: TileCategory
    display_text: str
    target: int | float
    tracking_source: TrackingSource
    contribution_mode: ContributionMode
    metric_id: Optional[str] = None
    source_id: Optional[str] = None
    skill_id: Optional[str] = None
    boss_id: Optional[str] = None
    drop_id: Optional[str] = None
    drop_group_id: Optional[str] = None
    pet_id: Optional[str] = None
    pet_group_id: Optional[str] = None
    hard_unique_tags: FrozenSet[str] = field(default_factory=frozenset)
    expected_rolls: Optional[Decimal] = None

    @property
    def generated_hard_unique_tags(self):
        tags = {
            build_tag("metric", self.metric_id),
            build_tag("source", self.source_id),
            build_tag("skill", self.skill_id),
            build_tag("boss", self.boss_id),
            build_tag("drop", self.drop_id),
            build_tag("drop_group", self.drop_group_id),
            build_tag("pet", self.pet_id),
            build_tag("pet_group", self.pet_group_id),
        }

        return frozenset(
            tag
            for tag in tags
            if tag is not None
        )

    @property
    def all_hard_unique_tags(self):
        return frozenset(
            {
                *self.generated_hard_unique_tags,
                *self.hard_unique_tags,
            }
        )


@dataclass(frozen=True)
class TileCandidate:
    title: str
    point_value: int
    primary_category: TileCategory
    route_mode: RouteMode
    routes: Sequence[Route]
    secondary_categories: FrozenSet[TileCategory] = field(default_factory=frozenset)
    pet_role: PetRole = PetRole.NONE
    hard_unique_tags: FrozenSet[str] = field(default_factory=frozenset)
    tracking_sources: FrozenSet[TrackingSource] = field(default_factory=frozenset)
    rng_level: int = 0
    has_fallback: bool = False
    access_profile: AccessProfile = field(default_factory=AccessProfile)
    required_route_count: Optional[int] = None
    explanation: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self):
        if self.point_value < 1 or self.point_value > 5:
            raise ValueError(
                "Generated tile point value must be between 1 and 5."
            )

        if self.rng_level < 0 or self.rng_level > 4:
            raise ValueError(
                "Generated tile RNG level must be between 0 and 4."
            )

        if len(self.routes) == 0:
            raise ValueError(
                "Generated tile must have at least one completion route."
            )

        errors = self.validation_errors()

        if errors:
            raise ValueError(
                "; ".join(errors)
            )

    @property
    def route_expected_rolls(self):
        return tuple(
            route.expected_rolls
            for route in self.routes
            if route.expected_rolls is not None
        )

    @property
    def expected_rolls(self):
        if not self.route_expected_rolls:
            return None

        if len(self.route_expected_rolls) != len(self.routes):
            return None

        if self.route_mode == RouteMode.SINGLE:
            if len(self.routes) != 1:
                return None

            return self.route_expected_rolls[0]

        if self.route_mode == RouteMode.AND:
            return sum(
                self.route_expected_rolls
            )

        if self.route_mode == RouteMode.OR:
            return min(
                self.route_expected_rolls
            )

        if self.route_mode == RouteMode.N_OF:
            if self.required_route_count is None:
                return None

            if self.required_route_count < 1:
                return None

            if self.required_route_count > len(self.route_expected_rolls):
                return None

            return sum(
                sorted(
                    self.route_expected_rolls
                )[:self.required_route_count]
            )

        return None

    @property
    def all_hard_unique_tags(self):
        route_tags = set()

        for route in self.routes:
            route_tags.update(
                route.all_hard_unique_tags
            )

        return frozenset(
            {
                *route_tags,
                *self.hard_unique_tags,
            }
        )

    @property
    def all_tracking_sources(self):
        if self.tracking_sources:
            return self.tracking_sources

        return frozenset(
            route.tracking_source
            for route in self.routes
        )

    def validation_errors(self):
        errors = []

        if self.route_mode == RouteMode.SINGLE and len(self.routes) != 1:
            errors.append(
                "SINGLE route mode must contain exactly one route."
            )

        if self.route_mode == RouteMode.N_OF:
            if self.required_route_count is None:
                errors.append(
                    "N_OF route mode requires required_route_count."
                )
            elif self.required_route_count < 1:
                errors.append(
                    "N_OF required_route_count must be at least 1."
                )
            elif self.required_route_count > len(self.routes):
                errors.append(
                    "N_OF required_route_count cannot exceed route count."
                )

        return errors


def find_conflicting_tags(candidate, used_tags):
    return candidate.all_hard_unique_tags.intersection(
        frozenset(used_tags)
    )


def reserve_candidate_tags(candidate, used_tags):
    used_tags = frozenset(used_tags)
    conflicting_tags = find_conflicting_tags(
        candidate,
        used_tags
    )

    if conflicting_tags:
        raise ValueError(
            "Generated tile conflicts with existing board tags: "
            + ", ".join(
                sorted(conflicting_tags)
            )
        )

    return frozenset(
        {
            *used_tags,
            *candidate.all_hard_unique_tags,
        }
    )


class BoardAssemblyError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedBoard:
    candidates: tuple[TileCandidate, ...]
    used_hard_unique_tags: FrozenSet[str]

    @property
    def point_total(self):
        return sum(
            candidate.point_value
            for candidate in self.candidates
        )


def secondary_pet_route_count(candidate):
    if candidate.pet_role != PetRole.SECONDARY:
        return 0

    return sum(
        1
        for route in candidate.routes
        if route.pet_id is not None
        or route.pet_group_id is not None
        or route.route_type == TileCategory.PET
    )


def count_primary_pet_tiles(candidates):
    return sum(
        1
        for candidate in candidates
        if candidate.pet_role == PetRole.PRIMARY
    )


def count_secondary_pet_routes(candidates):
    return sum(
        secondary_pet_route_count(candidate)
        for candidate in candidates
    )


def candidate_fits_pet_limits(candidate, selected_candidates, rules):
    primary_pet_count = count_primary_pet_tiles(
        selected_candidates
    )
    secondary_pet_count = count_secondary_pet_routes(
        selected_candidates
    )

    if candidate.pet_role == PetRole.PRIMARY:
        primary_pet_count += 1

    secondary_pet_count += secondary_pet_route_count(
        candidate
    )

    return (
        primary_pet_count <= rules.primary_pet_tiles_max
        and secondary_pet_count <= rules.secondary_pet_routes_max
    )


def validate_generated_board_candidates(candidates, rules=None):
    if rules is None:
        rules = BoardGenerationRules()

    candidates = tuple(candidates)
    errors = []

    if len(candidates) != rules.board_size:
        errors.append(
            f"Generated board must contain {rules.board_size} tiles."
        )

    point_counts = Counter(
        candidate.point_value
        for candidate in candidates
    )

    for point_value, required_count in rules.points_distribution.items():
        if point_counts[point_value] != required_count:
            errors.append(
                f"Generated board must contain {required_count} "
                f"{point_value}-point tiles."
            )

    for point_value, required_categories in rules.required_categories_by_point.items():
        point_candidates = [
            candidate
            for candidate in candidates
            if candidate.point_value == point_value
        ]

        category_counts = Counter(
            candidate.primary_category
            for candidate in point_candidates
        )

        for category in required_categories:
            if category_counts[category] < 1:
                errors.append(
                    f"Generated board must include a {category.value} "
                    f"tile in the {point_value}-point tier."
                )

    for tier in rules.points_distribution:
        tier_counts = Counter(c.primary_category for c in candidates if c.point_value == tier)
        minimum = rules.minimum_primary_categories_per_tier
        maximum = rules.maximum_primary_category_tiles_per_tier
        if minimum is not None and len(tier_counts) < minimum:
            errors.append(f"{tier}-point tier category minimum is {minimum} distinct categories.")
        if maximum is not None and any(count > maximum for count in tier_counts.values()):
            errors.append(f"{tier}-point tier category maximum is {maximum} tiles per category.")

    category_counts = Counter(candidate.primary_category for candidate in candidates)
    for category, minimum in rules.minimum_primary_category_counts.items():
        if category_counts[category] < minimum:
            errors.append(
                f"Generated board requires at least {minimum} "
                f"{category.value} category tiles."
            )

    primary_pet_count = count_primary_pet_tiles(
        candidates
    )
    secondary_pet_count = count_secondary_pet_routes(
        candidates
    )

    if not (
        rules.primary_pet_tiles_min
        <= primary_pet_count
        <= rules.primary_pet_tiles_max
    ):
        errors.append(
            "Generated board primary pet tile count must be between "
            f"{rules.primary_pet_tiles_min} and "
            f"{rules.primary_pet_tiles_max}."
        )

    if not (
        rules.secondary_pet_routes_min
        <= secondary_pet_count
        <= rules.secondary_pet_routes_max
    ):
        errors.append(
            "Generated board secondary pet route count must be between "
            f"{rules.secondary_pet_routes_min} and "
            f"{rules.secondary_pet_routes_max}."
        )

    return errors



def candidate_has_wilderness_drop_route(candidate):
    return any(
        route.route_type == TileCategory.DROP
        and is_wilderness_drop_group_id(
            route.drop_group_id
        )
        for route in candidate.routes
    )


def candidate_has_wilderness_killcount_route(candidate):
    return any(
        route.route_type == TileCategory.KILLCOUNT
        and get_wilderness_boss_pair_id(
            route.boss_id
        )
        for route in candidate.routes
    )


def count_wilderness_killcount_candidates(candidates):
    return sum(
        1
        for candidate in candidates
        if candidate_has_wilderness_killcount_route(
            candidate
        )
    )


def has_pending_required_drop_slot(pending_slots):
    return any(
        not slot.is_flex
        and slot.required_category == TileCategory.DROP
        for slot in pending_slots
    )


def has_pending_required_killcount_slot(pending_slots):
    return any(
        not slot.is_flex
        and slot.required_category == TileCategory.KILLCOUNT
        for slot in pending_slots
    )


def candidate_fits_wilderness_pvm_limits(
    candidate,
    selected_candidates,
    pending_slots=(),
    max_wilderness_killcount_tiles=MAX_WILDERNESS_KC_TILES,
):
    candidate_has_drop = candidate_has_wilderness_drop_route(
        candidate
    )
    candidate_has_killcount = candidate_has_wilderness_killcount_route(
        candidate
    )

    if not candidate_has_drop and not candidate_has_killcount:
        return True

    if (
        candidate_has_drop
        and has_pending_required_killcount_slot(
            pending_slots
        )
    ):
        return False

    selected_has_drop = any(
        candidate_has_wilderness_drop_route(
            selected_candidate
        )
        for selected_candidate in selected_candidates
    )
    selected_has_killcount = any(
        candidate_has_wilderness_killcount_route(
            selected_candidate
        )
        for selected_candidate in selected_candidates
    )

    if candidate_has_drop and selected_has_killcount:
        return False

    if candidate_has_killcount and selected_has_drop:
        return False

    if (
        candidate_has_killcount
        and count_wilderness_killcount_candidates(
            selected_candidates
        )
        >= max_wilderness_killcount_tiles
    ):
        return False

    return True

def ordered_slot_candidates(
    slot,
    pending_slots,
    remaining_candidates,
    candidate_order_key=None,
):
    indexed_candidates = list(
        enumerate(
            remaining_candidates
        )
    )

    if candidate_order_key is not None:
        indexed_candidates = sorted(
            indexed_candidates,
            key=lambda item: (
                candidate_order_key(item[1]),
                (
                    candidate_order_key(item[1])
                    if candidate_order_key is not None
                    else 0
                ),
                item[0],
            ),
        )

    if (
        not slot.is_flex
        and slot.required_category == TileCategory.KILLCOUNT
        and has_pending_required_drop_slot(
            pending_slots
        )
    ):
        return sorted(
            indexed_candidates,
            key=lambda item: (
                0
                if candidate_has_wilderness_killcount_route(
                    item[1]
                )
                else 1,
                item[0],
            ),
        )

    return indexed_candidates


def future_pet_route_preserves_category_capacity(pet_candidate, selected, pending_slots, rules):
    if not rules.minimum_primary_category_counts:
        return True
    if not candidate_fits_pet_limits(pet_candidate, selected, rules):
        return False
    projected = (*selected, pet_candidate)
    counts = Counter(tile.primary_category for tile in projected)
    tier_counts = Counter((tile.point_value, tile.primary_category) for tile in projected)
    cap = rules.maximum_primary_category_tiles_per_tier
    if cap is not None and tier_counts[(pet_candidate.point_value, pet_candidate.primary_category)] > cap:
        return False
    for reserved_index, reserved_slot in enumerate(pending_slots):
        if not reserved_slot.matches_candidate(pet_candidate):
            continue
        remaining_slots = [slot for index, slot in enumerate(pending_slots) if index != reserved_index]
        outstanding = sum(max(0, minimum - counts[category]) for category, minimum in rules.minimum_primary_category_counts.items())
        if outstanding > len(remaining_slots):
            continue
        feasible = True
        for category, minimum in rules.minimum_primary_category_counts.items():
            needed = max(0, minimum - counts[category])
            capacity = 0
            for tier in rules.points_distribution:
                open_slots = sum(slot.point_value == tier and (slot.is_flex or slot.required_category == category) for slot in remaining_slots)
                free_cap = open_slots if cap is None else max(0, cap - tier_counts[(tier, category)])
                capacity += min(open_slots, free_cap)
            if capacity < needed:
                feasible = False
                break
        if feasible:
            return True
    return False

def assemble_board_candidates(candidates, rules=None, candidate_order_key=None, preselected_candidates=()):
    if rules is None:
        rules = BoardGenerationRules()

    remaining_candidates = list(candidates)
    candidate_tag_sets = {
        id(candidate): candidate.all_hard_unique_tags
        for candidate in remaining_candidates
    }
    selected_candidates = []
    used_tags = frozenset()
    slots = list(rules.build_slots())

    for preselected_candidate in preselected_candidates:
        limit = rules.maximum_primary_category_tiles_per_tier
        if limit is not None and sum(
            existing.point_value == preselected_candidate.point_value
            and existing.primary_category == preselected_candidate.primary_category
            for existing in selected_candidates
        ) >= limit:
            raise BoardAssemblyError("Kept tiles exceed per-tier category limit.")

        slot_index = next(
            (
                index
                for index, slot in enumerate(slots)
                if slot.matches_candidate(preselected_candidate)
            ),
            None,
        )

        if slot_index is None:
            raise BoardAssemblyError(
                f"Could not fit preselected tile {preselected_candidate.title}."
            )

        if find_conflicting_tags(preselected_candidate, used_tags):
            raise BoardAssemblyError(
                f"Preselected tile conflicts with another kept tile: "
                f"{preselected_candidate.title}."
            )

        used_tags = reserve_candidate_tags(
            preselected_candidate,
            used_tags
        )
        selected_candidates.append(
            preselected_candidate
        )
        slots.pop(
            slot_index
        )

        for candidate_index, candidate in enumerate(tuple(remaining_candidates)):
            if candidate == preselected_candidate:
                remaining_candidates.pop(
                    candidate_index
                )
                break

    for category, minimum in rules.minimum_primary_category_counts.items():
        available = sum(t.primary_category == category for t in selected_candidates)
        available += sum(
            t.primary_category == category
            and any(slot.matches_candidate(t) for slot in slots)
            for t in remaining_candidates
        )
        if available < minimum:
            raise BoardAssemblyError(
                f"Insufficient {category.value} category candidates for minimum {minimum}."
            )

    slots = tuple(slots)

    for slot_index, slot in enumerate(slots):
        selected_candidate = None
        selected_candidate_index = None
        pending_slots = slots[
            slot_index + 1:
        ]

        slot_candidates = ordered_slot_candidates(
            slot,
            pending_slots,
            remaining_candidates,
            candidate_order_key=candidate_order_key,
        )
        if slot.is_flex:
            tier_categories = {
                prior.primary_category
                for prior in selected_candidates
                if prior.point_value == slot.point_value
            }
            prefer_variety = (
                rules.target_primary_categories_per_tier is not None
                and len(tier_categories) < rules.target_primary_categories_per_tier
            )
            prefer_pet_route = (
                count_secondary_pet_routes(selected_candidates)
                < rules.secondary_pet_routes_target
            )
            if prefer_pet_route or prefer_variety:
                future_pet_options = (
                    tuple(
                        other for other in remaining_candidates
                        if secondary_pet_route_count(other) > 0
                        and not find_conflicting_tags(other, used_tags)
                        and any(s.matches_candidate(other) for s in pending_slots)
                    ) if prefer_pet_route else ()
                )
                future_pet_tag_sets = tuple(
                    candidate_tag_sets[id(pet)]
                    for pet in future_pet_options
                )
                slot_candidates = sorted(
                    slot_candidates,
                    key=lambda item: (
                        prefer_pet_route and secondary_pet_route_count(item[1]) == 0,
                        sum(
                            bool(candidate_tag_sets[id(item[1])] & pet_tags)
                            for pet_tags in future_pet_tag_sets
                        ),
                        prefer_variety and item[1].primary_category in tier_categories,
                    ),
                )
        for candidate_index, candidate in slot_candidates:
            if not slot.matches_candidate(candidate):
                continue

            limit = rules.maximum_primary_category_tiles_per_tier
            if limit is not None and sum(
                existing.point_value == candidate.point_value
                and existing.primary_category == candidate.primary_category
                for existing in selected_candidates
            ) >= limit:
                continue

            if find_conflicting_tags(candidate, used_tags):
                continue

            if not candidate_fits_pet_limits(
                candidate,
                selected_candidates,
                rules
            ):
                continue

            if not candidate_fits_wilderness_pvm_limits(
                candidate,
                selected_candidates,
                pending_slots=pending_slots,
            ):
                continue

            if rules.minimum_primary_category_counts:
                projected_counts = Counter(x.primary_category for x in selected_candidates)
                projected_counts[candidate.primary_category] += 1
                outstanding = sum(
                    max(0, minimum - projected_counts[category])
                    for category, minimum in rules.minimum_primary_category_counts.items()
                )
                if outstanding > len(pending_slots):
                    continue
                projected_tier_counts = Counter(
                    (t.point_value, t.primary_category) for t in selected_candidates
                )
                projected_tier_counts[(candidate.point_value, candidate.primary_category)] += 1
                tier_capacity_blocked = False
                for category, minimum in rules.minimum_primary_category_counts.items():
                    needed = max(0, minimum - projected_counts[category])
                    if needed == 0:
                        continue
                    total_capacity = 0
                    for tier in rules.points_distribution:
                        matching_slots = sum(
                            future_slot.point_value == tier
                            and (future_slot.is_flex or future_slot.required_category == category)
                            for future_slot in pending_slots
                        )
                        cap = rules.maximum_primary_category_tiles_per_tier
                        available = (
                            matching_slots if cap is None else
                            max(0, cap - projected_tier_counts[(tier, category)])
                        )
                        total_capacity += min(matching_slots, available)
                    if total_capacity < needed:
                        tier_capacity_blocked = True
                        break
                if tier_capacity_blocked:
                    continue
                future_tags = reserve_candidate_tags(candidate, used_tags)
                requirement_options = []
                category_unavailable = False
                for category, minimum in rules.minimum_primary_category_counts.items():
                    needed = max(0, minimum - projected_counts[category])
                    if needed == 0:
                        continue
                    eligible_candidates = [
                        other
                        for other_index, other in enumerate(remaining_candidates)
                        if other_index != candidate_index
                        and other.primary_category == category
                        and not find_conflicting_tags(other, future_tags)
                        and any(slot.matches_candidate(other) for slot in pending_slots)
                    ]
                    def has_compatible_set(start, count, reserved_tags):
                        if count == 0:
                            return True
                        if len(eligible_candidates) - start < count:
                            return False
                        for index in range(start, len(eligible_candidates)):
                            other = eligible_candidates[index]
                            if find_conflicting_tags(other, reserved_tags):
                                continue
                            if has_compatible_set(
                                index + 1,
                                count - 1,
                                reserved_tags | other.all_hard_unique_tags,
                            ):
                                return True
                        return False
                    if not has_compatible_set(0, needed, future_tags):
                        category_unavailable = True
                        break
                    eligible_slots = tuple(
                        index
                        for index, future_slot in enumerate(pending_slots)
                        if any(
                            other.primary_category == category
                            and future_slot.matches_candidate(other)
                            and not find_conflicting_tags(other, future_tags)
                            for other_index, other in enumerate(remaining_candidates)
                            if other_index != candidate_index
                        )
                    )
                    if len(eligible_slots) < needed:
                        category_unavailable = True
                        break
                    requirement_options.extend([eligible_slots] * needed)
                if category_unavailable:
                    continue
                assigned_slots = {}
                def assign_category_slot(options, visited):
                    for index in options:
                        if index in visited:
                            continue
                        visited.add(index)
                        previous_options = assigned_slots.get(index)
                        if previous_options is None or assign_category_slot(previous_options, visited):
                            assigned_slots[index] = options
                            return True
                    return False
                if any(
                    not assign_category_slot(options, set())
                    for options in requirement_options
                ):
                    continue
                outstanding_categories = [
                    (category, minimum - projected_counts[category])
                    for category, minimum in rules.minimum_primary_category_counts.items()
                    if projected_counts[category] < minimum
                ]
                if len(outstanding_categories) > 1:
                    joint_options = []
                    for category, needed in outstanding_categories:
                        options = tuple(
                            (other_index, future_slot_index)
                            for other_index, other in enumerate(remaining_candidates)
                            if other_index != candidate_index
                            and other.primary_category == category
                            and not find_conflicting_tags(other, future_tags)
                            for future_slot_index, future_slot in enumerate(pending_slots)
                            if future_slot.matches_candidate(other)
                        )
                        joint_options.extend([options] * needed)
                    joint_options.sort(key=len)
                    search_nodes = [0]
                    def can_jointly_reserve(index, occupied_slots, used_indices, reserved_tags):
                        search_nodes[0] += 1
                        if search_nodes[0] > 1500:
                            return None
                        if index == len(joint_options):
                            return True
                        for other_index, future_slot_index in joint_options[index]:
                            if other_index in used_indices or future_slot_index in occupied_slots:
                                continue
                            other = remaining_candidates[other_index]
                            if find_conflicting_tags(other, reserved_tags):
                                continue
                            result = can_jointly_reserve(
                                index + 1,
                                occupied_slots | {future_slot_index},
                                used_indices | {other_index},
                                reserved_tags | other.all_hard_unique_tags,
                            )
                            if result is True:
                                return True
                            if result is None:
                                return None
                        return False
                    if can_jointly_reserve(0, frozenset(), frozenset(), future_tags) is False:
                        continue

            secondary_count = (
                count_secondary_pet_routes(selected_candidates)
                + secondary_pet_route_count(candidate)
            )

            if secondary_count < rules.secondary_pet_routes_min:
                reserved_tags = reserve_candidate_tags(
                    candidate,
                    used_tags,
                )

                future_pet_candidates = [
                    other_candidate
                    for other_index, other_candidate in enumerate(
                        remaining_candidates
                    )
                    if other_index != candidate_index
                    and secondary_pet_route_count(other_candidate) > 0
                    and (
                        rules.secondary_pet_routes_min - secondary_count != 1
                        or future_pet_route_preserves_category_capacity(
                            other_candidate,
                            (*selected_candidates, candidate),
                            pending_slots,
                            rules,
                        )
                    )
                    and not find_conflicting_tags(
                        other_candidate,
                        reserved_tags,
                    )
                    and any(
                        future_slot.matches_candidate(other_candidate)
                        for future_slot in pending_slots
                    )
                ]

                candidate_capacity = sum(
                    sorted(
                        (
                            secondary_pet_route_count(other)
                            for other in future_pet_candidates
                        ),
                        reverse=True,
                    )[:len(pending_slots)]
                )

                slot_capacity = sum(
                    max(
                        (
                            secondary_pet_route_count(other)
                            for other in future_pet_candidates
                            if future_slot.matches_candidate(other)
                        ),
                        default=0,
                    )
                    for future_slot in pending_slots
                )

                if (
                    secondary_count
                    + min(candidate_capacity, slot_capacity)
                    < rules.secondary_pet_routes_min
                ):
                    continue

            selected_candidate = candidate
            selected_candidate_index = candidate_index
            break

        if selected_candidate is None:
            slot_description = (
                f"{slot.point_value}-point flex slot"
                if slot.is_flex
                else (
                    f"{slot.point_value}-point "
                    f"{slot.required_category.value} slot"
                )
            )

            raise BoardAssemblyError(
                f"Could not fill generated board {slot_description}."
            )

        used_tags = reserve_candidate_tags(
            selected_candidate,
            used_tags
        )
        selected_candidates.append(
            selected_candidate
        )
        remaining_candidates.pop(
            selected_candidate_index
        )

    errors = validate_generated_board_candidates(
        selected_candidates,
        rules
    )

    if errors:
        raise BoardAssemblyError(
            "; ".join(errors)
        )

    return GeneratedBoard(
        candidates=tuple(selected_candidates),
        used_hard_unique_tags=used_tags
    )
