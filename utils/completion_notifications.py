import logging
from utils import (
    bingo,
    board_renderer,
    database,
    db_entities,
    send_webhook
)

logger = logging.getLogger(__name__)

def notify_tile_completion(team_id, tile_id):
    team_data = database.get_team_by_id(
        team_id
    )

    if team_data is None:
        raise ValueError(
            f"Team {team_id} does not exist."
        )

    team = db_entities.Team(
        team_data
    )

    tile_data = database.get_tile_by_id(
        tile_id
    )

    if tile_data is None:
        raise ValueError(
            f"Tile {tile_id} does not exist."
        )

    tile = db_entities.Tile(
        tile_data
    )

    if not team.team_webhook:
        return False

    board_state = bingo.get_board_render_state(
        team.team_id
    )

    board_image = board_renderer.render_bingo_board(
        board_state["tile_names_by_coordinate"],
        completed_coordinates=(
            board_state["completed_coordinates"]
        ),
        partial_coordinates=(
            board_state["partial_coordinates"]
        ),
        show_progress=True
    )

    message = (
        f"Congratulations {team.team_name}, you have completed "
        f"{tile.tile_name} at {tile.board_coordinate}! "
        f"You have gained {tile.tile_points:g} Bingo Points!"
    )

    return send_webhook.send_completion_webhook(
        team.team_webhook,
        message,
        board_image,
        discord_role_id=team.discord_role_id
    )


def notify_progress_completions(progress_results):
    notified_completions = set()

    for progress_result in progress_results:
        if not progress_result.get(
            "completed",
            False
        ):
            continue

        completion_key = (
            progress_result["team_id"],
            progress_result["tile_id"]
        )

        if completion_key in notified_completions:
            continue

        notified_completions.add(
            completion_key
        )

        try:
            notify_tile_completion(
                team_id=completion_key[0],
                tile_id=completion_key[1]
            )
        except Exception:
            logger.exception(
                "Failed to send tile completion notification "
                "for team_id=%s tile_id=%s.",
                completion_key[0],
                completion_key[1]
            )