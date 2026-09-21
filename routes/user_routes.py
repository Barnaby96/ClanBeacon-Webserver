import os
from collections import defaultdict

from flask import (
    render_template,
    Blueprint,
    request,
    flash,
    redirect,
    url_for,
    send_file,
    abort
)
from flask_login import current_user, login_required
from utils import autocomplete, scapify, database, db_entities, wom, wom_tracking
from utils.branding import BOT_NAME
from utils.dink_evidence import resolve_dink_evidence_path
from utils.manual_evidence_files import resolve_manual_evidence_path
from utils.team_photo_files import resolve_team_photo_path

user_routes = Blueprint("user_routes", __name__)


@user_routes.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    player = None
    team = None
    link_code = None

    if current_user.player_id is not None:
        player_data = database.get_player_by_id(
            current_user.player_id
        )

        if player_data is not None:
            player = db_entities.Player(player_data)

            team_data = database.get_team_by_id(
                player.team_id
            )

            if team_data is not None:
                team = db_entities.Team(team_data)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'generate_link_code':
            try:
                link_code = (
                    database.create_dashboard_link_code(
                        current_user.id
                    )
                )
            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )

        elif action == 'change_password':
            current_password = request.form.get(
                'current_password',
                ''
            )
            new_password = request.form.get(
                'new_password',
                ''
            )
            confirm_password = request.form.get(
                'confirm_password',
                ''
            )

            if (
                not current_password
                or not new_password
                or not confirm_password
            ):
                flash(
                    'Please complete all password fields.',
                    'danger'
                )
                return redirect(
                    url_for('user_routes.account')
                )

            if new_password != confirm_password:
                flash(
                    'The new passwords do not match.',
                    'danger'
                )
                return redirect(
                    url_for('user_routes.account')
                )

            try:
                database.change_user_password(
                    current_user.id,
                    current_password,
                    new_password
                )
            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )
                return redirect(
                    url_for('user_routes.account')
                )

            flash(
                f'Your {BOT_NAME} password has been changed.',
                'success'
            )
            return redirect(
                url_for('user_routes.account')
            )

    discord_server_name = os.getenv(
        'DISCORD_SERVER_NAME',
        'your Discord server'
    )

    return render_template(
        'user_templates/account.html',
        player=player,
        team=team,
        link_code=link_code,
        discord_server_name=discord_server_name
    )


@user_routes.route('/team')
@login_required
def team_landing():
    viewer_player_id = current_user.player_id

    if viewer_player_id is not None:
        own_player_data = database.get_player_by_id(
            viewer_player_id
        )

        if own_player_data is not None:
            own_player = db_entities.Player(
                own_player_data
            )

            own_team_data = database.get_team_by_id(
                own_player.team_id
            )

            if own_team_data is not None:
                own_team = db_entities.Team(
                    own_team_data
                )

                return redirect(
                    url_for(
                        'user_routes.team',
                        team_name=own_team.team_name
                    )
                )

        if not current_user.is_admin:
            flash(
                'Your linked RuneScape account or team could not '
                'be found. Please contact an organiser.',
                'danger'
            )
            return redirect(
                url_for('user_routes.account')
            )

    elif not current_user.is_admin:
        return redirect(
            url_for(
                'user_routes.account',
                link_required=1
            )
        )

    teamnames = sorted(
        (
            db_entities.Team(team_row).team_name
            for team_row in database.get_teams()
        ),
        key=str.lower
    )

    return render_template(
        'user_templates/team_select.html',
        teamnames=teamnames
    )


@user_routes.route('/team/<team_name>')
@login_required
def team(team_name):
    viewer_player_id = current_user.player_id

    if not current_user.is_admin:
        if viewer_player_id is None:
            return redirect(
                url_for(
                    'user_routes.account',
                    link_required=1
                )
            )

        own_player_data = database.get_player_by_id(
            viewer_player_id
        )

        if own_player_data is None:
            flash(
                'Your linked RuneScape account could not be found. '
                'Please contact an organiser.',
                'danger'
            )
            return redirect(
                url_for('user_routes.account')
            )

        own_player = db_entities.Player(
            own_player_data
        )

        own_team_data = database.get_team_by_id(
            own_player.team_id
        )

        if own_team_data is None:
            flash(
                'Your linked RuneScape account is not assigned '
                'to a valid team. Please contact an organiser.',
                'danger'
            )
            return redirect(
                url_for('user_routes.account')
            )

        own_team = db_entities.Team(
            own_team_data
        )

        if (
            team_name.strip().lower()
            != own_team.team_name.strip().lower()
        ):
            return redirect(
                url_for(
                    'user_routes.team',
                    team_name=own_team.team_name
                )
            )

        team_data = own_team_data

    else:
        team_data = database.get_team_by_name(
            team_name
        )

        if team_data is None:
            abort(404)

    team = db_entities.Team(
        team_data
    )

    team_summary = database.get_team_data_summary(
        team.team_id
    )

    if team_summary is None:
        abort(404)

    teamnames = []

    if current_user.is_admin:
        teamnames = sorted(
            (
                db_entities.Team(team_row).team_name
                for team_row in database.get_teams()
            ),
            key=str.lower
        )

    competition_timing = (
        database.get_wom_competition_timing()
    )

    if competition_timing is not None:
        competition_timing = {
            "starts_at": competition_timing[
                "starts_at"
            ].isoformat(),
            "ends_at": competition_timing[
                "ends_at"
            ].isoformat()
        }

    return render_template(
        'user_templates/team.html',
        team=team,
        team_summary=team_summary,
        teamnames=teamnames,
        can_view_all_data=current_user.is_admin,
        viewer_player_id=viewer_player_id,
        competition_timing=competition_timing
    )


@user_routes.route('/team/<team_name>/wom/update', methods=['POST'])
@login_required
def update_team_wom_players(team_name):

    team_data = database.get_team_by_name(
        team_name
    )

    if team_data is None:
        abort(404)

    team = db_entities.Team(
        team_data
    )

    if not current_user.is_admin:
        if current_user.player_id is None:
            abort(404)

        viewer_player_data = database.get_player_by_id(
            current_user.player_id
        )

        if viewer_player_data is None:
            abort(404)

        viewer_player = db_entities.Player(
            viewer_player_data
        )

        if viewer_player.team_id != team.team_id:
            abort(404)


    players = database.get_players_by_team_id(
        team.team_id
    )

    player_names = [
        player[1]
        for player in players
    ]

    if not player_names:
        flash(
            f'{team.team_name} does not have any players to update.',
            'warning'
        )
        return redirect(
            url_for(
                'user_routes.team',
                team_name=team.team_name
            )
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
            f'{team.team_name} player(s).',
            'success'
        )

    if failed_count:
        failed_players = ', '.join(
            failure["player_name"]
            for failure in results["failed"]
        )

        flash(
            f'Wise Old Man could not update {failed_count} '
            f'{team.team_name} player(s): {failed_players}.',
            'warning'
        )

    if not updated_count and not failed_count:
        flash(
            f'{team.team_name} does not have any valid player names to update.',
            'warning'
        )

    return redirect(
        url_for(
            'user_routes.team',
            team_name=team.team_name
        )
    )


@user_routes.route('/wom/competition/refresh', methods=['POST'])
@login_required
def refresh_wom_competition():
    result = wom_tracking.process_wom_competition()

    competition_id = result["competition_id"]
    metrics_processed = result["metrics_processed"]
    players_processed = result["players_processed"]
    tiles_completed = len(
        result["tiles_completed"]
    )
    errors = len(
        result["errors"]
    )

    if competition_id is None:
        flash(
            'No Wise Old Man competition has been configured yet.',
            'warning'
        )
    else:
        flash(
            'Fetched latest Wise Old Man competition data: '
            f'{metrics_processed} metric(s), '
            f'{players_processed} player progress update(s), '
            f'{tiles_completed} tile completion(s).',
            'success'
        )

        if errors:
            flash(
                f'Wise Old Man refresh finished with {errors} warning(s).',
                'warning'
            )

    return redirect(
        request.referrer or url_for('user_routes.leaderboard')
    )


@user_routes.route('/team/<int:team_id>/photo')
@login_required
def team_photo(team_id):
    team_data = database.get_team_by_id(
        team_id
    )

    if team_data is None:
        abort(404)

    team = db_entities.Team(
        team_data
    )

    if not team.team_photo_path:
        abort(404)

    if not current_user.is_admin:
        if current_user.player_id is None:
            abort(404)

        player_data = database.get_player_by_id(
            current_user.player_id
        )

        if player_data is None:
            abort(404)

        player = db_entities.Player(
            player_data
        )

        if player.team_id != team.team_id:
            abort(404)

    absolute_path = resolve_team_photo_path(
        team.team_photo_path
    )

    if absolute_path is None:
        abort(404)

    return send_file(
        absolute_path
    )


@user_routes.route(
    '/player/evidence/<evidence_type>/<int:evidence_id>'
)
@login_required
def player_evidence(evidence_type, evidence_id):
    evidence_type = str(
        evidence_type
    ).strip().lower()

    if evidence_type == 'dink':
        evidence = database.get_dink_event_by_id(
            evidence_id
        )

        if evidence is None:
            abort(404)

        player_id = evidence[5]
        screenshot_path = evidence[8]

        absolute_path = resolve_dink_evidence_path(
            event_id=evidence_id,
            screenshot_path=screenshot_path
        )

    elif evidence_type == 'manual':
        evidence = database.get_manual_evidence_by_id(
            evidence_id
        )

        if evidence is None:
            abort(404)

        player_id = evidence[1]
        evidence_path = evidence[2]

        absolute_path = resolve_manual_evidence_path(
            evidence_path
        )

    else:
        abort(404)

    if not current_user.is_admin:
        if (
            current_user.player_id is None
            or player_id != current_user.player_id
        ):
            abort(404)

    if absolute_path is None:
        abort(404)

    return send_file(
        absolute_path
    )


@user_routes.route('/player')
@login_required
def player_landing():
    viewer_player_id = current_user.player_id

    if viewer_player_id is not None:
        own_player_data = database.get_player_by_id(
            viewer_player_id
        )

        if own_player_data is not None:
            own_player = db_entities.Player(
                own_player_data
            )

            return redirect(
                url_for(
                    'user_routes.player',
                    player_name=own_player.player_name
                )
            )

        if not current_user.is_admin:
            flash(
                'Your linked RuneScape account could not be found. '
                'Please contact an organiser.',
                'danger'
            )
            return redirect(
                url_for('user_routes.account')
            )

    elif not current_user.is_admin:
        return redirect(
            url_for(
                'user_routes.account',
                link_required=1
            )
        )

    return render_template(
        'user_templates/player_select.html',
        playernames=autocomplete.player_names()
    )


@user_routes.route('/player/<player_name>')
@login_required
def player(player_name):
    if not current_user.is_admin:
        if current_user.player_id is None:
            return redirect(
                url_for(
                    'user_routes.account',
                    link_required=1
                )
            )

        own_player_data = database.get_player_by_id(
            current_user.player_id
        )

        if own_player_data is None:
            flash(
                'Your linked RuneScape account could not be found. '
                'Please contact an organiser.',
                'danger'
            )
            return redirect(
                url_for('user_routes.account')
            )

        own_player = db_entities.Player(
            own_player_data
        )

        if (
            player_name.strip().lower()
            != own_player.player_name.strip().lower()
        ):
            return redirect(
                url_for(
                    'user_routes.player',
                    player_name=own_player.player_name
                )
            )

    player = database.get_player_by_name(player_name)
    try:
        player = db_entities.Player(player)
        team = database.get_team_by_id(player.team_id)
        team = db_entities.Team(team)
    except:
        player = db_entities.Player((-1, "None", 0, 0, 0, -1, 0, 0))
        team = db_entities.Team(("None", 0, None, -1))

    player.gp_gained = scapify.int_to_gp(player.gp_gained)

    drops_dict = {}
    for drop in database.get_drops_by_player_id(player.player_id):
        drop = db_entities.Drop(drop)
        if drop.drop_name in drops_dict:
            quantity = drops_dict[drop.drop_name][0]
            value = drops_dict[drop.drop_name][1]
            drops_dict[drop.drop_name] = (quantity + drop.drop_quantity, value + (drop.drop_value * drop.drop_quantity))
        else:
            drops_dict[drop.drop_name] = (drop.drop_quantity, drop.drop_value * drop.drop_quantity)

    drops = []
    for key, value in drops_dict.items():
        drops.append((key, value[0], value[1]))
    drops = sorted(drops, key=lambda drop: drop[2], reverse=True)
    drops = [(drop[0], drop[1], scapify.int_to_gp(drop[2])) for drop in drops]

    killcount = []
    for kc in database.get_killcount_by_player_id(player.player_id):
        kc = db_entities.Killcount(kc)
        killcount.append(kc)
    killcount = sorted(killcount, key=lambda kc: kc.kills, reverse=True)

    partial_completions = 0
    for partial_completion in database.get_partial_completions_by_player_id(player.player_id):
        partial_completion = db_entities.PartialCompletion(partial_completion)
        partial_completions += partial_completion.partial_completion
    player.tiles_completed = round(player.tiles_completed, 2)

    relevant_drops = []
    for relevant_drop in database.get_relevant_drop_by_player_id(player.player_id):
        relevant_drop = db_entities.RelevantDrop(relevant_drop)
        relevant_drops.append(relevant_drop)
    if len(relevant_drops) > 0:
        relevant_drops = sorted(relevant_drops, key=lambda relevant_drop: relevant_drop.tile_name, reverse=True)

    relevant_drop_summary = (
        database.get_player_relevant_drop_summary(
            player.player_id
        )
    )

    relevant_boss_kc_summary = (
        database.get_player_relevant_boss_kc_summary(
            player.player_id
        )
    )

    relevant_xp_summary = (
        database.get_player_relevant_xp_summary(
            player.player_id
        )
    )

    bingo_evidence = []

    for evidence in database.get_player_bingo_evidence(
        player.player_id
    ):
        if evidence["evidence_type"] == "dink":
            absolute_path = resolve_dink_evidence_path(
                event_id=evidence["evidence_id"],
                screenshot_path=evidence["screenshot_path"]
            )
        else:
            absolute_path = resolve_manual_evidence_path(
                evidence["screenshot_path"]
            )

        if absolute_path is not None:
            bingo_evidence.append(evidence)

    return render_template(
        'user_templates/player.html',
        player=player,
        drops=drops,
        killcount=killcount,
        team=team,
        playernames=autocomplete.player_names(),
        partial_completions=round(
            partial_completions,
            2
        ),
        relevant_drops=relevant_drops,
        relevant_drop_summary=relevant_drop_summary,
        relevant_boss_kc_summary=relevant_boss_kc_summary,
        relevant_xp_summary=relevant_xp_summary,
        bingo_evidence=bingo_evidence
    )


@user_routes.route('/leaderboard', methods=['GET'])
@login_required
def leaderboard():
    leaderboard_summary = database.get_leaderboard_summary()

    viewer_player_id = current_user.player_id
    viewer_team_id = None

    if viewer_player_id is not None:
        viewer_player_data = database.get_player_by_id(
            viewer_player_id
        )

        if viewer_player_data is not None:
            viewer_player = db_entities.Player(
                viewer_player_data
            )
            viewer_team_id = viewer_player.team_id

    competition_id = leaderboard_summary[
        "competition_id"
    ]

    competition_url = (
        f"https://wiseoldman.net/competitions/{competition_id}"
        if competition_id is not None
        else None
    )

    return render_template(
        "user_templates/leaderboard.html",
        leaderboard=leaderboard_summary,
        competition_url=competition_url,
        can_view_all_data=current_user.is_admin,
        viewer_player_id=viewer_player_id,
        viewer_team_id=viewer_team_id
    )