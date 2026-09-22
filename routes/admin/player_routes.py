import os

from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint

from utils.auth import admin_required
from utils.branding import get_wom_user_agent
from utils import db_entities, wom, team_balancing
from utils.database import add_player, get_players, get_player_by_id, remove_player, rename_player, \
    get_players_by_team_id, update_player, change_player_team, get_team_by_name, get_teams, \
    get_manage_players_roster, get_team_by_id
import requests



player_routes = Blueprint("player_management", __name__)

@player_routes.route('/players', methods=['GET'])
@admin_required
def player_list():
    teams = get_manage_players_roster()
    team_count = len(teams)
    player_count = sum(
        len(team["players"])
        for team in teams
    )

    return render_template(
        'admin_templates/player_templates/player_list.html',
        teams=teams,
        team_count=team_count,
        player_count=player_count
    )


@player_routes.route('/players/balance', methods=['GET', 'POST'])
@admin_required
def balance_players():
    group_id = str(
        request.values.get(
            "group_id",
            ""
        )
    ).strip()

    team_count_raw = str(
        request.values.get(
            "team_count",
            "2"
        )
    ).strip()

    try:
        team_count = int(
            team_count_raw
        )
    except ValueError:
        team_count = 2

    group_name = None
    group_members = []
    selected_player_names = []
    suggested_teams = None
    failed_players = []

    keep_apart_text = str(
        request.values.get(
            "keep_apart_text",
            ""
        )
    ).strip()

    keep_apart_groups = team_balancing.parse_keep_apart_text(
        keep_apart_text
    )

    if group_id:
        try:
            group_data = wom.get_group(
                group_id
            )
        except wom.WiseOldManError as error:
            flash(
                str(error),
                "danger"
            )
        else:
            group_name = group_data.get(
                "name"
            )

            seen_players = set()

            for membership in group_data.get(
                "memberships",
                []
            ):
                player = membership.get(
                    "player"
                ) or {}

                player_name = str(
                    player.get("displayName")
                    or player.get("username")
                    or ""
                ).strip()

                if not player_name:
                    continue

                player_key = player_name.casefold()

                if player_key in seen_players:
                    continue

                seen_players.add(
                    player_key
                )

                group_members.append(
                    {
                        "player_id": player.get("id"),
                        "player_name": player_name,
                        "username": player.get("username")
                    }
                )

            group_members.sort(
                key=lambda player: player["player_name"].casefold()
            )

    if request.method == "POST":
        selected_player_names = [
            str(player_name).strip()
            for player_name in request.form.getlist(
                "player_names"
            )
            if str(player_name).strip()
        ]

        if team_count <= 0:
            flash(
                "Team count must be greater than zero.",
                "danger"
            )
        elif not selected_player_names:
            flash(
                "Select at least one player before building teams.",
                "warning"
            )
        else:
            player_data = []

            for player_name in selected_player_names:
                try:
                    player_data.append(
                        wom.get_player(
                            player_name
                        )
                    )
                except wom.WiseOldManError as error:
                    failed_players.append(
                        {
                            "player_name": player_name,
                            "error": str(error)
                        }
                    )

            if failed_players:
                failed_names = ", ".join(
                    failed_player["player_name"]
                    for failed_player in failed_players
                )

                flash(
                    f"Could not fetch WOM stats for: {failed_names}.",
                    "warning"
                )

            if player_data:
                try:
                    suggested_teams = team_balancing.build_balanced_teams(
                        player_data,
                        team_count,
                        keep_apart_groups=keep_apart_groups
                    )
                except ValueError as error:
                    flash(
                        str(error),
                        "danger"
                    )

    selected_player_keys = {
        player_name.casefold()
        for player_name in selected_player_names
    }

    return render_template(
        'admin_templates/player_templates/team_balance.html',
        group_id=group_id,
        group_name=group_name,
        group_members=group_members,
        selected_player_keys=selected_player_keys,
        team_count=team_count,
        keep_apart_text=keep_apart_text,
        suggested_teams=suggested_teams,
        failed_players=failed_players
    )


@player_routes.route('/players/wom/update', methods=['POST'])
@admin_required
def update_all_wom_players():
    teams = get_manage_players_roster()

    player_names = [
        player["player_name"]
        for team in teams
        for player in team["players"]
    ]

    if not player_names:
        flash(
            'There are no event players to update on Wise Old Man.',
            'warning'
        )
        return redirect(
            url_for('player_management.player_list')
        )

    results = wom.update_players(
        player_names
    )

    updated_count = len(
        results["updated"]
    )
    failed_count = len(
        results["failed"]
    )

    if updated_count:
        flash(
            f'Forced Wise Old Man updates for {updated_count} '
            'event player(s).',
            'success'
        )

    if failed_count:
        failed_players = ', '.join(
            failure["player_name"]
            for failure in results["failed"]
        )

        flash(
            f'Wise Old Man could not update {failed_count} '
            f'event player(s): {failed_players}.',
            'warning'
        )

    if not updated_count and not failed_count:
        flash(
            'There are no valid event player names to update on Wise Old Man.',
            'warning'
        )

    return redirect(
        url_for('player_management.player_list')
    )


API_KEY = os.getenv('WOM_KEY')
DISCORD_NAME = get_wom_user_agent()

@player_routes.route('/add_list/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def add_player_list(team_id):
    team = get_team_by_id(team_id)
    team = db_entities.Team(team)
    team_name = team.team_name
    successful = True
    if request.method == 'POST':
        players_to_add = []
        for player in request.form.get('player_names').split('\n'):
            player = player.strip().replace('\r','')
            headers = {
                'x-api-key': API_KEY,
                'User-Agent': DISCORD_NAME
            }
            response = requests.get(f'https://api.wiseoldman.net/v2/players/{player.strip().replace("-", "%20")}',
                                    headers)

            if response.status_code == 200:
                data = response.json()
                foundName = data['displayName']
                if foundName.lower() != player.lower():
                    flash(f'Warning! {player} does not exist but instead found {foundName}. Adding {foundName} instead. ')
                    player = foundName

                players_to_add.append(player)
            elif response.status_code == 404:
                response_suggestion = requests.get(f"https://api.wiseoldman.net/v2/players/search?username={player.strip().replace('-', '%20')}&limit=1")
                response_data = response_suggestion.json()

                if response_data and len(response_data) > 0:
                    suggested_name = response_data[0]["displayName"]
                    flash(
                        f'The given RSN {player} does not exist and was not added to the team. Did you mean {suggested_name} instead?',
                        'danger')
                else:
                    flash(f'The given RSN {player} does not exist and was not added to the team.', 'danger')

                successful = False
                continue
            else:
                flash('We are limited to checking 100 usernames per minute. Please wait before trying again (no players were added)', 'danger')
                return render_template('admin_templates/player_templates/new_player_list.html', team_name=team_name,
                                       team_id=team_id)

        for player in players_to_add:
            add_player(player, 0, 0, 0, team_id, 0)

        if successful:
            flash('Added all players!')
            return redirect(url_for('team_routes.team_list'))
        else:
            return render_template('admin_templates/player_templates/new_player_list.html', team_name=team_name, team_id=team_id)

    return render_template('admin_templates/player_templates/new_player_list.html', team_name=team_name, team_id=team_id)


@player_routes.route('/new', methods=['GET', 'POST'])
@admin_required
def create_player():
    teams = get_teams()  # Fetch all teams to get their names
    if request.method == 'POST':
        player = request.form.get('player_name')
        team_name = request.form.get('team_name')

        # Call the external API to search for the player
        headers = {
            'x-api-key': API_KEY,
            'User-Agent': DISCORD_NAME
        }
        response = requests.get(f'https://api.wiseoldman.net/v2/players/{player.strip().replace("-", "%20")}', headers)

        if response.status_code == 200:
            data = response.json()
            foundName = data['displayName']
            if foundName.lower() != player.lower():
                flash(f'Warning! {player} does not exist but instead found {foundName}. Adding {foundName} instead. ')
                player = foundName

            # Get team_id by team_name
            team = get_team_by_name(team_name)
            team_id = team[3]  # Assuming team_id is in the 4th position in the result

            add_player(player, 0, 0, 0, team_id, 0)

            flash('Player created successfully!', 'success')
            return redirect(url_for('player_management.player_list'))
        elif response.status_code == 404:
            response_suggestion = requests.get(
                f"https://api.wiseoldman.net/v2/players/search?username={player.strip().replace('-', '%20')}&limit=1")
            flash(
                f'The given RSN {player} does not exist and was not added to the team. Did you mean {response_suggestion.json()[0]["displayName"]} instead?',
                'danger')
        else:
            flash('Failed to connect to the Wise Old Man API. Please try again later.', 'danger')
            return redirect(url_for('player_management.create_player'))

    return render_template('admin_templates/player_templates/new_player_form.html', teams=teams)



@player_routes.route('/edit/<int:player_id>', methods=['GET', 'POST'])
@admin_required
def edit_player(player_id):
    player = get_player_by_id(player_id)
    teams = get_teams()  # Fetch all teams to get their names
    if request.method == 'POST':
        player_name = request.form.get('player_name')
        deaths = request.form.get('deaths', player[2])
        gp_gained = request.form.get('gp_gained', player[3])
        tiles_completed = request.form.get('tiles_completed', player[4])
        team_name = request.form.get('team_name')
        pet_count = request.form.get('pet_count', player[6])

        # Get team_id by team_name
        team = get_team_by_name(team_name)
        team_id = team[3]  # Assuming team_id is in the 4th position in the result

        update_player(player_id, player_name, deaths, gp_gained, tiles_completed, team_id, pet_count)

        flash('Player updated successfully!', 'success')
        return redirect(url_for('player_management.player_list'))

    return render_template('admin_templates/player_templates/edit_player.html', player=player, teams=teams)


@player_routes.route('/delete/<int:player_id>', methods=['GET','POST'])
@admin_required
def delete_player(player_id):
    remove_player(player_id)
    flash('Player deleted successfully!', 'success')
    return redirect(url_for('player_management.player_list'))
