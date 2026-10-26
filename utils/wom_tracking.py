from utils import (
    completion_notifications,
    database,
    db_entities,
    wom
)
from utils.branding import BOT_NAME


def process_wom_competition():
    competition_id = database.get_wom_competition_id()

    if competition_id is None:
        return {
            "competition_id": None,
            "metrics_processed": 0,
            "players_processed": 0,
            "tiles_completed": [],
            "errors": []
        }

    conditions = database.get_wom_tile_conditions()

    metric_types = {
        (
            condition[3],
            str(condition[4]).strip().lower()
        )
        for condition in conditions
        if condition[4]
    }

    result = {
        "competition_id": competition_id,
        "metrics_processed": 0,
        "players_processed": 0,
        "tiles_completed": [],
        "errors": []
    }

    for condition_type, metric in sorted(metric_types):
        try:
            competition = wom.get_competition_details(
                competition_id,
                metric=metric
            )
        except wom.WiseOldManError as error:
            result["errors"].append(
                {
                    "metric": metric,
                    "error": str(error)
                }
            )
            continue

        result["metrics_processed"] += 1

        for participation in competition.get(
            "participations",
            []
        ):
            wom_player_id = participation.get("playerId")

            if wom_player_id is None:
                continue

            player_row = database.get_player_by_wom_player_id(
                wom_player_id
            )

            if player_row is None:
                result["errors"].append(
                    {
                        "metric": metric,
                        "wom_player_id": wom_player_id,
                        "error": (
                            "WOM participant is not linked "
                            f"to a {BOT_NAME} player."
                        )
                    }
                )
                continue

            player = db_entities.Player(player_row)

            progress = participation.get("progress") or {}
            current_gain = progress.get("gained")

            if current_gain is None:
                result["errors"].append(
                    {
                        "metric": metric,
                        "wom_player_id": wom_player_id,
                        "error": (
                            "WOM participation has no "
                            "gained progress value."
                        )
                    }
                )
                continue

            try:
                progress_result = (
                    database.apply_wom_metric_progress(
                        competition_id,
                        player.player_id,
                        condition_type,
                        metric,
                        current_gain
                    )
                )
            except (TypeError, ValueError) as error:
                result["errors"].append(
                    {
                        "metric": metric,
                        "wom_player_id": wom_player_id,
                        "error": str(error)
                    }
                )
                continue

            result["players_processed"] += 1

            for tile_result in progress_result["tiles"]:
                if not tile_result["ready"]:
                    continue

                try:
                    completed = (
                        database.complete_tile_with_contributions(
                            player.team_id,
                            tile_result["tile_id"]
                        )
                    )
                except ValueError as error:
                    result["errors"].append(
                        {
                            "metric": metric,
                            "tile_id": tile_result["tile_id"],
                            "error": str(error)
                        }
                    )
                    continue

                if completed:
                    result["tiles_completed"].append(
                        {
                            "tile_id": tile_result["tile_id"],
                            "team_id": player.team_id,
                            "metric": metric
                        }
                    )

                    completion_notifications.notify_progress_completions(
                        [
                            {
                                "team_id": player.team_id,
                                "tile_id": tile_result["tile_id"],
                                "completed": True
                            }
                        ]
                    )

    return result


def try_process_wom_competition(*, scheduled_slot=None):
    """Run WOM processing only when no refresh is active.

    Returns the normal processing result when successful.
    Returns None when another process holds the refresh lock.

    Database connection and lock lifetime cover the entire
    competition-processing operation.
    """
    with database.wom_refresh_lock() as acquired:
        if not acquired:
            return None

        if scheduled_slot is not None:
            if not database.claim_wom_poll_slot(*scheduled_slot):
                return None

        return process_wom_competition()
