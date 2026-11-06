"""Reviewed OSRS acquisition-source access metadata.

This module maps explicitly reviewed source-access records to
existing curated content access profiles.

It does not verify whether a source drops a particular item.

A review declaration and its evidence references must be
independently checked before real production approval.
"""

from collections.abc import Mapping

from utils.osrs_content_access import (
    build_access_profile_for_content,
    get_curated_content_access_requirements,
)


def build_reviewed_drop_source_access_profiles(
    source_ids,
    *,
    access_review_records=(),
):
    """Return access profiles for explicitly reviewed sources.

    Unknown, malformed, ambiguous or unreviewed records never
    establish source accessibility.

    Quest requirements are inherited from the existing curated
    content-access and prerequisite-quest resolvers.
    """
    if (
        not isinstance(source_ids, (tuple, list, set, frozenset))
        or not isinstance(
            access_review_records,
            (tuple, list),
        )
    ):
        return {}

    if any(
        not isinstance(source_id, str)
        or not source_id
        or source_id != source_id.strip()
        for source_id in source_ids
    ):
        return {}

    requested_source_ids = set(source_ids)

    if not requested_source_ids:
        return {}

    curated_content_ids = {
        requirement.content_id
        for requirement in get_curated_content_access_requirements()
    }

    records_by_source = {}
    ambiguous_source_ids = set()

    for record in access_review_records:
        if not isinstance(record, Mapping):
            return {}

        source_id = record.get("source_id")

        if not isinstance(source_id, str) or not source_id:
            return {}

        if source_id != source_id.strip():
            return {}

        if source_id in records_by_source:
            ambiguous_source_ids.add(source_id)
        else:
            records_by_source[source_id] = record

    profiles = {}

    for source_id in requested_source_ids:
        if source_id in ambiguous_source_ids:
            continue

        record = records_by_source.get(source_id)

        if record is None:
            continue

        # Do not allow a review for one monster to approve
        # an unrelated source through a substituted content ID.
        content_id = record.get("content_id")

        if content_id != source_id:
            continue

        if content_id not in curated_content_ids:
            continue

        if record.get("requirements_reviewed") is not True:
            continue

        evidence_refs = record.get("evidence_refs")

        if not isinstance(evidence_refs, (tuple, list)):
            continue

        if not evidence_refs:
            continue

        if any(
            not isinstance(ref, str)
            or not ref.strip()
            for ref in evidence_refs
        ):
            continue

        # The existing content-access builder resolves all
        # prerequisite quest skill requirements.
        #
        # This is a source-access assessment only; it does not
        # approve any DROP-to-source relationship.
        access_profile = build_access_profile_for_content(
            content_id
        )

        profiles[source_id] = {
            "access_profile": access_profile,
            "requirements_verified": True,
        }

    return profiles
