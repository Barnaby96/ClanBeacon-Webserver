"""Import the OSRS Wiki miniquest catalogue as a separate dataset.

This script does not import requirements or modify eligibility rules.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

from scripts.import_osrs_quest_catalogue import API, USER_AGENT


EXPECTED_MINIQUEST_COUNT = 20

TABLE_PATTERN = re.compile(
    r"<table\b[^>]*>.*?</table>",
    re.IGNORECASE | re.DOTALL,
)

ROW_PATTERN = re.compile(
    r"<tr\b[^>]*>.*?</tr>",
    re.IGNORECASE | re.DOTALL,
)

CELL_PATTERN = re.compile(
    r"<td\b[^>]*>.*?</td>",
    re.IGNORECASE | re.DOTALL,
)

LINK_PATTERN = re.compile(
    r'<a\b[^>]*href="(/w/[^"]+)"',
    re.IGNORECASE,
)


def readable_html(value):
    """Extract plain text from a simple Wiki table cell."""
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalise_miniquest_id(name):
    """Create a stable, distinct identifier for a miniquest."""
    value = unescape(name).casefold()
    value = re.sub(
        r"\s*\(miniquest\)\s*$",
        "",
        value,
    )
    value = value.replace("?", "'")
    value = value.replace("&", " and ")
    value = value.replace("'", "")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")

    if not value:
        raise ValueError("Empty normalised miniquest name.")

    return "miniquest_" + value


def fetch_miniquest_catalogue():
    """Fetch the authoritative miniquest table from Quests/List."""
    url = API + "?" + urlencode({
        "action": "parse",
        "format": "json",
        "formatversion": "2",
        "page": "Quests/List",
        "prop": "text|revid",
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

    parsed = payload.get("parse", {})
    revision = parsed.get("revid")
    html = parsed.get("text")

    if not isinstance(revision, int) or revision <= 0:
        raise ValueError("Missing valid Wiki revision.")

    if not isinstance(html, str) or not html:
        raise ValueError("Missing rendered quest list.")

    matching_tables = []

    for table in TABLE_PATTERN.findall(html):
        rows = ROW_PATTERN.findall(table)

        if not rows:
            continue

        header = readable_html(rows[0])

        if (
            header.startswith("Name Difficulty Length")
            and "Leagues region" in header
        ):
            matching_tables.append(rows)

    if len(matching_tables) != 1:
        raise ValueError(
            "Expected one miniquest table, found "
            f"{len(matching_tables)}."
        )

    records = []

    for position, row in enumerate(
        matching_tables[0][1:], 1
    ):
        cells = CELL_PATTERN.findall(row)

        if not cells:
            raise ValueError(
                f"Miniquest row {position} has no cells."
            )

        name = readable_html(cells[0])
        paths = LINK_PATTERN.findall(cells[0])

        if not name or not paths:
            raise ValueError(
                f"Miniquest row {position} has no name/link."
            )

        if len(paths) != 1:
            raise ValueError(
                f"Miniquest row {position} has "
                f"{len(paths)} links; review required."
            )

        path = unquote(unescape(paths[0]))

        if not path.startswith("/w/"):
            raise ValueError(
                f"Unexpected miniquest Wiki path: {path}"
            )

        page_title = path[len("/w/"):].replace("_", " ")

        records.append({
            "quest_id": normalise_miniquest_id(name),
            "display_name": name,
            "wiki_path": path,
            "wiki_page_title": page_title,
            "record_type": "MINIQUEST",
            "source_list_position": position,
        })

    if len(records) != EXPECTED_MINIQUEST_COUNT:
        raise ValueError(
            "Unexpected miniquest count: "
            f"{len(records)} rather than "
            f"{EXPECTED_MINIQUEST_COUNT}."
        )

    ids = [record["quest_id"] for record in records]
    titles = [
        record["wiki_page_title"].casefold()
        for record in records
    ]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate miniquest IDs.")

    if len(titles) != len(set(titles)):
        raise ValueError("Duplicate miniquest Wiki titles.")

    return revision, records


def validate_against_quest_catalogue(records):
    """Ensure miniquests do not collide with existing quest IDs."""
    path = Path("data/osrs_quest_catalogue_v1.json")

    catalogue = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    existing = catalogue["quest_entries"]

    if len(existing) != 194:
        raise ValueError(
            "Expected 194 existing quests/subquests."
        )

    existing_ids = {
        record["quest_id"]
        for record in existing
    }

    if len(existing_ids) != 194:
        raise ValueError(
            "Duplicate IDs in the existing quest catalogue."
        )

    miniquest_ids = {
        record["quest_id"]
        for record in records
    }

    collisions = existing_ids & miniquest_ids

    if collisions:
        raise ValueError(
            f"Quest ID collisions: {sorted(collisions)}"
        )

    expected_ids = {
        "miniquest_alfred_grimhands_barcrawl",
        "miniquest_enter_the_abyss",
        "miniquest_the_generals_shadow",
        "miniquest_barbarian_training",
        "miniquest_skippy_and_the_mogres",
        "miniquest_curse_of_the_empty_lord",
        "miniquest_his_faithful_servants",
        "miniquest_vale_totems",
        "miniquest_the_fractured_archive",
    }

    missing = expected_ids - miniquest_ids

    if missing:
        raise ValueError(
            "Known miniquest IDs missing: "
            f"{sorted(missing)}"
        )

    return len(existing)


def main():
    parser = argparse.ArgumentParser(
        description="Import the OSRS miniquest catalogue."
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

    revision, records = fetch_miniquest_catalogue()
    existing_count = validate_against_quest_catalogue(
        records
    )

    document = {
        "schema_version": 1,
        "source": {
            "wiki_page": "Quests/List",
            "wiki_revision": revision,
            "retrieved_at_utc": (
                datetime.now(timezone.utc).isoformat()
            ),
        },
        "miniquest_count": len(records),
        "miniquest_entries": records,
    }

    print("=== MINIQUEST CATALOGUE ===")
    print("Wiki revision:", revision)
    print("Existing quests/subquests:", existing_count)
    print("Miniquests:", len(records))
    print("Combined dependency records:",
          existing_count + len(records))

    print()
    print("=== MINIQUEST IDENTIFIERS ===")

    for record in records:
        print(
            f"  {record['quest_id']}"
            f" -> {record['display_name']}"
        )

    print()
    print("Catalogue validation passed.")

    if args.dry_run:
        print("DRY RUN PASSED")
        print("No JSON written.")
        return

    with args.output.open("x", encoding="utf-8") as file:
        json.dump(
            document,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    print(f"Catalogue exported: {args.output}")


if __name__ == "__main__":
    main()
