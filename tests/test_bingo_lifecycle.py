from datetime import datetime, timezone
from io import BytesIO

from utils import bingo_lifecycle


def _status(
    starts_at,
    ends_at,
    start_sent=None,
    end_sent=None,
    lifecycle_ready=True,
    lifecycle_ready_at=None
):
    return {
        "starts_at": starts_at,
        "ends_at": ends_at,
        "start_webhook_sent_at": start_sent,
        "end_webhook_sent_at": end_sent,
        "lifecycle_ready": lifecycle_ready,
        "lifecycle_ready_at": lifecycle_ready_at,
    }


def _fake_image_and_state(team_id=None, completed_coordinates=None):
    return (
        BytesIO(b"fake board"),
        {
            "tile_names_by_coordinate": {},
            "completed_coordinates": completed_coordinates or [],
            "partial_coordinates": [],
        }
    )


def test_lifecycle_no_timing_does_not_send(monkeypatch):
    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: None
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        lambda *args, **kwargs: sent.append(args)
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements()

    assert result["processed"] is False
    assert result["reason"] == "missing_bingo_config"
    assert sent == []
    assert marked == []


def test_lifecycle_not_ready_does_not_send(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)

    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(
            starts_at,
            ends_at,
            lifecycle_ready=False
        )
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        lambda *args, **kwargs: sent.append(args)
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is False
    assert result["reason"] == "bingo_lifecycle_not_ready"
    assert sent == []
    assert marked == []


def test_lifecycle_before_start_does_not_send(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)

    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(starts_at, ends_at)
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        lambda *args, **kwargs: sent.append(args)
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is False
    assert result["reason"] == "no_lifecycle_announcements_due"
    assert sent == []
    assert marked == []


def test_lifecycle_start_due_sends_clean_board_once(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)

    board_calls = []
    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(starts_at, ends_at)
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            (
                "Team One",
                0,
                "https://discord.com/api/webhooks/1/token",
                1,
                "123456789"
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "_render_board_image_and_state",
        lambda team_id=None: (
            board_calls.append(team_id)
            or _fake_image_and_state(team_id)
        )
    )

    def fake_send(url, message, board_image, discord_role_id=None):
        sent.append(
            {
                "url": url,
                "message": message,
                "discord_role_id": discord_role_id,
                "board": board_image.getvalue(),
            }
        )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        fake_send
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is True
    assert result["start"]["sent_count"] == 1
    assert result["end"] is None
    assert board_calls == [None]
    assert marked == ["start"]
    assert sent[0]["discord_role_id"] == "123456789"
    assert "bingo has begun" in sent[0]["message"]
    assert "Here is the board. Good luck Team One" in sent[0]["message"]


def test_lifecycle_ready_after_start_does_not_send_stale_start(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)
    ready_at = datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc)
    now = datetime(2026, 1, 1, 12, 6, tzinfo=timezone.utc)

    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(
            starts_at,
            ends_at,
            lifecycle_ready=True,
            lifecycle_ready_at=ready_at
        )
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            (
                "Team One",
                0,
                "https://discord.com/api/webhooks/1/token",
                1,
                "123456789"
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        lambda *args, **kwargs: sent.append(args)
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is False
    assert result["reason"] == "no_lifecycle_announcements_due"
    assert sent == []
    assert marked == []


def test_lifecycle_ready_after_start_but_before_end_still_sends_end(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)
    ready_at = datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc)
    now = datetime(2026, 1, 1, 12, 31, tzinfo=timezone.utc)

    board_calls = []
    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(
            starts_at,
            ends_at,
            lifecycle_ready=True,
            lifecycle_ready_at=ready_at
        )
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            (
                "Team One",
                7,
                "https://discord.com/api/webhooks/1/token",
                1,
                "123456789"
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "_render_board_image_and_state",
        lambda team_id=None: (
            board_calls.append(team_id)
            or _fake_image_and_state(
                team_id,
                completed_coordinates=[
                    (1, 1),
                    (1, 2)
                ]
            )
        )
    )

    def fake_send(url, message, board_image, discord_role_id=None):
        sent.append(
            {
                "url": url,
                "message": message,
                "discord_role_id": discord_role_id,
                "board": board_image.getvalue(),
            }
        )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        fake_send
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is True
    assert result["start"] is None
    assert result["end"]["sent_count"] == 1
    assert board_calls == [1]
    assert marked == ["end"]
    assert "bingo has ended" in sent[0]["message"]
    assert "You completed 2 tiles for a total of 7 points!" in sent[0]["message"]


def test_lifecycle_after_end_without_start_sent_sends_end_only(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 2, 12, 1, tzinfo=timezone.utc)

    board_calls = []
    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(starts_at, ends_at)
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            (
                "Team One",
                42,
                "https://discord.com/api/webhooks/1/token",
                7,
                None
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "_render_board_image_and_state",
        lambda team_id=None: (
            board_calls.append(team_id)
            or _fake_image_and_state(
                team_id,
                completed_coordinates=[
                    (1, 1),
                    (1, 2),
                    (1, 3)
                ]
            )
        )
    )

    def fake_send(url, message, board_image, discord_role_id=None):
        sent.append(
            {
                "url": url,
                "message": message,
                "discord_role_id": discord_role_id,
                "board": board_image.getvalue(),
            }
        )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        fake_send
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is True
    assert result["start"] is None
    assert result["end"]["sent_count"] == 1
    assert board_calls == [7]
    assert marked == ["end"]
    assert "bingo has ended" in sent[0]["message"]
    assert "You completed 3 tiles for a total of 42 points!" in sent[0]["message"]
    assert "Full results will be published after a review by the admin team!" in sent[0]["message"]
    assert "Here is your final board." in sent[0]["message"]


def test_lifecycle_end_due_sends_team_board_once(monkeypatch):
    starts_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 2, 12, 1, tzinfo=timezone.utc)

    board_calls = []
    sent = []
    marked = []

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_bingo_lifecycle_status",
        lambda: _status(
            starts_at,
            ends_at,
            start_sent=datetime(
                2026,
                1,
                1,
                12,
                1,
                tzinfo=timezone.utc
            )
        )
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            (
                "Team One",
                5,
                "https://discord.com/api/webhooks/1/token",
                7,
                None
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "_render_board_image_and_state",
        lambda team_id=None: (
            board_calls.append(team_id)
            or _fake_image_and_state(
                team_id,
                completed_coordinates=[
                    (2, 1)
                ]
            )
        )
    )

    def fake_send(url, message, board_image, discord_role_id=None):
        sent.append(
            {
                "url": url,
                "message": message,
                "discord_role_id": discord_role_id,
                "board": board_image.getvalue(),
            }
        )

    monkeypatch.setattr(
        bingo_lifecycle,
        "send_completion_webhook",
        fake_send
    )

    monkeypatch.setattr(
        bingo_lifecycle.database,
        "mark_bingo_lifecycle_webhook_sent",
        lambda event_type: marked.append(event_type)
    )

    result = bingo_lifecycle.process_due_lifecycle_announcements(now=now)

    assert result["processed"] is True
    assert result["start"] is None
    assert result["end"]["sent_count"] == 1
    assert board_calls == [7]
    assert marked == ["end"]
    assert "bingo has ended" in sent[0]["message"]
    assert "You completed 1 tile for a total of 5 points!" in sent[0]["message"]
    assert "Here is your final board." in sent[0]["message"]