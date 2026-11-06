"""Source coverage information for OSRS drop records.

Recorded sources are imported spreadsheet observations.
They are not necessarily exhaustive or independently verified.

Do not use this mapping alone to activate generated objectives
or certify hard source-uniqueness coverage.
"""


def build_recorded_drop_source_id_map(rows):
    """Collect recorded source IDs for each drop without verifying them."""
    source_ids_by_drop_id = {}

    for row in rows:
        drop_id = row.get("drop_id")

        if not drop_id:
            continue

        source_ids = row.get("source_ids") or ()

        recorded_sources = source_ids_by_drop_id.setdefault(
            drop_id,
            set(),
        )

        recorded_sources.update(
            source_id
            for source_id in source_ids
            if source_id
        )

    return {
        drop_id: frozenset(source_ids)
        for drop_id, source_ids in source_ids_by_drop_id.items()
    }


def build_verified_drop_source_id_map(records=()):
    """Return explicitly verified, fully covered acquisition sources.

    Spreadsheet-recorded sources are not automatically verified.
    Evidence references are required but are not independently checked
    by this function.
    """
    verified_sources = {}
    seen_drop_ids = set()

    for record in records:
        if not isinstance(record, dict):
            raise ValueError(
                "Verification records must be dictionaries."
            )

        drop_id = record.get("drop_id")

        if not isinstance(drop_id, str) or not drop_id.strip():
            continue

        if drop_id in seen_drop_ids:
            raise ValueError(
                f"Duplicate verification record for {drop_id}."
            )

        seen_drop_ids.add(drop_id)

        if record.get("verification_status") != "verified":
            continue

        if record.get("coverage_complete") is not True:
            continue

        source_ids = record.get("source_ids")
        evidence_refs = record.get("evidence_refs")

        if not isinstance(source_ids, (tuple, list, set, frozenset)):
            continue

        if not isinstance(evidence_refs, (tuple, list, set, frozenset)):
            continue

        if not source_ids or not evidence_refs:
            continue

        if not all(
            isinstance(source_id, str)
            and source_id
            and source_id == source_id.strip()
            for source_id in source_ids
        ):
            continue

        if not all(
            isinstance(reference, str)
            and reference.strip()
            for reference in evidence_refs
        ):
            continue

        verified_sources[drop_id] = frozenset(source_ids)

    return verified_sources


def apply_verified_drop_source_tags(candidate, verification_records):
    """Reserve all explicitly verified acquisition sources for DROP routes.

    This function validates declared verification records; it does not
    independently establish the accuracy or completeness of OSRS evidence.

    DROP routes without a specific item ID are not supported here.
    Group routes require their own per-item source verification.
    """
    from dataclasses import replace

    from utils.board_generation import (
        TileCategory,
        build_tag,
    )

    verified_sources = build_verified_drop_source_id_map(
        verification_records
    )

    updated_routes = []
    found_drop_route = False

    for route in candidate.routes:
        if route.route_type != TileCategory.DROP:
            updated_routes.append(route)
            continue

        found_drop_route = True

        if not route.drop_id:
            raise ValueError(
                "Verified DROP source tagging requires a specific "
                "drop ID; group-source verification is not implemented."
            )

        if not route.source_id:
            raise ValueError(
                f"DROP route {route.drop_id} has no declared source."
            )

        source_ids = verified_sources.get(route.drop_id)

        if not source_ids:
            raise ValueError(
                f"No complete verified acquisition-source coverage "
                f"for {route.drop_id}."
            )

        if route.source_id not in source_ids:
            raise ValueError(
                f"Declared source {route.source_id} is missing from "
                f"verified coverage for {route.drop_id}."
            )

        source_tags = frozenset(
            build_tag("source", source_id)
            for source_id in source_ids
        )

        if None in source_tags:
            raise ValueError(
                f"Invalid verified source tag for {route.drop_id}."
            )

        updated_routes.append(
            replace(
                route,
                hard_unique_tags=(
                    route.hard_unique_tags | source_tags
                ),
            )
        )

    if not found_drop_route:
        raise ValueError(
            "Candidate has no DROP route requiring source verification."
        )

    return replace(
        candidate,
        routes=tuple(updated_routes),
    )


def select_source_verified_nonunique_drops(
    rows,
    verification_records=(),
):
    """Select non-unique drops with declared complete source coverage.

    Recorded spreadsheet sources are not automatically verified.
    Verification evidence must be reviewed independently before
    real records are approved.

    This checks source eligibility only, not recipe activation,
    difficulty calibration, tracking or access requirements.
    """
    rows = tuple(rows)

    recorded_sources = build_recorded_drop_source_id_map(
        rows
    )

    verified_sources = build_verified_drop_source_id_map(
        verification_records
    )

    eligible_classification = {}

    for row in rows:
        drop_id = row.get("drop_id")

        if not isinstance(drop_id, str) or not drop_id.strip():
            continue

        source_ids = row.get("source_ids")

        valid_source_record = (
            isinstance(source_ids, (tuple, list, set, frozenset))
            and bool(source_ids)
            and all(
                isinstance(source_id, str)
                and bool(source_id.strip())
                and source_id == source_id.strip()
                for source_id in source_ids
            )
        )

        # Every row for the item must explicitly be non-unique
        # and have usable source metadata. Unknown values fail closed.
        eligible_classification[drop_id] = (
            eligible_classification.get(drop_id, True)
            and row.get("include_in_unique_group") is False
            and valid_source_record
        )

    eligible = {}

    for drop_id, source_ids in recorded_sources.items():
        if not eligible_classification.get(drop_id, False):
            continue

        if not source_ids:
            continue

        verified = verified_sources.get(drop_id)

        if not verified:
            continue

        if not source_ids.issubset(verified):
            continue

        # Return the full verified set, including any additional
        # independently documented acquisition sources.
        eligible[drop_id] = verified

    return eligible
