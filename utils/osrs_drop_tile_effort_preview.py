from dataclasses import dataclass
from itertools import zip_longest
from decimal import Decimal

from utils.osrs_drop_group_data import DROP_GROUP_DATA
from utils.osrs_drop_groups import DropGroupDefinition
from utils.osrs_drop_tile_source_effort import get_drop_tile_source_effort_profile
from utils.osrs_drop_tile_effort import (
    DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
    DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
    estimate_group_unique_tile_effort,
    estimate_specific_drop_tile_effort_from_rate,
    suggest_drop_tile_point_value,
)
from utils.osrs_tile_template_expansion import (
    build_drop_group_tile_audit_rows,
    build_drop_id_source_id_map,
)


@dataclass(frozen=True)
class DropTileEffortPreviewRow:
    tile_mode: str
    drop_group_id: str
    display_name: str
    source_id: str
    source_name: str
    target: int | None = None
    drop_id: str | None = None
    drop_name: str | None = None
    drop_rate: str = ""
    expected_rolls: Decimal | None = None
    total_effort: Decimal | None = None
    suggested_point_value: int | None = None
    raw_suggested_point_value: int | None = None
    minimum_point_value: int | None = None
    parseable: bool = False
    reason: str = ""
    access_requirement_multiplier: Decimal = Decimal("1")
    source_difficulty_multiplier: Decimal = Decimal("1")
    source_effort_reason: str = ""

    @property
    def expected_rolls_display(self):
        return format_effort_decimal(
            self.expected_rolls
        )

    @property
    def total_effort_display(self):
        return format_effort_decimal(
            self.total_effort
        )

    @property
    def access_requirement_multiplier_display(self):
        return format_effort_decimal(
            self.access_requirement_multiplier
        )

    @property
    def source_difficulty_multiplier_display(self):
        return format_effort_decimal(
            self.source_difficulty_multiplier
        )


def build_drop_group_definitions_by_id(drop_groups):
    return {
        definition.drop_group_id: definition
        for definition in (
            DropGroupDefinition.from_data_record(group)
            for group in drop_groups
        )
    }


def format_effort_decimal(value):
    if value is None:
        return "Review"

    value = Decimal(value)

    if value == value.to_integral_value():
        return f"{int(value):,}"

    return format(
        value.quantize(
            Decimal("0.01")
        ),
        ",f",
    ).rstrip("0").rstrip(".")


def format_joined(values):
    return ", ".join(
        value
        for value in values
        if value
    )


def apply_minimum_point_value(point_value, minimum_point_value):
    if point_value is None:
        return minimum_point_value

    if minimum_point_value is None:
        return point_value

    return max(
        point_value,
        minimum_point_value,
    )


def get_drop_group_effort_profile(drop_group):
    if len(drop_group.source_ids) == 1:
        return get_drop_tile_source_effort_profile(
            drop_group.source_ids[0]
        )

    if any(
        source_id in {
            "artio",
            "callisto",
            "calvarion",
            "calvar'ion",
            "chaos_fanatic",
            "crazy_archaeologist",
            "scorpia",
            "spindel",
            "venenatis",
            "vetion",
            "vet'ion",
        }
        for source_id in drop_group.source_ids
    ):
        return get_drop_tile_source_effort_profile(
            "wilderness_multi_source"
        )

    return None


def iter_group_unique_effort_preview_rows(drop_group, max_target=5):
    max_target = min(
        max_target,
        len(
            drop_group.distinct_drop_ids
        ),
    )

    for target in range(
        1,
        max_target + 1,
    ):
        source_effort_profile = get_drop_group_effort_profile(
            drop_group
        )

        effort_kwargs = {}
        access_requirement_multiplier = Decimal("1")
        source_difficulty_multiplier = Decimal("1")
        source_effort_reason = ""
        minimum_point_value = None

        if source_effort_profile is not None:
            access_requirement_multiplier = source_effort_profile.access_requirement_multiplier
            source_difficulty_multiplier = source_effort_profile.source_difficulty_multiplier
            source_effort_reason = source_effort_profile.reason
            minimum_point_value = source_effort_profile.minimum_point_value
            effort_kwargs = {
                "access_requirement_multiplier": access_requirement_multiplier,
                "source_difficulty_multiplier": source_difficulty_multiplier,
            }

        effort = estimate_group_unique_tile_effort(
            drop_group,
            target,
            **effort_kwargs,
        )

        raw_suggested_point_value = suggest_drop_tile_point_value(
            effort.total_effort
        )

        yield DropTileEffortPreviewRow(
            tile_mode=DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
            drop_group_id=drop_group.drop_group_id,
            display_name=drop_group.display_name,
            source_id=format_joined(
                drop_group.source_ids
            ),
            source_name=format_joined(
                drop_group.source_names
            ),
            target=target,
            expected_rolls=effort.expected_rolls,
            total_effort=effort.total_effort,
            suggested_point_value=apply_minimum_point_value(
                raw_suggested_point_value,
                minimum_point_value,
            ),
            raw_suggested_point_value=raw_suggested_point_value,
            minimum_point_value=minimum_point_value,
            parseable=effort.parseable,
            reason=effort.reason,
            access_requirement_multiplier=access_requirement_multiplier,
            source_difficulty_multiplier=source_difficulty_multiplier,
            source_effort_reason=source_effort_reason,
        )


def iter_specific_drop_effort_preview_rows(
    drop_group,
    drop_id_source_ids,
):
    source_ids = tuple(
        drop_group.source_ids
    )

    if len(source_ids) != 1:
        return

    source_id = source_ids[0]
    source_name = (
        drop_group.source_names[0]
        if drop_group.source_names
        else source_id
    )

    for drop_id, drop_name, drop_rate in zip_longest(
        drop_group.distinct_drop_ids,
        drop_group.distinct_drop_names,
        drop_group.distinct_drop_rates,
        fillvalue="",
    ):
        if not drop_id:
            continue

        if drop_id_source_ids.get(drop_id) != frozenset((source_id,)):
            continue

        source_effort_profile = get_drop_tile_source_effort_profile(
            source_id
        )

        effort = estimate_specific_drop_tile_effort_from_rate(
            drop_rate,
            access_requirement_multiplier=source_effort_profile.access_requirement_multiplier,
            source_difficulty_multiplier=source_effort_profile.source_difficulty_multiplier,
        )

        raw_suggested_point_value = suggest_drop_tile_point_value(
            effort.total_effort
        )

        yield DropTileEffortPreviewRow(
            tile_mode=DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
            drop_group_id=drop_group.drop_group_id,
            display_name=drop_group.display_name,
            source_id=source_id,
            source_name=source_name,
            drop_id=drop_id,
            drop_name=drop_name,
            drop_rate=drop_rate,
            expected_rolls=effort.expected_rolls,
            total_effort=effort.total_effort,
            suggested_point_value=apply_minimum_point_value(
                raw_suggested_point_value,
                source_effort_profile.minimum_point_value,
            ),
            raw_suggested_point_value=raw_suggested_point_value,
            minimum_point_value=source_effort_profile.minimum_point_value,
            parseable=effort.parseable,
            reason=effort.reason,
            access_requirement_multiplier=source_effort_profile.access_requirement_multiplier,
            source_difficulty_multiplier=source_effort_profile.source_difficulty_multiplier,
            source_effort_reason=source_effort_profile.reason,
        )


def build_drop_tile_effort_preview_rows(
    drop_groups=None,
    include_group_unique_tiles=True,
    include_specific_drop_tiles=True,
    max_group_target=5,
):
    if drop_groups is None:
        drop_groups = DROP_GROUP_DATA

    definitions_by_id = build_drop_group_definitions_by_id(
        drop_groups
    )
    drop_id_source_ids = build_drop_id_source_id_map(
        drop_groups
    )
    audit_rows = build_drop_group_tile_audit_rows(
        drop_groups
    )

    rows = []

    for audit_row in audit_rows:
        drop_group = definitions_by_id.get(
            audit_row.drop_group_id
        )

        if drop_group is None:
            continue

        if (
            include_group_unique_tiles
            and audit_row.supports_group_unique_tiles
        ):
            rows.extend(
                iter_group_unique_effort_preview_rows(
                    drop_group,
                    max_target=max_group_target,
                )
            )

        if (
            include_specific_drop_tiles
            and audit_row.supports_specific_drop_tiles
        ):
            rows.extend(
                iter_specific_drop_effort_preview_rows(
                    drop_group,
                    drop_id_source_ids,
                )
            )

    return tuple(rows)
