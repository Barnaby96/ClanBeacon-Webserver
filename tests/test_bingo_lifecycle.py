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


class FakeTeam:
    def __init__(
        self,
        team_name,
        team_points,
        team_webhook,
        team_id,
        discord_role_id=None
    ):
        self.team_name = team_name
        self.team_points = team_points
        self.team_webhook = team_webhook
        self.team_id = team_id
        self.discord_role_id = discord_role_id


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
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            ("Team One", 0, "https://discord.com/api/webhooks/1/token", 1)
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
        bingo_lifecycle.database,
        "get_teams",
        lambda: [
            ("Team One", 0, "https://discord.com/api/webhooks/1/token", 1)
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
        "_render_board_image",
        lambda team_id=None: (
            board_calls.append(team_id)
            or BytesIO(b"fake board")
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
    assert "has begun" in sent[0]["message"]


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
                0,
                "https://discord.com/api/webhooks/1/token",
                7,
                None
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "_render_board_image",
        lambda team_id=None: (
            board_calls.append(team_id)
            or BytesIO(b"fake board")
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
    assert "has ended" in sent[0]["message"]


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
                0,
                "https://discord.com/api/webhooks/1/token",
                7,
                None
            )
        ]
    )

    monkeypatch.setattr(
        bingo_lifecycle,
        "_render_board_image",
        lambda team_id=None: (
            board_calls.append(team_id)
            or BytesIO(b"fake board")
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
    assert "has ended" in sent[0]["message"]
    assert "Team One's final board" in sent[0]["message"]