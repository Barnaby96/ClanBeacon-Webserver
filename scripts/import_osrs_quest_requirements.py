"""Fetch source requirements for the complete OSRS quest catalogue.

Preserve Wiki wikitext and individual revision IDs. Do not infer
eligibility or modify ClanBeacon's curated quest requirements.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.import_osrs_quest_catalogue import API, USER_AGENT


CATALOGUE_PATH = Path("data/osrs_quest_catalogue_v1.json")
EXPECTED_ENTRIES = 194
BATCH_SIZE = 50

DETAILS_PATTERN = re.compile(
    r"\{\{\s*Quest[ _]details\b",
    re.IGNORECASE,
)

REQUIREMENTS_PATTERN = re.compile(
    r"^\s*\|\s*requirements\s*=",
    re.IGNORECASE,
)

NEXT_FIELD_PATTERN = re.compile(
    r"^\|\s*[A-Za-z][\w -]*\s*=",
)


def load_catalogue():
    catalogue = json.loads(
        CATALOGUE_PATH.read_text(encoding="utf-8-sig")
    )

    entries = catalogue["quest_entries"]

    if len(entries) != EXPECTED_ENTRIES:
        raise ValueError(
            f"Expected {EXPECTED_ENTRIES} catalogue entries, "
            f"found {len(entries)}."
        )

    titles = [entry["wiki_page_title"] for entry in entries]
    ids = [entry["quest_id"] for entry in entries]

    if len(set(titles)) != len(entries):
        raise ValueError("Duplicate Wiki page titles.")

    if len(set(ids)) != len(entries):
        raise ValueError("Duplicate quest IDs.")

    return catalogue


def fetch_page_batch(titles):
    parameters = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "titles": "|".join(titles),
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
    }

    request = Request(
        API + "?" + urlencode(parameters),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=60) as response:
        payload = json.load(response)

    if "error" in payload:
        raise ValueError(
            f"Wiki API error: {payload['error']}"
        )

    query = payload.get("query", {})

    if query.get("redirects") or query.get("normalized"):
        raise ValueError(
            "Wiki page titles changed. Manual review required."
        )

    pages = query.get("pages", [])

    if len(pages) != len(titles):
        raise ValueError(
            "Wiki returned an unexpected number of pages."
        )

    found = {}

    for page in pages:
        title = page.get("title")

        if (
            title not in titles
            or page.get("missing")
            or len(page.get("revisions", [])) != 1
        ):
            raise ValueError(
                f"Missing or unexpected Wiki page: {title}"
            )

        revision = page["revisions"][0]

        content = (
            revision.get("slots", {})
            .get("main", {})
            .get("content")
        )

        if not isinstance(content, str):
            raise ValueError(
                f"Unreadable Wiki source: {title}"
            )

        if not isinstance(revision.get("revid"), int):
            raise ValueError(
                f"Missing revision ID: {title}"
            )

        found[title] = {
            "revision": revision["revid"],
            "timestamp": revision.get("timestamp"),
            "source": content,
        }

    if set(found) != set(titles):
        raise ValueError(
            "Wiki page title mismatch."
        )

    return found


def extract_raw_requirements(source):
    """Extract requirements only from the Quest details template.

    Respect nested Wiki templates and top-level parameter
    boundaries. Do not infer quest eligibility or requirements.
    """
    details = list(DETAILS_PATTERN.finditer(source))

    if len(details) != 1:
        raise ValueError(
            "Expected exactly one Quest details template."
        )

    template_start = details[0].start()
    depth = 0
    template_end = None

    # Find the matching closing braces of Quest details,
    # rather than stopping at the first nested closing line.
    for token in re.finditer(
        r"\{\{|\}\}", source[template_start:]
    ):
        if token.group() == "{{":
            depth += 1
        else:
            depth -= 1

        if depth < 0:
            raise ValueError("Unexpected Wiki template closure.")

        if depth == 0:
            template_end = template_start + token.start()
            break

    if template_end is None:
        raise ValueError("Unclosed Quest details template.")

    template_source = source[
        template_start:template_end
    ]

    depth = 0
    field_lines = None
    collecting = False

    for line in template_source.splitlines():
        # Only direct Quest details parameters count.
        # Nested template parameters cannot end the field.
        if (
            depth == 1
            and REQUIREMENTS_PATTERN.match(line)
        ):
            if field_lines is not None:
                raise ValueError(
                    "Multiple requirements fields found."
                )

            field_lines = [line]
            collecting = True

        elif (
            collecting
            and depth == 1
            and NEXT_FIELD_PATTERN.match(line.lstrip())
        ):
            collecting = False

        elif collecting:
            field_lines.append(line)

        for token in re.finditer(r"\{\{|\}\}", line):
            if token.group() == "{{":
                depth += 1
            else:
                depth -= 1

            if depth < 0:
                raise ValueError(
                    "Unexpected nested template closure."
                )

    if depth != 1:
        raise ValueError(
            "Unexpected Quest details nesting depth."
        )

    if field_lines is None:
        return "FIELD_ABSENT", None

    first_line = re.sub(
        r"^\s*\|\s*requirements\s*=\s*",
        "",
        field_lines[0],
        count=1,
        flags=re.IGNORECASE,
    )

    raw_text = "\n".join(
        [first_line] + field_lines[1:]
    ).strip()

    if not raw_text:
        return "FIELD_EMPTY", None

    return "FIELD_PRESENT", raw_text


def collect_requirements(catalogue):
    entries = catalogue["quest_entries"]

    result = []
    counts = Counter()

    for start in range(0, len(entries), BATCH_SIZE):
        batch = entries[start:start + BATCH_SIZE]

        titles = [
            entry["wiki_page_title"]
            for entry in batch
        ]

        pages = fetch_page_batch(titles)

        for entry in batch:
            title = entry["wiki_page_title"]
            page = pages[title]

            try:
                status, raw_text = extract_raw_requirements(
                    page["source"]
                )
            except ValueError as error:
                raise ValueError(
                    f"{title}: {error}"
                ) from error

            if (
                status == "FIELD_EMPTY"
                and entry["quest_id"] == "learning_the_ropes"
            ):
                status = "IGNORED_TUTORIAL"

            counts[status] += 1

            result.append({
                "quest_id": entry["quest_id"],
                "record_type": entry["record_type"],
                "wiki_page_title": title,
                "wiki_revision": page["revision"],
                "wiki_revision_timestamp": page["timestamp"],
                "requirements_status": status,
                "requirements_wikitext": raw_text,
            })

        print(
            f"Fetched and examined {len(result)} "
            f"of {len(entries)} pages."
        )

    if len(result) != EXPECTED_ENTRIES:
        raise ValueError(
            "Requirements source count mismatch."
        )

    if len({
        item["quest_id"] for item in result
    }) != EXPECTED_ENTRIES:
        raise ValueError(
            "Duplicate quest IDs in requirements sources."
        )

    if counts["IGNORED_TUTORIAL"] != 1:
        raise ValueError(
            "Expected exactly one ignored tutorial quest."
        )

    return result, counts


def export_requirements_snapshot(
    catalogue, records, counts, destination
):
    """Save complete, provenance-linked requirements without overwriting."""
    if len(records) != EXPECTED_ENTRIES:
        raise ValueError("Incomplete requirements snapshot.")

    catalogue_ids = {
        entry["quest_id"]
        for entry in catalogue["quest_entries"]
    }
    record_ids = {
        entry["quest_id"]
        for entry in records
    }

    if catalogue_ids != record_ids:
        raise ValueError("Requirements do not match the catalogue.")

    allowed_statuses = {
        "FIELD_PRESENT",
        "FIELD_ABSENT",
        "FIELD_EMPTY",
        "IGNORED_TUTORIAL",
    }

    for record in records:
        status = record["requirements_status"]
        raw = record["requirements_wikitext"]

        if status not in allowed_statuses:
            raise ValueError(f"Unknown requirements status: {status}")

        if (status == "FIELD_PRESENT") != (
            isinstance(raw, str) and bool(raw.strip())
        ):
            raise ValueError(
                f"Inconsistent requirements: {record['quest_id']}"
            )

        if not isinstance(record["wiki_revision"], int):
            raise ValueError(
                f"Missing Wiki revision: {record['quest_id']}"
            )

    snapshot = {
        "schema_version": 1,
        "catalogue_source": catalogue["source"],
        "requirements_source": "individual_osrs_wiki_quest_pages",
        "requirements_status_counts": dict(counts),
        "requirements_records": records,
    }

    destination = Path(destination)
    payload = json.dumps(
        snapshot, ensure_ascii=False, indent=2
    ) + "\n"

    destination.parent.mkdir(parents=True, exist_ok=True)

    created = False

    try:
        with destination.open(
            "x", encoding="utf-8", newline="\n"
        ) as handle:
            created = True
            handle.write(payload)
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise

    return destination


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)

    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit requirements without saving.",
    )

    mode.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="Export requirements JSON without overwriting.",
    )

    args = parser.parse_args()

    catalogue = load_catalogue()
    result, counts = collect_requirements(catalogue)

    print()
    print("=== QUEST REQUIREMENTS SOURCE IMPORT ===")
    print("Catalogue revision:",
          catalogue["source"]["wiki_revision"])
    print("Quest records:", len(result))
    print("Requirements present:", counts["FIELD_PRESENT"])
    print("Requirements absent:", counts["FIELD_ABSENT"])
    print("Requirements explicitly empty:", counts["FIELD_EMPTY"])
    print("Ignored tutorial:", counts["IGNORED_TUTORIAL"])

    print()
    print("=== REPRESENTATIVE REQUIREMENTS ===")

    for quest_id in (
        "crab_quest",
        "the_final_dawn",
        "recipe_for_disaster_freeing_king_awowogei",
        "monkey_madness_ii",
        "druidic_ritual",
    ):
        record = next(
            item for item in result
            if item["quest_id"] == quest_id
        )

        print()
        print(quest_id)
        print("Revision:", record["wiki_revision"])
        print("Status:", record["requirements_status"])

        raw = record["requirements_wikitext"]

        if raw is not None:
            for line in raw.splitlines()[:7]:
                print(" ", line[:160])

    print()
    print("SOURCE AUDIT PASSED")

    if args.output is not None:
        destination = export_requirements_snapshot(
            catalogue, result, counts, args.output
        )
        print(f"Requirements JSON exported: {destination}")
    else:
        print("No JSON exported.")

    print("No database or Git operations.")


if __name__ == "__main__":
    main()