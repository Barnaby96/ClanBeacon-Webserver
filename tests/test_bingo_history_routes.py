import pytest

from main import app
from utils import database


@pytest.fixture()
def client():
    database.reset_tables()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def _create_user(
    username,
    password="test-password",
    account_role="PLAYER"
):
    database.add_user(
        username,
        password
    )

    with database.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET
                account_role = %s,
                is_admin = %s
            WHERE username = %s
            """,
            (
                account_role,
                account_role in ("ADMIN", "ORGANISER"),
                username
            )
        )
        conn.commit()


def _login(
    client,
    username,
    password="test-password"
):
    response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert response.status_code == 302


def _create_history_record(title="Indoor Sky Bingo 01/09/2026 - 07/09/2026"):
    return database.create_bingo_history_record(
        title=title,
        clan_name="Indoor Sky",
        competition_id=123456,
        competition_starts_at=None,
        competition_ends_at=None,
        published_by_user_id=None,
        published_by_username="Organiser User",
        final_message="Final results message",
        leaderboard_snapshot={
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
                }
            ],
            "clan": {
                "relevant_boss_kc": 123,
                "relevant_drop_quantity": 4,
                "relevant_xp": 5678
            }
        },
        board_snapshot={
            "winning_team_id": 1,
            "tile_names_by_coordinate": {
                "A1": "First Tile"
            },
            "completed_coordinates": [
                "A1"
            ],
            "partial_coordinates": []
        }
    )


def test_bingo_history_page_shows_visible_records(client):
    _create_user("History Player")
    history_id = _create_history_record()

    _login(client, "History Player")

    response = client.get("/user/bingo_history")

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Bingo History" in html
    assert "Indoor Sky Bingo 01/09/2026 - 07/09/2026" in html
    assert "Winning Team" in html
    assert "Final results message" in html
    assert f"/user/bingo_history/{history_id}/board" in html
    assert "Delete Record" not in html


def test_bingo_history_page_hides_soft_deleted_records(client):
    _create_user("History Player")
    history_id = _create_history_record("Indoor Sky Bingo Hidden")

    database.soft_delete_bingo_history_record(
        history_id,
        deleted_by_user_id=None,
        deleted_by_username="Organiser User"
    )

    _login(client, "History Player")

    response = client.get("/user/bingo_history")

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Indoor Sky Bingo Hidden" not in html
    assert "No Bingo History Yet" in html


def test_bingo_history_board_route_returns_png(client):
    _create_user("History Player")
    history_id = _create_history_record()

    _login(client, "History Player")

    response = client.get(f"/user/bingo_history/{history_id}/board")

    assert response.status_code == 200
    assert response.content_type == "image/png"


def test_non_organiser_cannot_delete_bingo_history_record(client):
    _create_user("History Player")
    history_id = _create_history_record()

    _login(client, "History Player")

    response = client.post(
        f"/user/bingo_history/{history_id}/delete",
        data={
            "delete_password": "test-password"
        }
    )

    assert response.status_code == 403
    assert database.get_bingo_history_record(history_id) is not None


def test_organiser_delete_requires_correct_password(client):
    _create_user(
        "History Organiser",
        account_role="ORGANISER"
    )
    history_id = _create_history_record()

    _login(client, "History Organiser")

    response = client.post(
        f"/user/bingo_history/{history_id}/delete",
        data={
            "delete_password": "wrong-password"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert "Password confirmation was incorrect." in response.get_data(
        as_text=True
    )
    assert database.get_bingo_history_record(history_id) is not None


def test_organiser_can_soft_delete_bingo_history_record(client):
    _create_user(
        "History Organiser",
        account_role="ORGANISER"
    )
    history_id = _create_history_record()

    _login(client, "History Organiser")

    response = client.post(
        f"/user/bingo_history/{history_id}/delete",
        data={
            "delete_password": "test-password"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert "Bingo history record deleted." in response.get_data(
        as_text=True
    )
    assert database.get_bingo_history_record(history_id) is None

    deleted_record = database.get_bingo_history_record(
        history_id,
        include_deleted=True
    )

    assert deleted_record is not None
    assert deleted_record["deleted_by_username"] == "History Organiser"
