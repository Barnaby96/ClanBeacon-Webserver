from io import BytesIO

from utils import completion_notifications


def test_notify_tile_completion_posts_current_team_board(
    monkeypatch
):
    captured = {}

    team_row = (
        "Zamorak",
        25,
        "https://discord.com/api/webhooks/"
        "123456789012345678/test-webhook-token",
        2,
        987654321098765432,
        None
    )

    tile_row = (
        20,
        "Obtain 30 Feathers",
        None,
        None,
        None,
        False,
        1,
        1,
        5,
        None,
        "A1"
    )

    monkeypatch.setattr(
        completion_notifications.database,
        "get_team_by_id",
        lambda team_id: team_row
    )

    monkeypatch.setattr(
        completion_notifications.database,
        "get_tile_by_id",
        lambda tile_id: tile_row
    )

    monkeypatch.setattr(
        completion_notifications.bingo,
        "get_board_render_state",
        lambda team_id: {
            "tile_names_by_coordinate": {
                "A1": "Obtain 30 Feathers"
            },
            "completed_coordinates": {
                "A1"
            },
            "partial_coordinates": set()
        }
    )

    def fake_render_bingo_board(
        tile_names_by_coordinate,
        *,
        completed_coordinates=None,
        partial_coordinates=None,
        show_progress=True
    ):
        captured["render"] = {
            "tile_names_by_coordinate":
                tile_names_by_coordinate,
            "completed_coordinates":
                completed_coordinates,
            "partial_coordinates":
                partial_coordinates,
            "show_progress":
                show_progress
        }

        return BytesIO(
            b"current-team-board"
        )

    monkeypatch.setattr(
        completion_notifications.board_renderer,
        "render_bingo_board",
        fake_render_bingo_board
    )

    def fake_send_completion_webhook(
        url,
        message,
        board_image,
        discord_role_id=None
    ):
        captured["webhook"] = {
            "url": url,
            "message": message,
            "board_image": board_image.read(),
            "discord_role_id": discord_role_id
        }

        return True

    monkeypatch.setattr(
        completion_notifications.send_webhook,
        "send_completion_webhook",
        fake_send_completion_webhook
    )

    result = (
        completion_notifications.notify_tile_completion(
            team_id=2,
            tile_id=20
        )
    )

    assert result is True

    assert captured["render"] == {
        "tile_names_by_coordinate": {
            "A1": "Obtain 30 Feathers"
        },
        "completed_coordinates": {
            "A1"
        },
        "partial_coordinates": set(),
        "show_progress": True
    }

    assert captured["webhook"] == {
        "url": team_row[2],
        "message": (
            "Congratulations Zamorak, you have completed "
            "Obtain 30 Feathers at A1! You have gained "
            "5 Bingo Points!"
        ),
        "board_image": b"current-team-board",
        "discord_role_id": 987654321098765432
    }


def test_notify_progress_completions_only_notifies_new_tiles(
    monkeypatch
):
    notified = []

    def fake_notify_tile_completion(
        team_id,
        tile_id
    ):
        notified.append(
            (
                team_id,
                tile_id
            )
        )

        return True

    monkeypatch.setattr(
        completion_notifications,
        "notify_tile_completion",
        fake_notify_tile_completion
    )

    completion_notifications.notify_progress_completions(
        [
            {
                "team_id": 2,
                "tile_id": 20,
                "completed": True
            },
            {
                "team_id": 2,
                "tile_id": 20,
                "completed": True
            },
            {
                "team_id": 2,
                "tile_id": 21,
                "completed": False
            },
            {
                "team_id": 3,
                "tile_id": 22,
                "completed": True
            }
        ]
    )

    assert notified == [
        (
            2,
            20
        ),
        (
            3,
            22
        )
    ]


def test_notify_progress_completions_continues_after_notification_failure(
    monkeypatch
):
    from utils import completion_notifications

    notification_attempts = []

    def fake_notify_tile_completion(
        team_id,
        tile_id
    ):
        notification_attempts.append(
            (
                team_id,
                tile_id
            )
        )

        if tile_id == 20:
            raise RuntimeError(
                "Discord unavailable"
            )

        return True

    monkeypatch.setattr(
        completion_notifications,
        "notify_tile_completion",
        fake_notify_tile_completion
    )

    completion_notifications.notify_progress_completions(
        [
            {
                "team_id": 2,
                "tile_id": 20,
                "completed": True
            },
            {
                "team_id": 3,
                "tile_id": 22,
                "completed": True
            }
        ]
    )

    assert notification_attempts == [
        (
            2,
            20
        ),
        (
            3,
            22
        )
    ]


def test_notify_tile_correction_posts_updated_team_board(
    monkeypatch
):
    captured = {}

    team_row = (
        "Zamorak",
        25,
        "https://discord.com/api/webhooks/"
        "123456789012345678/test-webhook-token",
        2,
        987654321098765432,
        None
    )

    tile_row = (
        20,
        "Obtain 30 Feathers",
        None,
        None,
        None,
        False,
        1,
        1,
        5,
        None,
        "A1"
    )

    monkeypatch.setattr(
        completion_notifications.database,
        "get_team_by_id",
        lambda team_id: team_row
    )

    monkeypatch.setattr(
        completion_notifications.database,
        "get_tile_by_id",
        lambda tile_id: tile_row
    )

    monkeypatch.setattr(
        completion_notifications.bingo,
        "get_board_render_state",
        lambda team_id: {
            "tile_names_by_coordinate": {
                "A1": "Obtain 30 Feathers"
            },
            "completed_coordinates": set(),
            "partial_coordinates": {
                "A1"
            }
        }
    )

    def fake_render_bingo_board(
        tile_names_by_coordinate,
        *,
        completed_coordinates=None,
        partial_coordinates=None,
        show_progress=True
    ):
        captured["render"] = {
            "tile_names_by_coordinate":
                tile_names_by_coordinate,
            "completed_coordinates":
                completed_coordinates,
            "partial_coordinates":
                partial_coordinates,
            "show_progress":
                show_progress
        }

        return BytesIO(
            b"updated-team-board"
        )

    monkeypatch.setattr(
        completion_notifications.board_renderer,
        "render_bingo_board",
        fake_render_bingo_board
    )

    def fake_send_completion_webhook(
        url,
        message,
        board_image,
        discord_role_id=None
    ):
        captured["webhook"] = {
            "url": url,
            "message": message,
            "board_image": board_image.read(),
            "discord_role_id": discord_role_id
        }

        return True

    monkeypatch.setattr(
        completion_notifications.send_webhook,
        "send_completion_webhook",
        fake_send_completion_webhook
    )

    result = (
        completion_notifications.notify_tile_correction(
            team_id=2,
            tile_id=20
        )
    )

    assert result is True

    assert captured["render"] == {
        "tile_names_by_coordinate": {
            "A1": "Obtain 30 Feathers"
        },
        "completed_coordinates": set(),
        "partial_coordinates": {
            "A1"
        },
        "show_progress": True
    }

    assert captured["webhook"] == {
        "url": team_row[2],
        "message": (
            "Correction for Zamorak: Obtain 30 Feathers at A1 "
            "is no longer complete after an evidence review. "
            "Your updated bingo board is attached."
        ),
        "board_image": b"updated-team-board",
        "discord_role_id": 987654321098765432
    }


def test_notify_tile_corrections_only_notifies_reopened_tiles(
    monkeypatch
):
    notified = []

    def fake_notify_tile_correction(
        team_id,
        tile_id
    ):
        notified.append(
            (
                team_id,
                tile_id
            )
        )

        return True

    monkeypatch.setattr(
        completion_notifications,
        "notify_tile_correction",
        fake_notify_tile_correction
    )

    completion_notifications.notify_tile_corrections(
        [
            {
                "team_id": 2,
                "tile_id": 20
            },
            {
                "team_id": 2,
                "tile_id": 20
            },
            {
                "team_id": 3,
                "tile_id": 22
            }
        ]
    )

    assert notified == [
        (
            2,
            20
        ),
        (
            3,
            22
        )
    ]


def test_notify_tile_corrections_continues_after_notification_failure(
    monkeypatch
):
    notification_attempts = []

    def fake_notify_tile_correction(
        team_id,
        tile_id
    ):
        notification_attempts.append(
            (
                team_id,
                tile_id
            )
        )

        if tile_id == 20:
            raise RuntimeError(
                "Discord unavailable"
            )

        return True

    monkeypatch.setattr(
        completion_notifications,
        "notify_tile_correction",
        fake_notify_tile_correction
    )

    completion_notifications.notify_tile_corrections(
        [
            {
                "team_id": 2,
                "tile_id": 20
            },
            {
                "team_id": 3,
                "tile_id": 22
            }
        ]
    )

    assert notification_attempts == [
        (
            2,
            20
        ),
        (
            3,
            22
        )
    ]


def test_notify_tile_corrections_does_nothing_when_none_reopened(
    monkeypatch
):
    notification_attempts = []

    monkeypatch.setattr(
        completion_notifications,
        "notify_tile_correction",
        lambda **kwargs: notification_attempts.append(
            kwargs
        )
    )

    completion_notifications.notify_tile_corrections(
        []
    )

    assert notification_attempts == []
