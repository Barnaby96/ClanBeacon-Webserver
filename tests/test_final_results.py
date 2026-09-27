from datetime import datetime, timezone
from io import BytesIO

from utils import final_results


def _leaderboard_summary():
    return {
        "teams": [
            {
                "team_id": 1,
                "team_name": "Winning Team",
                "rank": 1,
                "bingo_points": 12.5,
                "tiles_completed": 20,
                "mvp_points": 8.5,
                "mvp_players": [
                    {
                        "player_id": 10,
                        "player_name": "Team MVP"
                    }
                ]
            },
            {
                "team_id": 2,
                "team_name": "Second Team",
                "rank": 2,
                "bingo_points": 9,
                "tiles_completed": 18,
                "mvp_points": 5,
                "mvp_players": [
                    {
                        "player_id": 20,
                        "player_name": "Second MVP"
                    }
                ]
            }
        ],
        "clan": {
            "completed_tiles": 38,
            "relevant_boss_kc": 1234,
            "relevant_drop_quantity": 56,
            "relevant_xp": 7890000,
            "mvp_points": 8.5,
            "mvp_players": [
                {
                    "player_id": 10,
                    "player_name": "Team MVP",
                    "team_id": 1,
                    "team_name": "Winning Team"
                }
            ]
        }
    }


def test_build_final_results_message_contains_rankings_and_totals():
    message = final_results.build_final_results_message(
        _leaderboard_summary()
    )

    assert (
        "Winning Team is the winning team"
        in message
    )
    assert (
        "1. Winning Team - 12.5 Bingo Points - "
        "20 Tiles Completed - Team MVP (8.5 MVP Points)"
        in message
    )
    assert (
        "Team MVP is the MVP with 8.5 Points"
        in message
    )
    assert "We killed 1,234 bosses" in message
    assert "We got 56 drops" in message
    assert "we gained a huge 7,890,000 XP" in message


def test_build_bingo_history_title_uses_clan_and_dates():
    title = final_results.build_bingo_history_title(
        "Indoor Sky",
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 7, tzinfo=timezone.utc)
    )

    assert title == "Indoor Sky Bingo 01/09/2026 - 07/09/2026"


def test_publish_final_results_posts_to_each_team_webhook_with_own_role(
    monkeypatch
):
    monkeypatch.setattr(
        final_results.database,
        "get_leaderboard_summary",
        _leaderboard_summary
    )

    monkeypatch.setattr(
        final_results.database,
        "get_wom_competition_id",
        lambda: 123456
    )

    starts_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ends_at = datetime(2026, 9, 7, tzinfo=timezone.utc)

    monkeypatch.setattr(
        final_results.database,
        "get_wom_competition_timing",
        lambda: (
            starts_at,
            ends_at
        )
    )

    monkeypatch.setenv(
        "DISCORD_SERVER_NAME",
        "Indoor Sky"
    )

    monkeypatch.setattr(
        final_results.database,
        "get_teams",
        lambda: [
            (
                "Winning Team",
                12.5,
                "https://discord.com/api/webhooks/1/token",
                1,
                111,
                None
            ),
            (
                "Second Team",
                9,
                "https://discord.com/api/webhooks/2/token",
                2,
                222,
                None
            ),
            (
                "No Webhook Team",
                0,
                None,
                3,
                333,
                None
            )
        ]
    )

    board_team_ids = []

    monkeypatch.setattr(
        final_results.bingo,
        "get_board_render_state",
        lambda team_id: board_team_ids.append(team_id) or {
            "tile_names_by_coordinate": {
                "A1": "First Tile"
            },
            "completed_coordinates": [
                "A1"
            ],
            "partial_coordinates": []
        }
    )

    monkeypatch.setattr(
        final_results.board_renderer,
        "render_bingo_board",
        lambda *args, **kwargs: BytesIO(b"board image")
    )

    history_calls = []

    def fake_create_bingo_history_record(**kwargs):
        history_calls.append(kwargs)
        return 456

    monkeypatch.setattr(
        final_results.database,
        "create_bingo_history_record",
        fake_create_bingo_history_record
    )

    class Publisher:
        id = 99
        username = "Organiser"

    calls = []

    def fake_send_completion_webhook(
        url,
        message,
        board_image,
        discord_role_id=None,
        **kwargs
    ):
        calls.append({
            "url": url,
            "message": message,
            "board_image": board_image.read(),
            "discord_role_id": discord_role_id
        })

    monkeypatch.setattr(
        final_results,
        "send_completion_webhook",
        fake_send_completion_webhook
    )

    result = final_results.publish_final_results_to_team_webhooks(
        published_by_user=Publisher()
    )

    assert result == {
        "sent_count": 2,
        "failed": [],
        "history_id": 456
    }

    assert board_team_ids == [
        1
    ]

    assert len(history_calls) == 1
    history_call = history_calls[0]
    assert history_call["title"] == (
        "Indoor Sky Bingo 01/09/2026 - 07/09/2026"
    )
    assert history_call["clan_name"] == "Indoor Sky"
    assert history_call["competition_id"] == 123456
    assert history_call["competition_starts_at"] == starts_at
    assert history_call["competition_ends_at"] == ends_at
    assert history_call["published_by_user_id"] == 99
    assert history_call["published_by_username"] == "Organiser"
    assert history_call["leaderboard_snapshot"] == _leaderboard_summary()
    assert history_call["board_snapshot"] == {
        "winning_team_id": 1,
        "tile_names_by_coordinate": {
            "A1": "First Tile"
        },
        "completed_coordinates": [
            "A1"
        ],
        "partial_coordinates": []
    }

    assert [
        call["url"]
        for call in calls
    ] == [
        "https://discord.com/api/webhooks/1/token",
        "https://discord.com/api/webhooks/2/token"
    ]

    assert [
        call["discord_role_id"]
        for call in calls
    ] == [
        111,
        222
    ]

    assert all(
        call["board_image"] == b"board image"
        for call in calls
    )
