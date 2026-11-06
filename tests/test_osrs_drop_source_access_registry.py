"""Reviewed source-access metadata regressions.

Source-access reviews are independent of evidence that
a particular monster drops a particular item.
"""

from utils.board_generation import AccessFlag


def _vorkath_review():
    return {
        "source_id": "vorkath",
        "content_id": "vorkath",
        "requirements_reviewed": True,
        "evidence_refs": (
            "test:reviewed-vorkath-access-requirements",
        ),
    }


def test_reviewed_source_reuses_curated_quest_requirements():
    from utils.osrs_drop_source_access_registry import (
        build_reviewed_drop_source_access_profiles,
    )
    from utils.osrs_player_access import (
        assess_player_source_access,
    )

    profiles = build_reviewed_drop_source_access_profiles(
        ("vorkath", "black_dragon"),
        access_review_records=(
            _vorkath_review(),
        ),
    )

    # Black dragon has no reviewed curated access
    # metadata and must not be silently approved.
    assert set(profiles) == {"vorkath"}

    metadata = profiles["vorkath"]

    assert metadata["requirements_verified"] is True

    profile = metadata["access_profile"]

    assert AccessFlag.QUEST_LOCKED in profile.access_flags

    # The existing resolver includes Dragon Slayer II
    # and all its curated prerequisite quest skills.
    requirements = dict(
        profile.effective_skill_requirements
    )

    assert len(requirements) == 18

    # Quest completion is presumed from skill levels.
    assert assess_player_source_access(
        profile,
        requirements,
        source_id="vorkath",
        requirements_verified=metadata[
            "requirements_verified"
        ],
    ) == "accessible"


def test_unreviewed_or_missing_source_data_grants_no_access():
    from utils.osrs_drop_source_access_registry import (
        build_reviewed_drop_source_access_profiles,
    )

    build = build_reviewed_drop_source_access_profiles

    # A curated content profile alone is not
    # proof that every access requirement was reviewed.
    assert build(("vorkath",)) == {}

    assert build(
        ("vorkath",),
        access_review_records=(
            {
                **_vorkath_review(),
                "requirements_reviewed": False,
            },
        ),
    ) == {}

    # Evidence references are mandatory for reviews.
    assert build(
        ("vorkath",),
        access_review_records=(
            {
                **_vorkath_review(),
                "evidence_refs": (),
            },
        ),
    ) == {}

    # An unknown content ID cannot be treated
    # as unrestricted or quest-free.
    assert build(
        ("black_dragon",),
        access_review_records=(
            {
                "source_id": "black_dragon",
                "content_id": "not_curated",
                "requirements_reviewed": True,
                "evidence_refs": (
                    "test:unknown-content",
                ),
            },
        ),
    ) == {}

    # A review must not approve a different source
    # merely because that source was requested.
    assert build(
        ("black_dragon",),
        access_review_records=(
            _vorkath_review(),
        ),
    ) == {}


def test_source_access_review_does_not_verify_item_drops():
    from utils.osrs_drop_source_access_registry import (
        build_reviewed_drop_source_access_profiles,
    )
    from utils.osrs_drop_source_coverage import (
        select_source_verified_nonunique_drops,
    )

    profiles = build_reviewed_drop_source_access_profiles(
        ("vorkath",),
        access_review_records=(
            _vorkath_review(),
        ),
    )

    assert profiles["vorkath"]["requirements_verified"]

    rows = (
        {
            "drop_id": "synthetic_rare_drop",
            "source_ids": ("vorkath",),
            "include_in_unique_group": False,
        },
    )

    # Knowing how to access Vorkath does not establish
    # that Vorkath drops this synthetic item.
    assert not select_source_verified_nonunique_drops(
        rows,
        verification_records=(),
    )
