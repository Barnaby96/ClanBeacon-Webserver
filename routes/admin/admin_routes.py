import secrets

from flask import request, render_template, Blueprint, flash, redirect, url_for, abort, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename

from routes import dink
from utils.auth import admin_required
from utils.branding import BOT_NAME
from utils import completion_notifications, database, db_entities, wom
from utils.dink_evidence import resolve_dink_evidence_path
from utils.database import get_player_names, get_tile_names, get_tiles
from utils.spoofed_jsons.spoof_chat import spoof_chat
from utils.spoofed_jsons.spoof_drop import award_drop_json
from utils.spoofed_jsons.spoof_kc import kc_spoof_json
from utils.spoofed_jsons.spoof_pet import spoof_pet

admin_routes = Blueprint("admin_routes", __name__)

@admin_routes.route('/', methods=['GET'])
@admin_required
def home():
    return render_template('admin_templates/admin_home.html')


@admin_routes.route('/user_accounts', methods=['GET', 'POST'])
@admin_required
def user_accounts():
    if not current_user.is_organiser:
        abort(403)

    if request.method == 'POST':
        action = request.form.get(
            'action',
            'update_role'
        ).strip()

        target_user_id_raw = request.form.get(
            'user_id',
            ''
        ).strip()

        try:
            target_user_id = int(
                target_user_id_raw
            )
        except ValueError:
            flash(
                'Invalid dashboard user selected.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.user_accounts')
            )

        if action == 'reset_password':
            target_user = database.get_user_by_id(
                target_user_id
            )
            confirmation_username = request.form.get(
                'confirmation_username',
                ''
            ).strip()

            if target_user is None:
                flash(
                    'Dashboard user not found.',
                    'danger'
                )
            elif confirmation_username != target_user.username:
                flash(
                    f'Type {target_user.username} exactly to reset this password.',
                    'danger'
                )
            else:
                temporary_password = secrets.token_urlsafe(
                    12
                )

                try:
                    database.reset_user_password(
                        target_user_id,
                        temporary_password
                    )
                except ValueError as error:
                    flash(
                        str(error),
                        'danger'
                    )
                else:
                    flash(
                        f'Reset password for {target_user.username}. '
                        f'Temporary password: {temporary_password}',
                        'success'
                    )

            return redirect(
                url_for('admin_routes.user_accounts')
            )

        if action != 'update_role':
            flash(
                'Unknown user account action.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.user_accounts')
            )

        account_role = request.form.get(
            'account_role',
            ''
        ).strip().upper()

        if account_role not in {
            'PLAYER',
            'ADMIN',
            'ORGANISER'
        }:
            flash(
                'Invalid dashboard role selected.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.user_accounts')
            )

        if (
            target_user_id == int(current_user.id)
            and account_role != 'ORGANISER'
        ):
            flash(
                'You cannot remove your own organiser access.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.user_accounts')
            )

        try:
            updated_user = database.update_user_account_role(
                target_user_id,
                account_role
            )
        except ValueError as error:
            flash(
                str(error),
                'danger'
            )
            return redirect(
                url_for('admin_routes.user_accounts')
            )

        if updated_user is None:
            flash(
                'Dashboard user not found.',
                'danger'
            )
        else:
            updated_username = updated_user[1]

            flash(
                f'Updated {updated_username} to {account_role}.',
                'success'
            )

        return redirect(
            url_for('admin_routes.user_accounts')
        )

    users = database.get_dashboard_users()

    return render_template(
        'admin_templates/user_accounts.html',
        users=users,
        account_roles=[
            'PLAYER',
            'ADMIN',
            'ORGANISER'
        ]
    )


@admin_routes.route('/dink_audit', methods=['GET'])
@admin_required
def dink_audit():
    audit_rows = database.get_recent_dink_auth_failures(
        limit=100
    )

    audit_entries = [
        {
            'audit_id': row[0],
            'failure_reason': row[1],
            'claimed_player_name': row[2],
            'claimed_dink_account_hash': row[3],
            'claimed_event_type': row[4],
            'request_format': row[5],
            'source_ip': row[6],
            'user_agent': row[7],
            'received_at': row[8]
        }
        for row in audit_rows
    ]

    return render_template(
        'admin_templates/dink_audit.html',
        audit_entries=audit_entries
    )


@admin_routes.route(
    '/dink_event/<int:event_id>/screenshot',
    methods=['GET']
)
@admin_required
def dink_event_screenshot(event_id):
    event = database.get_dink_event_by_id(
        event_id
    )

    if event is None:
        abort(404)

    absolute_path = resolve_dink_evidence_path(
        event_id=event_id,
        screenshot_path=event[8]
    )

    if absolute_path is None:
        abort(404)

    return send_file(
        absolute_path
    )

@admin_routes.route(
    '/dink_identities',
    methods=['GET', 'POST']
)
@admin_required
def dink_identities():
    if request.method == 'POST':
        action = request.form.get(
            'action',
            ''
        ).strip()

        if action != 'manual_link':
            flash(
                'Unknown player account action.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_identities')
            )

        dink_account_hash = request.form.get(
            'dink_account_hash',
            ''
        ).strip()

        player_id_value = request.form.get(
            'player_id',
            ''
        ).strip()

        if not dink_account_hash:
            flash(
                'The RuneScape account reference is missing.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_identities')
            )

        try:
            player_id = int(player_id_value)

            if player_id <= 0:
                raise ValueError

        except (TypeError, ValueError):
            flash(
                f'Please select a valid {BOT_NAME} player.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_identities')
            )

        result = database.manually_link_dink_identity(
            dink_account_hash,
            player_id
        )

        if result['status'] == 'LINKED':
            player = database.get_player_by_id(
                result['player_id']
            )

            player_name = (
                player[1]
                if player is not None
                else f"Player {result['player_id']}"
            )

            flash(
                f'RuneScape account matched to {player_name}. '
                'Any submissions waiting for review still need '
                'a staff decision.',
                'success'
            )

        elif result['status'] == 'IDENTITY_NOT_FOUND':
            flash(
                'That RuneScape account is no longer available.',
                'danger'
            )

        elif result['status'] == 'PLAYER_NOT_FOUND':
            flash(
                f'The selected {BOT_NAME} player no longer exists.',
                'danger'
            )

        elif result['status'] == 'IDENTITY_ALREADY_LINKED':
            flash(
                'That RuneScape account is already matched to '
                'a different player.',
                'danger'
            )

        elif result['status'] == 'PLAYER_ALREADY_LINKED':
            flash(
                'That player is already matched to another '
                'RuneScape account.',
                'danger'
            )

        else:
            flash(
                'The RuneScape account could not be matched.',
                'danger'
            )

        return redirect(
            url_for('admin_routes.dink_identities')
        )

    identity_rows = database.get_dink_identity_review_rows()

    identity_entries = []

    for row in identity_rows:
        stored_status = row[2]
        observations = row[9]
        conflicting_rsns = row[10] or []
        matching_player_id = row[11]
        existing_linked_hash = row[14]

        display_status = stored_status
        review_reason = None

        if stored_status == 'LINKED':
            review_reason = 'Account matched to a player'

        elif stored_status == 'CONFLICT':
            if conflicting_rsns:
                review_reason = (
                    'Different RuneScape names were seen '
                    'for this account'
                )
            elif existing_linked_hash:
                review_reason = (
                    'Player is already matched to another '
                    'RuneScape account'
                )
            else:
                review_reason = (
                    'Account match needs a staff check'
                )

        elif stored_status == 'PENDING':
            if (
                observations >= 3
                and matching_player_id is None
            ):
                display_status = 'PLAYER_NOT_FOUND'
                review_reason = (
                    'Seen 3 or more times, but no matching '
                    'bingo player was found'
                )
            elif observations < 3:
                review_reason = (
                    f'Seen {observations} of 3 times needed '
                    f'for automatic matching'
                )
            else:
                review_reason = (
                    'Account is still waiting to be checked'
                )

        identity_entries.append(
            {
                'dink_account_hash': row[0],
                'observed_rsn': row[1],
                'stored_status': stored_status,
                'display_status': display_status,
                'player_id': row[3],
                'linked_player_name': row[4],
                'linked_team_name': row[5],
                'first_seen': row[6],
                'last_seen': row[7],
                'linked_at': row[8],
                'observations': observations,
                'conflicting_rsns': conflicting_rsns,
                'matching_player_id': matching_player_id,
                'matching_player_name': row[12],
                'matching_team_name': row[13],
                'existing_linked_hash': existing_linked_hash,
                'review_reason': review_reason
            }
        )

    players_by_team = database.get_players_by_team()

    return render_template(
        'admin_templates/dink_identities.html',
        identity_entries=identity_entries,
        players_by_team=players_by_team
    )


@admin_routes.route(
    '/dink_events',
    methods=['GET', 'POST']
)
@admin_required
def dink_events():
    if request.method == 'POST':
        action = request.form.get(
            'action',
            ''
        ).strip()

        if action == 'invalidate_manual_evidence':
            evidence_id_value = request.form.get(
                'evidence_id',
                ''
            ).strip()

            try:
                evidence_id = int(
                    evidence_id_value
                )

                if evidence_id <= 0:
                    raise ValueError

            except (TypeError, ValueError):
                flash(
                    'Please select valid manual evidence.',
                    'danger'
                )
                return redirect(
                    url_for(
                        'admin_routes.dink_events'
                    )
                )

            reason_code = request.form.get(
                'reason_code',
                ''
            ).strip()

            reason = request.form.get(
                'reason',
                ''
            ).strip()

            if len(reason) > 500:
                flash(
                    (
                        'Additional invalidation details '
                        'cannot exceed 500 characters.'
                    ),
                    'danger'
                )
                return redirect(
                    url_for(
                        'admin_routes.dink_events'
                    )
                )

            try:
                result = database.invalidate_bingo_evidence(
                    subject_type='MANUAL_EVIDENCE',
                    subject_id=evidence_id,
                    reason_code=reason_code,
                    review_source='WEB',
                    reviewer_id=current_user.id,
                    reviewer_name=current_user.username,
                    details=reason
                )

            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )
                return redirect(
                    url_for(
                        'admin_routes.dink_events'
                    )
                )

            if result['status'] == 'INVALIDATED':

                completion_notifications.notify_tile_corrections(
                    result.get(
                        'reopened_tiles',
                        []
                    )
                )

                success_message = (
                    f'Manual evidence #{evidence_id} '
                    'was invalidated.'
                )

                replayed_count = len(
                    result.get(
                        'replayed_manual_evidence',
                        []
                    )
                )

                if replayed_count:
                    replayed_label = (
                        'submission'
                        if replayed_count == 1
                        else 'submissions'
                    )

                    success_message += (
                        f' {replayed_count} later accepted '
                        f'manual {replayed_label} '
                        'was replayed.'
                        if replayed_count == 1
                        else
                        f' {replayed_count} later accepted '
                        f'manual {replayed_label} '
                        'were replayed.'
                    )

                reopened_count = len(
                    result.get(
                        'reopened_tiles',
                        []
                    )
                )

                if reopened_count:
                    tile_label = (
                        'tile'
                        if reopened_count == 1
                        else 'tiles'
                    )

                    open_verb = (
                        'remains'
                        if reopened_count == 1
                        else 'remain'
                    )

                    success_message += (
                        f' {reopened_count} affected '
                        f'{tile_label} {open_verb} open '
                        'after reconciliation.'
                    )

                flash(
                    success_message,
                    'success'
                )

            else:
                flash(
                    (
                        'This manual evidence could not '
                        'be invalidated.'
                    ),
                    'danger'
                )

            return redirect(
                url_for(
                    'admin_routes.dink_events'
                )
            )

        if action in {
            'accept_manual_evidence',
            'accept_manual_evidence_with_mvp',
            'reject_manual_evidence'
        }:
            evidence_id_value = request.form.get(
                'evidence_id',
                ''
            ).strip()

            try:
                evidence_id = int(
                    evidence_id_value
                )

                if evidence_id <= 0:
                    raise ValueError

            except (TypeError, ValueError):
                flash(
                    'Please select valid manual evidence.',
                    'danger'
                )
                return redirect(
                    url_for(
                        'admin_routes.dink_events'
                    )
                )

            if action == 'reject_manual_evidence':
                reason_code = request.form.get(
                    'reason_code',
                    ''
                ).strip()

                reason = request.form.get(
                    'reason',
                    ''
                ).strip()

                if len(reason) > 500:
                    flash(
                        (
                            'Additional rejection details '
                            'cannot exceed 500 characters.'
                        ),
                        'danger'
                    )
                    return redirect(
                        url_for(
                            'admin_routes.dink_events'
                        )
                    )

                try:
                    result = database.reject_pending_manual_evidence(
                        evidence_id=evidence_id,
                        review_source='WEB',
                        reviewer_id=current_user.id,
                        reviewer_name=current_user.username,
                        reason=reason,
                        reason_code=reason_code
                    )

                except ValueError as error:
                    flash(
                        str(error),
                        'danger'
                    )
                    return redirect(
                        url_for(
                            'admin_routes.dink_events'
                        )
                    )

                if result['status'] == 'REJECTED':
                    flash(
                        f'Manual submission #{evidence_id} was rejected.',
                        'success'
                    )

                elif result['status'] == 'EVIDENCE_NOT_FOUND':
                    flash(
                        'That manual submission no longer exists.',
                        'danger'
                    )

                elif result['status'] == 'INVALID_STATUS':
                    flash(
                        (
                            f'Manual submission #{evidence_id} can no '
                            'longer be rejected because it is no longer '
                            'awaiting review.'
                        ),
                        'danger'
                    )

                elif result['status'] == 'EARLIER_PENDING_EVIDENCE':
                    flash(
                        result.get(
                            'message',
                            (
                                'An earlier submission for this tile '
                                'must be reviewed first.'
                            )
                        ),
                        'danger'
                    )

                else:
                    flash(
                        'The manual submission could not be rejected.',
                        'danger'
                    )

                return redirect(
                    url_for(
                        'admin_routes.dink_events'
                    )
                )

            try:
                result = database.accept_pending_manual_evidence(
                    evidence_id=evidence_id,
                    review_source='WEB',
                    reviewer_id=current_user.id,
                    reviewer_name=current_user.username,
                    award_lost_mvp=(
                        action == 'accept_manual_evidence_with_mvp'
                    )
                )

            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )
                return redirect(
                    url_for(
                        'admin_routes.dink_events'
                    )
                )

            if result.get(
                'newly_completed',
                False
            ):
                completion_notifications.notify_progress_completions(
                    [
                        {
                            'team_id': result['team_id'],
                            'tile_id': result['tile_id'],
                            'completed': True
                        }
                    ]
                )

            if result['status'] == 'ACCEPTED':
                message = (
                    f'Manual submission #{evidence_id} was accepted.'
                )

                if result.get(
                    'audit_only',
                    False
                ):
                    message += (
                        ' It was accepted for audit only because '
                        'the tile changed after submission.'
                    )

                elif result.get(
                    'late_review',
                    False
                ):
                    message += (
                        ' The tile had already completed before '
                        'this submission was reviewed.'
                    )

                late_review_points = float(
                    result.get(
                        'late_review_points',
                        0
                    )
                    or 0
                )

                lost_mvp = float(
                    result.get(
                        'lost_mvp_contribution',
                        0
                    )
                    or 0
                )

                if late_review_points > 0:
                    message += (
                        f' {late_review_points:g} discretionary '
                        'MVP points were awarded.'
                    )

                elif lost_mvp > 0:
                    message += (
                        ' No discretionary MVP points were awarded.'
                    )

                flash(
                    message,
                    'success'
                )

            elif result['status'] == 'EVIDENCE_NOT_FOUND':
                flash(
                    'That manual submission no longer exists.',
                    'danger'
                )

            elif result['status'] == 'INVALID_STATUS':
                flash(
                    (
                        f'Manual submission #{evidence_id} has '
                        'already been reviewed.'
                    ),
                    'danger'
                )

            elif result['status'] == 'EARLIER_PENDING_EVIDENCE':
                flash(
                    result.get(
                        'message',
                        (
                            'An earlier submission for this tile '
                            'must be reviewed first.'
                        )
                    ),
                    'danger'
                )

            else:
                flash(
                    result.get(
                        'message',
                        'This manual submission could not be accepted.'
                    ),
                    'danger'
                )

            return redirect(
                url_for(
                    'admin_routes.dink_events'
                )
            )

        event_id_value = request.form.get(
            'event_id',
            ''
        ).strip()

        try:
            event_id = int(event_id_value)

            if event_id <= 0:
                raise ValueError

        except (TypeError, ValueError):
            flash(
                'Please select a valid submission.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_events')
            )

        if action == 'reject_event':
            reason_code = request.form.get(
                'reason_code',
                ''
            ).strip()

            reason = request.form.get(
                'reason',
                ''
            ).strip()

            if len(reason) > 500:
                flash(
                    'Additional rejection details cannot exceed '
                    '500 characters.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            try:
                result = database.reject_pending_dink_event(
                    event_id=event_id,
                    review_source='WEB',
                    reviewer_id=current_user.id,
                    reviewer_name=current_user.username,
                    reason=reason,
                    reason_code=reason_code
                )

            except ValueError as exc:
                flash(
                    str(exc),
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if result['status'] == 'REJECTED':
                flash(
                    f'Submission #{event_id} was rejected.',
                    'success'
                )

            elif result['status'] == 'EVENT_NOT_FOUND':
                flash(
                    'That submission no longer exists.',
                    'danger'
                )

            elif result['status'] == 'DUPLICATE_EVENT':
                flash(
                    'Duplicate submissions cannot be reviewed manually.',
                    'danger'
                )

            elif result['status'] == 'INVALID_STATUS':
                flash(
                    f'Submission #{event_id} can no longer '
                    'be rejected because it is no longer awaiting review.',
                    'danger'
                )

            else:
                flash(
                    'The submission could not be rejected.',
                    'danger'
                )

            return redirect(
                url_for('admin_routes.dink_events')
            )

        if action == 'accept_event':
            event = database.get_dink_event_by_id(
                event_id
            )

            if event is None:
                flash(
                    'That submission no longer exists.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if event[2] is not None:
                flash(
                    'Duplicate submissions cannot be reviewed manually.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if event[10] != 'PENDING_IDENTITY':
                flash(
                    f'Submission #{event_id} can no longer '
                    'be accepted because it is no longer awaiting review.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            identity = database.get_dink_identity_by_hash(
                event[3]
            )

            if (
                identity is None
                or identity[3] != 'LINKED'
                or identity[1] is None
            ):
                flash(
                    'This submission cannot be accepted until '
                    'the RuneScape account has been checked.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            try:
                event_progress = dink.get_dink_event_progress(
                    event[7]
                )

                result = database.process_dink_event_progress(
                    event_id=event_id,
                    player_id=identity[1],
                    event_progress=event_progress,
                    review_source='WEB',
                    reviewer_id=current_user.id,
                    reviewer_name=current_user.username
                )

            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if result['status'] == 'IGNORED':
                dink.cleanup_ignored_dink_event(
                    event_id
                )

                flash(
                    f'Submission #{event_id} was accepted, '
                    'but it did not match any active bingo '
                    'progress.',
                    'info'
                )

            else:
                flash(
                    f'Submission #{event_id} was accepted '
                    'and bingo progress was updated.',
                    'success'
                )

            return redirect(
                url_for('admin_routes.dink_events')
            )

        flash(
            'Unknown submission review action.',
            'danger'
        )

        return redirect(
            url_for('admin_routes.dink_events')
        )

    event_rows = (
        database.get_pending_dink_event_review_rows()
    )

    event_entries = []

    for row in event_rows:
        if row[7] != 'LINKED' or row[9] is None:
            continue
        claimed_rsn = row[2]

        event_entries.append(
            {
                'event_id': row[0],
                'dink_account_hash': row[1],
                'claimed_rsn': claimed_rsn,
                'event_type': row[3],
                'raw_payload': row[4],
                'screenshot_path': row[5],
                'received_at': row[6],
                'linked_player_id': row[9],
                'linked_player_name': row[10],
                'linked_team_name': row[11]
            }
        )

    pending_manual_evidence_entries = (
        database.get_pending_manual_evidence_review_rows()
    )

    manual_evidence_entries = (
        database.get_accepted_manual_evidence_invalidation_rows()
    )

    return render_template(
        'admin_templates/dink_events.html',
        event_entries=event_entries,
        pending_manual_evidence_entries=(
            pending_manual_evidence_entries
        ),
        manual_evidence_entries=manual_evidence_entries
    )

@admin_routes.route('/bingo_setup', methods=['GET', 'POST'])
@admin_required
def bingo_setup():
    competition_id = database.get_wom_competition_id()
    evidence_codeword = database.get_evidence_codeword() or ''
    competition = None
    teams = {}
    wom_player_ids = {}
    participant_count = 0
    conflicts = []
    import_plan = None
    recent_wom_refreshes = database.get_recent_wom_refresh_audit_rows()

    if request.method == 'POST':
        competition_id = request.form.get(
            'competition_id',
            ''
        ).strip()

        action = request.form.get('action', 'preview')
        evidence_codeword = request.form.get(
            'evidence_codeword',
            evidence_codeword
        ).strip()

        try:
            competition = wom.get_competition_details(
                competition_id
            )
        except wom.WiseOldManError as error:
            flash(str(error), 'danger')
            return render_template(
                'admin_templates/bingo_setup.html',
                competition_id=competition_id,
                competition=None,
                teams={},
                participant_count=0,
                conflicts=[],
                import_plan=None,
                evidence_codeword=evidence_codeword,
                recent_wom_refreshes=recent_wom_refreshes
            )

        if competition.get('type') != 'team':
            flash(
                'The selected Wise Old Man competition is not '
                'a team competition.',
                'danger'
            )
            return render_template(
                'admin_templates/bingo_setup.html',
                competition_id=competition_id,
                competition=None,
                teams={},
                participant_count=0,
                conflicts=[],
                import_plan=None,
                evidence_codeword=evidence_codeword,
                recent_wom_refreshes=recent_wom_refreshes
            )

        participations = competition.get(
            'participations'
        ) or []

        for participation in participations:
            team_name = str(
                participation.get('teamName') or ''
            ).strip()

            player = participation.get('player') or {}

            player_name = str(
                player.get('displayName')
                or player.get('username')
                or ''
            ).strip()

            wom_player_id = participation.get('playerId')

            if wom_player_id is None:
                wom_player_id = player.get('id')

            if not team_name or not player_name:
                continue

            teams.setdefault(
                team_name,
                []
            ).append(player_name)

            if wom_player_id is not None:
                wom_player_ids[player_name.lower()] = int(
                    wom_player_id
                )

            participant_count += 1

        if participant_count == 0:
            flash(
                'No valid team participants were found in '
                'this competition.',
                'danger'
            )
            competition = None

        else:
            if evidence_codeword:
                import_plan = database.preview_wom_competition_import(
                    competition_id,
                    teams,
                    evidence_codeword,
                    wom_player_ids,
                    competition_starts_at=competition.get(
                        'startsAt'
                    ),
                    competition_ends_at=competition.get(
                        'endsAt'
                    )
                )

                if import_plan["has_conflicts"]:
                    conflicts = import_plan["conflicts"]

            if action == 'import':
                if not evidence_codeword:
                    flash(
                        'Please enter an evidence codeword before '
                        'confirming the import.',
                        'danger'
                    )
                else:
                    result = database.import_wom_competition(
                        competition_id,
                        teams,
                        evidence_codeword,
                        wom_player_ids,
                        competition_starts_at=competition.get(
                            'startsAt'
                        ),
                        competition_ends_at=competition.get(
                            'endsAt'
                        )
                    )

                    if not result['imported']:
                        conflicts = result['conflicts']

                        flash(
                            'The competition could not be imported '
                            'because some existing players are assigned '
                            'to different teams.',
                            'danger'
                        )
                    else:
                        flash(
                            (
                                'Competition imported successfully. '
                                f"{result['teams_created']} teams created, "
                                f"{result['players_created']} players created "
                                f"and {result['players_reused']} existing "
                                'players reused.'
                            ),
                            'success'
                        )

    return render_template(
        'admin_templates/bingo_setup.html',
        competition_id=competition_id,
        competition=competition,
        teams=teams,
        participant_count=participant_count,
        conflicts=conflicts,
        import_plan=import_plan,
        evidence_codeword=evidence_codeword,
        recent_wom_refreshes=recent_wom_refreshes
    )



@admin_routes.route('/reset_database', methods=['GET', 'POST'])
@admin_required
def reset_database():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        database.reset_tables()
        flash("Database reset successfully.")
    return render_template('admin_templates/reset_database.html')


@admin_routes.route('/start_tracking', methods=['GET', 'POST'])
@admin_required
def start_tracking():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("Now tracking user data")
    return render_template('admin_templates/start_tracking.html')


@admin_routes.route('/stop_tracking', methods=['GET', 'POST'])
@admin_required
def stop_tracking():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("No longer tracking user data")
    return render_template('admin_templates/stop_tracking.html')

@admin_routes.route('/hide_board', methods=['GET', 'POST'])
@admin_required
def hide_board():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("Board will now be hidden. Uploading tiles will not change the visibility")
    return render_template('admin_templates/hide_board.html')

@admin_routes.route('/show_board', methods=['GET', 'POST'])
@admin_required
def show_board():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("Board is now being show. Uploading tiles will not change the visibility")
    return render_template('admin_templates/show_board.html')
