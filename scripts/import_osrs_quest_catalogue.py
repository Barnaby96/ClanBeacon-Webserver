"""Read and validate the OSRS Wiki quest catalogue.

Standard quests and Recipe for Disaster subquests are both
first-class dependency records. A parent relationship never
implies completion of the parent quest.
"""

import argparse
import json
import re
import sys
from collections import Counter
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.osrs_quest_data import get_curated_quest_requirements


API = "https://oldschool.runescape.wiki/api.php"
SOURCE_PAGE = "Quests/List"

EXPECTED_STANDARD_QUESTS = 184
EXPECTED_SUBQUESTS = 10

USER_AGENT = (
    "ClanBeaconQuestImporter/0.1 "
    "(https://github.com/Barnaby96/ClanBeacon-Webserver)"
)


def normalise_quest_id(name):
    """Create a stable, punctuation-free dependency ID."""
    name = name.casefold().replace("&", " and ")
    name = name.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def title_key(name):
    """Match Wiki names against existing curated quest names."""
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def readable(markup):
    markup = re.sub(r"<[^>]*>", " ", markup)
    return re.sub(r"\s+", " ", unescape(markup)).strip()


def first_wiki_link(markup):
    links = re.findall(
        r'<a\b[^>]*href="([^"]+)"',
        markup,
        flags=re.I,
    )

    for href in links:
        if href.startswith("/w/"):
            return unquote(unescape(href))

    return None


def fetch_catalogue():
    parameters = {
        "action": "parse",
        "format": "json",
        "formatversion": "2",
        "page": SOURCE_PAGE,
        "prop": "text|revid",
    }

    request = Request(
        API + "?" + urlencode(parameters),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=45) as response:
        payload = json.load(response)

    if "error" in payload:
        raise ValueError(payload["error"])

    page = payload["parse"]

    if page.get("title") != SOURCE_PAGE:
        raise ValueError("Unexpected Wiki page returned.")

    if not isinstance(page.get("revid"), int):
        raise ValueError("Missing Wiki revision ID.")

    if not isinstance(page.get("text"), str):
        raise ValueError("Missing Wiki catalogue HTML.")

    return page


def extract_catalogue(page):
    tables = re.findall(
        r"<table\b[^>]*>.*?</table>",
        page["text"],
        flags=re.I | re.S,
    )

    quest_tables = []

    for table in tables:
        rows = re.findall(
            r"<tr\b[^>]*>.*?</tr>",
            table,
            flags=re.I | re.S,
        )

        if rows and re.match(
            r"^#\s+Name\b",
            readable(rows[0]),
            flags=re.I,
        ):
            quest_tables.append(rows)

    if len(quest_tables) != 2:
        raise ValueError(
            "Expected two standard quest tables; "
            f"found {len(quest_tables)}."
        )

    records = []

    for membership, rows in zip(
        ("FREE_TO_PLAY", "MEMBERS"),
        quest_tables,
    ):
        for row_number, row in enumerate(rows[1:], 2):
            cells = re.findall(
                r"<td\b[^>]*>.*?</td>",
                row,
                flags=re.I | re.S,
            )

            if len(cells) < 2:
                raise ValueError(
                    f"{membership} row {row_number}: "
                    "missing cells."
                )

            number = readable(cells[0])
            name = readable(cells[1])
            wiki_path = first_wiki_link(cells[1])

            if not name or not wiki_path:
                raise ValueError(
                    f"{membership} row {row_number}: "
                    "missing name or Wiki link."
                )

            quest_id = normalise_quest_id(name)

            if not quest_id:
                raise ValueError(
                    f"Invalid quest ID for {name!r}."
                )

            record = {
                "quest_id": quest_id,
                "display_name": name,
                "wiki_path": wiki_path,
                "wiki_page_title": (
                    wiki_path.removeprefix("/w/")
                    .replace("_", " ")
                ),
                "source_number": number,
                "membership": membership,
            }

            if re.fullmatch(r"\d+", number):
                record["record_type"] = "QUEST"
                record["quest_number"] = int(number)
                record["parent_quest_id"] = None

            elif (
                re.fullmatch(r"100\.\d+", number)
                and membership == "MEMBERS"
                and wiki_path.startswith(
                    "/w/Recipe_for_Disaster/"
                )
            ):
                record["record_type"] = "SUBQUEST"
                record["parent_quest_id"] = (
                    "recipe_for_disaster"
                )

            else:
                raise ValueError(
                    "Unexpected catalogue entry: "
                    f"{number!r} / {name!r}"
                )

            records.append(record)

    validate_catalogue(records)

    return {
        "schema_version": 1,
        "source": {
            "wiki_page": SOURCE_PAGE,
            "wiki_revision": page["revid"],
            "wiki_api": API,
        },
        "quest_entries": records,
    }


def validate_catalogue(records):
    standard = [
        record for record in records
        if record["record_type"] == "QUEST"
    ]

    subquests = [
        record for record in records
        if record["record_type"] == "SUBQUEST"
    ]

    if len(standard) != EXPECTED_STANDARD_QUESTS:
        raise ValueError(
            f"Expected {EXPECTED_STANDARD_QUESTS} quests; "
            f"found {len(standard)}."
        )

    if len(subquests) != EXPECTED_SUBQUESTS:
        raise ValueError(
            f"Expected {EXPECTED_SUBQUESTS} subquests; "
            f"found {len(subquests)}."
        )

    membership = Counter(
        record["membership"] for record in standard
    )

    if membership != {
        "FREE_TO_PLAY": 24,
        "MEMBERS": 160,
    }:
        raise ValueError(
            f"Unexpected membership totals: {membership}"
        )

    for field in ("quest_id", "wiki_path"):
        values = [
            record[field] for record in records
        ]

        if len(values) != len(set(values)):
            raise ValueError(
                f"Duplicate {field} detected."
            )

    # Existing curated IDs are part of ClanBeacon's public
    # dependency vocabulary. Reject incompatible imports.
    for curated in get_curated_quest_requirements():
        matching = [
            record for record in records
            if title_key(record["display_name"])
            == title_key(curated.display_name)
        ]

        if len(matching) != 1:
            raise ValueError(
                "Curated quest missing or ambiguous: "
                f"{curated.display_name}"
            )

        if matching[0]["quest_id"] != curated.quest_id:
            raise ValueError(
                "Curated quest ID mismatch for "
                f"{curated.display_name}: "
                f"{matching[0]['quest_id']} != "
                f"{curated.quest_id}"
            )

    standard_ids = {
        record["quest_id"] for record in standard
    }

    if "recipe_for_disaster" not in standard_ids:
        raise ValueError(
            "Recipe for Disaster parent quest missing."
        )

    expected_numbers = {
        f"100.{number}" for number in range(1, 11)
    }

    actual_numbers = {
        record["source_number"] for record in subquests
    }

    if actual_numbers != expected_numbers:
        raise ValueError(
            "Unexpected Recipe for Disaster subquest numbers."
        )

    if any(
        record["parent_quest_id"] != "recipe_for_disaster"
        for record in subquests
    ):
        raise ValueError(
            "Unexpected subquest parent."
        )



def export_catalogue(catalogue, destination):
    """Write a validated catalogue without replacing existing files."""
    destination = Path(destination)

    payload = json.dumps(
        catalogue,
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    if destination.exists():
        raise FileExistsError(
            f"Catalogue already exists: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)

    created = False

    try:
        with destination.open(
            "x",
            encoding="utf-8",
            newline="\n",
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
        help="Fetch and validate without saving anything.",
    )

    mode.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="Export validated JSON without overwriting.",
    )

    args = parser.parse_args()

    page = fetch_catalogue()
    catalogue = extract_catalogue(page)

    records = catalogue["quest_entries"]

    standard = [
        record for record in records
        if record["record_type"] == "QUEST"
    ]

    subquests = [
        record for record in records
        if record["record_type"] == "SUBQUEST"
    ]

    print("=== OSRS QUEST CATALOGUE IMPORT ===")
    print("Wiki revision:", page["revid"])
    print("Standard quests:", len(standard))
    print("Recipe for Disaster subquests:", len(subquests))
    print("Total dependency entries:", len(records))

    print()
    print("=== RECIPE FOR DISASTER SUBQUESTS ===")

    for record in subquests:
        print(
            record["source_number"],
            record["quest_id"],
            "parent=" + record["parent_quest_id"],
        )

    print()
    print("=== RECENT QUEST EXAMPLES ===")

    for record in records:
        if record["display_name"] in (
            "Crab Quest",
            "The Final Dawn",
            "Monkey Madness II",
        ):
            print(
                record["quest_id"],
                record["record_type"],
            )

    print()
    print("CATALOGUE VALIDATION PASSED")

    if args.output is not None:
        destination = export_catalogue(
            catalogue,
            args.output,
        )
        print(f"JSON exported: {destination}")
    else:
        print("No JSON exported.")

    print("No databases or Git operations.")


if __name__ == "__main__":
    main()