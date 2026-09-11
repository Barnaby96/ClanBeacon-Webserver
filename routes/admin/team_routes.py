import hashlib
import hmac
import time

from flask import (
    Flask,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for
)

from utils.auth import admin_required
from utils.branding import BOT_NAME
from utils import db_entities
from utils.database import add_team, get_teams, get_team_by_id, remove_team, rename_team, \
    update_team_webhook, get_players_by_team_id, remove_player, get_drops_by_team_id, remove_drop, remove_drop_by_pk, \
    get_partial_completions_by_team_id, set_team_photo_path
from utils.send_webhook import send_test_webhook
from utils.team_photo_files import (
    MAX_TEAM_PHOTO_BYTES,
    save_team_photo_file,
    delete_team_photo_file
)

team_routes = Blueprint("team_routes", __name__)

WEBHOOK_TEST_SESSION_KEY = "tested_team_webhook"
WEBHOOK_TEST_MAX_AGE_SECONDS = 600


def _webhook_fingerprint(webhook_url):
    webhook_url = str(
        webhook_url or ""
    ).strip()

    return hashlib.sha256(
        webhook_url.encode("utf-8")
    ).hexdigest()


def _remember_tested_webhook(
    team_id,
    webhook_url
):
    session[WEBHOOK_TEST_SESSION_KEY] = {
        "team_id": int(team_id),
        "fingerprint": _webhook_fingerprint(
            webhook_url
        ),
        "tested_at": time.time()
    }

    session.modified = True


def _clear_tested_webhook():
    session.pop(
        WEBHOOK_TEST_SESSION_KEY,
        None
    )


def _is_tested_webhook_valid(
    team_id,
    webhook_url
):
    tested_webhook = session.get(
        WEBHOOK_TEST_SESSION_KEY
    )

    if not isinstance(
        tested_webhook,
        dict
    ):
        return False

    try:
        tested_team_id = int(
            tested_webhook.get("team_id")
        )

        tested_at = float(
            tested_webhook.get("tested_at")
        )

    except (
        TypeError,
        ValueError
    ):
        return False

    if tested_team_id != int(team_id):
        return False

    test_age = (
        time.time()
        - tested_at
    )

    if (
        test_age < 0
        or test_age
        > WEBHOOK_TEST_MAX_AGE_SECONDS
    ):
        _clear_tested_webhook()
        return False

    tested_fingerprint = (
        tested_webhook.get(
            "fingerprint"
        )
    )

    if not isinstance(
        tested_fingerprint,
        str
    ):
        return False

    return hmac.compare_digest(
        tested_fingerprint,
        _webhook_fingerprint(
            webhook_url
        )
    )


@team_routes.route('/teams', methods=['GET'])
@admin_required
def team_list():
    teams = get_teams()
    return render_template('admin_templates/team_templates/team_list.html', teams=teams)

@team_routes.route('/teams/new', methods=['GET', 'POST'])
@admin_required
def create_team():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        team_webhook = request.form.get('team_webhook')

        add_team(team_name, 0, team_webhook)

        flash('Team created successfully!', 'success')
        return redirect(url_for('team_routes.team_list'))

    return render_template('admin_templates/team_templates/new_team_form.html')

@team_routes.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def edit_team(team_id):
    team_data = get_team_by_id(
        team_id
    )

    if team_data is None:
        flash(
            'Team could not be found.',
            'danger'
        )
        return redirect(
            url_for(
                'team_routes.team_list'
            )
        )

    team = db_entities.Team(
        team_data
    )

    if request.method == 'POST':
        new_team_name = str(
            request.form.get(
                'team_name',
                ''
            )
        ).strip()

        if not new_team_name:
            flash(
                'Team Name cannot be blank.',
                'danger'
            )
            return redirect(
                url_for(
                    'team_routes.edit_team',
                    team_id=team_id
                )
            )

        duplicate_team = None

        for existing_team_data in get_teams():
            existing_team = db_entities.Team(
                existing_team_data
            )

            if (
                existing_team.team_id != team_id
                and existing_team.team_name.casefold()
                == new_team_name.casefold()
            ):
                duplicate_team = existing_team
                break

        if duplicate_team is not None:
            flash(
                'A team with that name already exists.',
                'danger'
            )
            return redirect(
                url_for(
                    'team_routes.edit_team',
                    team_id=team_id
                )
            )

        team_photo_file = request.files.get(
            'team_photo'
        )

        has_new_team_photo = (
            team_photo_file is not None
            and bool(team_photo_file.filename)
        )

        new_team_photo_path = None

        if has_new_team_photo:
            photo_bytes = team_photo_file.read(
                MAX_TEAM_PHOTO_BYTES + 1
            )

            try:
                new_team_photo_path = (
                    save_team_photo_file(
                        photo_bytes,
                        team_photo_file.filename
                    )
                )
            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )
                return redirect(
                    url_for(
                        'team_routes.edit_team',
                        team_id=team_id
                    )
                )

        try:
            if new_team_name != team.team_name:
                rename_team(
                    team.team_name,
                    new_team_name
                )

            if new_team_photo_path is not None:
                set_team_photo_path(
                    team_id,
                    new_team_photo_path
                )

        except Exception:
            if new_team_photo_path is not None:
                try:
                    delete_team_photo_file(
                        new_team_photo_path
                    )
                except OSError:
                    pass

            raise

        if (
            team.team_photo_path
            and new_team_photo_path is not None
        ):
            try:
                delete_team_photo_file(
                    team.team_photo_path
                )
            except OSError:
                flash(
                    'The team details were updated, but the old '
                    'team photo file could not be deleted.',
                    'warning'
                )

        flash(
            'Team details updated successfully!',
            'success'
        )

        return redirect(
            url_for(
                'user_routes.team',
                team_name=new_team_name
            )
        )

    return render_template(
        'admin_templates/team_templates/edit_team.html',
        team=team
    )


@team_routes.route(
    '/teams/edit/<int:team_id>/photo/remove',
    methods=['POST']
)
@admin_required
def remove_team_photo(team_id):
    team_data = get_team_by_id(
        team_id
    )

    if team_data is None:
        flash(
            'Team could not be found.',
            'danger'
        )
        return redirect(
            url_for(
                'team_routes.team_list'
            )
        )

    team = db_entities.Team(
        team_data
    )

    if team.team_photo_path is not None:
        set_team_photo_path(
            team_id,
            None
        )

        try:
            delete_team_photo_file(
                team.team_photo_path
            )
        except OSError:
            flash(
                'The team photo was removed, but the old '
                'photo file could not be deleted.',
                'warning'
            )
            return redirect(
                url_for(
                    'team_routes.edit_team',
                    team_id=team_id
                )
            )

    flash(
        'Team photo removed successfully!',
        'success'
    )

    return redirect(
        url_for(
            'team_routes.edit_team',
            team_id=team_id
        )
    )


@team_routes.route(
    '/teams/edit/<int:team_id>/webhook/test',
    methods=['POST']
)
@admin_required
def test_team_webhook(team_id):
    team_data = get_team_by_id(
        team_id
    )

    if team_data is None:
        return jsonify(
            {
                "success": False,
                "message": "Team could not be found."
            }
        ), 404

    team = db_entities.Team(
        team_data
    )

    payload = request.get_json(
        silent=True
    ) or {}

    webhook_url = str(
        payload.get(
            "webhook_url",
            ""
        )
    ).strip()

    _clear_tested_webhook()

    try:
        send_test_webhook(
            webhook_url,
            (
                f"{BOT_NAME} Webhook Test\n"
                f"This is a test message for team "
                f"{team.team_name}."
            )
        )

    except (
        ValueError,
        RuntimeError
    ) as error:
        return jsonify(
            {
                "success": False,
                "message": str(error)
            }
        ), 400

    _remember_tested_webhook(
        team_id,
        webhook_url
    )

    return jsonify(
        {
            "success": True,
            "message": (
                "Test message sent successfully. "
                "Check that it appeared in the correct "
                "Discord channel before saving."
            )
        }
    )


@team_routes.route(
    '/teams/edit/<int:team_id>/webhook/save',
    methods=['POST']
)
@admin_required
def save_team_webhook(team_id):
    team_data = get_team_by_id(
        team_id
    )

    if team_data is None:
        return jsonify(
            {
                "success": False,
                "message": "Team could not be found."
            }
        ), 404

    payload = request.get_json(
        silent=True
    ) or {}

    webhook_url = str(
        payload.get(
            "webhook_url",
            ""
        )
    ).strip()

    if not _is_tested_webhook_valid(
        team_id,
        webhook_url
    ):
        return jsonify(
            {
                "success": False,
                "message": (
                    "Test this exact webhook successfully "
                    "before saving it."
                )
            }
        ), 400

    update_team_webhook(
        team_id,
        webhook_url
    )

    _clear_tested_webhook()

    return jsonify(
        {
            "success": True,
            "message": (
                "Team Discord webhook saved successfully."
            )
        }
    )


@team_routes.route(
    '/teams/edit/<int:team_id>/webhook/remove',
    methods=['POST']
)
@admin_required
def remove_team_webhook(team_id):
    team_data = get_team_by_id(
        team_id
    )

    if team_data is None:
        return jsonify(
            {
                "success": False,
                "message": "Team could not be found."
            }
        ), 404

    update_team_webhook(
        team_id,
        None
    )

    _clear_tested_webhook()

    return jsonify(
        {
            "success": True,
            "message": (
                "Team Discord webhook removed successfully."
            )
        }
    )


@team_routes.route('/teams/delete/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    remove_team(team_id)
    flash('Team deleted successfully!', 'success')
    return redirect(url_for('team_routes.team_list'))
