"""Sourced OSRS training-method estimates."""
from utils.board_generation import AccessProfile

FLY_FISHING_METHOD = {
    "method_id": "fly_fishing_standard",
    "skill_id": "fishing",
    "name": "Fly fishing (no tick manipulation)",
    "access_profile": AccessProfile(effective_skill_requirements={"fishing": 20}),
    "xp_per_hour_by_level": {20: 13000, 30: 25000, 40: 30000, 50: 34000, 60: 37000, 70: 41000, 80: 44000, 90: 47000, 99: 50000},
    "source_url": "https://oldschool.runescape.wiki/w/Pay-to-play_Fishing_training",
}
