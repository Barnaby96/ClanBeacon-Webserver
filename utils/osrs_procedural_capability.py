"""Read WOM capabilities without treating missing values as zero."""


def _get_wom_measurement(player_data, section_name, metric_name, field_name):
    if not isinstance(player_data, dict):
        return None

    snapshot = player_data.get("latestSnapshot")
    if not isinstance(snapshot, dict):
        return None

    data = snapshot.get("data")
    if not isinstance(data, dict):
        return None

    section = data.get(section_name)
    if not isinstance(section, dict):
        return None

    metric = section.get(metric_name)
    if not isinstance(metric, dict):
        return None

    value = metric.get(field_name)

    if type(value) is not int or value < 0:
        return None

    return value


def get_wom_skill_level(player_data, skill_name):
    """Return a recorded skill level, or None when unknown."""
    return _get_wom_measurement(
        player_data,
        "skills",
        skill_name,
        "level",
    )


def get_wom_boss_kills(player_data, boss_name):
    """Return recorded boss kills, or None when unknown."""
    return _get_wom_measurement(
        player_data,
        "bosses",
        boss_name,
        "kills",
    )