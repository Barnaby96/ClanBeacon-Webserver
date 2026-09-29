from collections import Counter
from dataclasses import dataclass, field
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
    primary_pet_tiles_target: int = 2
    primary_pet_tiles_max: int = 2
    secondary_pet_routes_min: int = 2
    secondary_pet_routes_target: int = 4
    secondary_pet_routes_max: int = 6

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
        slots = []

        for point_value in sorted(
            self.points_distribution
        ):
            for category in self.required_categories_by_point.get(
                point_value,
                ()
            ):
                slots.append(
                    BoardSlot(
                        point_value=point_value,
                        required_category=category
                    )
                )

            for _ in range(
                self.flex_slots_by_point.get(
                    point_value,
                    0
                )
            ):
                slots.append(
                    BoardSlot(
                        point_value=point_value
                    )
                )

        return tuple(slots)


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
    hard_unique_tags: FrozenSet[str] = field(default_factory=frozenset)

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


def assemble_board_candidates(candidates, rules=None):
    if rules is None:
        rules = BoardGenerationRules()

    remaining_candidates = list(candidates)
    selected_candidates = []
    used_tags = frozenset()

    for slot in rules.build_slots():
        selected_candidate = None

        for candidate in remaining_candidates:
            if not slot.matches_candidate(candidate):
                continue

            if find_conflicting_tags(candidate, used_tags):
                continue

            if not candidate_fits_pet_limits(
                candidate,
                selected_candidates,
                rules
            ):
                continue

            selected_candidate = candidate
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
        remaining_candidates.remove(
            selected_candidate
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

