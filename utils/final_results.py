import os
from datetime import datetime

from utils import bingo, board_renderer, database, db_entities
from utils.send_webhook import send_completion_webhook


def _format_number(value):
    if value is None:
        return "0"

    numeric_value = float(value)

    if numeric_value.is_integer():
        return f"{int(numeric_value):,}"

    return f"{numeric_value:,.2f}".rstrip("0").rstrip(".")


def _format_points(value):
    return _format_number(value)


def _join_names(names):
    names = [
        str(name).strip()
        for name in names
        if str(name).strip()
    ]

    if not names:
        return "No one"

    if len(names) == 1:
        return names[0]

    if len(names) == 2:
        return f"{names[0]} and {names[1]}"

    return f"{', '.join(names[:-1])} and {names[-1]}"


def _team_mvp_text(team):
    mvp_players = team.get("mvp_players") or []

    if not mvp_players:
        return "No MVP Points awarded"

    player_names = [
        player["player_name"]
        for player in mvp_players
    ]

    return (
        f"{_join_names(player_names)} "
        f"({_format_points(team.get('mvp_points', 0))} MVP Points)"
    )


def _winning_team_text(winning_teams):
    winning_names = [
        team["team_name"]
        for team in winning_teams
    ]

    if len(winning_names) == 1:
        return f"{winning_names[0]} is the winning team"

    return f"{_join_names(winning_names)} are the winning teams"


def _clan_mvp_text(clan_summary):
    mvp_players = clan_summary.get("mvp_players") or []

    if not mvp_players:
        return "no Clan MVP was awarded"

    player_names = [
        player["player_name"]
        for player in mvp_players
    ]

    mvp_points = _format_points(
        clan_summary.get("mvp_points", 0)
    )

    if len(player_names) == 1:
        return (
            f"{player_names[0]} is the MVP with "
            f"{mvp_points} Points"
        )

    return (
        f"{_join_names(player_names)} are the MVPs with "
        f"{mvp_points} Points"
    )


def build_final_results_message(leaderboard_summary):
    teams = leaderboard_summary.get("teams") or []

    if not teams:
        raise ValueError(
            "Final results cannot be published because no teams "
            "are configured."
        )

    winning_rank = teams[0]["rank"]
    winning_teams = [
        team
        for team in teams
        if team["rank"] == winning_rank
    ]

    ranking_lines = []

    for team in teams:
        ranking_lines.append(
            f"{team['rank']}. {team['team_name']} - "
            f"{_format_points(team['bingo_points'])} Bingo Points - "
            f"{team['tiles_completed']} Tiles Completed - "
            f"{_team_mvp_text(team)}"
        )

    clan = leaderboard_summary.get("clan") or {}

    return (
        "Our bingo staff have finished their review and we are proud "
        f"to say that {_winning_team_text(winning_teams)}!\n\n"
        "Team rankings:\n"
        "Place. Team Name - Bingo Points - Tiles Completed - Team MVP\n"
        f"{chr(10).join(ranking_lines)}\n\n"
        f"and that {_clan_mvp_text(clan)}!\n\n"
        "Well done to all of you for the amazing performance:\n\n"
        f"We killed {_format_number(clan.get('relevant_boss_kc', 0))} bosses\n"
        f"We got {_format_number(clan.get('relevant_drop_quantity', 0))} drops\n"
        f"and we gained a huge {_format_number(clan.get('relevant_xp', 0))} XP\n\n"
        "Here is the winning team's final board."
    )


def _history_clan_name():
    return (
        os.getenv("DISCORD_SERVER_NAME", "Clan").strip()
        or "Clan"
    )


def _history_date_label(value):
    if value is None:
        return "Unknown Date"

    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")

    value_text = str(value).strip()
    if not value_text:
        return "Unknown Date"

    iso_candidates = [
        value_text,
        value_text.replace("Z", "+00:00")
    ]

    for candidate in iso_candidates:
        try:
            parsed_value = datetime.fromisoformat(candidate)
        except ValueError:
            continue

        return parsed_value.strftime("%d/%m/%Y")

    date_part = value_text.split("T", 1)[0].split(" ", 1)[0]
    if (
        len(date_part) == 10
        and date_part[4] == "-"
        and date_part[7] == "-"
    ):
        year, month, day = date_part.split("-")
        return f"{day}/{month}/{year}"

    return value_text


def build_bingo_history_title(clan_name, starts_at, ends_at):
    return (
        f"{clan_name} Bingo "
        f"{_history_date_label(starts_at)} - "
        f"{_history_date_label(ends_at)}"
    )


def _publisher_details(published_by_user):
    if published_by_user is None:
        return None, None

    return (
        getattr(published_by_user, "id", None),
        getattr(published_by_user, "username", None)
    )


def _winning_team_board_snapshot(leaderboard_summary):
    teams = leaderboard_summary.get("teams") or []

    if not teams:
        raise ValueError(
            "Final results cannot be published because no teams "
            "are configured."
        )

    winning_team_id = teams[0]["team_id"]
    board_state = bingo.get_board_render_state(winning_team_id)

    return {
        "winning_team_id": winning_team_id,
        "tile_names_by_coordinate": dict(
            board_state["tile_names_by_coordinate"]
        ),
        "completed_coordinates": list(
            board_state["completed_coordinates"]
        ),
        "partial_coordinates": list(
            board_state["partial_coordinates"]
        )
    }


def _render_board_from_snapshot(board_snapshot):
    board_image = board_renderer.render_bingo_board(
        board_snapshot["tile_names_by_coordinate"],
        completed_coordinates=board_snapshot["completed_coordinates"],
        partial_coordinates=board_snapshot["partial_coordinates"]
    )

    board_image.seek(0)

    return board_image


def _render_winning_team_board(leaderboard_summary):
    board_snapshot = _winning_team_board_snapshot(leaderboard_summary)
    return _render_board_from_snapshot(board_snapshot)


def _all_teams():
    return [
        db_entities.Team(team_row)
        for team_row in database.get_teams()
    ]



def _teams_with_webhooks(teams):
    return [
        team
        for team in teams
        if str(team.team_webhook or "").strip()
    ]


def publish_final_results_to_team_webhooks(published_by_user=None):
    leaderboard_summary = database.get_leaderboard_summary()
    message = build_final_results_message(leaderboard_summary)

    teams = _all_teams()
    teams_with_webhooks = _teams_with_webhooks(teams)
    if not teams_with_webhooks:
        raise ValueError(
            "Final results cannot be published because no team "
            "webhooks are configured."
        )

    board_snapshot = _winning_team_board_snapshot(leaderboard_summary)
    competition_id = database.get_wom_competition_id()
    timing = database.get_wom_competition_timing()

    if timing is None:
        starts_at = None
        ends_at = None
    else:
        starts_at, ends_at = timing

    clan_name = _history_clan_name()
    published_by_user_id, published_by_username = _publisher_details(
        published_by_user
    )

    history_id = database.create_bingo_history_record(
        title=build_bingo_history_title(
            clan_name,
            starts_at,
            ends_at
        ),
        clan_name=clan_name,
        competition_id=competition_id,
        competition_starts_at=starts_at,
        competition_ends_at=ends_at,
        published_by_user_id=published_by_user_id,
        published_by_username=published_by_username,
        final_message=message,
        leaderboard_snapshot=leaderboard_summary,
        board_snapshot=board_snapshot
    )

    sent_count = 0
    failed = []

    for team in teams_with_webhooks:
        board_image = _render_board_from_snapshot(board_snapshot)

        try:
            send_completion_webhook(
                team.team_webhook,
                message,
                board_image,
                discord_role_id=team.discord_role_id
            )
            sent_count += 1
        except Exception as error:
            failed.append({
                "team_id": team.team_id,
                "team_name": team.team_name,
                "error": str(error)
            })

    return {
        "sent_count": sent_count,
        "failed": failed,
        "history_id": history_id
    }
