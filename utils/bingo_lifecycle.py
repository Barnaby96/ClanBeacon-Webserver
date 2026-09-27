from datetime import datetime, timezone

from utils import bingo, board_renderer, database, db_entities
from utils.branding import BOT_NAME
from utils.send_webhook import send_completion_webhook


def _as_utc(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _ready_at_or_before(lifecycle_ready_at, event_time):
    ready_at = _as_utc(lifecycle_ready_at)

    if ready_at is None:
        return True

    return ready_at <= event_time

def _format_number(value):
    if value is None:
        return "0"

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def _pluralise(count, singular, plural=None):
    if count == 1:
        return singular

    if plural is not None:
        return plural

    return f"{singular}s"


def _completed_tile_count(board_state):
    completed_coordinates = board_state.get(
        "completed_coordinates",
        []
    ) or []

    return len(completed_coordinates)


def _render_board_image_from_state(board_state):
    board_image = board_renderer.render_bingo_board(
        board_state["tile_names_by_coordinate"],
        completed_coordinates=board_state["completed_coordinates"],
        partial_coordinates=board_state["partial_coordinates"]
    )

    board_image.seek(0)
    return board_image


def _render_board_image_and_state(team_id=None):
    board_state = bingo.get_board_render_state(team_id)
    board_image = _render_board_image_from_state(board_state)

    return board_image, board_state


def _configured_teams():
    teams = []

    for team_row in database.get_teams():
        team = db_entities.Team(team_row)

        if team.team_webhook:
            teams.append(team)

    return teams


def _start_message(team):
    return (
        f"{BOT_NAME} bingo has begun!\n\n"
        f"Here is the board. Good luck {team.team_name}"
    )


def _end_message(team, completed_tiles):
    tile_word = _pluralise(completed_tiles, "tile")
    points = _format_number(team.team_points)
    point_word = _pluralise(team.team_points or 0, "point")

    return (
        f"{BOT_NAME} bingo has ended!\n\n"
        f"You completed {completed_tiles} {tile_word} "
        f"for a total of {points} {point_word}!\n\n"
        "Full results will be published after a review by the admin team!\n\n"
        "Here is your final board."
    )


def _send_start_announcements(teams):
    sent_count = 0
    failed = []

    for team in teams:
        board_image, _board_state = _render_board_image_and_state(
            team_id=None
        )

        try:
            send_completion_webhook(
                team.team_webhook,
                _start_message(team),
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
        board_image, board_state = _render_board_image_and_state(
            team_id=team.team_id
        )
        completed_tiles = _completed_tile_count(board_state)

        try:
            send_completion_webhook(
                team.team_webhook,
                _end_message(team, completed_tiles),
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

    results = {
        "processed": False,
        "start": None,
        "end": None,
    }

    if now >= ends_at:
        if (
            status["end_webhook_sent_at"] is None
            and _ready_at_or_before(
                status.get("lifecycle_ready_at"),
                ends_at
            )
        ):
            teams = _configured_teams()
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
        and _ready_at_or_before(
            status.get("lifecycle_ready_at"),
            starts_at
        )
    ):
        teams = _configured_teams()
        start_result = _send_start_announcements(teams)
        database.mark_bingo_lifecycle_webhook_sent("start")

        results["processed"] = True
        results["start"] = start_result

    if not results["processed"]:
        results["reason"] = "no_lifecycle_announcements_due"

    return results