"""PostgreSQL integration tests for automatic WOM polling claims."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from utils import database


@pytest.fixture
def configured_competition():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "WOM polling claims must only be tested "
            "against danbot_test."
        )

    database.reset_tables()

    start = datetime(
        2026, 10, 25, 12,
        tzinfo=timezone.utc,
    )
    end = start + timedelta(hours=5)
    competition_id = 151069

    with closing(database.connect()) as conn:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database()"
                )
                assert cursor.fetchone()[0] == "danbot_test"

                cursor.execute(
                    """
                    INSERT INTO bingo_config (
                        config_id,
                        wom_competition_id,
                        wom_competition_starts_at,
                        wom_competition_ends_at
                    )
                    VALUES (1, %s, %s, %s)
                    ON CONFLICT (config_id)
                    DO UPDATE SET
                        wom_competition_id = EXCLUDED.wom_competition_id,
                        wom_competition_starts_at =
                            EXCLUDED.wom_competition_starts_at,
                        wom_competition_ends_at =
                            EXCLUDED.wom_competition_ends_at
                    """,
                    (competition_id, start, end),
                )

    return competition_id, start, end


def test_claim_rejects_duplicates_invalid_and_stale_slots(
    configured_competition,
):
    competition_id, start, end = configured_competition
    slot = start + timedelta(hours=1)

    assert database.claim_wom_poll_slot(
        competition_id, start, end, slot
    ) is True

    assert database.claim_wom_poll_slot(
        competition_id, start, end, slot
    ) is False

    assert database.claim_wom_poll_slot(
        competition_id,
        start,
        end,
        slot + timedelta(hours=1),
    ) is True

    assert database.claim_wom_poll_slot(
        competition_id,
        start,
        end,
        start - timedelta(minutes=1),
    ) is False

    assert database.claim_wom_poll_slot(
        competition_id,
        start,
        end,
        end + timedelta(minutes=1),
    ) is False

    assert database.claim_wom_poll_slot(
        True, start, end, slot
    ) is False

    assert database.claim_wom_poll_slot(
        competition_id,
        start.replace(tzinfo=None),
        end,
        slot,
    ) is False

    # A changed competition configuration must invalidate
    # claims using the old timing.
    revised_end = end + timedelta(hours=1)

    with closing(database.connect()) as conn:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE bingo_config
                    SET wom_competition_ends_at = %s
                    WHERE config_id = 1
                    """,
                    (revised_end,),
                )

    new_slot = slot + timedelta(hours=2)

    assert database.claim_wom_poll_slot(
        competition_id, start, end, new_slot
    ) is False

    assert database.claim_wom_poll_slot(
        competition_id,
        start,
        revised_end,
        new_slot,
    ) is True

    with closing(database.connect()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM wom_poll_slots"
            )
            assert cursor.fetchone()[0] == 3


def test_concurrent_claims_have_only_one_winner(
    configured_competition,
):
    competition_id, start, end = configured_competition
    slot = end - timedelta(minutes=15)

    def claim(_):
        return database.claim_wom_poll_slot(
            competition_id, start, end, slot
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, range(2)))

    assert sorted(results) == [False, True]

    with closing(database.connect()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM wom_poll_slots
                WHERE competition_id = %s
                  AND scheduled_for = %s
                """,
                (competition_id, slot),
            )
            assert cursor.fetchone()[0] == 1
