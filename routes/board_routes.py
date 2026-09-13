from flask import render_template, Blueprint, request, jsonify, make_response, redirect, url_for
from utils import autocomplete, database, db_entities, bingo
from flask_login import current_user, login_required

board_routes = Blueprint("board_routes", __name__)


class PanelData:
    def __init__(self):
        self.progress = None
        self.completions = "Completed: No"
        self.rules = None

def _get_current_user_team():
    if current_user.player_id is None:
        return None

    player_row = database.get_player_by_id(
        current_user.player_id
    )

    if player_row is None:
        return None

    player = db_entities.Player(
        player_row
    )

    team_row = database.get_team_by_id(
        player.team_id
    )

    if team_row is None:
        return None

    return db_entities.Team(
        team_row
    )

@board_routes.route('/', methods=['GET'])
@login_required
def index():
    panelData = {}

    tiles = []
    tiles_by_coordinate = {}

    for tile in database.get_tiles():
        tile = db_entities.Tile(tile)
        tiles.append(tile)

        if tile.board_coordinate is not None:
            tiles_by_coordinate[
                tile.board_coordinate
            ] = tile

        pd = PanelData()
        pd.progress = (
            "Progress: Please select a team "
            "to see your progress"
        )
        pd.rules = f"Rules: {tile.tile_rules}"
        panelData[tile.tile_name] = pd

    tiles = sorted(
        tiles,
        key=lambda tile: tile.tile_id
    )


    completed_tiles = []
    partial_tiles = []

    linked_team = _get_current_user_team()

    if linked_team is not None:
        return redirect(
            url_for(
                'board_routes.board',
                team_name=linked_team.team_name
            )
        )

    if not current_user.is_admin:
        return redirect(
            url_for(
                'user_routes.account',
                link_required=1
            )
        )

    team_name = request.cookies.get(
        'teamname'
    )

    if team_name:
        return redirect(
            url_for(
                'board_routes.board',
                team_name=team_name
            )
        )

    teams = database.get_teams()

    if len(teams) > 0:
        team = db_entities.Team(
            teams[0]
        )

        return board(
            team.team_name
        )
    return render_template(
        'board_templates/board.html',
        teamname=None,
        teamnames=autocomplete.team_names(),
        can_view_all_boards=current_user.is_admin,
        boardsize=get_board_size(),
        completed_tiles=completed_tiles,
        partial_tiles=partial_tiles,
        panelData=panelData,
        tiles_by_coordinate=tiles_by_coordinate
    )


@board_routes.route('/get_progress', methods=['GET'])
@login_required
def get_progress():
    tile_name = request.args.get(
        'tileName'
    )
    team_name = request.args.get(
        'teamName'
    )

    if not current_user.is_admin:
        linked_team = _get_current_user_team()

        if linked_team is None:
            return jsonify(
                "Board access requires a linked player team."
            ), 403

        if (
            team_name is None
            or team_name.strip().lower()
            != linked_team.team_name.strip().lower()
        ):
            return jsonify(
                "You can only view progress for your own team."
            ), 403

        team = linked_team

    else:
        team_row = database.get_team_by_name(
            team_name
        )

        if team_row is None:
            return jsonify(
                "Team not found."
            ), 404

        team = db_entities.Team(
            team_row
        )

    tile_row = database.get_tile_by_name(
        tile_name
    )

    if tile_row is None:
        return jsonify(
            "Tile not found."
        ), 404

    tile = db_entities.Tile(
        tile_row
    )

    progress = bingo.get_progress(
        team.team_id,
        tile.tile_id
    )

    if progress is None:
        return jsonify(
            "Please select a team to see your progress"
        )

    return jsonify(
        progress.status_text
    )


@board_routes.route('/<team_name>', methods=['GET'])
@login_required
def board(team_name):


    panelData = {}

    linked_team = _get_current_user_team()

    if not current_user.is_admin:
        if linked_team is None:
            return redirect(
                url_for(
                    'user_routes.account',
                    link_required=1
                )
            )

        if (
            team_name.strip().lower()
            != linked_team.team_name.strip().lower()
        ):
            return redirect(
                url_for(
                    'board_routes.board',
                    team_name=linked_team.team_name
                )
            )

        team = linked_team
        team_name = linked_team.team_name

    else:
        team_row = database.get_team_by_name(
            team_name
        )

        if team_row is None:
            available_teams = database.get_teams()

            if available_teams:
                fallback_team = db_entities.Team(
                    available_teams[0]
                )

                resp = redirect(
                    url_for(
                        'board_routes.board',
                        team_name=fallback_team.team_name
                    )
                )

                resp.set_cookie(
                    'teamname',
                    fallback_team.team_name
                )

                return resp

            team = db_entities.Team(
                ("None", 0, None, -1)
            )

        else:
            team = db_entities.Team(
                team_row
            )

    # get tiles for board population
    tiles = []
    tiles_by_coordinate = {}

    for tile in database.get_tiles():
        tile = db_entities.Tile(tile)
        tiles.append(tile)

        if tile.board_coordinate is not None:
            tiles_by_coordinate[
                tile.board_coordinate
            ] = tile

        pd = PanelData()
        pd.rules = f"Rules: {tile.tile_rules}"
        panelData[tile.tile_name] = pd

    tiles = sorted(
        tiles,
        key=lambda tile: tile.tile_id
    )

    completed_tiles = []
    partial_tiles = []

    for tile in tiles:
        progress = bingo.get_progress(
            team.team_id,
            tile.tile_id
        )

        panelData[tile.tile_name].completions = (
            "Completed: Yes"
            if progress.completions > 0
            else "Completed: No"
        )

        if progress.completions > 0:
            completed_tiles.append(
                tile.tile_name
            )
        elif progress.progress_value > 0:
            partial_tiles.append(
                tile.tile_name
            )


    if current_user.is_admin:
        teamnames = autocomplete.team_names()
    else:
        teamnames = [
            team.team_name
        ]


    resp = make_response(
        render_template(
            'board_templates/board.html',
            teamname=team_name,
            teamnames=teamnames,
            can_view_all_boards=current_user.is_admin,
            boardsize=get_board_size(),
            completed_tiles=completed_tiles,
            partial_tiles=partial_tiles,
            panelData=panelData,
            tiles_by_coordinate=tiles_by_coordinate
        )
    )

    resp.set_cookie('teamname', team_name)
    return resp


def get_board_size():
    # Bingo boards are always 5 x 5.
    return 5