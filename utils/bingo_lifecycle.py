from datetime import datetime, timezone

from utils import bingo, board_renderer, database, db_entities
from utils.branding import BOT_NAME
from utils.send_webhook import send_completion_webhook


START_COLOUR = 0x2ECC71
END_COLOUR = 0xF1C40F


def _as_utc(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _render_board_image(team_id=None):
    board_state = bingo.get_board_render_state(team_id)

    board_image = board_renderer.render_bingo_board(
        board_state["tile_names_by_coordinate"],
        completed_coordinates=board_state["completed_coordinates"],
        partial_coordinates=board_state["partial_coordinates"]
    )

    board_image.seek(0)
    return board_image


def _configured_teams():
    teams = []

    for team_row in database.get_teams():
        team = db_entities.Team(team_row)

        if team.team_webhook:
            teams.append(team)

    return teams


def _send_start_announcements(teams):
    sent_count = 0
    failed = []

    for team in teams:
        board_image = _render_board_image(team_id=None)

        message = (
            f"{BOT_NAME} bingo has begun!\n\n"
            "Here is the clean board. Good luck, team!"
        )

        try:
            send_completion_webhook(
                team.team_webhook,
                message,
                board_image,
                discord_role_id=team.discord_role_id
            )
            sent_count += 1
        except Exception as error:
            failed.append(
                {
                    "team_id": team.team_id,
                    "team_name": team.team_name,
                    "error": str(error),
                }
            )

    return {
        "sent_count": sent_count,
        "failed": failed,
    }


def _send_end_announcements(teams):
    sent_count = 0
    failed = []

    for team in teams:
        board_image = _render_board_image(team_id=team.team_id)

        message = (
            f"{BOT_NAME} bingo has ended!\n\n"
            f"Here is {team.team_name}'s final board."
        )

        try:
            send_completion_webhook(
                team.team_webhook,
                message,
                board_image,
                discord_role_id=team.discord_role_id
            )
            sent_count += 1
        except Exception as error:
            failed.append(
                {
                    "team_id": team.team_id,
                    "team_name": team.team_name,
                    "error": str(error),
                }
            )

    return {
        "sent_count": sent_count,
        "failed": failed,
    }


def process_due_lifecycle_announcements(now=None):
    status = database.get_bingo_lifecycle_status()

    if status is None:
        return {
            "processed": False,
            "reason": "missing_bingo_config",
        }

    starts_at = _as_utc(status["starts_at"])
    ends_at = _as_utc(status["ends_at"])

    if starts_at is None or ends_at is None:
        return {
            "processed": False,
            "reason": "missing_competition_timing",
        }

    if not status.get("lifecycle_ready"):
        return {
            "processed": False,
            "reason": "bingo_lifecycle_not_ready",
        }

    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = _as_utc(now)

    teams = _configured_teams()

    results = {
        "processed": False,
        "start": None,
        "end": None,
    }

    if now >= ends_at:
        if status["end_webhook_sent_at"] is None:
            end_result = _send_end_announcements(teams)
            database.mark_bingo_lifecycle_webhook_sent("end")

            results["processed"] = True
            results["end"] = end_result

        if not results["processed"]:
            results["reason"] = "no_lifecycle_announcements_due"

        return results

    if (
        status["start_webhook_sent_at"] is None
        and now >= starts_at
    ):
        start_result = _send_start_announcements(teams)
        database.mark_bingo_lifecycle_webhook_sent("start")

        results["processed"] = True
        results["start"] = start_result

    if not results["processed"]:
        results["reason"] = "no_lifecycle_announcements_due"

    return results