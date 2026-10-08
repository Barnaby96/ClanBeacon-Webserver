from utils.board_generation import canonical_id


_SKILL_WOM_METRIC_OVERRIDES = {
    "runecraft": "runecrafting",
}


def get_skill_wom_metric_id(skill_id):
    skill_id = canonical_id(skill_id)

    if not skill_id:
        raise ValueError(
            "A skill ID is required to resolve a WOM metric."
        )

    return _SKILL_WOM_METRIC_OVERRIDES.get(
        skill_id,
        skill_id,
    )
