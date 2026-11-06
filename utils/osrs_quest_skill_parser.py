"""Extract structured skill requirements from saved OSRS Wiki wikitext.

This parser is intentionally not an eligibility evaluator.
Compound conditions and ambiguous syntax remain for review.
"""

import re


SKILLS = frozenset({
    "agility", "attack", "construction", "cooking",
    "crafting", "defence", "farming", "firemaking",
    "fishing", "fletching", "herblore", "hitpoints",
    "hunter", "magic", "mining", "prayer", "ranged",
    "runecraft", "sailing", "slayer", "smithing",
    "strength", "thieving", "woodcutting",
})

SCP_START = re.compile(
    r"\{\{\s*SCP\s*\|",
    re.IGNORECASE,
)

SCP_TEMPLATE = re.compile(
    r"\{\{\s*SCP\s*\|([^{}\r\n]*)\}\}",
    re.IGNORECASE,
)


HTML_COMMENT = re.compile(
    r"<!--.*?-->",
    re.DOTALL,
)

REFERENCE_NOTE = re.compile(
    r"<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>",
    re.IGNORECASE | re.DOTALL,
)

REFN_START = re.compile(
    r"\{\{\s*Refn\s*\|",
    re.IGNORECASE,
)

CONDITION_PATTERNS = {
    "ALTERNATIVE": re.compile(
        r"\bor\b|\beither\b|\balternativ(?:e|ely)\b|"
        r"\binstead\b|\bunless\b",
        re.IGNORECASE,
    ),
    "BYPASS": re.compile(
        r"\bbypass(?:ed|able)?\b",
        re.IGNORECASE,
    ),
    "OPTIONAL": re.compile(
        r"\boptional\b|\brecommended\b|"
        r"\bif desired\b|\bif you wish\b",
        re.IGNORECASE,
    ),
    "CONDITIONAL": re.compile(
        r"\bif\b|\bonly\b|\bdepending\b|"
        r"\bwithout\b",
        re.IGNORECASE,
    ),
}


def classify_skill_source_condition(line):
    """Identify conditional wording and its source location.

    This is a conservative screening tool, not a Wiki markup
    interpreter or an eligibility-rule evaluator.
    """
    comments = " ".join(HTML_COMMENT.findall(line))
    main = HTML_COMMENT.sub(" ", line)

    reference_notes = " ".join(REFERENCE_NOTE.findall(main))
    main = REFERENCE_NOTE.sub(" ", main)

    refn_match = REFN_START.search(main)

    if refn_match:
        reference_notes += " " + main[refn_match.start():]
        main = main[:refn_match.start()]

    def flags(text):
        return [
            name
            for name, pattern in CONDITION_PATTERNS.items()
            if pattern.search(text)
        ]

    main_flags = flags(main)
    note_flags = flags(reference_notes)
    comment_flags = flags(comments)

    if not (main_flags or note_flags or comment_flags):
        return None

    scp_count = len(SCP_TEMPLATE.findall(line))

    if scp_count > 1 and "ALTERNATIVE" in main_flags:
        kind = "COMPOUND_ALTERNATIVE"
    elif (
        "BYPASS" in main_flags
        or "BYPASS" in note_flags
    ):
        kind = "BYPASSABLE"
    elif (
        "ALTERNATIVE" in main_flags
        or re.search(
            r"\botherwise\b",
            reference_notes,
            re.IGNORECASE,
        )
    ):
        kind = "ALTERNATIVE"
    elif main_flags or note_flags:
        kind = "CONTEXTUAL_REVIEW"
    else:
        kind = "COMMENT_ONLY"

    return {
        "condition_kind": kind,
        "main_text_flags": main_flags,
        "footnote_flags": note_flags,
        "comment_flags": comment_flags,
        "main_text": main.strip(),
        "footnote_text": reference_notes.strip(),
        "comment_text": comments.strip(),
        "needs_review": kind != "COMMENT_ONLY",
        "verification_status": "UNVERIFIED",
    }


def annotation_value(line, template_name):
    """Return yes, no or unknown, plus the original annotation."""
    pattern = re.compile(
        r"\{\{\s*"
        + re.escape(template_name)
        + r"\s*\|([^{}\r\n]*)\}\}",
        re.IGNORECASE,
    )

    values = [
        match.group(1).strip()
        for match in pattern.finditer(line)
    ]

    if len(values) != 1:
        return "unknown", values

    raw = values[0]
    normalised = raw.casefold()

    # A single trailing empty argument is tolerated only
    # for Questreqstart. Other unexpected annotations
    # must remain unknown rather than being guessed.
    if (
        template_name.casefold() == "questreqstart"
        and normalised in ("yes|", "no|")
    ):
        return normalised[:-1], values

    if normalised in ("yes", "no"):
        return normalised, values

    return "unknown", values


def parse_skill_requirements(quest_id, requirements_wikitext):
    """Parse unambiguous levels; retain exceptions for review."""
    result = {
        "quest_id": quest_id,
        "skills": [],
        "combat_levels": [],
        "quest_points": [],
        "review_items": [],
        "conditional_skill_lines": [],
    }

    if requirements_wikitext is None:
        return result

    if not isinstance(requirements_wikitext, str):
        raise TypeError("Requirements wikitext must be a string.")

    def add_review(kind, line_number, text):
        result["review_items"].append({
            "type": kind,
            "line_number": line_number,
            "source_text": text,
        })

    for line_number, line in enumerate(
        requirements_wikitext.splitlines(), 1
    ):
        markers = len(SCP_START.findall(line))

        if markers == 0:
            continue

        condition = classify_skill_source_condition(line)

        if condition is not None:
            result["conditional_skill_lines"].append({
                "line_number": line_number,
                "source_text": line,
                **condition,
            })

        matches = list(SCP_TEMPLATE.finditer(line))

        if len(matches) != markers:
            add_review("UNRECOGNISED_SCP", line_number, line)
            continue

        # Multiple level requirements on one line may be OR
        # alternatives. Never interpret them automatically as AND.
        if len(matches) > 1:
            add_review("COMPOUND_SCP", line_number, line)
            continue

        parts = [
            part.strip()
            for part in matches[0].group(1).split("|")
        ]

        name = parts[0].casefold() if parts else ""
        level_text = parts[1] if len(parts) > 1 else ""

        if not re.fullmatch(r"[0-9]+", level_text):
            add_review("NON_NUMERIC_SCP", line_number, line)
            continue

        level = int(level_text)

        boostable, boostable_raw = annotation_value(
            line, "Boostable"
        )
        start, start_raw = annotation_value(
            line, "Questreqstart"
        )

        requirement = {
            "level": level,
            "boostable": boostable,
            "required_to_start": start,
            "line_number": line_number,
            "source_text": line,
            "condition_kind": (
                condition["condition_kind"]
                if condition is not None
                else "NONE_DETECTED"
            ),
            "needs_condition_review": (
                condition["needs_review"]
                if condition is not None
                else False
            ),
            "verification_status": "UNVERIFIED",
        }

        if name == "quest":
            result["quest_points"].append(requirement)

        elif name == "combat":
            # Combat level is a derived player statistic,
            # not an individual skill. Keep it separate
            # from ordinary skill requirements.
            result["combat_levels"].append({
                "stat": "combat_level",
                **requirement,
            })

            # Preserve the existing review flag until the
            # observation has been independently reviewed.
            add_review("COMBAT_LEVEL", line_number, line)
            continue

        elif name in SKILLS:
            result["skills"].append({
                "skill": name,
                **requirement,
            })

        else:
            add_review("UNKNOWN_SKILL", line_number, line)
            continue

        for label, raw_values in (
            ("BOOSTABLE", boostable_raw),
            ("QUESTREQSTART", start_raw),
        ):
            allowed_values = {"yes", "no", ""}

            # Match the narrowly permitted Questreqstart
            # trailing-empty-argument interpretation.
            if label == "QUESTREQSTART":
                allowed_values.update({"yes|", "no|"})

            if (
                raw_values
                and (
                    len(raw_values) != 1
                    or raw_values[0].casefold()
                    not in allowed_values
                )
            ):
                add_review(
                    "UNUSUAL_" + label,
                    line_number,
                    line,
                )

    return result