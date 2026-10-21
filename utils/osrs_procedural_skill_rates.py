from decimal import Decimal

def resolve_skill_xp_rate(skill_id, skill_level, rates):
    """Select the best unlocked supplied XP rate, or None."""
    if not isinstance(skill_level, int) or isinstance(skill_level, bool):
        return None
    options = rates.get(skill_id) if isinstance(rates, dict) else None
    if not isinstance(options, dict):
        return None
    eligible = [level for level in options if type(level) is int and level <= skill_level]
    if not eligible:
        return None
    return Decimal(str(options[max(eligible)]))

def assess_training_method_access(profile, skill_levels, confirmed_access_flags=(), method_id=None, confirmed_method_ids=()):
    from utils.board_generation import AccessFlag
    unknown = False
    for skill, minimum in profile.effective_skill_requirements.items():
        level = skill_levels.get(skill) if isinstance(skill_levels, dict) else None
        if type(level) is not int or level < 0:
            unknown = True
        elif level < minimum:
            return "inaccessible"
    if unknown:
        return "unknown"
    gates = {AccessFlag.QUEST_LOCKED, AccessFlag.DIARY_LOCKED, AccessFlag.MINIGAME_UNLOCK, AccessFlag.RAID_ACCESS, AccessFlag.MEMBERS_AREA}
    if method_id is not None and (profile.access_flags & gates):
        return "accessible" if method_id in (confirmed_method_ids or ()) else "unknown"
    return "accessible" if (profile.access_flags & gates) <= set(confirmed_access_flags) else "unknown"

def select_training_method_rate(methods, skill_levels, confirmed_method_ids=()):
    """Return the best accessible method and unknown method IDs."""
    selected = None
    unknown = []
    for method_id, rate, profile in methods:
        status = assess_training_method_access(profile, skill_levels, method_id=method_id, confirmed_method_ids=confirmed_method_ids)
        if status == "unknown":
            unknown.append(method_id)
        elif status == "accessible":
            if isinstance(rate, bool):
                raise ValueError("Invalid training rate.")
            try:
                value = Decimal(str(rate))
            except (ArithmeticError, TypeError, ValueError) as error:
                raise ValueError("Invalid training rate.") from error
            if not value.is_finite() or value <= 0:
                raise ValueError("Invalid training rate.")
            if selected is None or value > selected[1]:
                selected = (method_id, value)
    return selected, tuple(unknown)

def select_training_method_rate_from_catalogue(methods, skill_levels, confirmed_method_ids=()):
    usable, unknown = [], []
    levels = skill_levels if isinstance(skill_levels, dict) else {}
    for method in methods:
        method_id = method["method_id"]
        state = assess_training_method_access(method["access_profile"], levels, method_id=method_id, confirmed_method_ids=confirmed_method_ids)
        if state == "unknown":
            unknown.append(method_id)
        elif state == "accessible":
            skill_id = method["skill_id"]
            rate = resolve_skill_xp_rate(skill_id, levels.get(skill_id), {skill_id: method["xp_per_hour_by_level"]})
            if rate is not None:
                usable.append((method_id, rate, method["access_profile"]))
    selected, remaining_unknown = select_training_method_rate(usable, levels, confirmed_method_ids=confirmed_method_ids)
    return selected, tuple(unknown) + remaining_unknown
