"""Identify quest references in OSRS Wiki requirement text.

This module reports source observations, not verified dependencies.
Do not use its output directly for player or team eligibility.
"""

import re
from html import unescape
from urllib.parse import unquote


WIKI_LINK_PATTERN = re.compile(
    r"\[\[([^\[\]\r\n]+)\]\]"
)

BULLET_PATTERN = re.compile(
    r"^(\*+)\s*(.*)$"
)

EXPLICIT_COMPLETION_PATTERN = re.compile(
    r"^\s*(?:completion of|completed)\b",
    re.IGNORECASE,
)

STARTED_PATTERN = re.compile(
    r"\bstart(?:ed)?\b",
    re.IGNORECASE,
)

PARTIAL_PATTERN = re.compile(
    r"\bpartial(?:ly)?\s+completion\b",
    re.IGNORECASE,
)


def wiki_title_key(value):
    """Normalise a Wiki link target for catalogue matching."""
    value = unquote(unescape(value))
    value = value.split("#", 1)[0]
    value = value.replace("_", " ")
    value = value.replace("’", "'")

    return re.sub(
        r"\s+", " ", value
    ).strip().casefold()


def build_quest_title_lookup(catalogue):
    """Create a unique Wiki-title-to-quest-ID lookup."""
    lookup = {}

    for record in catalogue["quest_entries"]:
        key = wiki_title_key(record["wiki_page_title"])

        if not key or key in lookup:
            raise ValueError(
                f"Duplicate or invalid Wiki title: {key!r}"
            )

        lookup[key] = record["quest_id"]

    return lookup


def classify_reference(text, depth):
    """Classify wording without inferring an eligibility rule."""
    if PARTIAL_PATTERN.search(text):
        return "PARTIAL_COMPLETION"

    if STARTED_PATTERN.search(text):
        return "STARTED_QUEST"

    if EXPLICIT_COMPLETION_PATTERN.match(text):
        return "EXPLICIT_COMPLETION"

    if depth >= 2:
        return "NESTED_CANDIDATE"

    return "OTHER_REFERENCE"


# Reviewed exceptions to otherwise strict direct-link extraction.
# These are source matches, not approved eligibility rules.
# Changes to Wiki wording revert the reference to manual review.
CURATED_DIRECT_ALIAS_TARGETS = {
    (
        "monkey_madness_ii",
        "[[Recipe for Disaster/Freeing_King_Awowogei|Recipe for Disaster]] "
        "(Freeing King [[Awowogei]])",
    ): "recipe_for_disaster_freeing_king_awowogei",
}


COMPLETION_HEADINGS = frozenset({
    "Completion of the following quests:",
    "Completions of the following quests:",
    "Completion of the following quest:",
    "Must have completed the following quests:",
})

MIXED_COMPLETION_HEADING = (
    "Completion (or partial completion where stated) "
    "of the following quests:"
)

PLAIN_QUEST_LINK = re.compile(
    r"^\[\[([^\[\]\r\n]+)\]\]$"
)

TOP_LEVEL_COMPLETION = re.compile(
    r"^(?:completion of|completed)\b",
    re.IGNORECASE,
)


EXPLICIT_UNBULLETED_COMPLETION = re.compile(
    r"^(?:Completion of|Completed|Finished)\s+\[\[([^\[\]\r\n]+)\]\]$",
    re.IGNORECASE,
)


TOP_LEVEL_DIRECT_COMPLETION = re.compile(
    r"^(?:Completion of|Completed)\s+"
    r"(?:\{\{\s*SCP\s*\|\s*Quest\s*\}\}\s*)?"
    r"\[\[(?P<target>[^\[\]\r\n]+)\]\]"
    r"(?:\s+quest|,\s+which requires the following quests:)?"
    r"\s*(?:\{\{\s*Questreqstart\s*\|\s*(?P<start>yes|no)\s*\}\})?$",
    re.IGNORECASE,
)


def extract_direct_prerequisite_candidates(
    quest_id, requirements_wikitext, title_lookup
):
    """Extract simple direct references without approving eligibility.

    Only immediate children of explicit completion headings qualify.
    Other conditions are retained for review or future parsing.
    """
    result = {
        "quest_id": quest_id,
        "direct_candidates": [],
        "inherited_prerequisite_observations": [],
        "direct_review": [],
        "structural_notes": [],
        "mixed_completion_review": [],
        "other_nested_review": [],
        "top_level_completion_review": [],
        "transitive_lines": 0,
    }

    if requirements_wikitext is None:
        return result

    if not isinstance(requirements_wikitext, str):
        raise TypeError("Requirements wikitext must be a string.")

    heading = None
    seen = set()

    for line_number, line in enumerate(
        requirements_wikitext.splitlines(), 1
    ):
        match = BULLET_PATTERN.match(line)

        if not match:
            explicit = EXPLICIT_UNBULLETED_COMPLETION.fullmatch(
                line.strip()
            )

            if explicit is not None:
                wiki_target = explicit.group(1).split("|", 1)[0]
                target_id = title_lookup.get(
                    wiki_title_key(wiki_target)
                )

                if target_id is None:
                    result["top_level_completion_review"].append({
                        "line_number": line_number,
                        "source_text": line,
                        "heading": None,
                        "reason": "UNRESOLVED_UNBULLETED_COMPLETION",
                    })
                    continue

                relationship = (quest_id, target_id)

                if relationship in seen or quest_id == target_id:
                    raise ValueError(
                        f"Invalid direct prerequisite: {relationship}"
                    )

                seen.add(relationship)

                result["direct_candidates"].append({
                    "target_quest_id": target_id,
                    "line_number": line_number,
                    "source_heading": None,
                    "source_text": line,
                    "verification_status": "UNVERIFIED",
                    "resolution_method": (
                        "EXPLICIT_UNBULLETED_COMPLETION"
                    ),
                })

            continue

        depth = len(match.group(1))
        text = match.group(2).strip()

        observation = {
            "line_number": line_number,
            "source_text": line,
            "heading": heading,
        }

        if depth == 1:
            heading = text

            if (
                TOP_LEVEL_COMPLETION.match(text)
                and WIKI_LINK_PATTERN.search(text)
            ):
                recognised = TOP_LEVEL_DIRECT_COMPLETION.fullmatch(
                    text
                )

                if recognised is not None:
                    wiki_target = (
                        recognised.group("target")
                        .split("|", 1)[0]
                        .strip()
                    )
                    target_id = title_lookup.get(
                        wiki_title_key(wiki_target)
                    )

                    if target_id is not None:
                        relationship = (quest_id, target_id)

                        if (
                            relationship in seen
                            or quest_id == target_id
                        ):
                            raise ValueError(
                                "Invalid direct prerequisite: "
                                f"{relationship}"
                            )

                        seen.add(relationship)

                        start_annotation = recognised.group("start")

                        result["direct_candidates"].append({
                            "target_quest_id": target_id,
                            "line_number": line_number,
                            "source_heading": None,
                            "source_text": line,
                            "required_to_start": (
                                start_annotation.upper()
                                if start_annotation is not None
                                else "UNKNOWN"
                            ),
                            "verification_status": "UNVERIFIED",
                            "resolution_method": (
                                "TOP_LEVEL_EXPLICIT_COMPLETION"
                            ),
                        })
                        continue

                result["top_level_completion_review"].append({
                    **observation,
                    "heading": heading,
                    "reason": (
                        "UNRESOLVED_TARGET"
                        if recognised is not None
                        else "COMPLEX_COMPLETION_WORDING"
                    ),
                })

            continue

        if heading == MIXED_COMPLETION_HEADING:
            if depth == 2:
                result["mixed_completion_review"].append(
                    observation
                )
            else:
                result["transitive_lines"] += 1

            continue

        # The Fractured Archive directly requires completing
        # While Guthix Sleeps. The following nested list
        # describes prerequisites inherited through that quest.
        # Only resolved, plain quest links are classified here;
        # changed or unfamiliar wording stays in review.
        if (
            quest_id == "miniquest_the_fractured_archive"
            and heading == (
                "Completion of [[While Guthix Sleeps]], "
                "which requires the following quests:"
            )
            and depth >= 2
            and len(result["direct_candidates"]) == 1
            and result["direct_candidates"][0][
                "target_quest_id"
            ] == "while_guthix_sleeps"
        ):
            inherited_link = PLAIN_QUEST_LINK.fullmatch(text)

            if inherited_link is not None:
                inherited_title = (
                    inherited_link.group(1)
                    .split("|", 1)[0]
                    .strip()
                )

                inherited_id = title_lookup.get(
                    wiki_title_key(inherited_title)
                )

                if (
                    inherited_id is not None
                    and inherited_id != quest_id
                ):
                    result[
                        "inherited_prerequisite_observations"
                    ].append({
                        "target_quest_id": inherited_id,
                        "inherited_via_quest_id": (
                            "while_guthix_sleeps"
                        ),
                        "line_number": line_number,
                        "depth": depth,
                        "source_heading": heading,
                        "source_text": line,
                        "verification_status": "UNVERIFIED",
                    })

                    result["transitive_lines"] += 1
                    continue

        if heading not in COMPLETION_HEADINGS:
            result["other_nested_review"].append(
                observation
            )
            continue

        if depth > 2:
            result["transitive_lines"] += 1
            continue

        # This exact Wiki heading describes prerequisites
        # shared by the five preceding quests. It is not
        # itself a sixth direct quest prerequisite.
        if (
            quest_id == "a_kingdom_divided"
            and heading == "Completion of the following quests:"
            and text == (
                "The above quests all require the following "
                "quests to be completed:"
            )
            and {
                item["target_quest_id"]
                for item in result["direct_candidates"]
            } == {
                "the_depths_of_despair",
                "the_queen_of_thieves",
                "the_ascent_of_arceuus",
                "the_forsaken_tower",
                "tale_of_the_righteous",
            }
            and len(result["direct_candidates"]) == 5
        ):
            result["structural_notes"].append({
                **observation,
                "note_type": "SHARED_PREREQUISITE_HEADING",
                "verification_status": "UNVERIFIED",
            })
            continue

        plain = PLAIN_QUEST_LINK.fullmatch(text)

        if plain is None:
            override_id = CURATED_DIRECT_ALIAS_TARGETS.get(
                (quest_id, text)
            )

            if override_id is not None:
                linked_targets = [
                    target.split("|", 1)[0].strip()
                    for target in WIKI_LINK_PATTERN.findall(text)
                ]

                resolved_ids = {
                    title_lookup.get(wiki_title_key(target))
                    for target in linked_targets
                }
                resolved_ids.discard(None)

                if resolved_ids != {override_id}:
                    raise ValueError(
                        "Curated Wiki alias no longer resolves "
                        f"as expected: {quest_id}"
                    )

                relationship = (quest_id, override_id)

                if relationship in seen or quest_id == override_id:
                    raise ValueError(
                        f"Invalid direct prerequisite: {relationship}"
                    )

                seen.add(relationship)

                result["direct_candidates"].append({
                    "target_quest_id": override_id,
                    "line_number": line_number,
                    "source_heading": heading,
                    "source_text": line,
                    "verification_status": "UNVERIFIED",
                    "resolution_method": "CURATED_WIKI_ALIAS",
                })
                continue

            result["direct_review"].append({
                **observation,
                "reason": "COMPLEX_DIRECT_LINE",
            })
            continue

        wiki_target = plain.group(1).split("|", 1)[0]
        target_id = title_lookup.get(
            wiki_title_key(wiki_target)
        )

        if target_id is None:
            result["direct_review"].append({
                **observation,
                "reason": "UNRESOLVED_QUEST_OR_MINIQUEST",
                "wiki_target": wiki_target,
            })
            continue

        relationship = (quest_id, target_id)

        if relationship in seen:
            raise ValueError(
                f"Duplicate direct prerequisite: {relationship}"
            )

        if quest_id == target_id:
            raise ValueError(
                f"Quest references itself as a prerequisite: {quest_id}"
            )

        seen.add(relationship)

        result["direct_candidates"].append({
            "target_quest_id": target_id,
            "line_number": line_number,
            "source_heading": heading,
            "source_text": line,
            "verification_status": "UNVERIFIED",
        })

    return result


# Audited non-quest Wiki links encountered in progression wording.
# This is deliberately not a universal non-quest catalogue.
# Unknown targets must still enter the review queue.
KNOWN_NON_QUEST_PROGRESSION_LINKS = frozenset(
    wiki_title_key(title)
    for title in (
        "Commorb",
        "Tai Bwo Wannai Cleanup",
        "minigame",
        "Medium Karamja Diary",
        "Balloon transport system",
        "Gnome Stronghold",
    )
)


PROGRESSION_STARTED = re.compile(
    r"\bstart(?:ed|ing)?\b",
    re.IGNORECASE,
)

PROGRESSION_PARTIAL = re.compile(
    r"\bpartial(?:ly)?\s+complet(?:ion|ed)\b",
    re.IGNORECASE,
)

PROGRESSION_MILESTONE = re.compile(
    r"\bup until\b|\bportion\b",
    re.IGNORECASE,
)

PROGRESSION_START_ANNOTATION = re.compile(
    r"\{\{\s*Questreqstart\s*\|([^{}\r\n]*)\}\}",
    re.IGNORECASE,
)


def extract_progression_observations(
    quest_id, requirements_wikitext, title_lookup
):
    """Capture quest progression wording without inferring eligibility.

    Multiple linked targets remain in a single source observation.
    Nested requirements are not promoted to direct dependencies.
    """
    result = {
        "quest_id": quest_id,
        "progression_observations": [],
        "context_notes": [],
        "non_quest_context_notes": [],
        "review_items": [],
    }

    if requirements_wikitext is None:
        return result

    if not isinstance(requirements_wikitext, str):
        raise TypeError("Requirements wikitext must be a string.")

    parents = {}

    for line_number, line in enumerate(
        requirements_wikitext.splitlines(), 1
    ):
        bullet = BULLET_PATTERN.match(line)

        if bullet:
            depth = len(bullet.group(1))
            text = bullet.group(2).strip()

            for previous_depth in list(parents):
                if previous_depth >= depth:
                    del parents[previous_depth]

            ancestors = [
                parents[index]
                for index in sorted(parents)
                if index < depth
            ]

            parents[depth] = text
        else:
            depth = 0
            text = line.strip()
            ancestors = []

        partial = bool(PROGRESSION_PARTIAL.search(text))
        started = bool(PROGRESSION_STARTED.search(text))

        if not partial and not started:
            continue

        wiki_targets = [
            value.split("|", 1)[0].strip()
            for value in WIKI_LINK_PATTERN.findall(line)
        ]

        resolved = []
        unresolved = []

        for target in wiki_targets:
            target_id = title_lookup.get(
                wiki_title_key(target)
            )

            if target_id is None:
                unresolved.append(target)
            elif target_id not in resolved:
                resolved.append(target_id)

        if not resolved:
            if wiki_targets:
                known_non_quest = all(
                    wiki_title_key(target)
                    in KNOWN_NON_QUEST_PROGRESSION_LINKS
                    for target in wiki_targets
                )

                if known_non_quest:
                    optional = bool(re.search(
                        r"\brecommended\b",
                        text,
                        re.IGNORECASE,
                    ))

                    result["non_quest_context_notes"].append({
                        "line_number": line_number,
                        "depth": depth,
                        "source_text": line,
                        "wiki_targets": wiki_targets,
                        "ancestor_text": ancestors,
                        "note_kind": (
                            "OPTIONAL_RECOMMENDATION"
                            if optional
                            else "NON_QUEST_CONDITION_CANDIDATE"
                        ),
                        "verification_status": "UNVERIFIED",
                        "requires_review": True,
                    })
                else:
                    result["review_items"].append({
                        "type": "UNRESOLVED_PROGRESSION_TARGET",
                        "line_number": line_number,
                        "source_text": line,
                        "wiki_targets": wiki_targets,
                    })
            continue

        observation = {
            "line_number": line_number,
            "source_text": line,
            "depth": depth,
            "target_quest_ids": resolved,
            "wiki_targets": wiki_targets,
            "unresolved_wiki_targets": unresolved,
            "ancestor_text": ancestors,
        }

        if depth == 0:
            result["context_notes"].append({
                **observation,
                "note_type": "NON_BULLETED_PROGRESSION_CONTEXT",
            })
            continue

        ancestor_quest_ids = []

        for ancestor in ancestors:
            for value in WIKI_LINK_PATTERN.findall(ancestor):
                target = value.split("|", 1)[0].strip()
                target_id = title_lookup.get(
                    wiki_title_key(target)
                )

                if (
                    target_id is not None
                    and target_id not in ancestor_quest_ids
                ):
                    ancestor_quest_ids.append(target_id)

        if partial:
            progression_kind = "PARTIAL"
        elif PROGRESSION_MILESTONE.search(text):
            progression_kind = "MILESTONE"
        else:
            progression_kind = "STARTED"

        if ancestor_quest_ids:
            context_kind = "TRANSITIVE"
        elif (
            quest_id == "recipe_for_disaster"
            and MIXED_COMPLETION_HEADING in ancestors
        ):
            context_kind = "PARENT_AGGREGATE"
        elif any(
            ancestor.casefold().startswith("access to ")
            for ancestor in ancestors
        ):
            context_kind = "DIRECT_ACCESS"
        elif depth == 1:
            context_kind = "DIRECT"
        else:
            context_kind = "CONTEXT_REVIEW"

        annotations = [
            value.strip().casefold()
            for value in PROGRESSION_START_ANNOTATION.findall(line)
        ]

        if (
            len(annotations) == 1
            and annotations[0] in ("yes", "no")
        ):
            required_to_start = annotations[0].upper()
        else:
            required_to_start = "UNKNOWN"

        needs_review = (
            context_kind != "DIRECT"
            or progression_kind == "MILESTONE"
            or len(resolved) != 1
            or (
                bool(annotations)
                and required_to_start == "UNKNOWN"
            )
        )

        result["progression_observations"].append({
            **observation,
            "ancestor_quest_ids": ancestor_quest_ids,
            "progression_kind": progression_kind,
            "context_kind": context_kind,
            "required_to_start": required_to_start,
            "annotation_values": annotations,
            "needs_review": needs_review,
            "verification_status": "UNVERIFIED",
        })

    return result


def scan_quest_references(
    quest_id, requirements_wikitext, title_lookup
):
    """Return traceable quest references and unresolved nested lines."""
    result = {
        "quest_id": quest_id,
        "references": [],
        "unresolved_nested_lines": [],
    }

    if requirements_wikitext is None:
        return result

    if not isinstance(requirements_wikitext, str):
        raise TypeError("Requirements wikitext must be a string.")

    for line_number, line in enumerate(
        requirements_wikitext.splitlines(), 1
    ):
        match = BULLET_PATTERN.match(line)

        if not match:
            continue

        depth = len(match.group(1))
        text = match.group(2)

        links = [
            value.split("|", 1)[0].strip()
            for value in WIKI_LINK_PATTERN.findall(text)
        ]

        if not links:
            continue

        resolved = []
        unresolved = []

        for target in links:
            key = wiki_title_key(target)

            if key in title_lookup:
                target_id = title_lookup[key]

                if target_id not in resolved:
                    resolved.append(target_id)
            else:
                unresolved.append(target)

        if not resolved:
            if depth >= 2:
                result["unresolved_nested_lines"].append({
                    "line_number": line_number,
                    "depth": depth,
                    "source_text": line,
                    "wiki_targets": links,
                })
            continue

        classification = classify_reference(text, depth)

        # A reference is not automatically an eligibility rule.
        # Even explicitly completed quests require later context
        # and condition validation.
        requires_review = (
            classification != "EXPLICIT_COMPLETION"
            or len(resolved) != 1
            or bool(unresolved)
            or bool(re.search(r"\bor\b", text, re.I))
        )

        for target_id in resolved:
            result["references"].append({
                "target_quest_id": target_id,
                "classification": classification,
                "line_number": line_number,
                "depth": depth,
                "source_text": line,
                "other_wiki_targets": unresolved,
                "requires_review": requires_review,
            })

    return result