from utils.osrs_tile_catalogue import get_curated_tile_candidates
from utils.osrs_tile_catalogue_validation import (
    build_catalogue_summary,
    format_catalogue_summary,
)


def get_curated_tile_catalogue_summary(
    capability_profiles=None,
):
    return build_catalogue_summary(
        get_curated_tile_candidates(),
        capability_profiles=capability_profiles,
    )


def get_curated_tile_catalogue_preview():
    return format_catalogue_summary(
        get_curated_tile_catalogue_summary()
    )


def print_curated_tile_catalogue_preview():
    print(
        get_curated_tile_catalogue_preview()
    )


if __name__ == "__main__":
    print_curated_tile_catalogue_preview()
