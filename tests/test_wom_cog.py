import asyncio
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cogs.WOMCog import WOMCog
from utils import database


@pytest.fixture(autouse=True)
def wom_cog_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "WOM cog tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


def test_background_wom_poll_records_refresh_audit(
    monkeypatch
):
    def fake_process_wom_competition():
        return {
            "competition_id": 151069,
            "metrics_processed": 9,
            "players_processed": 45,
            "tiles_completed": [],
            "errors": []
        }

    monkeypatch.setattr(
        "cogs.WOMCog.wom_tracking.process_wom_competition",
        fake_process_wom_competition
    )

    cog = WOMCog(
        bot=None
    )

    asyncio.run(
        WOMCog.wom_poll.coro(
            cog
        )
    )

    rows = database.get_recent_wom_refresh_audit_rows()

    assert len(rows) == 1

    row = rows[0]

    assert row["requested_by_user_id"] is None
    assert row["requested_by_username"] == "Background WOM Poll"
    assert row["competition_id"] == 151069
    assert row["metrics_processed"] == 9
    assert row["players_processed"] == 45
    assert row["tiles_completed"] == 0
    assert row["warning_count"] == 0
    assert row["no_competition"] is False


def test_background_wom_poll_skips_audit_without_competition(
    monkeypatch
):
    def fake_process_wom_competition():
        return {
            "competition_id": None,
            "metrics_processed": 0,
            "players_processed": 0,
            "tiles_completed": [],
            "errors": []
        }

    monkeypatch.setattr(
        "cogs.WOMCog.wom_tracking.process_wom_competition",
        fake_process_wom_competition
    )

    cog = WOMCog(
        bot=None
    )

    asyncio.run(
        WOMCog.wom_poll.coro(
            cog
        )
    )

    rows = database.get_recent_wom_refresh_audit_rows()

    assert rows == []
