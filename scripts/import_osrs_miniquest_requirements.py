"""Capture source requirements for all OSRS miniquests.

Requirements are source observations, never eligibility rules.
Existing quest catalogues and requirement snapshots are untouched.
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.import_osrs_quest_catalogue import (
    API,
    USER_AGENT,
)
from scripts.import_osrs_quest_requirements import (
    extract_raw_requirements,
)
from utils.osrs_quest_prerequisite_parser import (
    wiki_title_key,
)


CATALOGUE_PATH = Path(
    "data/osrs_miniquest_catalogue_v1.json"
)

EXPECTED_COUNT = 20

VALID_STATUSES = frozenset({
    "FIELD_PRESENT",
    "FIELD_ABSENT",
    "FIELD_EMPTY",
})

ANNOTATION_ONLY = re.compile(
    r"\{\{\s*Questreqstart\s*\|[^{}]*\}\}",
    re.IGNORECASE,
)


def load_miniquest_catalogue():
    """Load and validate the separate miniquest catalogue."""
    document = json.loads(
        CATALOGUE_PATH.read_text(encoding="utf-8-sig")
    )

    if document.get("schema_version") != 1:
        raise ValueError(
            "Unexpected miniquest catalogue schema."
        )

    records = document.get("miniquest_entries")

    if not isinstance(records, list):
        raise ValueError("Miniquest entries are missing.")

    if len(records) != EXPECTED_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_COUNT} miniquests, "
            f"found {len(records)}."
        )

    ids = []
    titles = []

    for record in records:
        if record.get("record_type") != "MINIQUEST":
            raise ValueError(
                "Unexpected miniquest record type."
            )

        quest_id = record["quest_id"]
        title = record["wiki_page_title"]

        if not quest_id.startswith("miniquest_"):
            raise ValueError(
                f"Unexpected miniquest ID: {quest_id}"
            )

        ids.append(quest_id)
        titles.append(wiki_title_key(title))

    if len(set(ids)) != EXPECTED_COUNT:
        raise ValueError("Duplicate miniquest IDs.")

    if len(set(titles)) != EXPECTED_COUNT:
        raise ValueError("Duplicate miniquest titles.")

    return document, records


def fetch_miniquest_pages(records):
    """Read current Wiki wikitext and source revisions."""
    titles = [
        record["wiki_page_title"]
        for record in records
    ]

    url = API + "?" + urlencode({
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "titles": "|".join(titles),
    })

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=45) as response:
        payload = json.load(response)

    if "error" in payload:
        raise ValueError(
            f"Wiki API error: {payload['error']}"
        )

    query = payload.get("query", {})

    if query.get("redirects") or query.get("normalized"):
        raise ValueError(
            "Wiki redirected or normalised a miniquest title. "
            "Review before importing."
        )

    pages = query.get("pages", [])

    if len(pages) != EXPECTED_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_COUNT} Wiki pages, "
            f"received {len(pages)}."
        )

    page_lookup = {}

    for page in pages:
        if page.get("missing") or page.get("invalid"):
            raise ValueError(
                f"Missing or invalid Wiki page: {page}"
            )

        key = wiki_title_key(page["title"])

        if key in page_lookup:
            raise ValueError(
                f"Duplicate Wiki page: {page['title']}"
            )

        page_lookup[key] = page

    expected = {
        wiki_title_key(title)
        for title in titles
    }

    if set(page_lookup) != expected:
        raise ValueError(
            "Wiki page titles do not match the catalogue."
        )

    return page_lookup


def collect_miniquest_requirements(records):
    """Extract unmodified requirements and record provenance."""
    pages = fetch_miniquest_pages(records)
    results = []

    for record in records:
        quest_id = record["quest_id"]
        key = wiki_title_key(
            record["wiki_page_title"]
        )
        page = pages[key]

        revisions = page.get("revisions", [])

        if len(revisions) != 1:
            raise ValueError(
                f"Unexpected revision count: {quest_id}"
            )

        revision = revisions[0]
        revision_id = revision.get("revid")
        timestamp = revision.get("timestamp")

        if (
            not isinstance(revision_id, int)
            or revision_id <= 0
            or not isinstance(timestamp, str)
            or not timestamp
        ):
            raise ValueError(
                f"Invalid revision provenance: {quest_id}"
            )

        source = (
            revision.get("slots", {})
            .get("main", {})
            .get("content")
        )

        if not isinstance(source, str):
            raise ValueError(
                f"Missing readable wikitext: {quest_id}"
            )

        status, raw_requirements = (
            extract_raw_requirements(source)
        )

        if status not in VALID_STATUSES:
            raise ValueError(
                f"Unexpected requirements status: "
                f"{quest_id}: {status}"
            )

        if status == "FIELD_PRESENT":
            if (
                not isinstance(raw_requirements, str)
                or not raw_requirements.strip()
            ):
                raise ValueError(
                    f"Empty populated requirements: {quest_id}"
                )
        elif raw_requirements is not None:
            raise ValueError(
                f"Unexpected raw requirements: {quest_id}"
            )

        results.append({
            "quest_id": quest_id,
            "record_type": "MINIQUEST",
            "wiki_page_title": record["wiki_page_title"],
            "wiki_revision": revision_id,
            "wiki_revision_timestamp": timestamp,
            "requirements_status": status,
            "requirements_wikitext": raw_requirements,
        })

    if len(results) != EXPECTED_COUNT:
        raise ValueError(
            "Incomplete miniquest requirements collection."
        )

    return results


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Capture source requirements for OSRS miniquests."
        )
    )

    action = parser.add_mutually_exclusive_group(
        required=True
    )

    action.add_argument(
        "--dry-run",
        action="store_true",
    )
    action.add_argument(
        "--output",
        type=Path,
    )

    args = parser.parse_args()

    catalogue, records = load_miniquest_catalogue()
    requirements = collect_miniquest_requirements(
        records
    )

    counts = Counter(
        record["requirements_status"]
        for record in requirements
    )

    exact_none = [
        record["quest_id"]
        for record in requirements
        if (
            isinstance(record["requirements_wikitext"], str)
            and record["requirements_wikitext"]
            .strip().casefold() == "none"
        )
    ]

    annotation_only = [
        record["quest_id"]
        for record in requirements
        if (
            isinstance(record["requirements_wikitext"], str)
            and ANNOTATION_ONLY.fullmatch(
                record["requirements_wikitext"].strip()
            )
        )
    ]

    print("=== MINIQUEST REQUIREMENTS AUDIT ===")
    print("Miniquests:", len(requirements))

    print()
    print("=== REQUIREMENT STATUS COUNTS ===")

    for status in sorted(VALID_STATUSES):
        print(f"  {status}: {counts[status]}")

    print()
    print("=== INDIVIDUAL SOURCE RECORDS ===")

    for record in requirements:
        raw = record["requirements_wikitext"]
        preview = (
            " ".join(raw.split())[:135]
            if isinstance(raw, str)
            else "(no requirements text)"
        )

        print()
        print("  ID:", record["quest_id"])
        print("  Revision:", record["wiki_revision"])
        print("  Status:", record["requirements_status"])
        print("  Preview:", preview)

    print()
    print("Explicit literal 'None':", len(exact_none))
    print("Annotation-only fields:", len(annotation_only))

    for quest_id in annotation_only:
        print("  Review annotation-only:", quest_id)

    document = {
        "schema_version": 1,
        "catalogue_source": catalogue["source"],
        "requirements_source": {
            "wiki_api": API,
            "retrieved_at_utc": (
                datetime.now(timezone.utc).isoformat()
            ),
            "page_count": len(requirements),
        },
        "requirements_status_counts": dict(counts),
        "requirements_records": requirements,
    }

    if args.dry_run:
        print()
        print("SOURCE AUDIT PASSED")
        print("DRY RUN PASSED")
        print("No JSON written.")
        return

    with args.output.open(
        "x", encoding="utf-8"
    ) as output_file:
        json.dump(
            document,
            output_file,
            indent=2,
            ensure_ascii=False,
        )
        output_file.write("\n")

    print()
    print(f"Requirements exported: {args.output}")


if __name__ == "__main__":
    main()
