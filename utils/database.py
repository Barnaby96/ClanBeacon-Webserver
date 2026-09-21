import os
import csv
import json
import hashlib
import secrets
import psycopg2
from flask_bcrypt import Bcrypt
from flask_login import UserMixin, logout_user
import utils.db_entities as db_entities
from routes import dink
from utils.branding import BOT_NAME
from utils.db_entities import Player, Tile
from utils.spoofed_jsons import spoof_drop

bcrypt = Bcrypt()

def connect():
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE'),
        user=os.getenv('PGUSER'),
        password=os.getenv('PGPASSWORD'),
        host=os.getenv('PGHOST'),
        port=os.getenv('PGPORT')
    )

def ensure_schema():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'tiles'
                      AND column_name = 'board_coordinate'
                ) THEN
                    ALTER TABLE tiles
                    ADD COLUMN board_coordinate TEXT;

                    WITH ordered_tiles AS (
                        SELECT
                            tile_id,
                            ROW_NUMBER() OVER (
                                ORDER BY tile_id
                            ) AS board_position
                        FROM tiles
                    )
                    UPDATE tiles
                    SET board_coordinate =
                        CHR(
                            65
                            + (
                                (
                                    ordered_tiles.board_position
                                    - 1
                                ) / 5
                            )::INTEGER
                        )
                        || (
                            (
                                (
                                    ordered_tiles.board_position
                                    - 1
                                ) % 5
                            ) + 1
                        )::TEXT
                    FROM ordered_tiles
                    WHERE tiles.tile_id = ordered_tiles.tile_id
                      AND ordered_tiles.board_position <= 25;
                END IF;
            END
            $$;
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'tiles_board_coordinate_check'
                      AND conrelid = 'tiles'::regclass
                ) THEN
                    ALTER TABLE tiles
                    ADD CONSTRAINT tiles_board_coordinate_check
                    CHECK (
                        board_coordinate IS NULL
                        OR board_coordinate ~ '^[A-E][1-5]$'
                    );
                END IF;
            END
            $$;
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_tiles_board_coordinate
            ON tiles (board_coordinate)
            WHERE board_coordinate IS NOT NULL
        ''')

        cursor.execute('''
            ALTER TABLE IF EXISTS relevant_drops
            ALTER COLUMN drops_pk DROP NOT NULL
        ''')

        cursor.execute('''
            ALTER TABLE IF EXISTS relevant_drops
            ALTER COLUMN drops_pk DROP DEFAULT
        ''')

        cursor.execute('''
            ALTER TABLE players
            ADD COLUMN IF NOT EXISTS discord_user_id BIGINT
        ''')

        cursor.execute('''
            ALTER TABLE players
            ADD COLUMN IF NOT EXISTS discord_display_name TEXT
        ''')

        cursor.execute('''
            ALTER TABLE players
            ADD COLUMN IF NOT EXISTS discord_username TEXT
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_players_discord_user_id
            ON players (discord_user_id)
            WHERE discord_user_id IS NOT NULL
        ''')

        cursor.execute('''
            ALTER TABLE players
            ADD COLUMN IF NOT EXISTS player_points DOUBLE PRECISION NOT NULL DEFAULT 0
        ''')


        cursor.execute('''
                ALTER TABLE players
            ADD COLUMN IF NOT EXISTS wom_player_id BIGINT
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_players_wom_player_id
            ON players (wom_player_id)
            WHERE wom_player_id IS NOT NULL
        ''')

        cursor.execute('''
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS account_role TEXT
        ''')

        cursor.execute('''
            UPDATE users
            SET account_role = CASE
                WHEN is_admin = TRUE THEN 'ORGANISER'
                ELSE 'PLAYER'
            END
            WHERE account_role IS NULL
        ''')

        cursor.execute('''
            ALTER TABLE users
            ALTER COLUMN account_role SET DEFAULT 'PLAYER'
        ''')

        cursor.execute('''
            ALTER TABLE users
            ALTER COLUMN account_role SET NOT NULL
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'users_account_role_check'
                      AND conrelid = 'users'::regclass
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT users_account_role_check
                    CHECK (
                        account_role IN (
                            'PLAYER',
                            'ADMIN',
                            'ORGANISER'
                        )
                    );
                END IF;
            END
            $$;
        ''')

        cursor.execute('''
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS player_id INTEGER
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_player_id
            ON users (player_id)
            WHERE player_id IS NOT NULL
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'users_player_id_fkey'
                      AND conrelid = 'users'::regclass
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT users_player_id_fkey
                    FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE SET NULL;
                END IF;
            END
            $$;
        ''')

        cursor.execute('''
            ALTER TABLE users
            ALTER COLUMN email DROP NOT NULL
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_ci
            ON users (LOWER(BTRIM(username)))
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dashboard_link_codes (
                user_id INTEGER PRIMARY KEY,
                code_hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMPTZ NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wom_metric_state (
                competition_id BIGINT NOT NULL,
                player_id INTEGER NOT NULL,
                metric TEXT NOT NULL,
                last_processed_gain BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (
                    competition_id,
                    player_id,
                    metric
                ),
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE CASCADE
            )
        ''')


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tile_conditions (
                condition_id SERIAL PRIMARY KEY,
                tile_id INTEGER NOT NULL,
                completion_path INTEGER NOT NULL,
                condition_type TEXT NOT NULL,
                condition_trigger TEXT,
                target BIGINT NOT NULL DEFAULT 1,
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE CASCADE,
                CHECK (completion_path >= 1),
                CHECK (target > 0),
                CHECK (
                    condition_type IN (
                        'KILLCOUNT',
                        'EXPERIENCE',
                        'METRIC',
                        'DROP',
                        'PET',
                        'MANUAL'
                    )
                )
            )
        ''')

        cursor.execute('''
            ALTER TABLE tile_conditions
            DROP CONSTRAINT IF EXISTS
                tile_conditions_condition_type_check
        ''')

        cursor.execute('''
            ALTER TABLE tile_conditions
            ADD CONSTRAINT
                tile_conditions_condition_type_check
            CHECK (
                condition_type IN (
                    'KILLCOUNT',
                    'EXPERIENCE',
                    'METRIC',
                    'DROP',
                    'PET',
                    'MANUAL'
                )
            )
        ''')

        cursor.execute(
            "SELECT to_regclass('wom_condition_state')"
        )
        wom_condition_state_exists = (
            cursor.fetchone()[0] is not None
        )

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wom_condition_state (
                competition_id BIGINT NOT NULL,
                player_id INTEGER NOT NULL,
                condition_id INTEGER NOT NULL,
                last_processed_gain BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (
                    competition_id,
                    player_id,
                    condition_id
                ),
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE CASCADE
            )
        ''')

        # Existing WOM conditions must inherit the old
        # player/metric checkpoint exactly once during migration.
        # Otherwise the first poll after upgrading would replay all
        # competition progress into conditions that already received it.
        if not wom_condition_state_exists:
            cursor.execute('''
                INSERT INTO wom_condition_state (
                    competition_id,
                    player_id,
                    condition_id,
                    last_processed_gain
                )
                SELECT
                    w.competition_id,
                    w.player_id,
                    c.condition_id,
                    w.last_processed_gain
                FROM wom_metric_state AS w
                JOIN tile_conditions AS c
                  ON LOWER(BTRIM(c.condition_trigger))
                     = LOWER(BTRIM(w.metric))
                WHERE c.condition_type IN (
                    'KILLCOUNT',
                    'EXPERIENCE',
                    'METRIC'
                )
                  AND c.condition_trigger IS NOT NULL
                ON CONFLICT (
                    competition_id,
                    player_id,
                    condition_id
                )
                DO NOTHING
            ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tile_completion_paths (
                tile_id INTEGER NOT NULL,
                completion_path INTEGER NOT NULL,
                route_mode TEXT NOT NULL DEFAULT 'ALL',
                route_target BIGINT,
                require_unique BOOLEAN NOT NULL DEFAULT FALSE,
                PRIMARY KEY (
                    tile_id,
                    completion_path
                ),
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE CASCADE,
                CHECK (completion_path >= 1),
                CHECK (
                    route_mode IN (
                        'ALL',
                        'SUM',
                        'N_OF'
                    )
                ),
                CHECK (
                    (
                        route_mode = 'ALL'
                        AND route_target IS NULL
                    )
                    OR
                    (
                        route_mode IN ('SUM', 'N_OF')
                        AND route_target > 0
                    )
                ),
                CHECK (
                    route_mode = 'N_OF'
                    OR require_unique = FALSE
                )
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tile_condition_progress (
                team_id INTEGER NOT NULL,
                condition_id INTEGER NOT NULL,
                progress BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (
                    team_id,
                    condition_id
                ),
                FOREIGN KEY (team_id)
                    REFERENCES teams(team_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE CASCADE,
                CHECK (progress >= 0)
            )
        ''')

        cursor.execute('''
            INSERT INTO tile_completion_paths (
                tile_id,
                completion_path,
                route_mode,
                route_target,
                require_unique
            )
            SELECT DISTINCT
                tile_id,
                completion_path,
                'ALL',
                NULL::BIGINT,
                FALSE
            FROM tile_conditions
            ON CONFLICT (
                tile_id,
                completion_path
            )
            DO NOTHING
        ''')

        cursor.execute('''
            ALTER TABLE partial_completions
            ALTER COLUMN partial_completion
            TYPE NUMERIC(18, 12)
            USING partial_completion::NUMERIC(18, 12)
        ''')

        cursor.execute('''
            ALTER TABLE partial_completions
            DROP CONSTRAINT IF EXISTS
                partial_completions_player_id_fkey
        ''')

        cursor.execute('''
            ALTER TABLE partial_completions
            ADD CONSTRAINT
                partial_completions_player_id_fkey
            FOREIGN KEY (player_id)
            REFERENCES players(player_id)
            ON DELETE SET NULL
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_partial_completions_player_team_tile
            ON partial_completions (
                player_id,
                team_id,
                tile_id
            )
        ''')

        cursor.execute('''
            ALTER TABLE completed_tiles
            ADD COLUMN IF NOT EXISTS completed_at
                TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        ''')

        cursor.execute('''
            ALTER TABLE completed_tiles
            ADD COLUMN IF NOT EXISTS points_awarded
                NUMERIC(18, 12)
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_completed_tiles_team_tile
            ON completed_tiles (
                team_id,
                tile_id
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS
                completed_tile_partial_snapshot (
                    snapshot_id BIGSERIAL PRIMARY KEY,
                    completed_tile_pk INTEGER NOT NULL,
                    player_id INTEGER,
                    partial_completion NUMERIC(18, 12) NOT NULL,
                    FOREIGN KEY (completed_tile_pk)
                        REFERENCES completed_tiles(completed_tile_pk)
                        ON DELETE CASCADE,
                    CHECK (partial_completion > 0)
                )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS
                idx_completed_tile_partial_snapshot_completion
            ON completed_tile_partial_snapshot (
                completed_tile_pk
            )
        ''')

        cursor.execute('''
            ALTER TABLE teams
            ADD COLUMN IF NOT EXISTS discord_role_id BIGINT
        ''')

        cursor.execute('''
            ALTER TABLE teams
            ADD COLUMN IF NOT EXISTS team_photo_path TEXT
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_discord_role_id
            ON teams (discord_role_id)
            WHERE discord_role_id IS NOT NULL
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bingo_config (
                config_id SMALLINT PRIMARY KEY
                    CHECK (config_id = 1),
                wom_competition_id BIGINT,
                wom_competition_starts_at TIMESTAMPTZ,
                wom_competition_ends_at TIMESTAMPTZ,
                evidence_codeword TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wom_refresh_audit (
                refresh_id BIGSERIAL PRIMARY KEY,
                requested_by_user_id INTEGER,
                requested_by_username TEXT,
                requested_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                competition_id BIGINT,
                metrics_processed INTEGER NOT NULL DEFAULT 0,
                players_processed INTEGER NOT NULL DEFAULT 0,
                tiles_completed INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                no_competition BOOLEAN NOT NULL DEFAULT FALSE,
                FOREIGN KEY (requested_by_user_id)
                    REFERENCES users(user_id)
                    ON DELETE SET NULL,
                CHECK (metrics_processed >= 0),
                CHECK (players_processed >= 0),
                CHECK (tiles_completed >= 0),
                CHECK (warning_count >= 0)
            )
        ''')

        cursor.execute('''
            ALTER TABLE bingo_config
            ADD COLUMN IF NOT EXISTS evidence_codeword TEXT
        ''')

        cursor.execute('''
            ALTER TABLE bingo_config
            ADD COLUMN IF NOT EXISTS
                wom_competition_starts_at TIMESTAMPTZ
        ''')

        cursor.execute('''
            ALTER TABLE bingo_config
            ADD COLUMN IF NOT EXISTS
                wom_competition_ends_at TIMESTAMPTZ
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dink_identities (
                dink_account_hash TEXT PRIMARY KEY,
                player_id INTEGER,
                observed_rsn TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                first_seen TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                linked_at TIMESTAMPTZ,
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE SET NULL,
                CHECK (
                    status IN (
                        'PENDING',
                        'LINKED',
                        'CONFLICT'
                    )
                ),
                CHECK (
                    (
                        status = 'LINKED'
                        AND player_id IS NOT NULL
                        AND linked_at IS NOT NULL
                    )
                    OR status != 'LINKED'
                )
            )
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_dink_identities_linked_player
            ON dink_identities (player_id)
            WHERE
                status = 'LINKED'
                AND player_id IS NOT NULL
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dink_events (
                event_id BIGSERIAL PRIMARY KEY,
                event_fingerprint TEXT NOT NULL,
                duplicate_of_event_id BIGINT,
                dink_account_hash TEXT,
                player_name TEXT,
                player_id INTEGER,
                event_type TEXT,
                raw_payload JSONB NOT NULL,
                screenshot_path TEXT,
                screenshot_sha256 TEXT,
                status TEXT NOT NULL DEFAULT 'RECEIVED',
                received_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMPTZ,
                FOREIGN KEY (duplicate_of_event_id)
                    REFERENCES dink_events(event_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE SET NULL,
                CHECK (
                    status IN (
                        'RECEIVED',
                        'PENDING_IDENTITY',
                        'PROCESSED',
                        'IGNORED',
                        'REJECTED',
                        'ERROR'
                    )
                )
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_review_decisions (
                decision_id BIGSERIAL PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id BIGINT NOT NULL,
                decision TEXT NOT NULL,
                review_source TEXT NOT NULL,
                reviewer_id BIGINT NOT NULL,
                reviewer_name TEXT NOT NULL,
                reason TEXT,
                reason_code TEXT,
                audit_only BOOLEAN NOT NULL DEFAULT FALSE,
                decided_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    subject_type,
                    subject_id
                ),
                CHECK (
                    subject_type IN (
                        'DINK_EVENT',
                        'MANUAL_EVIDENCE'
                    )
                ),
                CHECK (
                    decision IN (
                        'ACCEPT',
                        'REJECT'
                    )
                ),
                CHECK (
                    review_source IN (
                        'WEB',
                        'DISCORD'
                    )
                ),
                CHECK (
                    reason_code IN (
                        'INSUFFICIENT_EVIDENCE',
                        'WRONG_ITEM_OR_ACTIVITY',
                        'DUPLICATE_EVIDENCE',
                        'WRONG_PLAYER_OR_ACCOUNT',
                        'WRONG_TILE_OR_CONDITION',
                        'DOES_NOT_MEET_REQUIREMENTS',
                        'OTHER'
                    )
                )
            )
        ''')

        cursor.execute('''
            ALTER TABLE staff_review_decisions
            ADD COLUMN IF NOT EXISTS
                audit_only BOOLEAN NOT NULL DEFAULT FALSE
        ''')

        cursor.execute('''
            ALTER TABLE staff_review_decisions
            ADD COLUMN IF NOT EXISTS
                reason_code TEXT
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname =
                        'staff_review_decisions_reason_code_check'
                      AND conrelid =
                        'staff_review_decisions'::regclass
                ) THEN
                    ALTER TABLE staff_review_decisions
                    ADD CONSTRAINT
                        staff_review_decisions_reason_code_check
                    CHECK (
                        reason_code IN (
                            'INSUFFICIENT_EVIDENCE',
                            'WRONG_ITEM_OR_ACTIVITY',
                            'DUPLICATE_EVIDENCE',
                            'WRONG_PLAYER_OR_ACCOUNT',
                            'WRONG_TILE_OR_CONDITION',
                            'DOES_NOT_MEET_REQUIREMENTS',
                            'OTHER'
                        )
                    );
                END IF;
            END
            $$;
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evidence_invalidations (
                invalidation_id BIGSERIAL PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id BIGINT NOT NULL,
                reason_code TEXT NOT NULL,
                details TEXT,
                review_source TEXT NOT NULL,
                reviewer_id BIGINT NOT NULL,
                reviewer_name TEXT NOT NULL,
                invalidated_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    subject_type,
                    subject_id
                ),
                CHECK (
                    subject_type IN (
                        'DINK_EVENT',
                        'MANUAL_EVIDENCE'
                    )
                ),
                CHECK (
                    reason_code IN (
                        'INCORRECT_EVIDENCE',
                        'WRONG_ITEM_OR_ACTIVITY',
                        'DUPLICATE_EVIDENCE',
                        'WRONG_PLAYER_OR_ACCOUNT',
                        'WRONG_TILE_OR_CONDITION',
                        'ADMINISTRATIVE_TEST_CORRECTION',
                        'OTHER'
                    )
                ),
                CHECK (
                    review_source IN (
                        'WEB',
                        'DISCORD'
                    )
                )
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_evidence (
                evidence_id BIGSERIAL PRIMARY KEY,
                player_id INTEGER,
                credited_player_name TEXT,
                team_id INTEGER,
                tile_id INTEGER,
                condition_id INTEGER,
                amount BIGINT NOT NULL DEFAULT 1,
                tile_points_at_submission REAL,
                banked_total_at_submission NUMERIC(18,12),
                tile_name_at_submission TEXT,
                description TEXT,
                evidence_path TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                submission_source TEXT NOT NULL,
                submitter_id BIGINT NOT NULL,
                submitter_name TEXT NOT NULL,
                discord_guild_id BIGINT,
                discord_channel_id BIGINT,
                discord_message_id BIGINT,
                evidence_author_id BIGINT,
                evidence_author_name TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                submitted_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (team_id)
                    REFERENCES teams(team_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE SET NULL,
                CHECK (amount > 0),
                CHECK (
                    submission_source IN (
                        'DISCORD',
                        'WEB'
                    )
                ),
                CHECK (
                    status IN (
                        'PENDING',
                        'ACCEPTED',
                        'REJECTED'
                    )
                )
            )
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence
            ADD COLUMN IF NOT EXISTS
                credited_player_name TEXT
        ''')

        # Backfill older evidence only where the original player
        # still exists. Never guess a deleted player's identity.
        cursor.execute('''
            UPDATE manual_evidence AS e
            SET credited_player_name = p.player_name
            FROM players AS p
            WHERE e.credited_player_name IS NULL
              AND e.player_id = p.player_id
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence
            ADD COLUMN IF NOT EXISTS
                tile_points_at_submission REAL
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence
            ADD COLUMN IF NOT EXISTS
                banked_total_at_submission NUMERIC(18,12)
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence
            ADD COLUMN IF NOT EXISTS
                tile_name_at_submission TEXT
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence
            ADD COLUMN IF NOT EXISTS
                evidence_codeword_at_submission TEXT
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS
                manual_evidence_path_snapshots (
                    evidence_id BIGINT NOT NULL,
                    completion_path INTEGER NOT NULL,
                    route_mode TEXT NOT NULL,
                    route_target BIGINT,
                    require_unique BOOLEAN NOT NULL
                        DEFAULT FALSE,
                    PRIMARY KEY (
                        evidence_id,
                        completion_path
                    ),
                    FOREIGN KEY (evidence_id)
                        REFERENCES manual_evidence(evidence_id)
                        ON DELETE CASCADE,
                    CHECK (completion_path >= 1),
                    CHECK (
                        route_mode IN (
                            'ALL',
                            'SUM',
                            'N_OF'
                        )
                    ),
                    CHECK (
                        (
                            route_mode = 'ALL'
                            AND route_target IS NULL
                        )
                        OR
                        (
                            route_mode IN ('SUM', 'N_OF')
                            AND route_target > 0
                        )
                    ),
                    CHECK (
                        route_mode = 'N_OF'
                        OR require_unique = FALSE
                    )
                )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS
                manual_evidence_condition_snapshots (
                    evidence_id BIGINT NOT NULL,
                    condition_id INTEGER NOT NULL,
                    completion_path INTEGER NOT NULL,
                    condition_type TEXT NOT NULL,
                    condition_trigger TEXT,
                    target BIGINT NOT NULL,
                    progress BIGINT NOT NULL,
                    selected_condition BOOLEAN NOT NULL
                        DEFAULT FALSE,
                    PRIMARY KEY (
                        evidence_id,
                        condition_id
                    ),
                    FOREIGN KEY (evidence_id)
                        REFERENCES manual_evidence(evidence_id)
                        ON DELETE CASCADE,
                    CHECK (completion_path >= 1),
                    CHECK (target > 0),
                    CHECK (progress >= 0),
                    CHECK (
                        condition_type IN (
                            'KILLCOUNT',
                            'EXPERIENCE',
                            'METRIC',
                            'DROP',
                            'PET',
                            'MANUAL'
                        )
                    )
                )
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_manual_evidence_snapshot_selected_condition
            ON manual_evidence_condition_snapshots (
                evidence_id
            )
            WHERE selected_condition = TRUE
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dink_auth_audit (
                audit_id BIGSERIAL PRIMARY KEY,
                failure_reason TEXT NOT NULL,
                claimed_player_name TEXT,
                claimed_dink_account_hash TEXT,
                claimed_event_type TEXT,
                request_format TEXT NOT NULL,
                source_ip TEXT,
                user_agent TEXT,
                received_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    failure_reason IN (
                        'MISSING_SECRET',
                        'INVALID_SECRET',
                        'SERVER_MISCONFIGURED'
                    )
                ),
                CHECK (
                    request_format IN (
                        'JSON',
                        'MULTIPART',
                        'OTHER'
                    )
                )
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_dink_auth_audit_received_at
            ON dink_auth_audit (received_at DESC)
        ''')


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dink_event_progress (
                progress_id BIGSERIAL PRIMARY KEY,
                event_id BIGINT NOT NULL,
                team_id INTEGER,
                condition_id INTEGER NOT NULL,
                tile_id INTEGER NOT NULL,
                completion_path INTEGER NOT NULL,
                trigger TEXT NOT NULL,
                amount BIGINT NOT NULL,
                counted_amount BIGINT NOT NULL DEFAULT 0,
                raw_progress BIGINT NOT NULL,
                route_progress NUMERIC(18, 12) NOT NULL,
                credited NUMERIC(18, 12) NOT NULL,
                banked_total NUMERIC(18, 12) NOT NULL,
                ready BOOLEAN NOT NULL,
                completed BOOLEAN NOT NULL,
                condition_type_snapshot TEXT,
                condition_trigger_snapshot TEXT,
                condition_target_snapshot BIGINT,
                route_mode_snapshot TEXT,
                route_target_snapshot BIGINT,
                require_unique_snapshot BOOLEAN,
                state TEXT NOT NULL DEFAULT 'APPLIED',
                processed_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id)
                    REFERENCES dink_events(event_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE CASCADE,
                CHECK (amount > 0),
                CHECK (counted_amount >= 0),
                CONSTRAINT dink_event_progress_state_valid
                CHECK (
                    state IN (
                        'APPLIED',
                        'SUPPRESSED_COMPLETED',
                        'INVALIDATED'
                    )
                )
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS
                idx_dink_event_progress_event
            ON dink_event_progress (event_id)
        ''')

        cursor.execute('''
            ALTER TABLE dink_event_progress
            ADD COLUMN IF NOT EXISTS team_id INTEGER
        ''')

        cursor.execute('''
            ALTER TABLE dink_event_progress
            ADD COLUMN IF NOT EXISTS counted_amount BIGINT
                NOT NULL DEFAULT 0
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname =
                        'dink_event_progress_counted_amount_nonnegative'
                )
                THEN
                    ALTER TABLE dink_event_progress
                    ADD CONSTRAINT
                        dink_event_progress_counted_amount_nonnegative
                    CHECK (counted_amount >= 0);
                END IF;
            END
            $$
        ''')

        cursor.execute('''
            ALTER TABLE dink_event_progress
            ADD COLUMN IF NOT EXISTS state TEXT
                NOT NULL DEFAULT 'APPLIED'
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname =
                        'dink_event_progress_state_valid'
                )
                THEN
                    ALTER TABLE dink_event_progress
                    ADD CONSTRAINT
                        dink_event_progress_state_valid
                    CHECK (
                        state IN (
                            'APPLIED',
                            'SUPPRESSED_COMPLETED',
                            'INVALIDATED'
                        )
                    );
                END IF;
            END
            $$
        ''')

        cursor.execute('''
            ALTER TABLE dink_event_progress
            ADD COLUMN IF NOT EXISTS
                condition_type_snapshot TEXT,
            ADD COLUMN IF NOT EXISTS
                condition_trigger_snapshot TEXT,
            ADD COLUMN IF NOT EXISTS
                condition_target_snapshot BIGINT,
            ADD COLUMN IF NOT EXISTS
                route_mode_snapshot TEXT,
            ADD COLUMN IF NOT EXISTS
                route_target_snapshot BIGINT,
            ADD COLUMN IF NOT EXISTS
                require_unique_snapshot BOOLEAN
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_evidence_progress (
                progress_id BIGSERIAL PRIMARY KEY,
                evidence_id BIGINT NOT NULL UNIQUE,
                condition_id INTEGER,
                tile_id INTEGER,
                completion_path INTEGER NOT NULL,
                amount BIGINT NOT NULL,
                counted_amount BIGINT NOT NULL DEFAULT 0,
                raw_progress BIGINT NOT NULL,
                route_progress NUMERIC(18, 12) NOT NULL,
                actual_contribution NUMERIC(18, 12) NOT NULL
                    DEFAULT 0,
                completion_remainder NUMERIC(18, 12) NOT NULL
                    DEFAULT 0,
                normal_player_credit NUMERIC(18, 12) NOT NULL
                    DEFAULT 0,
                potential_contribution NUMERIC(18, 12) NOT NULL
                    DEFAULT 0,
                lost_mvp_contribution NUMERIC(18, 12) NOT NULL
                    DEFAULT 0,
                banked_total NUMERIC(18, 12) NOT NULL,
                ready BOOLEAN NOT NULL,
                completed BOOLEAN NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (evidence_id)
                    REFERENCES manual_evidence(evidence_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE SET NULL,
                CHECK (amount > 0),
                CHECK (counted_amount >= 0)
            )
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name =
                          'manual_evidence_progress'
                      AND column_name = 'credited'
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name =
                          'manual_evidence_progress'
                      AND column_name =
                          'actual_contribution'
                )
                THEN
                    ALTER TABLE manual_evidence_progress
                    RENAME COLUMN credited
                    TO actual_contribution;
                END IF;
            END
            $$;
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence_progress
            ADD COLUMN IF NOT EXISTS
                completion_remainder NUMERIC(18, 12)
                NOT NULL DEFAULT 0
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence_progress
            ADD COLUMN IF NOT EXISTS
                normal_player_credit NUMERIC(18, 12)
                NOT NULL DEFAULT 0
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence_progress
            ADD COLUMN IF NOT EXISTS
                potential_contribution NUMERIC(18, 12)
                NOT NULL DEFAULT 0
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence_progress
            ADD COLUMN IF NOT EXISTS
                lost_mvp_contribution NUMERIC(18, 12)
                NOT NULL DEFAULT 0
        ''')

        cursor.execute('''
            ALTER TABLE manual_evidence_progress
            ADD COLUMN IF NOT EXISTS counted_amount BIGINT
                NOT NULL DEFAULT 0
        ''')

        cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname =
                        'manual_evidence_progress_counted_amount_nonnegative'
                )
                THEN
                    ALTER TABLE manual_evidence_progress
                    ADD CONSTRAINT
                        manual_evidence_progress_counted_amount_nonnegative
                    CHECK (counted_amount >= 0);
                END IF;
            END
            $$
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_tile_credits (
                credit_id BIGSERIAL PRIMARY KEY,
                player_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                tile_id INTEGER NOT NULL,
                contribution NUMERIC(18, 12) NOT NULL,
                points_awarded NUMERIC(18, 12) NOT NULL,
                credit_type TEXT NOT NULL,
                evidence_id BIGINT,
                awarded_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    contribution > 0
                    AND contribution <= 1
                ),
                CHECK (points_awarded >= 0),
                CHECK (
                    credit_type IN (
                        'TILE_COMPLETION',
                        'LATE_REVIEW'
                    )
                ),
                CHECK (
                    (
                        credit_type = 'TILE_COMPLETION'
                        AND evidence_id IS NULL
                    )
                    OR
                    (
                        credit_type = 'LATE_REVIEW'
                        AND evidence_id IS NOT NULL
                    )
                )
            )
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_player_tile_credits_evidence
            ON player_tile_credits (evidence_id)
            WHERE evidence_id IS NOT NULL
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS
                idx_player_tile_credits_player_tile
            ON player_tile_credits (
                player_id,
                team_id,
                tile_id
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_dink_events_fingerprint
            ON dink_events (
                event_fingerprint,
                received_at
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_dink_events_identity
            ON dink_events (
                dink_account_hash,
                player_name,
                received_at
            )
        ''')


def get_wom_competition_id():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT wom_competition_id
            FROM bingo_config
            WHERE config_id = 1
        ''')
        row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_wom_competition_timing():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                wom_competition_starts_at,
                wom_competition_ends_at
            FROM bingo_config
            WHERE config_id = 1
            '''
        )
        row = cursor.fetchone()

    if (
        row is None
        or row[0] is None
        or row[1] is None
    ):
        return None

    return {
        "starts_at": row[0],
        "ends_at": row[1]
    }


def record_wom_refresh_audit(
    requested_by_user_id,
    requested_by_username,
    result
):
    tiles_completed = result.get("tiles_completed") or []
    errors = result.get("errors") or []

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO wom_refresh_audit (
                requested_by_user_id,
                requested_by_username,
                competition_id,
                metrics_processed,
                players_processed,
                tiles_completed,
                warning_count,
                no_competition
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING refresh_id
            ''',
            (
                requested_by_user_id,
                requested_by_username,
                result.get("competition_id"),
                result.get("metrics_processed", 0),
                result.get("players_processed", 0),
                len(tiles_completed),
                len(errors),
                result.get("competition_id") is None
            )
        )

        row = cursor.fetchone()
        conn.commit()

    return row[0]

def get_recent_wom_refresh_audit_rows(limit=10):
    limit = int(limit)

    if limit < 1:
        limit = 1

    if limit > 50:
        limit = 50

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                refresh_id,
                requested_by_user_id,
                requested_by_username,
                requested_at,
                competition_id,
                metrics_processed,
                players_processed,
                tiles_completed,
                warning_count,
                no_competition
            FROM wom_refresh_audit
            ORDER BY requested_at DESC, refresh_id DESC
            LIMIT %s
            ''',
            (limit,)
        )

        rows = cursor.fetchall()

    return [
        {
            "refresh_id": row[0],
            "requested_by_user_id": row[1],
            "requested_by_username": row[2],
            "requested_at": row[3],
            "competition_id": row[4],
            "metrics_processed": row[5],
            "players_processed": row[6],
            "tiles_completed": row[7],
            "warning_count": row[8],
            "no_competition": row[9]
        }
        for row in rows
    ]


def set_wom_competition_id(competition_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bingo_config (
                config_id,
                wom_competition_id
            )
            VALUES (1, %s)
            ON CONFLICT (config_id)
            DO UPDATE SET
                wom_competition_starts_at = CASE
                    WHEN bingo_config.wom_competition_id
                        IS DISTINCT FROM EXCLUDED.wom_competition_id
                    THEN NULL
                    ELSE bingo_config.wom_competition_starts_at
                END,
                wom_competition_ends_at = CASE
                    WHEN bingo_config.wom_competition_id
                        IS DISTINCT FROM EXCLUDED.wom_competition_id
                    THEN NULL
                    ELSE bingo_config.wom_competition_ends_at
                END,
                wom_competition_id = EXCLUDED.wom_competition_id
        ''', (competition_id,))
        conn.commit()


def get_evidence_codeword():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT evidence_codeword
            FROM bingo_config
            WHERE config_id = 1
            '''
        )

        row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def set_evidence_codeword(evidence_codeword):
    evidence_codeword = str(
        evidence_codeword
    ).strip()

    if not evidence_codeword:
        raise ValueError(
            "Evidence codeword cannot be blank."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            INSERT INTO bingo_config (
                config_id,
                evidence_codeword
            )
            VALUES (1, %s)
            ON CONFLICT (config_id)
            DO UPDATE SET
                evidence_codeword =
                    EXCLUDED.evidence_codeword
            ''',
            (evidence_codeword,)
        )

        conn.commit()


def get_wom_last_processed_gain(
    competition_id,
    player_id,
    metric
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT last_processed_gain
            FROM wom_metric_state
            WHERE competition_id = %s
              AND player_id = %s
              AND lower(metric) = lower(%s)
            ''',
            (
                competition_id,
                player_id,
                metric
            )
        )
        row = cursor.fetchone()

    if row is None:
        return 0

    return row[0]

def get_player_relevant_boss_kc_summary(player_id):
    competition_id = get_wom_competition_id()

    if competition_id is None:
        return {
            "total_kc": 0,
            "bosses": []
        }

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                LOWER(BTRIM(c.condition_trigger)) AS metric,
                COALESCE(w.last_processed_gain, 0) AS kc_gained,
                ARRAY_AGG(
                    DISTINCT t.tile_name
                    ORDER BY t.tile_name
                ) AS related_tiles
            FROM tile_conditions c
            JOIN tiles t
              ON t.tile_id = c.tile_id
            LEFT JOIN wom_metric_state w
              ON w.competition_id = %s
             AND w.player_id = %s
             AND LOWER(BTRIM(w.metric))
                 = LOWER(BTRIM(c.condition_trigger))
            WHERE c.condition_type = 'KILLCOUNT'
              AND COALESCE(w.last_processed_gain, 0) > 0
            GROUP BY
                LOWER(BTRIM(c.condition_trigger)),
                w.last_processed_gain
            ORDER BY
                LOWER(BTRIM(c.condition_trigger))
            ''',
            (
                competition_id,
                player_id
            )
        )

        bosses = [
            {
                "metric": row[0],
                "kc_gained": int(row[1]),
                "related_tiles": list(row[2] or [])
            }
            for row in cursor.fetchall()
        ]

    return {
        "total_kc": sum(
            boss["kc_gained"]
            for boss in bosses
        ),
        "bosses": bosses
    }


def get_player_relevant_xp_summary(player_id):
    competition_id = get_wom_competition_id()

    if competition_id is None:
        return {
            "total_xp": 0,
            "skills": []
        }

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                LOWER(BTRIM(c.condition_trigger)) AS metric,
                COALESCE(w.last_processed_gain, 0) AS xp_gained,
                ARRAY_AGG(
                    DISTINCT t.tile_name
                    ORDER BY t.tile_name
                ) AS related_tiles
            FROM tile_conditions c
            JOIN tiles t
              ON t.tile_id = c.tile_id
            LEFT JOIN wom_metric_state w
              ON w.competition_id = %s
             AND w.player_id = %s
             AND LOWER(BTRIM(w.metric))
                 = LOWER(BTRIM(c.condition_trigger))
            WHERE c.condition_type = 'EXPERIENCE'
              AND COALESCE(w.last_processed_gain, 0) > 0
            GROUP BY
                LOWER(BTRIM(c.condition_trigger)),
                w.last_processed_gain
            ORDER BY
                LOWER(BTRIM(c.condition_trigger))
            ''',
            (
                competition_id,
                player_id
            )
        )

        skills = [
            {
                "metric": row[0],
                "xp_gained": int(row[1]),
                "related_tiles": list(row[2] or [])
            }
            for row in cursor.fetchall()
        ]

    return {
        "total_xp": sum(
            skill["xp_gained"]
            for skill in skills
        ),
        "skills": skills
    }


def get_leaderboard_summary():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                t.team_id,
                t.team_name,
                COALESCE(t.team_points, 0),
                COUNT(ct.completed_tile_pk)
            FROM teams AS t
            LEFT JOIN completed_tiles AS ct
              ON ct.team_id = t.team_id
            GROUP BY
                t.team_id,
                t.team_name,
                t.team_points
            ORDER BY t.team_id
            '''
        )

        teams = [
            {
                "team_id": int(row[0]),
                "team_name": row[1],
                "bingo_points": float(row[2]),
                "tiles_completed": int(row[3]),
                "mvp_points": 0.0,
                "mvp_players": []
            }
            for row in cursor.fetchall()
        ]

        teams_by_id = {
            team["team_id"]: team
            for team in teams
        }

        cursor.execute(
            '''
            SELECT
                p.player_id,
                p.player_name,
                p.team_id,
                COALESCE(p.player_points, 0)
            FROM players AS p
            JOIN teams AS t
              ON t.team_id = p.team_id
            ORDER BY
                p.team_id,
                LOWER(p.player_name),
                p.player_name
            '''
        )

        players = [
            {
                "player_id": int(row[0]),
                "player_name": row[1],
                "team_id": int(row[2]),
                "mvp_points": float(row[3])
            }
            for row in cursor.fetchall()
        ]

        for team in teams:
            team_players = [
                player
                for player in players
                if player["team_id"] == team["team_id"]
            ]

            if not team_players:
                continue

            highest_mvp_points = max(
                player["mvp_points"]
                for player in team_players
            )

            if highest_mvp_points <= 0:
                continue

            team["mvp_points"] = highest_mvp_points
            team["mvp_players"] = [
                {
                    "player_id": player["player_id"],
                    "player_name": player["player_name"]
                }
                for player in team_players
                if player["mvp_points"] == highest_mvp_points
            ]

        ranked_teams = sorted(
            teams,
            key=lambda team: (
                -team["bingo_points"],
                -team["tiles_completed"],
                team["team_name"].lower(),
                team["team_id"]
            )
        )

        previous_score = None
        displayed_rank = 0

        for position, team in enumerate(
            ranked_teams,
            start=1
        ):
            score = (
                team["bingo_points"],
                team["tiles_completed"]
            )

            if score != previous_score:
                displayed_rank = position
                previous_score = score

            team["rank"] = displayed_rank

        positive_mvp_players = [
            player
            for player in players
            if player["mvp_points"] > 0
        ]

        clan_mvp_points = 0.0
        clan_mvp_players = []

        if positive_mvp_players:
            clan_mvp_points = max(
                player["mvp_points"]
                for player in positive_mvp_players
            )

            clan_mvp_players = [
                {
                    "player_id": player["player_id"],
                    "player_name": player["player_name"],
                    "team_id": player["team_id"],
                    "team_name": teams_by_id[
                        player["team_id"]
                    ]["team_name"]
                }
                for player in positive_mvp_players
                if player["mvp_points"] == clan_mvp_points
            ]

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM completed_tiles
            '''
        )
        completed_tiles = int(cursor.fetchone()[0])

        cursor.execute(
            '''
            SELECT wom_competition_id
            FROM bingo_config
            WHERE config_id = 1
            '''
        )
        competition_row = cursor.fetchone()

        competition_id = (
            competition_row[0]
            if competition_row is not None
            else None
        )

        relevant_boss_kc = 0
        relevant_xp = 0

        if competition_id is not None:
            cursor.execute(
                '''
                SELECT COALESCE(SUM(metric_gain), 0)
                FROM (
                    SELECT
                        w.player_id,
                        LOWER(BTRIM(w.metric)) AS metric,
                        MAX(w.last_processed_gain) AS metric_gain
                    FROM wom_metric_state AS w
                    JOIN players AS p
                      ON p.player_id = w.player_id
                    WHERE w.competition_id = %s
                      AND w.last_processed_gain > 0
                      AND EXISTS (
                          SELECT 1
                          FROM tile_conditions AS c
                          WHERE
                              c.condition_type = 'KILLCOUNT'
                              AND LOWER(
                                  BTRIM(c.condition_trigger)
                              ) = LOWER(BTRIM(w.metric))
                      )
                    GROUP BY
                        w.player_id,
                        LOWER(BTRIM(w.metric))
                ) AS relevant_kc
                ''',
                (competition_id,)
            )
            relevant_boss_kc = int(
                cursor.fetchone()[0]
            )

            cursor.execute(
                '''
                SELECT COALESCE(SUM(metric_gain), 0)
                FROM (
                    SELECT
                        w.player_id,
                        LOWER(BTRIM(w.metric)) AS metric,
                        MAX(w.last_processed_gain) AS metric_gain
                    FROM wom_metric_state AS w
                    JOIN players AS p
                      ON p.player_id = w.player_id
                    WHERE w.competition_id = %s
                      AND w.last_processed_gain > 0
                      AND EXISTS (
                          SELECT 1
                          FROM tile_conditions AS c
                          WHERE
                              c.condition_type = 'EXPERIENCE'
                              AND LOWER(
                                  BTRIM(c.condition_trigger)
                              ) = LOWER(BTRIM(w.metric))
                      )
                    GROUP BY
                        w.player_id,
                        LOWER(BTRIM(w.metric))
                ) AS relevant_experience
                ''',
                (competition_id,)
            )
            relevant_xp = int(
                cursor.fetchone()[0]
            )

        cursor.execute(
            '''
            WITH relevant_drop_progress AS (
                SELECT
                    dep.counted_amount AS quantity
                FROM dink_event_progress AS dep
                JOIN dink_events AS de
                  ON de.event_id = dep.event_id
                WHERE de.status = 'PROCESSED'
                  AND dep.counted_amount > 0

                UNION ALL

                SELECT
                    progress.counted_amount AS quantity
                FROM manual_evidence_progress AS progress
                JOIN manual_evidence AS evidence
                  ON evidence.evidence_id =
                     progress.evidence_id
                JOIN manual_evidence_condition_snapshots
                    AS snapshot
                  ON snapshot.evidence_id =
                     evidence.evidence_id
                 AND snapshot.selected_condition = TRUE
                WHERE evidence.status = 'ACCEPTED'
                  AND UPPER(
                      BTRIM(snapshot.condition_type)
                  ) = 'DROP'
                  AND progress.counted_amount > 0
            )
            SELECT COALESCE(SUM(quantity), 0)
            FROM relevant_drop_progress
            '''
        )

        relevant_drop_quantity = int(
            cursor.fetchone()[0]
        )

    return {
        "teams": ranked_teams,
        "competition_id": competition_id,
        "clan": {
            "completed_tiles": completed_tiles,
            "relevant_boss_kc": relevant_boss_kc,
            "relevant_drop_quantity":
                relevant_drop_quantity,
            "relevant_xp": relevant_xp,
            "team_count": len(teams),
            "team_names": [
                team["team_name"]
                for team in sorted(
                    teams,
                    key=lambda team: team["team_id"]
                )
            ],
            "mvp_points": clan_mvp_points,
            "mvp_players": clan_mvp_players
        }
    }


def get_team_data_summary(team_id):
    team_id = int(team_id)

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                team_id,
                team_name,
                COALESCE(team_points, 0)
            FROM teams
            WHERE team_id = %s
            ''',
            (team_id,)
        )

        team_row = cursor.fetchone()

        if team_row is None:
            return None

        team = {
            "team_id": int(team_row[0]),
            "team_name": team_row[1],
            "bingo_points": float(team_row[2] or 0)
        }

        cursor.execute(
            '''
            SELECT
                player_id,
                player_name,
                COALESCE(player_points, 0),
                COALESCE(tiles_completed, 0)
            FROM players
            WHERE team_id = %s
            ORDER BY
                LOWER(player_name),
                player_id
            ''',
            (team_id,)
        )

        roster = [
            {
                "player_id": int(row[0]),
                "player_name": row[1],
                "mvp_points": float(row[2] or 0),
                "tile_contribution": round(
                    float(row[3] or 0),
                    2
                )
            }
            for row in cursor.fetchall()
        ]

        highest_mvp_points = max(
            (
                player["mvp_points"]
                for player in roster
            ),
            default=0
        )

        if highest_mvp_points > 0:
            mvp_players = [
                player
                for player in roster
                if player["mvp_points"]
                == highest_mvp_points
            ]
        else:
            highest_mvp_points = 0
            mvp_players = []

        cursor.execute(
            '''
            WITH relevant_drop_progress AS (
                SELECT
                    dep.trigger AS drop_name,
                    dep.counted_amount AS quantity
                FROM dink_event_progress AS dep
                JOIN dink_events AS de
                  ON de.event_id = dep.event_id
                WHERE dep.team_id = %s
                  AND de.status = 'PROCESSED'
                  AND dep.counted_amount > 0

                UNION ALL

                SELECT
                    snapshot.condition_trigger AS drop_name,
                    progress.counted_amount AS quantity
                FROM manual_evidence_progress AS progress
                JOIN manual_evidence AS evidence
                  ON evidence.evidence_id =
                     progress.evidence_id
                JOIN manual_evidence_condition_snapshots
                    AS snapshot
                  ON snapshot.evidence_id =
                     evidence.evidence_id
                 AND snapshot.selected_condition = TRUE
                WHERE evidence.team_id = %s
                  AND evidence.status = 'ACCEPTED'
                  AND UPPER(
                      BTRIM(snapshot.condition_type)
                  ) = 'DROP'
                  AND progress.counted_amount > 0
            )
            SELECT
                MIN(BTRIM(drop_name)) AS drop_name,
                SUM(quantity)::INTEGER AS quantity
            FROM relevant_drop_progress
            WHERE drop_name IS NOT NULL
              AND BTRIM(drop_name) <> ''
            GROUP BY LOWER(BTRIM(drop_name))
            ORDER BY LOWER(MIN(BTRIM(drop_name)))
            ''',
            (
                team_id,
                team_id
            )
        )

        relevant_drops = [
            {
                "drop_name": row[0],
                "quantity": int(row[1])
            }
            for row in cursor.fetchall()
        ]

        relevant_drop_quantity = sum(
            drop["quantity"]
            for drop in relevant_drops
        )

        cursor.execute(
            '''
            SELECT wom_competition_id
            FROM bingo_config
            WHERE config_id = 1
            '''
        )

        competition_row = cursor.fetchone()

        competition_id = (
            competition_row[0]
            if (
                competition_row is not None
                and competition_row[0] is not None
            )
            else None
        )

        relevant_bosses = []
        relevant_boss_kc = 0
        relevant_skills = []
        relevant_xp = 0

        if competition_id is not None:
            cursor.execute(
                '''
                WITH relevant_metrics AS (
                    SELECT DISTINCT
                        LOWER(
                            BTRIM(condition_trigger)
                        ) AS metric
                    FROM tile_conditions
                    WHERE condition_type = 'KILLCOUNT'
                ),
                player_metric_gains AS (
                    SELECT
                        w.player_id,
                        LOWER(
                            BTRIM(w.metric)
                        ) AS metric,
                        MAX(
                            w.last_processed_gain
                        )::BIGINT AS gained
                    FROM wom_metric_state AS w
                    JOIN players AS p
                      ON p.player_id = w.player_id
                    JOIN relevant_metrics AS rm
                      ON rm.metric
                         = LOWER(BTRIM(w.metric))
                    WHERE w.competition_id = %s
                      AND p.team_id = %s
                      AND w.last_processed_gain > 0
                    GROUP BY
                        w.player_id,
                        LOWER(BTRIM(w.metric))
                ),
                related_tiles AS (
                    SELECT
                        LOWER(
                            BTRIM(c.condition_trigger)
                        ) AS metric,
                        ARRAY_AGG(
                            DISTINCT t.tile_name
                            ORDER BY t.tile_name
                        ) AS tile_names
                    FROM tile_conditions AS c
                    JOIN tiles AS t
                      ON t.tile_id = c.tile_id
                    WHERE c.condition_type
                        = 'KILLCOUNT'
                    GROUP BY
                        LOWER(
                            BTRIM(c.condition_trigger)
                        )
                )
                SELECT
                    pmg.metric,
                    SUM(pmg.gained)::BIGINT,
                    rt.tile_names
                FROM player_metric_gains AS pmg
                JOIN related_tiles AS rt
                  ON rt.metric = pmg.metric
                GROUP BY
                    pmg.metric,
                    rt.tile_names
                ORDER BY pmg.metric
                ''',
                (
                    competition_id,
                    team_id
                )
            )

            relevant_bosses = [
                {
                    "metric": row[0],
                    "kc_gained": int(row[1]),
                    "related_tiles":
                        list(row[2] or [])
                }
                for row in cursor.fetchall()
            ]

            relevant_boss_kc = sum(
                boss["kc_gained"]
                for boss in relevant_bosses
            )

            cursor.execute(
                '''
                WITH relevant_metrics AS (
                    SELECT DISTINCT
                        LOWER(
                            BTRIM(condition_trigger)
                        ) AS metric
                    FROM tile_conditions
                    WHERE condition_type = 'EXPERIENCE'
                ),
                player_metric_gains AS (
                    SELECT
                        w.player_id,
                        LOWER(
                            BTRIM(w.metric)
                        ) AS metric,
                        MAX(
                            w.last_processed_gain
                        )::BIGINT AS gained
                    FROM wom_metric_state AS w
                    JOIN players AS p
                      ON p.player_id = w.player_id
                    JOIN relevant_metrics AS rm
                      ON rm.metric
                         = LOWER(BTRIM(w.metric))
                    WHERE w.competition_id = %s
                      AND p.team_id = %s
                      AND w.last_processed_gain > 0
                    GROUP BY
                        w.player_id,
                        LOWER(BTRIM(w.metric))
                ),
                related_tiles AS (
                    SELECT
                        LOWER(
                            BTRIM(c.condition_trigger)
                        ) AS metric,
                        ARRAY_AGG(
                            DISTINCT t.tile_name
                            ORDER BY t.tile_name
                        ) AS tile_names
                    FROM tile_conditions AS c
                    JOIN tiles AS t
                      ON t.tile_id = c.tile_id
                    WHERE c.condition_type
                        = 'EXPERIENCE'
                    GROUP BY
                        LOWER(
                            BTRIM(c.condition_trigger)
                        )
                )
                SELECT
                    pmg.metric,
                    SUM(pmg.gained)::BIGINT,
                    rt.tile_names
                FROM player_metric_gains AS pmg
                JOIN related_tiles AS rt
                  ON rt.metric = pmg.metric
                GROUP BY
                    pmg.metric,
                    rt.tile_names
                ORDER BY pmg.metric
                ''',
                (
                    competition_id,
                    team_id
                )
            )

            relevant_skills = [
                {
                    "metric": row[0],
                    "xp_gained": int(row[1]),
                    "related_tiles":
                        list(row[2] or [])
                }
                for row in cursor.fetchall()
            ]

            relevant_xp = sum(
                skill["xp_gained"]
                for skill in relevant_skills
            )

        cursor.execute(
            '''
            SELECT
                t.tile_id,
                t.tile_name,
                COALESCE(t.tile_points, 0),
                path.completion_path,
                path.route_mode,
                path.route_target,
                path.require_unique,
                c.condition_id,
                c.target,
                COALESCE(progress.progress, 0)
            FROM tiles AS t
            JOIN tile_completion_paths AS path
              ON path.tile_id = t.tile_id
            JOIN tile_conditions AS c
              ON c.tile_id = t.tile_id
             AND c.completion_path
                 = path.completion_path
            LEFT JOIN tile_condition_progress
                AS progress
              ON progress.condition_id
                 = c.condition_id
             AND progress.team_id = %s
            LEFT JOIN completed_tiles AS completed
              ON completed.tile_id = t.tile_id
             AND completed.team_id = %s
            WHERE completed.tile_id IS NULL
            ORDER BY
                t.tile_id,
                path.completion_path,
                c.condition_id
            ''',
            (
                team_id,
                team_id
            )
        )

        progress_rows = cursor.fetchall()

        path_data = {}

        for row in progress_rows:
            (
                tile_id,
                tile_name,
                tile_points,
                completion_path,
                route_mode,
                route_target,
                require_unique,
                condition_id,
                condition_target,
                condition_progress
            ) = row

            key = (
                int(tile_id),
                int(completion_path)
            )

            if key not in path_data:
                path_data[key] = {
                    "tile_id": int(tile_id),
                    "tile_name": tile_name,
                    "tile_points": float(
                        tile_points or 0
                    ),
                    "completion_path":
                        int(completion_path),
                    "route_mode":
                        str(route_mode),
                    "route_target": (
                        int(route_target)
                        if route_target is not None
                        else None
                    ),
                    "require_unique":
                        bool(require_unique),
                    "conditions": []
                }

            path_data[key]["conditions"].append(
                (
                    int(condition_id),
                    int(condition_target),
                    int(condition_progress)
                )
            )

        tile_progress = {}

        for path in path_data.values():
            state = _evaluate_completion_path_conditions(
                route_mode=path["route_mode"],
                route_target=path["route_target"],
                require_unique=path["require_unique"],
                conditions=path["conditions"]
            )

            tile_id = path["tile_id"]
            progress_fraction = float(
                state["progress_fraction"]
            )

            if tile_id not in tile_progress:
                tile_progress[tile_id] = {
                    "tile_id": tile_id,
                    "tile_name":
                        path["tile_name"],
                    "tile_points":
                        path["tile_points"],
                    "progress_fraction":
                        progress_fraction
                }
            else:
                tile_progress[tile_id][
                    "progress_fraction"
                ] = max(
                    tile_progress[tile_id][
                        "progress_fraction"
                    ],
                    progress_fraction
                )

        tiles_in_progress = []

        for tile in tile_progress.values():
            if tile["progress_fraction"] <= 0:
                continue

            tiles_in_progress.append(
                {
                    "tile_id": tile["tile_id"],
                    "tile_name":
                        tile["tile_name"],
                    "tile_points":
                        tile["tile_points"],
                    "progress_fraction": round(
                        tile["progress_fraction"],
                        12
                    ),
                    "progress_percentage": round(
                        tile["progress_fraction"]
                        * 100,
                        2
                    )
                }
            )

        tiles_in_progress.sort(
            key=lambda tile: (
                -tile["progress_fraction"],
                -tile["tile_points"],
                tile["tile_name"].lower(),
                tile["tile_id"]
            )
        )

        cursor.execute(
            '''
            SELECT
                t.tile_id,
                t.tile_name,
                COALESCE(t.tile_points, 0),
                completed.completed_at
            FROM completed_tiles AS completed
            JOIN tiles AS t
              ON t.tile_id = completed.tile_id
            WHERE completed.team_id = %s
            ORDER BY
                completed.completed_at DESC,
                LOWER(t.tile_name),
                t.tile_id
            ''',
            (team_id,)
        )

        completed_tiles = [
            {
                "tile_id": int(row[0]),
                "tile_name": row[1],
                "tile_points": float(row[2] or 0),
                "completed_at": row[3]
            }
            for row in cursor.fetchall()
        ]

    return {
        "team": team,
        "stats": {
            "bingo_points":
                team["bingo_points"],
            "tiles_completed":
                len(completed_tiles),
            "relevant_boss_kc":
                relevant_boss_kc,
            "relevant_drop_quantity":
                relevant_drop_quantity,
            "relevant_xp":
                relevant_xp
        },
        "roster": roster,
        "team_mvp": {
            "mvp_points":
                highest_mvp_points,
            "players":
                mvp_players
        },
        "relevant_drops": {
            "total_quantity":
                relevant_drop_quantity,
            "drops":
                relevant_drops
        },
        "relevant_boss_kc": {
            "total_kc":
                relevant_boss_kc,
            "bosses":
                relevant_bosses
        },
        "relevant_xp": {
            "total_xp":
                relevant_xp,
            "skills":
                relevant_skills
        },
        "tiles_in_progress":
            tiles_in_progress,
        "completed_tiles":
            completed_tiles
    }


def _bank_partial_contribution(
    cursor,
    player_id,
    team_id,
    tile_id,
    requested_contribution
):
    requested_contribution = float(
        requested_contribution
    )

    if requested_contribution < 0:
        raise ValueError(
            "Tile contribution cannot be negative."
        )

    cursor.execute(
        '''
        SELECT COALESCE(
            SUM(partial_completion),
            0
        )
        FROM partial_completions
        WHERE team_id = %s
          AND tile_id = %s
        ''',
        (
            team_id,
            tile_id
        )
    )

    banked_before = float(
        cursor.fetchone()[0]
    )

    remaining = round(
        max(
            0.0,
            1.0 - banked_before
        ),
        12
    )

    contribution = round(
        min(
            remaining,
            requested_contribution
        ),
        12
    )

    if contribution > 0:
        cursor.execute(
            '''
            INSERT INTO partial_completions (
                player_id,
                team_id,
                tile_id,
                partial_completion
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (
                player_id,
                team_id,
                tile_id
            )
            DO UPDATE SET
                partial_completion =
                    partial_completions.partial_completion
                    + EXCLUDED.partial_completion
            ''',
            (
                player_id,
                team_id,
                tile_id,
                contribution
            )
        )

    banked_after = round(
        banked_before + contribution,
        12
    )

    return contribution, banked_after


def apply_wom_metric_progress(
    competition_id,
    player_id,
    condition_type,
    metric,
    current_gain
):
    condition_type = str(condition_type).strip().upper()
    metric = str(metric).strip().lower()
    current_gain = int(current_gain)

    if condition_type not in {
        "KILLCOUNT",
        "EXPERIENCE",
        "METRIC"
    }:
        raise ValueError(
            "WOM progress can only be applied to "
            "KILLCOUNT, EXPERIENCE or METRIC conditions."
        )

    if current_gain < 0:
        raise ValueError(
            "WOM competition gain cannot be negative."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT team_id
            FROM players
            WHERE player_id = %s
            FOR UPDATE
            ''',
            (player_id,)
        )
        player_row = cursor.fetchone()

        if player_row is None:
            raise ValueError(
                f"Player {player_id} does not exist."
            )

        team_id = player_row[0]

        cursor.execute(
            '''
            INSERT INTO wom_metric_state (
                competition_id,
                player_id,
                metric,
                last_processed_gain
            )
            VALUES (%s, %s, %s, 0)
            ON CONFLICT (
                competition_id,
                player_id,
                metric
            )
            DO NOTHING
            ''',
            (
                competition_id,
                player_id,
                metric
            )
        )

        cursor.execute(
            '''
            SELECT last_processed_gain
            FROM wom_metric_state
            WHERE competition_id = %s
              AND player_id = %s
              AND metric = %s
            FOR UPDATE
            ''',
            (
                competition_id,
                player_id,
                metric
            )
        )
        last_processed_gain = cursor.fetchone()[0]

        if current_gain > last_processed_gain:
            new_gain = (
                current_gain
                - last_processed_gain
            )
        else:
            new_gain = 0

        cursor.execute(
            '''
            SELECT
                c.condition_id,
                c.tile_id,
                c.completion_path
            FROM tile_conditions c
            JOIN tile_completion_paths p
              ON p.tile_id = c.tile_id
             AND p.completion_path = c.completion_path
            WHERE c.condition_type = %s
              AND lower(c.condition_trigger) = %s
            ORDER BY
                c.tile_id,
                c.completion_path,
                c.condition_id
            ''',
            (
                condition_type,
                metric
            )
        )
        conditions = cursor.fetchall()

        tile_results = []

        for (
            condition_id,
            tile_id,
            completion_path
        ) in conditions:
            # Lock the tile so simultaneous WOM updates
            # cannot both claim the same remaining contribution.
            cursor.execute(
                '''
                SELECT tile_id
                FROM tiles
                WHERE tile_id = %s
                FOR UPDATE
                ''',
                (tile_id,)
            )

            if cursor.fetchone() is None:
                continue

            cursor.execute(
                '''
                SELECT 1
                FROM completed_tiles
                WHERE team_id = %s
                  AND tile_id = %s
                ''',
                (
                    team_id,
                    tile_id
                )
            )

            if cursor.fetchone() is not None:
                continue

            before = _evaluate_completion_path(
                cursor=cursor,
                team_id=team_id,
                tile_id=tile_id,
                completion_path=completion_path
            )

            cursor.execute(
                '''
                INSERT INTO wom_condition_state (
                    competition_id,
                    player_id,
                    condition_id,
                    last_processed_gain
                )
                VALUES (%s, %s, %s, 0)
                ON CONFLICT (
                    competition_id,
                    player_id,
                    condition_id
                )
                DO NOTHING
                ''',
                (
                    competition_id,
                    player_id,
                    condition_id
                )
            )

            cursor.execute(
                '''
                SELECT last_processed_gain
                FROM wom_condition_state
                WHERE competition_id = %s
                  AND player_id = %s
                  AND condition_id = %s
                FOR UPDATE
                ''',
                (
                    competition_id,
                    player_id,
                    condition_id
                )
            )

            condition_last_processed_gain = int(
                cursor.fetchone()[0]
            )

            if current_gain > condition_last_processed_gain:
                condition_new_gain = (
                    current_gain
                    - condition_last_processed_gain
                )
            else:
                condition_new_gain = 0

            if condition_new_gain > 0:
                raw_progress = (
                    _add_tile_condition_progress(
                        cursor=cursor,
                        team_id=team_id,
                        condition_id=condition_id,
                        amount=condition_new_gain
                    )
                )
            else:
                cursor.execute(
                    '''
                    SELECT COALESCE(progress, 0)
                    FROM tile_condition_progress
                    WHERE team_id = %s
                      AND condition_id = %s
                    ''',
                    (
                        team_id,
                        condition_id
                    )
                )

                progress_row = cursor.fetchone()

                if progress_row is None:
                    raw_progress = 0
                else:
                    raw_progress = int(
                        progress_row[0]
                    )

            if current_gain > condition_last_processed_gain:
                cursor.execute(
                    '''
                    UPDATE wom_condition_state
                    SET last_processed_gain = %s
                    WHERE competition_id = %s
                      AND player_id = %s
                      AND condition_id = %s
                    ''',
                    (
                        current_gain,
                        competition_id,
                        player_id,
                        condition_id
                    )
                )

            after = _evaluate_completion_path(
                cursor=cursor,
                team_id=team_id,
                tile_id=tile_id,
                completion_path=completion_path
            )

            progress_delta = round(
                max(
                    0.0,
                    after["progress_fraction"]
                    - before["progress_fraction"]
                ),
                12
            )

            contribution, banked_after = (
                _bank_partial_contribution(
                    cursor=cursor,
                    player_id=player_id,
                    team_id=team_id,
                    tile_id=tile_id,
                    requested_contribution=progress_delta
                )
            )

            tile_results.append(
                {
                    "condition_id": condition_id,
                    "tile_id": tile_id,
                    "completion_path":
                        completion_path,
                    "raw_progress": raw_progress,
                    "route_progress":
                        after["progress_fraction"],
                    "credited": contribution,
                    "banked_total": banked_after,
                    "ready": after["ready"]
                }
            )

        if current_gain > last_processed_gain:
            cursor.execute(
                '''
                UPDATE wom_metric_state
                SET last_processed_gain = %s
                WHERE competition_id = %s
                  AND player_id = %s
                  AND metric = %s
                ''',
                (
                    current_gain,
                    competition_id,
                    player_id,
                    metric
                )
            )

        conn.commit()

    return {
        "previous_gain": last_processed_gain,
        "current_gain": current_gain,
        "new_gain": new_gain,
        "tiles": tile_results
    }


def set_wom_last_processed_gain(
    competition_id,
    player_id,
    metric,
    last_processed_gain
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO wom_metric_state (
                competition_id,
                player_id,
                metric,
                last_processed_gain
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (
                competition_id,
                player_id,
                metric
            )
            DO UPDATE SET
                last_processed_gain =
                    EXCLUDED.last_processed_gain
            ''',
            (
                competition_id,
                player_id,
                metric.lower(),
                last_processed_gain
            )
        )
        conn.commit()


def import_wom_competition(
    competition_id,
    teams,
    evidence_codeword,
    wom_player_ids=None,
    competition_starts_at=None,
    competition_ends_at=None
):
    evidence_codeword = str(
        evidence_codeword
    ).strip()

    if not evidence_codeword:
        raise ValueError(
            "Evidence codeword cannot be blank."
        )

    if wom_player_ids is None:
        wom_player_ids = {}
    with connect() as conn:
        cursor = conn.cursor()

        conflicts = []

        # Check every existing player before changing anything.
        for team_name, player_names in teams.items():
            cursor.execute(
                '''
                SELECT team_id
                FROM teams
                WHERE lower(team_name) = lower(%s)
                ''',
                (team_name,)
            )
            team_row = cursor.fetchone()
            target_team_id = team_row[0] if team_row else None

            for player_name in player_names:
                wom_player_id = wom_player_ids.get(
                    player_name.lower()
                )

                player_row = None

                # A WOM player ID is the strongest identity match.
                if wom_player_id is not None:
                    cursor.execute(
                        '''
                        SELECT
                            player_id,
                            team_id,
                            wom_player_id,
                            player_name
                        FROM players
                        WHERE wom_player_id = %s
                        ''',
                        (wom_player_id,)
                    )
                    player_row = cursor.fetchone()

                # Fall back to the RuneScape name for players imported
                # before WOM IDs were stored.
                if player_row is None:
                    cursor.execute(
                        '''
                        SELECT
                            player_id,
                            team_id,
                            wom_player_id,
                            player_name
                        FROM players
                        WHERE lower(player_name) = lower(%s)
                        ''',
                        (player_name,)
                    )
                    player_row = cursor.fetchone()

                if player_row is None:
                    continue

                # Prevent a WOM-identified player being renamed to a name
                # already used by a different bingo player record.
                cursor.execute(
                    '''
                    SELECT player_id
                    FROM players
                    WHERE lower(player_name) = lower(%s)
                    AND player_id != %s
                    ''',
                    (
                        player_name,
                        player_row[0]
                    )
                )

                name_owner = cursor.fetchone()

                if name_owner is not None:
                    conflicts.append({
                        "player_name": player_name,
                        "wom_team": team_name,
                        "danbot_team": (
                            "RuneScape name already belongs to "
                            f"another {BOT_NAME} player"
                        )
                    })
                    continue

                existing_team_id = player_row[1]
                existing_wom_player_id = player_row[2]

                if (
                    wom_player_id is not None
                    and existing_wom_player_id is not None
                    and existing_wom_player_id != wom_player_id
                ):
                    conflicts.append({
                        "player_name": player_name,
                        "wom_team": team_name,
                        "danbot_team": "WOM identity mismatch"
                    })
                    continue

                # Protect against one WOM account being attached to
                # two different bingo player records.
                if wom_player_id is not None:
                    cursor.execute(
                        '''
                        SELECT player_id, player_name
                        FROM players
                        WHERE wom_player_id = %s
                        AND player_id != %s
                        ''',
                        (
                            wom_player_id,
                            player_row[0]
                        )
                    )

                    wom_id_owner = cursor.fetchone()

                    if wom_id_owner is not None:
                        conflicts.append({
                            "player_name": player_name,
                            "wom_team": team_name,
                            "danbot_team": (
                                f"WOM ID already belongs to "
                                f"{wom_id_owner[1]}"
                            )
                        })
                        continue

                if target_team_id is None:
                    cursor.execute(
                        '''
                        SELECT team_name
                        FROM teams
                        WHERE team_id = %s
                        ''',
                        (existing_team_id,)
                    )
                    existing_team = cursor.fetchone()

                    conflicts.append({
                        "player_name": player_name,
                        "wom_team": team_name,
                        "danbot_team": (
                            existing_team[0]
                            if existing_team
                            else "None"
                        )
                    })

                elif existing_team_id != target_team_id:
                    cursor.execute(
                        '''
                        SELECT team_name
                        FROM teams
                        WHERE team_id = %s
                        ''',
                        (existing_team_id,)
                    )
                    existing_team = cursor.fetchone()

                    conflicts.append({
                        "player_name": player_name,
                        "wom_team": team_name,
                        "danbot_team": (
                            existing_team[0]
                            if existing_team
                            else "None"
                        )
                    })

        if conflicts:
            return {
                "imported": False,
                "conflicts": conflicts
            }

        teams_created = 0
        players_created = 0
        players_reused = 0

        for team_name, player_names in teams.items():
            cursor.execute(
                '''
                SELECT team_id
                FROM teams
                WHERE lower(team_name) = lower(%s)
                ''',
                (team_name,)
            )
            team_row = cursor.fetchone()

            if team_row is None:
                cursor.execute(
                    '''
                    INSERT INTO teams (
                        team_name,
                        team_points,
                        team_webhook
                    )
                    VALUES (%s, 0, NULL)
                    RETURNING team_id
                    ''',
                    (team_name,)
                )
                team_id = cursor.fetchone()[0]
                teams_created += 1
            else:
                team_id = team_row[0]

            for player_name in player_names:
                wom_player_id = wom_player_ids.get(
                    player_name.lower()
                )

                player_row = None

                if wom_player_id is not None:
                    cursor.execute(
                        '''
                        SELECT
                            player_id,
                            player_name,
                            wom_player_id
                        FROM players
                        WHERE wom_player_id = %s
                        ''',
                        (wom_player_id,)
                    )
                    player_row = cursor.fetchone()

                if player_row is None:
                    cursor.execute(
                        '''
                        SELECT
                            player_id,
                            player_name,
                            wom_player_id
                        FROM players
                        WHERE lower(player_name) = lower(%s)
                        ''',
                        (player_name,)
                    )
                    player_row = cursor.fetchone()

                if player_row is None:
                    cursor.execute(
                        '''
                        INSERT INTO players (
                            player_name,
                            deaths,
                            gp_gained,
                            tiles_completed,
                            team_id,
                            pet_count,
                            wom_player_id
                        )
                        VALUES (%s, 0, 0, 0, %s, 0, %s)
                        ''',
                        (
                            player_name,
                            team_id,
                            wom_player_id
                        )
                    )
                    players_created += 1

                else:
                    player_id = player_row[0]

                    cursor.execute(
                        '''
                        UPDATE players
                        SET
                            player_name = %s,
                            wom_player_id = COALESCE(
                                wom_player_id,
                                %s
                            )
                        WHERE player_id = %s
                        ''',
                        (
                            player_name,
                            wom_player_id,
                            player_id
                        )
                    )

                    players_reused += 1

        cursor.execute(
            '''
            INSERT INTO bingo_config (
                config_id,
                wom_competition_id,
                wom_competition_starts_at,
                wom_competition_ends_at,
                evidence_codeword
            )
            VALUES (1, %s, %s, %s, %s)
            ON CONFLICT (config_id)
            DO UPDATE SET
                wom_competition_id =
                    EXCLUDED.wom_competition_id,
                wom_competition_starts_at =
                    EXCLUDED.wom_competition_starts_at,
                wom_competition_ends_at =
                    EXCLUDED.wom_competition_ends_at,
                evidence_codeword =
                    EXCLUDED.evidence_codeword
            ''',
            (
                competition_id,
                competition_starts_at,
                competition_ends_at,
                evidence_codeword
            )
        )

        conn.commit()

    return {
        "imported": True,
        "conflicts": [],
        "teams_created": teams_created,
        "players_created": players_created,
        "players_reused": players_reused
    }


# User authentication functions

class User(UserMixin):
    def __init__(
        self,
        user_id,
        username,
        email,
        password,
        is_admin=False,
        account_role=None,
        player_id=None
    ):
        self.id = user_id
        self.username = username
        self.email = email
        self.password = password
        self.player_id = player_id

        if account_role is None:
            account_role = (
                "ORGANISER"
                if is_admin
                else "PLAYER"
            )

        self.account_role = str(
            account_role
        ).strip().upper()

    @property
    def is_admin(self):
        return self.account_role in {
            "ADMIN",
            "ORGANISER"
        }

    @property
    def is_organiser(self):
        return self.account_role == "ORGANISER"

    @property
    def is_player(self):
        return self.account_role == "PLAYER"

def add_user(username, password):
    username = username.strip()

    with connect() as conn:
        cursor = conn.cursor()
        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode('utf-8')
        cursor.execute(
            '''
            INSERT INTO users (
                username,
                password
            )
            VALUES (%s, %s)
            ''',
            (
                username,
                hashed_password
            )
        )
        conn.commit()


def create_dashboard_link_code(user_id):
    raw_code = secrets.token_hex(6).upper()
    display_code = (
        f"{raw_code[:4]}-"
        f"{raw_code[4:8]}-"
        f"{raw_code[8:]}"
    )

    code_hash = hashlib.sha256(
        display_code.encode("utf-8")
    ).hexdigest()

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT player_id
            FROM users
            WHERE user_id = %s
            ''',
            (user_id,)
        )
        user = cursor.fetchone()

        if user is None:
            raise ValueError(
                "Dashboard account could not be found."
            )

        if user[0] is not None:
            raise ValueError(
                "This dashboard account is already linked "
                "to a player."
            )

        cursor.execute(
            '''
            INSERT INTO dashboard_link_codes (
                user_id,
                code_hash,
                created_at,
                expires_at
            )
            VALUES (
                %s,
                %s,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
                    + INTERVAL '10 minutes'
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
                code_hash = EXCLUDED.code_hash,
                created_at = EXCLUDED.created_at,
                expires_at = EXCLUDED.expires_at
            ''',
            (
                user_id,
                code_hash
            )
        )

    return display_code


def redeem_dashboard_link_code(
    discord_user_id,
    code
):
    normalised_code = str(code).strip().upper()

    code_hash = hashlib.sha256(
        normalised_code.encode("utf-8")
    ).hexdigest()

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                dlc.user_id,
                u.username,
                u.player_id
            FROM dashboard_link_codes dlc
            INNER JOIN users u
                ON u.user_id = dlc.user_id
            WHERE dlc.code_hash = %s
              AND dlc.expires_at > CURRENT_TIMESTAMP
            FOR UPDATE
            ''',
            (code_hash,)
        )
        link_code = cursor.fetchone()

        if link_code is None:
            raise ValueError(
                "That dashboard link code is invalid or has expired."
            )

        dashboard_user_id = link_code[0]
        dashboard_username = link_code[1]
        existing_player_id = link_code[2]

        if existing_player_id is not None:
            raise ValueError(
                f"That {BOT_NAME} account is already linked to a player."
            )

        cursor.execute(
            '''
            SELECT
                player_id,
                player_name
            FROM players
            WHERE discord_user_id = %s
            FOR UPDATE
            ''',
            (discord_user_id,)
        )
        player = cursor.fetchone()

        if player is None:
            raise ValueError(
                "Your Discord account is not registered to a player. "
                "Use `/register` first."
            )

        player_id = player[0]
        player_name = player[1]

        cursor.execute(
            '''
            SELECT username
            FROM users
            WHERE player_id = %s
              AND user_id != %s
            ''',
            (
                player_id,
                dashboard_user_id
            )
        )
        existing_dashboard_link = cursor.fetchone()

        if existing_dashboard_link is not None:
            raise ValueError(
                f"**{player_name}** is already linked to another "
                f"{BOT_NAME} account."
            )

        cursor.execute(
            '''
            UPDATE users
            SET player_id = %s
            WHERE user_id = %s
              AND player_id IS NULL
            ''',
            (
                player_id,
                dashboard_user_id
            )
        )

        if cursor.rowcount != 1:
            raise ValueError(
                f"That {BOT_NAME} account could not be linked. "
                "Please request a new link code."
            )

        cursor.execute(
            '''
            DELETE FROM dashboard_link_codes
            WHERE user_id = %s
            ''',
            (dashboard_user_id,)
        )

    return {
        "user_id": dashboard_user_id,
        "username": dashboard_username,
        "player_id": player_id,
        "player_name": player_name
    }


def get_tile_names():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tile_name FROM tiles")
        tiles = cursor.fetchall()

    # Extract the tile names from the fetched records
    tile_names = [tile[0] for tile in tiles]
    return tile_names


def get_player_names():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT player_name FROM players")
        players = cursor.fetchall()

    # Extract the player names from the fetched records
    player_names = [player[0] for player in players]
    return player_names


def update_tile(tile_id,new_tile_id, tile_name, tile_type, old_tile_triggers, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required, tile_repetition, tile_points, tile_rules):
    with connect() as conn:
        cursor = conn.cursor()

        if _tile_has_recorded_activity(
            cursor,
            tile_id
        ):
            raise ValueError(
                "This tile cannot be edited because progress "
                "or evidence has already been recorded for it."
            )

        cursor.execute('''
            UPDATE tiles
            SET tile_id = %s, tile_name = %s, tile_type = %s, tile_triggers = %s, tile_trigger_weights = %s, tile_unique_drops = %s,
                tile_triggers_required = %s, tile_repetition = %s, tile_points = %s, tile_rules = %s
            WHERE tile_id = %s
        ''', (new_tile_id, tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
              tile_repetition, tile_points, tile_rules, tile_id))

        cursor.execute('''
            DELETE FROM drop_whitelist
            WHERE tile_id = %s
        ''', (tile_id,))

        conn.commit()

    if tile_type == "DROP":
        old_trigger_set = set()
        for x in old_tile_triggers.split(','):
            for trigger in x.split('/'):
                old_trigger_set.add(trigger.strip())

        new_trigger_set = set()
        for x in tile_triggers.split(','):
            for trigger in x.split('/'):
                trigger = trigger.strip()
                add_drop_whitelist(trigger, new_tile_id)
                new_trigger_set.add(trigger)

        for trigger in new_trigger_set:
            if trigger not in old_trigger_set:
                drops = get_drops_by_item_name(trigger)
                for drop in drops:
                    drop = db_entities.Drop(drop)
                    remove_drop_by_pk(drop.drop_pk)
                    json_data = spoof_drop.award_drop_json(
                        drop.player_name,
                        drop.drop_name,
                        drop.drop_value,
                        drop.drop_quantity
                    )
                    dink.parse_loot(json_data, None)


def remove_drop_by_pk(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE drop_pk = %s", (drop_pk))

def _tile_has_recorded_activity(cursor, tile_id):
    cursor.execute(
        '''
        SELECT
            EXISTS (
                SELECT 1
                FROM manual_evidence
                WHERE tile_id = %s
            )
            OR EXISTS (
                SELECT 1
                FROM dink_event_progress
                WHERE tile_id = %s
            )
            OR EXISTS (
                SELECT 1
                FROM tile_condition_progress AS progress
                JOIN tile_conditions AS condition
                  ON condition.condition_id =
                        progress.condition_id
                WHERE condition.tile_id = %s
                  AND COALESCE(progress.progress, 0) > 0
            )
            OR EXISTS (
                SELECT 1
                FROM partial_completions
                WHERE tile_id = %s
                  AND COALESCE(partial_completion, 0) > 0
            )
            OR EXISTS (
                SELECT 1
                FROM player_tile_credits
                WHERE tile_id = %s
            )
            OR EXISTS (
                SELECT 1
                FROM completed_tiles
                WHERE tile_id = %s
            )
            OR EXISTS (
                SELECT 1
                FROM relevant_drops
                WHERE tile_id = %s
            )
        ''',
        (
            tile_id,
            tile_id,
            tile_id,
            tile_id,
            tile_id,
            tile_id,
            tile_id
        )
    )

    return bool(cursor.fetchone()[0])


def remove_tile(tile_id):
    with connect() as conn:
        cursor = conn.cursor()

        if _tile_has_recorded_activity(
            cursor,
            tile_id
        ):
            raise ValueError(
                "This tile cannot be deleted because progress "
                "or evidence has already been recorded for it."
            )

        cursor.execute('''
            DELETE FROM drop_whitelist
            WHERE tile_id = %s
        ''', (tile_id,))

        cursor.execute(
            "DELETE FROM tiles WHERE tile_id = %s",
            (tile_id,)
        )

        conn.commit()


def get_user_by_username(username):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                user_id,
                username,
                email,
                password,
                is_admin,
                account_role,
                player_id
            FROM users
            WHERE LOWER(BTRIM(username)) = LOWER(BTRIM(%s))
            ''',
            (username,)
        )
        result = cursor.fetchone()

    if result is None:
        return None

    return User(
        user_id=result[0],
        username=result[1],
        email=result[2],
        password=result[3],
        is_admin=result[4],
        account_role=result[5],
        player_id=result[6]
    )


def get_user_by_email(email):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                user_id,
                username,
                email,
                password,
                is_admin,
                account_role,
                player_id
            FROM users
            WHERE email = %s
            ''',
            (email,)
        )
        result = cursor.fetchone()

    if result is None:
        return None

    return User(
        user_id=result[0],
        username=result[1],
        email=result[2],
        password=result[3],
        is_admin=result[4],
        account_role=result[5],
        player_id=result[6]
    )

def get_user_by_id(user_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                user_id,
                username,
                email,
                password,
                is_admin,
                account_role,
                player_id
            FROM users
            WHERE user_id = %s
            ''',
            (user_id,)
        )
        result = cursor.fetchone()

    if result is None:
        return None

    return User(
        user_id=result[0],
        username=result[1],
        email=result[2],
        password=result[3],
        is_admin=result[4],
        account_role=result[5],
        player_id=result[6]
    )

def check_password(hashed_password, password):
    return bcrypt.check_password_hash(hashed_password, password)

def change_user_password(
    user_id,
    current_password,
    new_password
):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT password
            FROM users
            WHERE user_id = %s
            FOR UPDATE
            ''',
            (user_id,)
        )
        user = cursor.fetchone()

        if user is None:
            raise ValueError(
                f"{BOT_NAME} account could not be found."
            )

        if not bcrypt.check_password_hash(
            user[0],
            current_password
        ):
            raise ValueError(
                "Your current password is incorrect."
            )

        hashed_password = bcrypt.generate_password_hash(
            new_password
        ).decode('utf-8')

        cursor.execute(
            '''
            UPDATE users
            SET password = %s
            WHERE user_id = %s
            ''',
            (
                hashed_password,
                user_id
            )
        )

# Add these functions to your existing database functions

# Functions for 'teams' table
def add_team_points(team_id, team_points):
    with connect() as conn:
        cursor = conn.cursor()
        update_query = '''
            UPDATE teams
            SET team_points = team_points + %s
            WHERE team_id = %s
        '''
        cursor.execute(update_query, (team_points, team_id,))
        conn.commit()

def rename_team(old_team_name, new_team_name):
    with connect() as conn:
        cursor = conn.cursor()
        update_query = '''
            UPDATE teams
            SET team_name = %s
            WHERE lower(team_name) = lower(%s)
            '''
        cursor.execute(update_query, (new_team_name, old_team_name,))

# Functions for 'teams' table
def add_team(team_name, team_points, team_webhook):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO teams (team_name, team_points, team_webhook) VALUES (%s, %s, %s)",
                       (team_name, team_points, team_webhook))
        return cursor.execute("SELECT team_id from teams where lower(team_name) = lower(%s)", (team_name,))


def remove_team(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teams WHERE team_id = %s", (team_id,))


def get_teams():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams")
        return cursor.fetchall()


def get_team_by_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams where team_id = %s", (team_id,))
        return cursor.fetchone()


def get_team_by_name(team_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams where lower(team_name) = lower(%s)", (team_name,))
        return cursor.fetchone()

def get_team_by_discord_role_id(discord_role_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM teams WHERE discord_role_id = %s",
            (discord_role_id,)
        )
        return cursor.fetchone()

def set_team_discord_role_id(team_id, discord_role_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE teams
            SET discord_role_id = %s
            WHERE team_id = %s
            """,
            (discord_role_id, team_id)
        )
        conn.commit()


def set_team_photo_path(
    team_id,
    team_photo_path
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE teams
            SET team_photo_path = %s
            WHERE team_id = %s
            """,
            (
                team_photo_path,
                team_id
            )
        )

        if cursor.rowcount != 1:
            raise ValueError(
                f"Team {team_id} was not found."
            )

        conn.commit()


# Functions for 'players' table
def add_player(player_name, deaths, gp_gained, tiles_completed, team_id, pet_count):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO players (player_name, deaths, gp_gained, tiles_completed, team_id, pet_count) VALUES (%s, %s, %s, %s, %s, %s)",
            (player_name, deaths, gp_gained, tiles_completed, team_id, pet_count))


def add_death_by_playername(rsn):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET deaths = deaths + 1 WHERE lower(player_name) = lower(%s)", (rsn,))


def add_pet_by_playername(rsn):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET pet_count = pet_count + 1 WHERE lower(player_name) = lower(%s)", (rsn,))

def get_total_pets_by_team(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE team_id = %s", (team_id,))
    total_pets = 0
    for player in cursor.fetchall():
        player_obj = db_entities.Player(player)
        total_pets = total_pets + player_obj.pet_count
    return total_pets

def add_player_tile_completions(player_id, tiles_completed):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE players
            SET tiles_completed = tiles_completed + %s
            WHERE player_id = %s
        ''', (tiles_completed, player_id))

def add_player_points(player_id, points):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE players
            SET player_points = player_points + %s
            WHERE player_id = %s
        ''', (points, player_id))
        conn.commit()


def rename_player(old_player_name, new_player_name):
    with connect() as conn:
        cursor = conn.cursor()
        update_query = '''
            UPDATE players
            SET player_name = %s
            WHERE lower(player_name) = lower(%s)
            '''
        cursor.execute(update_query, (new_player_name, old_player_name,))




def remove_player(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM players WHERE player_id = %s", (player_id,))


def get_players():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players")
        return cursor.fetchall()


def get_players_by_team():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.team_name, p.player_id, p.player_name, p.deaths, p.gp_gained, p.tiles_completed, p.pet_count
            FROM players p
            JOIN teams t ON p.team_id = t.team_id
            ORDER BY t.team_name, p.player_id
        ''')
        players = cursor.fetchall()

    # Group players by team name
    players_by_team = {}
    for player in players:
        team_name = player[0]
        if team_name not in players_by_team:
            players_by_team[team_name] = []
        players_by_team[team_name].append(player[1:])

    return players_by_team


def get_manage_players_roster():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                t.team_id,
                t.team_name,
                p.player_id,
                p.player_name,
                COALESCE(p.player_points, 0),
                COALESCE(p.tiles_completed, 0),
                p.discord_user_id,
                p.discord_display_name,
                p.discord_username
            FROM teams t
            LEFT JOIN players p
                ON p.team_id = t.team_id
            ORDER BY
                t.team_id,
                LOWER(p.player_name),
                p.player_name
        ''')
        rows = cursor.fetchall()

    teams = []

    for row in rows:
        team_id = row[0]

        if not teams or teams[-1]["team_id"] != team_id:
            teams.append(
                {
                    "team_id": team_id,
                    "team_name": row[1],
                    "players": []
                }
            )

        if row[2] is None:
            continue

        teams[-1]["players"].append(
            {
                "player_id": row[2],
                "player_name": row[3],
                "mvp_points": row[4],
                "tile_contributions": row[5],
                "discord_user_id": row[6],
                "discord_display_name": row[7],
                "discord_username": row[8]
            }
        )

    return teams


def get_players_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE team_id = %s", (team_id,))
        return cursor.fetchall()


def get_player_by_name(player_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players where lower(player_name) = lower(%s)", (player_name,))
        return cursor.fetchone()


def get_player_by_wom_player_id(wom_player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT *
            FROM players
            WHERE wom_player_id = %s
            ''',
            (wom_player_id,)
        )
        return cursor.fetchone()


def get_player_by_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players where player_id = %s", (player_id,))
        return cursor.fetchone()

def get_player_by_discord_user_id(discord_user_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM players WHERE discord_user_id = %s",
            (discord_user_id,)
        )
        return cursor.fetchone()

def link_player_to_discord(
    player_id,
    discord_user_id,
    discord_display_name=None,
    discord_username=None
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE players
            SET discord_user_id = %s,
                discord_display_name = %s,
                discord_username = %s
            WHERE player_id = %s
              AND (
                  discord_user_id IS NULL
                  OR discord_user_id = %s
              )
            """,
            (
                discord_user_id,
                discord_display_name,
                discord_username,
                player_id,
                discord_user_id
            )
        )

def record_dink_auth_failure(
    failure_reason,
    request_format,
    claimed_player_name=None,
    claimed_dink_account_hash=None,
    claimed_event_type=None,
    source_ip=None,
    user_agent=None
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO dink_auth_audit (
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format,
                source_ip,
                user_agent
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING audit_id
            ''',
            (
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format,
                source_ip,
                user_agent
            )
        )

        return cursor.fetchone()[0]


def get_recent_dink_auth_failures(limit=100):
    limit = max(
        1,
        min(int(limit), 500)
    )

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                audit_id,
                failure_reason,
                claimed_player_name,
                claimed_dink_account_hash,
                claimed_event_type,
                request_format,
                source_ip,
                user_agent,
                received_at
            FROM dink_auth_audit
            ORDER BY
                received_at DESC,
                audit_id DESC
            LIMIT %s
            ''',
            (limit,)
        )

        return cursor.fetchall()


def get_dink_identity_review_rows():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                identity.dink_account_hash,
                identity.observed_rsn,
                identity.status,
                identity.player_id,
                linked_player.player_name,
                linked_team.team_name,
                identity.first_seen,
                identity.last_seen,
                identity.linked_at,

                (
                    SELECT COUNT(*)
                    FROM dink_events event
                    WHERE
                        event.dink_account_hash
                            = identity.dink_account_hash
                        AND lower(event.player_name)
                            = lower(identity.observed_rsn)
                        AND event.duplicate_of_event_id IS NULL
                ) AS observations,

                (
                    SELECT ARRAY_AGG(
                        DISTINCT event.player_name
                        ORDER BY event.player_name
                    )
                    FROM dink_events event
                    WHERE
                        event.dink_account_hash
                            = identity.dink_account_hash
                        AND event.player_name IS NOT NULL
                        AND lower(event.player_name)
                            != lower(identity.observed_rsn)
                        AND event.duplicate_of_event_id IS NULL
                ) AS conflicting_rsns,

                matching_player.player_id,
                matching_player.player_name,
                matching_team.team_name,

                (
                    SELECT linked_identity.dink_account_hash
                    FROM dink_identities linked_identity
                    WHERE
                        linked_identity.player_id
                            = matching_player.player_id
                        AND linked_identity.status = 'LINKED'
                        AND linked_identity.dink_account_hash
                            != identity.dink_account_hash
                    LIMIT 1
                ) AS existing_linked_hash

            FROM dink_identities identity

            LEFT JOIN players linked_player
                ON linked_player.player_id = identity.player_id

            LEFT JOIN teams linked_team
                ON linked_team.team_id = linked_player.team_id

            LEFT JOIN players matching_player
                ON lower(matching_player.player_name)
                    = lower(identity.observed_rsn)

            LEFT JOIN teams matching_team
                ON matching_team.team_id
                    = matching_player.team_id

            ORDER BY
                CASE identity.status
                    WHEN 'CONFLICT' THEN 1
                    WHEN 'PENDING' THEN 2
                    WHEN 'LINKED' THEN 3
                    ELSE 4
                END,
                identity.last_seen DESC,
                identity.dink_account_hash
            '''
        )

        return cursor.fetchall()



def get_dink_identity_by_hash(dink_account_hash):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                dink_account_hash,
                player_id,
                observed_rsn,
                status,
                first_seen,
                last_seen,
                linked_at
            FROM dink_identities
            WHERE dink_account_hash = %s
            ''',
            (dink_account_hash,)
        )
        return cursor.fetchone()

def get_recent_dink_event_by_fingerprint(
    event_fingerprint,
    retry_window_seconds=300
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                event_id,
                received_at,
                status,
                player_id,
                dink_account_hash
            FROM dink_events
            WHERE event_fingerprint = %s
              AND duplicate_of_event_id IS NULL
              AND received_at >= (
                  CURRENT_TIMESTAMP
                  - (%s * INTERVAL '1 second')
              )
            ORDER BY received_at DESC
            LIMIT 1
            ''',
            (
                event_fingerprint,
                retry_window_seconds
            )
        )
        return cursor.fetchone()

def count_dink_identity_observations(
    dink_account_hash,
    player_name
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM dink_events
            WHERE dink_account_hash = %s
              AND lower(player_name) = lower(%s)
              AND duplicate_of_event_id IS NULL
            ''',
            (
                dink_account_hash,
                player_name
            )
        )
        return cursor.fetchone()[0]

def count_dink_hash_observations(dink_account_hash):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM dink_events
            WHERE dink_account_hash = %s
              AND duplicate_of_event_id IS NULL
            ''',
            (dink_account_hash,)
        )
        return cursor.fetchone()[0]

def record_pending_dink_identity(
    dink_account_hash,
    player_name
    ):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                observed_rsn,
                status
            FROM dink_identities
            WHERE dink_account_hash = %s
            FOR UPDATE
            ''',
            (dink_account_hash,)
        )

        existing = cursor.fetchone()

        if existing is None:
            cursor.execute(
                '''
                INSERT INTO dink_identities (
                    dink_account_hash,
                    observed_rsn,
                    status
                )
                VALUES (%s, %s, 'PENDING')
                ''',
                (
                    dink_account_hash,
                    player_name
                )
            )

            conn.commit()
            return 'PENDING'

        observed_rsn, status = existing

        if observed_rsn.lower() != player_name.lower():
            cursor.execute(
                '''
                UPDATE dink_identities
                SET
                    status = 'CONFLICT',
                    last_seen = CURRENT_TIMESTAMP
                WHERE dink_account_hash = %s
                ''',
                (dink_account_hash,)
            )

            conn.commit()
            return 'CONFLICT'

        cursor.execute(
            '''
            UPDATE dink_identities
            SET last_seen = CURRENT_TIMESTAMP
            WHERE dink_account_hash = %s
            ''',
            (dink_account_hash,)
        )

        conn.commit()
        return status

def manually_link_dink_identity(
    dink_account_hash,
    player_id
):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                status
            FROM dink_identities
            WHERE dink_account_hash = %s
            FOR UPDATE
            ''',
            (dink_account_hash,)
        )

        identity = cursor.fetchone()

        if identity is None:
            return {
                'status': 'IDENTITY_NOT_FOUND',
                'player_id': None,
                'existing_linked_hash': None
            }

        current_player_id, current_status = identity

        if current_status == 'LINKED':
            if current_player_id == player_id:
                return {
                    'status': 'LINKED',
                    'player_id': player_id,
                    'existing_linked_hash': None
                }

            return {
                'status': 'IDENTITY_ALREADY_LINKED',
                'player_id': current_player_id,
                'existing_linked_hash': dink_account_hash
            }

        cursor.execute(
            '''
            SELECT player_id
            FROM players
            WHERE player_id = %s
            FOR UPDATE
            ''',
            (player_id,)
        )

        player = cursor.fetchone()

        if player is None:
            return {
                'status': 'PLAYER_NOT_FOUND',
                'player_id': None,
                'existing_linked_hash': None
            }

        cursor.execute(
            '''
            SELECT dink_account_hash
            FROM dink_identities
            WHERE player_id = %s
              AND status = 'LINKED'
              AND dink_account_hash != %s
            LIMIT 1
            ''',
            (
                player_id,
                dink_account_hash
            )
        )

        existing_link = cursor.fetchone()

        if existing_link is not None:
            return {
                'status': 'PLAYER_ALREADY_LINKED',
                'player_id': player_id,
                'existing_linked_hash': existing_link[0]
            }

        cursor.execute(
            '''
            UPDATE dink_identities
            SET
                player_id = %s,
                status = 'LINKED',
                linked_at = CURRENT_TIMESTAMP,
                last_seen = CURRENT_TIMESTAMP
            WHERE dink_account_hash = %s
            ''',
            (
                player_id,
                dink_account_hash
            )
        )

        conn.commit()

        return {
            'status': 'LINKED',
            'player_id': player_id,
            'existing_linked_hash': None
        }

def try_link_dink_identity(
    dink_account_hash,
    player_name,
    required_observations=3
    ):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                observed_rsn,
                status
            FROM dink_identities
            WHERE dink_account_hash = %s
            FOR UPDATE
            ''',
            (dink_account_hash,)
        )

        identity = cursor.fetchone()

        if identity is None:
            return {
                'status': 'PENDING',
                'observations': 0,
                'player_id': None
            }

        linked_player_id, observed_rsn, status = identity

        if status == 'CONFLICT':
            return {
                'status': 'CONFLICT',
                'observations': 0,
                'player_id': linked_player_id
            }

        if observed_rsn.lower() != player_name.lower():
            cursor.execute(
                '''
                UPDATE dink_identities
                SET
                    status = 'CONFLICT',
                    last_seen = CURRENT_TIMESTAMP
                WHERE dink_account_hash = %s
                ''',
                (dink_account_hash,)
            )
            conn.commit()

            return {
                'status': 'CONFLICT',
                'observations': 0,
                'player_id': None
            }

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM dink_events
            WHERE dink_account_hash = %s
              AND lower(player_name) = lower(%s)
              AND duplicate_of_event_id IS NULL
            ''',
            (
                dink_account_hash,
                player_name
            )
        )

        observations = cursor.fetchone()[0]

        if status == 'LINKED':
            return {
                'status': 'LINKED',
                'observations': observations,
                'player_id': linked_player_id
            }

        if observations < required_observations:
            return {
                'status': 'PENDING',
                'observations': observations,
                'player_id': None
            }

        cursor.execute(
            '''
            SELECT player_id
            FROM players
            WHERE lower(player_name) = lower(%s)
            ''',
            (player_name,)
        )

        player = cursor.fetchone()

        if player is None:
            return {
                'status': 'PLAYER_NOT_FOUND',
                'observations': observations,
                'player_id': None
            }

        player_id = player[0]

        cursor.execute(
            '''
            SELECT dink_account_hash
            FROM dink_identities
            WHERE player_id = %s
              AND status = 'LINKED'
              AND dink_account_hash != %s
            LIMIT 1
            ''',
            (
                player_id,
                dink_account_hash
            )
        )

        existing_link = cursor.fetchone()

        if existing_link is not None:
            cursor.execute(
                '''
                UPDATE dink_identities
                SET
                    status = 'CONFLICT',
                    last_seen = CURRENT_TIMESTAMP
                WHERE dink_account_hash = %s
                ''',
                (dink_account_hash,)
            )
            conn.commit()

            return {
                'status': 'CONFLICT',
                'observations': observations,
                'player_id': None
            }

        cursor.execute(
            '''
            UPDATE dink_identities
            SET
                player_id = %s,
                status = 'LINKED',
                linked_at = CURRENT_TIMESTAMP,
                last_seen = CURRENT_TIMESTAMP
            WHERE dink_account_hash = %s
            ''',
            (
                player_id,
                dink_account_hash
            )
        )

        conn.commit()

        return {
            'status': 'LINKED',
            'observations': observations,
            'player_id': player_id
        }

def add_dink_event(
    event_fingerprint,
    raw_payload,
    dink_account_hash=None,
    player_name=None,
    player_id=None,
    event_type=None,
    screenshot_path=None,
    screenshot_sha256=None,
    duplicate_of_event_id=None,
    status='RECEIVED'
    ):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO dink_events (
                event_fingerprint,
                duplicate_of_event_id,
                dink_account_hash,
                player_name,
                player_id,
                event_type,
                raw_payload,
                screenshot_path,
                screenshot_sha256,
                status,
                processed_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                %s,
                %s,
                %s,
                CASE
                    WHEN %s IN (
                        'PROCESSED',
                        'IGNORED',
                        'REJECTED',
                        'ERROR'
                    )
                    THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END
            )
            RETURNING event_id
            ''',
            (
                event_fingerprint,
                duplicate_of_event_id,
                dink_account_hash,
                player_name,
                player_id,
                event_type,
                json.dumps(raw_payload),
                screenshot_path,
                screenshot_sha256,
                status,
                status
            )
        )
        event_id = cursor.fetchone()[0]
        conn.commit()
        return event_id

def update_dink_event_screenshot(
    event_id,
    screenshot_path,
    screenshot_sha256
):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE dink_events
            SET
                screenshot_path = %s,
                screenshot_sha256 = %s
            WHERE event_id = %s
            ''',
            (
                screenshot_path,
                screenshot_sha256,
                event_id
            )
        )

        if cursor.rowcount != 1:
            raise ValueError(
                f"Dink event {event_id} was not found"
            )

        conn.commit()

def get_dink_event_by_id(event_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                event_id,
                event_fingerprint,
                duplicate_of_event_id,
                dink_account_hash,
                player_name,
                player_id,
                event_type,
                raw_payload,
                screenshot_path,
                screenshot_sha256,
                status,
                received_at,
                processed_at
            FROM dink_events
            WHERE event_id = %s
            ''',
            (event_id,)
        )

        return cursor.fetchone()



def get_manual_evidence_by_id(evidence_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                evidence_id,
                player_id,
                evidence_path,
                status
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (evidence_id,)
        )

        return cursor.fetchone()


def minimise_ignored_dink_event(event_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT screenshot_path
            FROM dink_events
            WHERE event_id = %s
              AND status = 'IGNORED'
            FOR UPDATE
            """,
            (event_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        screenshot_path = row[0]

        cursor.execute(
            """
            UPDATE dink_events
            SET raw_payload = '{}'::jsonb
            WHERE event_id = %s
              AND status = 'IGNORED'
            """,
            (event_id,)
        )

        conn.commit()

        return screenshot_path


def clear_dink_event_screenshot_path(event_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE dink_events
            SET screenshot_path = NULL
            WHERE event_id = %s
              AND status = 'IGNORED'
            """,
            (event_id,)
        )

        conn.commit()

def _update_dink_event_identity(
    cursor,
    event_id,
    player_id,
    status
):
    cursor.execute(
        '''
        UPDATE dink_events
        SET
            player_id = %s,
            status = %s,
            processed_at = CASE
                WHEN %s IN (
                    'PROCESSED',
                    'IGNORED',
                    'REJECTED',
                    'ERROR'
                )
                THEN CURRENT_TIMESTAMP
                ELSE processed_at
            END
        WHERE event_id = %s
        ''',
        (
            player_id,
            status,
            status,
            event_id
        )
    )

    if cursor.rowcount != 1:
        raise ValueError(
            f"Dink event {event_id} was not found"
        )


def update_dink_event_identity(
    event_id,
    player_id,
    status
):
    with connect() as conn:
        cursor = conn.cursor()

        _update_dink_event_identity(
            cursor=cursor,
            event_id=event_id,
            player_id=player_id,
            status=status
        )

        conn.commit()


def _record_staff_review_decision(
    cursor,
    subject_type,
    subject_id,
    decision,
    review_source,
    reviewer_id,
    reviewer_name,
    reason=None,
    audit_only=False,
    reason_code=None
):
    if reviewer_name is None:
        raise ValueError(
            "Reviewer name is required."
        )

    reviewer_name = str(
        reviewer_name
    ).strip()

    if not reviewer_name:
        raise ValueError(
            "Reviewer name is required."
        )
    if reviewer_id is None:
        raise ValueError(
            "Reviewer ID is required."
        )

    if reason is not None:
        reason = str(reason).strip()

        if not reason:
            reason = None

    cursor.execute(
        '''
        INSERT INTO staff_review_decisions (
            subject_type,
            subject_id,
            decision,
            review_source,
            reviewer_id,
            reviewer_name,
            reason,
            reason_code,
            audit_only,
            decided_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            clock_timestamp()
        )
        RETURNING decision_id
        ''',
        (
            subject_type,
            subject_id,
            decision,
            review_source,
            reviewer_id,
            reviewer_name,
            reason,
            reason_code,
            bool(audit_only)
        )
    )

    return cursor.fetchone()[0]


def _record_evidence_invalidation(
    cursor,
    subject_type,
    subject_id,
    reason_code,
    review_source,
    reviewer_id,
    reviewer_name,
    details=None
):
    valid_subject_types = {
        "DINK_EVENT",
        "MANUAL_EVIDENCE"
    }

    valid_reason_codes = {
        "INCORRECT_EVIDENCE",
        "WRONG_ITEM_OR_ACTIVITY",
        "DUPLICATE_EVIDENCE",
        "WRONG_PLAYER_OR_ACCOUNT",
        "WRONG_TILE_OR_CONDITION",
        "ADMINISTRATIVE_TEST_CORRECTION",
        "OTHER"
    }

    valid_review_sources = {
        "WEB",
        "DISCORD"
    }

    subject_type = str(subject_type).strip().upper()
    reason_code = str(reason_code).strip().upper()
    review_source = str(review_source).strip().upper()

    if subject_type not in valid_subject_types:
        raise ValueError(
            f"Unsupported invalidation subject type: {subject_type}"
        )

    if reason_code not in valid_reason_codes:
        raise ValueError(
            f"Unsupported invalidation reason code: {reason_code}"
        )

    if review_source not in valid_review_sources:
        raise ValueError(
            f"Unsupported invalidation review source: {review_source}"
        )

    if subject_id is None:
        raise ValueError(
            "Invalidation subject ID is required."
        )

    if reviewer_id is None:
        raise ValueError(
            "Reviewer ID is required."
        )

    if reviewer_name is None:
        raise ValueError(
            "Reviewer name is required."
        )

    reviewer_name = str(reviewer_name).strip()

    if not reviewer_name:
        raise ValueError(
            "Reviewer name is required."
        )

    if details is not None:
        details = str(details).strip()

        if not details:
            details = None

    if reason_code == "OTHER" and details is None:
        raise ValueError(
            "Additional details are required when the "
            "invalidation reason is Other."
        )

    cursor.execute(
        '''
        SELECT invalidation_id
        FROM evidence_invalidations
        WHERE subject_type = %s
          AND subject_id = %s
        ''',
        (
            subject_type,
            subject_id
        )
    )

    if cursor.fetchone() is not None:
        raise ValueError(
            "This evidence has already been invalidated."
        )

    cursor.execute(
        '''
        INSERT INTO evidence_invalidations (
            subject_type,
            subject_id,
            reason_code,
            details,
            review_source,
            reviewer_id,
            reviewer_name,
            invalidated_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            clock_timestamp()
        )
        RETURNING invalidation_id
        ''',
        (
            subject_type,
            subject_id,
            reason_code,
            details,
            review_source,
            reviewer_id,
            reviewer_name
        )
    )

    return cursor.fetchone()[0]


def _reverse_completed_tile_for_invalidation(
    cursor,
    team_id,
    tile_id
):
    cursor.execute(
        '''
        SELECT
            completed_tile_pk,
            points_awarded
        FROM completed_tiles
        WHERE team_id = %s
          AND tile_id = %s
        FOR UPDATE
        ''',
        (
            team_id,
            tile_id
        )
    )

    completion = cursor.fetchone()

    if completion is None:
        return False

    completed_tile_pk, points_awarded = completion

    if points_awarded is None:
        raise ValueError(
            "This tile completion predates frozen point awards "
            "and cannot be safely invalidated automatically."
        )

    points_awarded = float(points_awarded)

    cursor.execute(
        '''
        SELECT
            credit_id,
            player_id,
            contribution,
            points_awarded
        FROM player_tile_credits
        WHERE team_id = %s
          AND tile_id = %s
          AND credit_type = 'TILE_COMPLETION'
        ORDER BY credit_id
        FOR UPDATE
        ''',
        (
            team_id,
            tile_id
        )
    )

    completion_credits = cursor.fetchall()

    cursor.execute(
        '''
        SELECT 1
        FROM player_tile_credits
        WHERE team_id = %s
          AND tile_id = %s
          AND credit_type = 'LATE_REVIEW'
        LIMIT 1
        ''',
        (
            team_id,
            tile_id
        )
    )

    if cursor.fetchone() is not None:
        raise ValueError(
            "This completed tile has a late-review credit "
            "and cannot be safely invalidated until "
            "late-review reconciliation is implemented."
        )

    for (
        _,
        player_id,
        contribution,
        player_points_awarded
    ) in completion_credits:
        contribution = float(contribution)
        player_points_awarded = float(
            player_points_awarded
        )

        cursor.execute(
            '''
            SELECT
                tiles_completed,
                player_points
            FROM players
            WHERE player_id = %s
            FOR UPDATE
            ''',
            (player_id,)
        )

        player_row = cursor.fetchone()

        if player_row is None:
            continue

        tiles_completed = float(
            player_row[0] or 0
        )
        player_points = float(
            player_row[1] or 0
        )

        if (
            tiles_completed + 0.000000001
            < contribution
        ):
            raise ValueError(
                "Player tile completion total is smaller than "
                "the stored completion credit."
            )

        if (
            player_points + 0.000000001
            < player_points_awarded
        ):
            raise ValueError(
                "Player point total is smaller than the "
                "stored completion credit."
            )

    cursor.execute(
        '''
        SELECT team_points
        FROM teams
        WHERE team_id = %s
        FOR UPDATE
        ''',
        (team_id,)
    )

    team_row = cursor.fetchone()

    if team_row is None:
        raise ValueError(
            f"Team {team_id} does not exist."
        )

    team_points = float(
        team_row[0] or 0
    )

    if (
        team_points + 0.000000001
        < points_awarded
    ):
        raise ValueError(
            "Team point total is smaller than the frozen "
            "tile completion award."
        )

    # Restore the exact contribution bank that existed immediately
    # before completion consumed it. The completion snapshot must be
    # read before deleting completed_tiles because it is cascaded.
    cursor.execute(
        '''
        INSERT INTO partial_completions (
            team_id,
            tile_id,
            player_id,
            partial_completion
        )
        SELECT
            %s,
            %s,
            player_id,
            partial_completion
        FROM completed_tile_partial_snapshot
        WHERE completed_tile_pk = %s
        ORDER BY snapshot_id
        ''',
        (
            team_id,
            tile_id,
            completed_tile_pk
        )
    )

    for (
        _,
        player_id,
        contribution,
        player_points_awarded
    ) in completion_credits:
        cursor.execute(
            '''
            UPDATE players
            SET
                tiles_completed =
                    COALESCE(tiles_completed, 0) - %s,
                player_points =
                    COALESCE(player_points, 0) - %s
            WHERE player_id = %s
            ''',
            (
                contribution,
                player_points_awarded,
                player_id
            )
        )

    cursor.execute(
        '''
        DELETE FROM player_tile_credits
        WHERE team_id = %s
          AND tile_id = %s
          AND credit_type = 'TILE_COMPLETION'
        ''',
        (
            team_id,
            tile_id
        )
    )

    cursor.execute(
        '''
        UPDATE teams
        SET team_points = team_points - %s
        WHERE team_id = %s
        ''',
        (
            points_awarded,
            team_id
        )
    )

    cursor.execute(
        '''
        DELETE FROM completed_tiles
        WHERE completed_tile_pk = %s
        ''',
        (completed_tile_pk,)
    )

    return True


def _replay_late_manual_evidence_after_invalidation(
    cursor,
    team_id,
    tile_id,
    completed_at
):
    cursor.execute(
        '''
        SELECT
            e.evidence_id,
            e.player_id,
            e.amount,
            e.submitted_at,
            p.progress_id,
            p.potential_contribution
        FROM manual_evidence AS e
        INNER JOIN manual_evidence_progress AS p
            ON p.evidence_id = e.evidence_id
        WHERE e.team_id = %s
          AND e.tile_id = %s
          AND e.status = 'ACCEPTED'
          AND e.submitted_at <= %s
          AND p.processed_at >= %s
          AND p.actual_contribution = 0
          AND p.completed = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM evidence_invalidations AS invalidation
              WHERE invalidation.subject_type =
                    'MANUAL_EVIDENCE'
                AND invalidation.subject_id =
                    e.evidence_id
          )
        ORDER BY
            e.submitted_at,
            e.evidence_id
        FOR UPDATE OF e, p
        ''',
        (
            team_id,
            tile_id,
            completed_at,
            completed_at
        )
    )

    candidates = cursor.fetchall()
    replayed_evidence = []

    for (
        evidence_id,
        player_id,
        amount,
        _,
        progress_id,
        potential_contribution
    ) in candidates:
        cursor.execute(
            '''
            SELECT 1
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        # An earlier replayed submission has genuinely completed
        # the tile. Later accepted evidence therefore remains late
        # evidence and must not add further live progress.
        if cursor.fetchone() is not None:
            break

        compatibility = (
            _check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        if not compatibility["compatible"]:
            raise ValueError(
                "Accepted manual evidence cannot be replayed "
                "because the tile changed after submission: "
                f"{compatibility['reason']}."
            )

        player_exists = False

        if player_id is not None:
            cursor.execute(
                '''
                SELECT player_id
                FROM players
                WHERE player_id = %s
                FOR UPDATE
                ''',
                (player_id,)
            )

            player_exists = (
                cursor.fetchone() is not None
            )

        condition_id = int(
            compatibility["condition_id"]
        )

        completion_path = int(
            compatibility["completion_path"]
        )

        amount = int(amount)

        before = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        raw_progress = _add_tile_condition_progress(
            cursor=cursor,
            team_id=team_id,
            condition_id=condition_id,
            amount=amount
        )

        counted_amount = _calculate_counted_drop_amount(
            condition_type=compatibility[
                "condition_type"
            ],
            amount=amount,
            condition_target=compatibility["target"],
            condition_progress_before=(
                raw_progress - amount
            ),
            route_state=before
        )

        after = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        route_progress_delta = round(
            max(
                0.0,
                after["progress_fraction"]
                - before["progress_fraction"]
            ),
            12
        )

        bank_player_id = (
            player_id
            if player_exists
            else None
        )

        (
            actual_contribution,
            banked_total
        ) = _bank_partial_contribution(
            cursor=cursor,
            player_id=bank_player_id,
            team_id=team_id,
            tile_id=tile_id,
            requested_contribution=
                route_progress_delta
        )

        completion_details = None
        completed = False

        if after["ready"]:
            completion_details = (
                _complete_tile_with_contributions(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id,
                    finisher_player_id=(
                        player_id
                        if player_exists
                        else None
                    ),
                    return_details=True,
                    uncredited_finisher=(
                        not player_exists
                    )
                )
            )

            completed = bool(
                completion_details["completed"]
            )

        completion_remainder = 0.0

        if (
            completed
            and player_exists
            and completion_details is not None
        ):
            completion_remainder = round(
                float(
                    completion_details[
                        "finisher_remainder"
                    ]
                ),
                12
            )

        if player_exists:
            normal_player_credit = round(
                actual_contribution
                + completion_remainder,
                12
            )
        else:
            normal_player_credit = 0.0

        potential_contribution = round(
            float(potential_contribution or 0),
            12
        )

        if completed:
            lost_mvp_contribution = round(
                max(
                    0.0,
                    potential_contribution
                    - actual_contribution
                ),
                12
            )
        else:
            lost_mvp_contribution = 0.0

        cursor.execute(
            '''
            UPDATE manual_evidence_progress
            SET
                condition_id = %s,
                tile_id = %s,
                completion_path = %s,
                amount = %s,
                counted_amount = %s,
                raw_progress = %s,
                route_progress = %s,
                actual_contribution = %s,
                completion_remainder = %s,
                normal_player_credit = %s,
                lost_mvp_contribution = %s,
                banked_total = %s,
                ready = %s,
                completed = %s,
                processed_at = clock_timestamp()
            WHERE progress_id = %s
            ''',
            (
                condition_id,
                tile_id,
                completion_path,
                amount,
                counted_amount,
                raw_progress,
                after["progress_fraction"],
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                lost_mvp_contribution,
                banked_total,
                after["ready"],
                completed,
                progress_id
            )
        )

        replayed_evidence.append(
            {
                "evidence_id": int(evidence_id),
                "team_id": int(team_id),
                "tile_id": int(tile_id),
                "actual_contribution": round(
                    float(actual_contribution),
                    12
                ),
                "completed": completed
            }
        )

    return replayed_evidence


def _replay_suppressed_dink_progress_after_invalidation(
    cursor,
    team_id,
    tile_id,
    completed_at
):
    cursor.execute(
        '''
        SELECT
            dep.progress_id,
            dep.event_id,
            de.player_id,
            dep.condition_id,
            dep.completion_path,
            dep.amount,
            dep.condition_type_snapshot,
            dep.condition_trigger_snapshot,
            dep.condition_target_snapshot,
            dep.route_mode_snapshot,
            dep.route_target_snapshot,
            dep.require_unique_snapshot
        FROM dink_event_progress AS dep
        INNER JOIN dink_events AS de
            ON de.event_id = dep.event_id
        WHERE dep.team_id = %s
          AND dep.tile_id = %s
          AND dep.state = 'SUPPRESSED_COMPLETED'
          AND de.status = 'PROCESSED'
          AND de.received_at >= %s
          AND NOT EXISTS (
              SELECT 1
              FROM evidence_invalidations AS invalidation
              WHERE invalidation.subject_type = 'DINK_EVENT'
                AND invalidation.subject_id = dep.event_id
          )
        ORDER BY
            de.received_at,
            dep.event_id,
            dep.progress_id
        FOR UPDATE OF dep, de
        ''',
        (
            team_id,
            tile_id,
            completed_at
        )
    )

    candidates = cursor.fetchall()
    replayed_progress = []

    for (
        progress_id,
        event_id,
        player_id,
        condition_id,
        completion_path,
        amount,
        condition_type_snapshot,
        condition_trigger_snapshot,
        condition_target_snapshot,
        route_mode_snapshot,
        route_target_snapshot,
        require_unique_snapshot
    ) in candidates:
        cursor.execute(
            '''
            SELECT 1
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        # An earlier replay has genuinely completed the tile.
        # Any later Dink evidence remains suppressed.
        if cursor.fetchone() is not None:
            break

        if (
            condition_type_snapshot is None
            or condition_trigger_snapshot is None
            or condition_target_snapshot is None
            or route_mode_snapshot is None
            or require_unique_snapshot is None
        ):
            raise ValueError(
                "Suppressed Dink evidence cannot be replayed "
                "because its frozen tile definition is incomplete."
            )

        cursor.execute(
            '''
            SELECT tile_id
            FROM tiles
            WHERE tile_id = %s
            FOR UPDATE
            ''',
            (tile_id,)
        )

        if cursor.fetchone() is None:
            raise ValueError(
                "Suppressed Dink evidence cannot be replayed "
                "because the tile no longer exists."
            )

        cursor.execute(
            '''
            SELECT
                condition.condition_type,
                condition.condition_trigger,
                condition.target,
                path.route_mode,
                path.route_target,
                path.require_unique
            FROM tile_conditions AS condition
            INNER JOIN tile_completion_paths AS path
                ON path.tile_id = condition.tile_id
               AND path.completion_path =
                   condition.completion_path
            WHERE condition.condition_id = %s
              AND condition.tile_id = %s
              AND condition.completion_path = %s
            FOR UPDATE OF condition, path
            ''',
            (
                condition_id,
                tile_id,
                completion_path
            )
        )

        live_definition = cursor.fetchone()

        if live_definition is None:
            raise ValueError(
                "Suppressed Dink evidence cannot be replayed "
                "because its tile condition or path no longer "
                "exists."
            )

        (
            live_condition_type,
            live_condition_trigger,
            live_condition_target,
            live_route_mode,
            live_route_target,
            live_require_unique
        ) = live_definition

        frozen_definition = (
            str(condition_type_snapshot),
            str(condition_trigger_snapshot),
            int(condition_target_snapshot),
            str(route_mode_snapshot),
            (
                None
                if route_target_snapshot is None
                else int(route_target_snapshot)
            ),
            bool(require_unique_snapshot)
        )

        current_definition = (
            str(live_condition_type),
            str(live_condition_trigger),
            int(live_condition_target),
            str(live_route_mode),
            (
                None
                if live_route_target is None
                else int(live_route_target)
            ),
            bool(live_require_unique)
        )

        if current_definition != frozen_definition:
            raise ValueError(
                "Suppressed Dink evidence cannot be replayed "
                "because the tile changed after the event was "
                "received."
            )

        amount = int(amount)

        if amount < 1:
            raise ValueError(
                "Suppressed Dink evidence has an invalid amount."
            )

        before = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        raw_progress = _add_tile_condition_progress(
            cursor=cursor,
            team_id=team_id,
            condition_id=condition_id,
            amount=amount
        )

        counted_amount = _calculate_counted_drop_amount(
            condition_type=condition_type_snapshot,
            amount=amount,
            condition_target=condition_target_snapshot,
            condition_progress_before=(
                raw_progress - amount
            ),
            route_state=before
        )

        after = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        progress_delta = round(
            max(
                0.0,
                after["progress_fraction"]
                - before["progress_fraction"]
            ),
            12
        )

        player_exists = False

        if player_id is not None:
            cursor.execute(
                '''
                SELECT player_id
                FROM players
                WHERE player_id = %s
                FOR UPDATE
                ''',
                (player_id,)
            )

            player_exists = (
                cursor.fetchone() is not None
            )

        (
            contribution,
            banked_after
        ) = _bank_partial_contribution(
            cursor=cursor,
            player_id=(
                player_id
                if player_exists
                else None
            ),
            team_id=team_id,
            tile_id=tile_id,
            requested_contribution=progress_delta
        )

        completed = False

        if after["ready"]:
            completed = (
                _complete_tile_with_contributions(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id
                )
            )

        cursor.execute(
            '''
            UPDATE dink_event_progress
            SET
                counted_amount = %s,
                raw_progress = %s,
                route_progress = %s,
                credited = %s,
                banked_total = %s,
                ready = %s,
                completed = %s,
                state = 'APPLIED'
            WHERE progress_id = %s
            ''',
            (
                counted_amount,
                raw_progress,
                after["progress_fraction"],
                contribution,
                banked_after,
                after["ready"],
                completed,
                progress_id
            )
        )

        replayed_progress.append(
            {
                "event_id": int(event_id),
                "progress_id": int(progress_id),
                "team_id": int(team_id),
                "tile_id": int(tile_id),
                "counted_amount": int(counted_amount),
                "credited": round(
                    float(contribution),
                    12
                ),
                "completed": completed
            }
        )

    return replayed_progress


def _invalidate_incomplete_manual_evidence(
    cursor,
    evidence_id,
    reason_code,
    review_source,
    reviewer_id,
    reviewer_name,
    details=None
):
    cursor.execute(
        '''
        SELECT
            player_id,
            team_id,
            tile_id,
            condition_id,
            status
        FROM manual_evidence
        WHERE evidence_id = %s
        FOR UPDATE
        ''',
        (evidence_id,)
    )

    evidence = cursor.fetchone()

    if evidence is None:
        raise ValueError(
            f"Manual evidence {evidence_id} was not found."
        )

    (
        player_id,
        team_id,
        tile_id,
        condition_id,
        evidence_status
    ) = evidence

    if evidence_status != "ACCEPTED":
        raise ValueError(
            "Only accepted manual evidence can be invalidated."
        )

    if team_id is None:
        raise ValueError(
            "Manual evidence without a frozen team cannot be "
            "safely invalidated."
        )

    if tile_id is None or condition_id is None:
        raise ValueError(
            "Manual evidence without its original tile and "
            "condition cannot be safely invalidated."
        )

    cursor.execute(
        '''
        SELECT
            condition_id,
            tile_id,
            amount,
            actual_contribution,
            completion_remainder,
            lost_mvp_contribution,
            completed
        FROM manual_evidence_progress
        WHERE evidence_id = %s
        FOR UPDATE
        ''',
        (evidence_id,)
    )

    progress = cursor.fetchone()

    if progress is None:
        raise ValueError(
            "This manual evidence has no stored bingo progress."
        )

    (
        progress_condition_id,
        progress_tile_id,
        amount,
        actual_contribution,
        completion_remainder,
        lost_mvp_contribution,
        completed
    ) = progress

    if (
        progress_condition_id is None
        or progress_tile_id is None
        or int(progress_condition_id) != int(condition_id)
        or int(progress_tile_id) != int(tile_id)
    ):
        raise ValueError(
            "The stored manual evidence progress no longer "
            "matches its original tile and condition."
        )

    compatibility = _check_manual_evidence_live_compatibility(
        cursor=cursor,
        evidence_id=evidence_id,
        tile_id=tile_id
    )

    if not compatibility["compatible"]:
        raise ValueError(
            "Accepted manual evidence cannot be invalidated "
            "because the tile changed after submission: "
            f"{compatibility['reason']}."
        )

    completed = bool(completed)

    if (
        not completed
        and abs(float(completion_remainder or 0)) > 0.000000001
    ):
        raise ValueError(
            "Incomplete manual evidence has an unexpected "
            "completion remainder."
        )

    if abs(float(lost_mvp_contribution or 0)) > 0.000000001:
        raise ValueError(
            "Manual evidence with lost-MVP contribution cannot "
            "yet be safely invalidated."
        )

    cursor.execute(
        '''
        SELECT 1
        FROM player_tile_credits
        WHERE evidence_id = %s
          AND credit_type = 'LATE_REVIEW'
        LIMIT 1
        ''',
        (evidence_id,)
    )

    if cursor.fetchone() is not None:
        raise ValueError(
            "Manual evidence with discretionary late-review "
            "credit cannot yet be safely invalidated."
        )

    cursor.execute(
        '''
        SELECT completed_at
        FROM completed_tiles
        WHERE team_id = %s
          AND tile_id = %s
        ''',
        (
            team_id,
            tile_id
        )
    )

    completion_row = cursor.fetchone()

    tile_is_completed = (
        completion_row is not None
    )

    completed_at = (
        None
        if completion_row is None
        else completion_row[0]
    )

    if completed and not tile_is_completed:
        raise ValueError(
            "The manual evidence is recorded as a tile "
            "completion, but the completed tile record is "
            "missing."
        )

    if not completed and tile_is_completed:
        raise ValueError(
            "Manual evidence that did not itself complete the "
            "tile requires later-evidence reconciliation before "
            "it can be safely invalidated."
        )

    reopened_tiles = []

    if completed:
        reopened = _reverse_completed_tile_for_invalidation(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id
        )

        if not reopened:
            raise ValueError(
                "The completed tile could not be reversed."
            )

        reopened_tiles.append(
            {
                "team_id": int(team_id),
                "tile_id": int(tile_id)
            }
        )

    cursor.execute(
        '''
        SELECT progress
        FROM tile_condition_progress
        WHERE team_id = %s
          AND condition_id = %s
        FOR UPDATE
        ''',
        (
            team_id,
            condition_id
        )
    )

    condition_row = cursor.fetchone()

    if condition_row is None:
        raise ValueError(
            "The invalidated manual condition progress could "
            "not be found."
        )

    remaining_condition_progress = (
        int(condition_row[0])
        - int(amount)
    )

    if remaining_condition_progress < 0:
        raise ValueError(
            "The invalidated manual evidence amount exceeds "
            "the stored condition progress."
        )

    actual_contribution = round(
        float(actual_contribution or 0),
        12
    )

    partial_completion_pk = None
    remaining_partial_completion = None

    if actual_contribution > 0:
        cursor.execute(
            '''
            SELECT
                partial_completion_pk,
                partial_completion
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
              AND player_id IS NOT DISTINCT FROM %s
            FOR UPDATE
            ''',
            (
                team_id,
                tile_id,
                player_id
            )
        )

        partial_row = cursor.fetchone()

        if partial_row is None:
            raise ValueError(
                "The invalidated manual contribution could not "
                "be found in the tile contribution bank."
            )

        (
            partial_completion_pk,
            partial_completion
        ) = partial_row

        remaining_partial_completion = round(
            float(partial_completion)
            - actual_contribution,
            12
        )

        if remaining_partial_completion < -0.000000001:
            raise ValueError(
                "The invalidated manual contribution exceeds "
                "the stored tile contribution."
            )

    invalidation_id = _record_evidence_invalidation(
        cursor=cursor,
        subject_type="MANUAL_EVIDENCE",
        subject_id=evidence_id,
        reason_code=reason_code,
        review_source=review_source,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer_name,
        details=details
    )

    if actual_contribution > 0:
        if remaining_partial_completion <= 0:
            cursor.execute(
                '''
                DELETE FROM partial_completions
                WHERE partial_completion_pk = %s
                ''',
                (partial_completion_pk,)
            )
        else:
            cursor.execute(
                '''
                UPDATE partial_completions
                SET partial_completion = %s
                WHERE partial_completion_pk = %s
                ''',
                (
                    remaining_partial_completion,
                    partial_completion_pk
                )
            )

    cursor.execute(
        '''
        UPDATE tile_condition_progress
        SET progress = %s
        WHERE team_id = %s
          AND condition_id = %s
        ''',
        (
            remaining_condition_progress,
            team_id,
            condition_id
        )
    )

    replayed_manual_evidence = []

    if completed_at is not None:
        replayed_manual_evidence.extend(
            _replay_late_manual_evidence_after_invalidation(
                cursor=cursor,
                team_id=team_id,
                tile_id=tile_id,
                completed_at=completed_at
            )
        )

    final_reopened_tiles = []

    for reopened_tile in reopened_tiles:
        cursor.execute(
            '''
            SELECT 1
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                reopened_tile["team_id"],
                reopened_tile["tile_id"]
            )
        )

        # Only report the tile as reopened if it is still open
        # after all accepted manual evidence has been replayed.
        if cursor.fetchone() is None:
            final_reopened_tiles.append(
                reopened_tile
            )

    return {
        "invalidation_id": invalidation_id,
        "reopened_tiles": final_reopened_tiles,
        "replayed_manual_evidence":
            replayed_manual_evidence
    }


def invalidate_bingo_evidence(
    subject_type,
    subject_id,
    reason_code,
    review_source,
    reviewer_id,
    reviewer_name,
    details=None
):
    subject_type = str(
        subject_type
    ).strip().upper()

    if subject_type not in {
        "DINK_EVENT",
        "MANUAL_EVIDENCE"
    }:
        raise ValueError(
            "Unsupported evidence subject type."
        )

    subject_id = int(subject_id)

    with connect() as conn:
        cursor = conn.cursor()

        if subject_type == "MANUAL_EVIDENCE":
            manual_result = (
                _invalidate_incomplete_manual_evidence(
                    cursor=cursor,
                    evidence_id=subject_id,
                    reason_code=reason_code,
                    review_source=review_source,
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    details=details
                )
            )

            conn.commit()

            return {
                "status": "INVALIDATED",
                "invalidation_id": (
                    manual_result["invalidation_id"]
                ),
                "reopened_tiles": (
                    manual_result["reopened_tiles"]
                ),
                "replayed_manual_evidence": (
                    manual_result["replayed_manual_evidence"]
                )
            }

        cursor.execute(
            '''
            SELECT
                player_id,
                status,
                duplicate_of_event_id
            FROM dink_events
            WHERE event_id = %s
            FOR UPDATE
            ''',
            (subject_id,)
        )

        event = cursor.fetchone()

        if event is None:
            raise ValueError(
                f"Dink event {subject_id} was not found."
            )

        (
            player_id,
            event_status,
            duplicate_of_event_id
        ) = event

        if duplicate_of_event_id is not None:
            raise ValueError(
                "Duplicate Dink events do not contain "
                "independent bingo progress."
            )

        if event_status != "PROCESSED":
            raise ValueError(
                "Only processed Dink evidence can be "
                "invalidated."
            )

        if player_id is None:
            raise ValueError(
                "Processed Dink evidence has no linked player."
            )

        cursor.execute(
            '''
            SELECT
                progress_id,
                team_id,
                condition_id,
                tile_id,
                amount,
                credited,
                completed,
                state
            FROM dink_event_progress
            WHERE event_id = %s
            ORDER BY progress_id
            FOR UPDATE
            ''',
            (subject_id,)
        )

        progress_rows = cursor.fetchall()

        if not progress_rows:
            raise ValueError(
                "This Dink event has no stored bingo progress."
            )

        affected_tiles = {}
        condition_amounts = {}

        for (
            _,
            team_id,
            condition_id,
            tile_id,
            amount,
            credited,
            completed,
            progress_state
        ) in progress_rows:
            if team_id is None:
                raise ValueError(
                    "Historical Dink progress without a frozen "
                    "team cannot be safely invalidated."
                )

            progress_state = str(
                progress_state
            ).strip().upper()

            if progress_state == "INVALIDATED":
                raise ValueError(
                    "This Dink progress has already been "
                    "invalidated."
                )

            # Suppressed evidence was retained for possible future
            # replay, but it never altered live progress, contribution
            # banking or completion state. There is therefore nothing
            # to reverse for that row.
            if progress_state == "SUPPRESSED_COMPLETED":
                continue

            if progress_state != "APPLIED":
                raise ValueError(
                    "This Dink progress has an unsupported "
                    f"lifecycle state: {progress_state}."
                )

            tile_key = (
                int(team_id),
                int(tile_id)
            )

            if tile_key not in affected_tiles:
                affected_tiles[tile_key] = {
                    "credited": 0.0,
                    "completed_by_event": False
                }

            affected_tiles[tile_key]["credited"] = round(
                affected_tiles[tile_key]["credited"]
                + float(credited or 0),
                12
            )

            if completed:
                affected_tiles[
                    tile_key
                ]["completed_by_event"] = True

            condition_key = (
                int(team_id),
                int(condition_id)
            )

            condition_amounts[condition_key] = (
                condition_amounts.get(
                    condition_key,
                    0
                )
                + int(amount)
            )

        # This first implementation only reverses a completion when
        # this Dink event was itself the finisher. If an earlier source
        # is being invalidated after some later source completed the
        # tile, the later evidence must be replayed instead.
        for (
            team_id,
            tile_id
        ), tile_state in affected_tiles.items():
            cursor.execute(
                '''
                SELECT completed_at
                FROM completed_tiles
                WHERE team_id = %s
                  AND tile_id = %s
                ''',
                (
                    team_id,
                    tile_id
                )
            )

            completion_row = cursor.fetchone()

            tile_state["completed_at"] = (
                None
                if completion_row is None
                else completion_row[0]
            )

            if (
                completion_row is not None
                and not tile_state[
                    "completed_by_event"
                ]
            ):
                raise ValueError(
                    "This invalidation requires later evidence "
                    "to be replayed before it can be applied "
                    "safely."
                )

        invalidation_id = (
            _record_evidence_invalidation(
                cursor=cursor,
                subject_type=subject_type,
                subject_id=subject_id,
                reason_code=reason_code,
                review_source=review_source,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                details=details
            )
        )

        reopened_tiles = []

        for (
            team_id,
            tile_id
        ), tile_state in affected_tiles.items():
            reopened = (
                _reverse_completed_tile_for_invalidation(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id
                )
            )

            if reopened:
                reopened_tiles.append(
                    {
                        "team_id": team_id,
                        "tile_id": tile_id
                    }
                )

            credited = tile_state["credited"]

            if credited <= 0:
                continue

            cursor.execute(
                '''
                SELECT
                    partial_completion_pk,
                    partial_completion
                FROM partial_completions
                WHERE team_id = %s
                  AND tile_id = %s
                  AND player_id = %s
                FOR UPDATE
                ''',
                (
                    team_id,
                    tile_id,
                    player_id
                )
            )

            partial_row = cursor.fetchone()

            if partial_row is None:
                raise ValueError(
                    "The invalidated Dink contribution could "
                    "not be found in the tile contribution bank."
                )

            (
                partial_completion_pk,
                partial_completion
            ) = partial_row

            remaining = round(
                float(partial_completion)
                - credited,
                12
            )

            if remaining < -0.000000001:
                raise ValueError(
                    "The invalidated Dink contribution exceeds "
                    "the stored tile contribution."
                )

            if remaining <= 0:
                cursor.execute(
                    '''
                    DELETE FROM partial_completions
                    WHERE partial_completion_pk = %s
                    ''',
                    (partial_completion_pk,)
                )
            else:
                cursor.execute(
                    '''
                    UPDATE partial_completions
                    SET partial_completion = %s
                    WHERE partial_completion_pk = %s
                    ''',
                    (
                        remaining,
                        partial_completion_pk
                    )
                )

        for (
            team_id,
            condition_id
        ), amount in condition_amounts.items():
            cursor.execute(
                '''
                SELECT progress
                FROM tile_condition_progress
                WHERE team_id = %s
                  AND condition_id = %s
                FOR UPDATE
                ''',
                (
                    team_id,
                    condition_id
                )
            )

            condition_row = cursor.fetchone()

            if condition_row is None:
                raise ValueError(
                    "The invalidated Dink condition progress "
                    "could not be found."
                )

            remaining = (
                int(condition_row[0])
                - int(amount)
            )

            if remaining < 0:
                raise ValueError(
                    "The invalidated Dink amount exceeds the "
                    "stored condition progress."
                )

            cursor.execute(
                '''
                UPDATE tile_condition_progress
                SET progress = %s
                WHERE team_id = %s
                  AND condition_id = %s
                ''',
                (
                    remaining,
                    team_id,
                    condition_id
                )
            )

        cursor.execute(
            '''
            UPDATE dink_event_progress
            SET state = 'INVALIDATED'
            WHERE event_id = %s
            ''',
            (subject_id,)
        )

        replayed_manual_evidence = []

        for (
            team_id,
            tile_id
        ), tile_state in affected_tiles.items():
            completed_at = tile_state.get(
                "completed_at"
            )

            if completed_at is None:
                continue

            replayed_manual_evidence.extend(
                _replay_late_manual_evidence_after_invalidation(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id,
                    completed_at=completed_at
                )
            )

        replayed_dink_progress = []

        for (
            team_id,
            tile_id
        ), tile_state in affected_tiles.items():
            completed_at = tile_state.get(
                "completed_at"
            )

            if completed_at is None:
                continue

            replayed_dink_progress.extend(
                _replay_suppressed_dink_progress_after_invalidation(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id,
                    completed_at=completed_at
                )
            )

        final_reopened_tiles = []

        for reopened_tile in reopened_tiles:
            cursor.execute(
                '''
                SELECT 1
                FROM completed_tiles
                WHERE team_id = %s
                  AND tile_id = %s
                ''',
                (
                    reopened_tile["team_id"],
                    reopened_tile["tile_id"]
                )
            )

            # A tile should only be reported as reopened if it is
            # still open after all reconciliation/replay has finished.
            if cursor.fetchone() is None:
                final_reopened_tiles.append(
                    reopened_tile
                )

        reopened_tiles = final_reopened_tiles

        conn.commit()

    return {
        "status": "INVALIDATED",
        "invalidation_id": invalidation_id,
        "reopened_tiles": reopened_tiles,
        "replayed_manual_evidence":
            replayed_manual_evidence
    }


def add_manual_evidence(
    player_id,
    condition_id,
    amount,
    evidence_path,
    evidence_sha256,
    submission_source,
    submitter_id,
    submitter_name,
    description=None,
    discord_guild_id=None,
    discord_channel_id=None,
    discord_message_id=None,
    evidence_author_id=None,
    evidence_author_name=None
):
    amount = int(amount)

    if amount < 1:
        raise ValueError(
            "Manual evidence amount must be greater than 0."
        )

    submission_source = str(
        submission_source
    ).strip().upper()

    if submission_source not in {
        "DISCORD",
        "WEB"
    }:
        raise ValueError(
            "Manual evidence submission source must be "
            "DISCORD or WEB."
        )

    if submitter_id is None:
        raise ValueError(
            "Manual evidence submitter ID is required."
        )

    submitter_name = str(
        submitter_name
    ).strip()

    if not submitter_name:
        raise ValueError(
            "Manual evidence submitter name is required."
        )

    evidence_path = str(
        evidence_path
    ).strip()

    if not evidence_path:
        raise ValueError(
            "Manual evidence path is required."
        )

    evidence_sha256 = str(
        evidence_sha256
    ).strip()

    if not evidence_sha256:
        raise ValueError(
            "Manual evidence hash is required."
        )

    if description is not None:
        description = str(
            description
        ).strip()

        if not description:
            description = None

    if evidence_author_name is not None:
        evidence_author_name = str(
            evidence_author_name
        ).strip()

        if not evidence_author_name:
            evidence_author_name = None

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT evidence_codeword
            FROM bingo_config
            WHERE config_id = 1
            FOR SHARE
            '''
        )

        codeword_row = cursor.fetchone()

        evidence_codeword_at_submission = (
            None
            if (
                codeword_row is None
                or codeword_row[0] is None
                or not str(codeword_row[0]).strip()
            )
            else str(codeword_row[0]).strip()
        )


        cursor.execute(
            '''
            SELECT
                team_id,
                player_name
            FROM players
            WHERE player_id = %s
            FOR UPDATE
            ''',
            (player_id,)
        )

        player = cursor.fetchone()

        if player is None:
            raise ValueError(
                f"Player {player_id} does not exist."
            )

        team_id = player[0]

        credited_player_name = str(
            player[1]
        ).strip()

        if team_id is None:
            raise ValueError(
                f"Player {player_id} is not on a team."
            )

        # First identify the tile, then lock it before reading
        # any progress used by the submission snapshot.
        cursor.execute(
            '''
            SELECT tile_id
            FROM tile_conditions
            WHERE condition_id = %s
            ''',
            (condition_id,)
        )

        condition_tile = cursor.fetchone()

        if condition_tile is None:
            raise ValueError(
                f"Condition {condition_id} does not exist."
            )

        tile_id = int(condition_tile[0])

        # Use the same tile-level serialisation as automatic
        # progress so the saved condition progress and banked
        # contribution represent one coherent moment.
        cursor.execute(
            '''
            SELECT
                tile_id,
                tile_name
            FROM tiles
            WHERE tile_id = %s
            FOR UPDATE
            ''',
            (tile_id,)
        )

        tile_row = cursor.fetchone()

        if tile_row is None:
            raise ValueError(
                f"Tile {tile_id} does not exist."
            )

        tile_name_at_submission = str(
            tile_row[1]
        )

        # Re-read the selected condition only after acquiring
        # the tile lock. The earlier lookup was solely to find
        # which tile needed locking.
        cursor.execute(
            '''
            SELECT
                c.tile_id,
                c.condition_type,
                c.completion_path,
                c.target,
                COALESCE(p.progress, 0)
            FROM tile_conditions c
            LEFT JOIN tile_condition_progress p
              ON p.condition_id = c.condition_id
             AND p.team_id = %s
            WHERE c.condition_id = %s
            ''',
            (
                team_id,
                condition_id
            )
        )

        condition = cursor.fetchone()

        if condition is None:
            raise ValueError(
                f"Condition {condition_id} does not exist."
            )

        tile_id = condition[0]

        condition_type = str(
            condition[1]
        ).strip().upper()

        completion_path = int(condition[2])
        condition_target = int(condition[3])
        condition_progress = int(condition[4])

        if condition_type in {
            "KILLCOUNT",
            "EXPERIENCE"
        }:
            raise ValueError(
                "Manual evidence cannot be submitted for "
                "KILLCOUNT or EXPERIENCE conditions."
            )

        cursor.execute(
            '''
            SELECT 1
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        if cursor.fetchone() is not None:
            raise ValueError(
                "Manual evidence cannot be submitted because "
                "this tile is already complete."
            )

        path_state = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        route_mode = path_state["route_mode"]

        if route_mode == "ALL":
            if condition_progress >= condition_target:
                raise ValueError(
                    "Manual evidence cannot be submitted because "
                    "this part of the tile is already complete."
                )

        elif route_mode == "SUM":
            if path_state["ready"]:
                raise ValueError(
                    "Manual evidence cannot be submitted because "
                    "this completion route is already complete."
                )

        elif route_mode == "N_OF":
            if path_state["ready"]:
                raise ValueError(
                    "Manual evidence cannot be submitted because "
                    "this completion route is already complete."
                )

            if (
                path_state.get("require_unique", False)
                and condition_progress > 0
            ):
                raise ValueError(
                    "Manual evidence cannot be submitted because "
                    "this unique part of the tile has already "
                    "contributed."
                )

        cursor.execute(
            '''
            SELECT tile_points
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        tile = cursor.fetchone()

        if tile is None:
            raise ValueError(
                f"Tile {tile_id} does not exist."
            )

        if tile[0] is None:
            raise ValueError(
                f"Tile {tile_id} has no point value."
            )

        tile_points_at_submission = float(tile[0])

        cursor.execute(
            '''
            SELECT COALESCE(
                SUM(partial_completion),
                0
            )
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        banked_total_at_submission = round(
            float(cursor.fetchone()[0]),
            12
        )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence
            WHERE team_id = %s
              AND tile_id = %s
              AND status = 'PENDING'
            ''',
            (
                team_id,
                tile_id
            )
        )

        earlier_pending_evidence_count = int(
            cursor.fetchone()[0]
        )

        has_earlier_pending_evidence = (
            earlier_pending_evidence_count > 0
        )

        if has_earlier_pending_evidence:
            pending_warning = (
                "Another submission for this tile is already "
                "waiting for review. If that earlier submission "
                "is accepted, it may reduce or remove the MVP "
                "points available for this submission. This will "
                "not affect the team's tile points."
            )
        else:
            pending_warning = None

        cursor.execute(
            '''
            INSERT INTO manual_evidence (
                player_id,
                credited_player_name,
                team_id,
                tile_id,
                condition_id,
                amount,
                tile_points_at_submission,
                banked_total_at_submission,
                tile_name_at_submission,
                evidence_codeword_at_submission,
                description,
                evidence_path,
                evidence_sha256,
                submission_source,
                submitter_id,
                submitter_name,
                discord_guild_id,
                discord_channel_id,
                discord_message_id,
                evidence_author_id,
                evidence_author_name,
                submitted_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                clock_timestamp()
            )
            RETURNING evidence_id
            ''',
            (
                player_id,
                credited_player_name,
                team_id,
                tile_id,
                condition_id,
                amount,
                tile_points_at_submission,
                banked_total_at_submission,
                tile_name_at_submission,
                evidence_codeword_at_submission,
                description,
                evidence_path,
                evidence_sha256,
                submission_source,
                submitter_id,
                submitter_name,
                discord_guild_id,
                discord_channel_id,
                discord_message_id,
                evidence_author_id,
                evidence_author_name
            )
        )

        evidence_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO manual_evidence_path_snapshots (
                evidence_id,
                completion_path,
                route_mode,
                route_target,
                require_unique
            )
            SELECT
                %s,
                completion_path,
                route_mode,
                route_target,
                require_unique
            FROM tile_completion_paths
            WHERE tile_id = %s
            ORDER BY completion_path
            ''',
            (
                evidence_id,
                tile_id
            )
        )

        if cursor.rowcount < 1:
            raise ValueError(
                f"Tile {tile_id} has no completion paths."
            )

        cursor.execute(
            '''
            INSERT INTO manual_evidence_condition_snapshots (
                evidence_id,
                condition_id,
                completion_path,
                condition_type,
                condition_trigger,
                target,
                progress,
                selected_condition
            )
            SELECT
                %s,
                c.condition_id,
                c.completion_path,
                c.condition_type,
                c.condition_trigger,
                c.target,
                COALESCE(p.progress, 0),
                c.condition_id = %s
            FROM tile_conditions c
            LEFT JOIN tile_condition_progress p
              ON p.condition_id = c.condition_id
             AND p.team_id = %s
            WHERE c.tile_id = %s
            ORDER BY
                c.completion_path,
                c.condition_id
            ''',
            (
                evidence_id,
                condition_id,
                team_id,
                tile_id
            )
        )

        if cursor.rowcount < 1:
            raise ValueError(
                f"Tile {tile_id} has no conditions."
            )

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM manual_evidence_condition_snapshots
            WHERE evidence_id = %s
              AND selected_condition = TRUE
            ''',
            (evidence_id,)
        )

        selected_count = cursor.fetchone()[0]

        if selected_count != 1:
            raise ValueError(
                "Manual evidence snapshot must contain "
                "exactly one selected condition."
            )

        conn.commit()

    return {
        "evidence_id": evidence_id,
        "status": "PENDING",
        "player_id": player_id,
        "team_id": team_id,
        "tile_id": tile_id,
        "condition_id": condition_id,
        "amount": amount,
        "tile_points_at_submission":
            tile_points_at_submission,
        "banked_total_at_submission":
            banked_total_at_submission,
        "has_earlier_pending_evidence":
            has_earlier_pending_evidence,
        "earlier_pending_evidence_count":
            earlier_pending_evidence_count,
        "pending_warning": pending_warning
    }


def _evaluate_manual_evidence_snapshot_route(
    cursor,
    evidence_id,
    amount,
    progress_adjustments=None
):
    amount = int(amount)

    if amount < 1:
        raise ValueError(
            "Manual evidence amount must be greater than 0."
        )

    cursor.execute(
        '''
        SELECT
            condition_id,
            completion_path
        FROM manual_evidence_condition_snapshots
        WHERE evidence_id = %s
          AND selected_condition = TRUE
        ''',
        (evidence_id,)
    )

    selected_condition = cursor.fetchone()

    if selected_condition is None:
        raise ValueError(
            "Manual evidence condition snapshot is missing."
        )

    condition_id = int(selected_condition[0])
    completion_path = int(selected_condition[1])

    cursor.execute(
        '''
        SELECT
            route_mode,
            route_target,
            require_unique
        FROM manual_evidence_path_snapshots
        WHERE evidence_id = %s
          AND completion_path = %s
        ''',
        (
            evidence_id,
            completion_path
        )
    )

    path = cursor.fetchone()

    if path is None:
        raise ValueError(
            "Manual evidence path snapshot is missing."
        )

    route_mode = str(path[0])
    route_target = (
        None
        if path[1] is None
        else int(path[1])
    )
    require_unique = bool(path[2])

    cursor.execute(
        '''
        SELECT
            condition_id,
            target,
            progress
        FROM manual_evidence_condition_snapshots
        WHERE evidence_id = %s
          AND completion_path = %s
        ORDER BY condition_id
        ''',
        (
            evidence_id,
            completion_path
        )
    )

    condition_rows = cursor.fetchall()

    if not condition_rows:
        raise ValueError(
            "Manual evidence path snapshot has no conditions."
        )

    targets = {}
    progress = {}

    for (
        snapshot_condition_id,
        target,
        saved_progress
    ) in condition_rows:
        snapshot_condition_id = int(
            snapshot_condition_id
        )

        targets[snapshot_condition_id] = int(target)
        progress[snapshot_condition_id] = int(
            saved_progress
        )

    if condition_id not in progress:
        raise ValueError(
            "Selected manual evidence condition is not in "
            "its saved completion path."
        )

    # Earlier manual submissions can be replayed here before
    # evaluating this submission. Adjustments for conditions on
    # other completion paths do not affect this route.
    if progress_adjustments is not None:
        for (
            adjusted_condition_id,
            adjustment
        ) in progress_adjustments.items():
            adjusted_condition_id = int(
                adjusted_condition_id
            )
            adjustment = int(adjustment)

            if adjustment < 0:
                raise ValueError(
                    "Snapshot progress adjustment cannot "
                    "be negative."
                )

            if adjusted_condition_id not in progress:
                continue

            progress[adjusted_condition_id] += adjustment

    def evaluate_route(progress_values):
        if route_mode == "ALL":
            completed_conditions = sum(
                1
                for snapshot_condition_id in progress_values
                if (
                    progress_values[snapshot_condition_id]
                    >= targets[snapshot_condition_id]
                )
            )

            progress_fraction = sum(
                min(
                    progress_values[snapshot_condition_id]
                    / targets[snapshot_condition_id],
                    1.0
                )
                for snapshot_condition_id in progress_values
            ) / len(progress_values)

            return {
                "current": completed_conditions,
                "target": len(progress_values),
                "progress_fraction": round(
                    progress_fraction,
                    12
                ),
                "ready": (
                    completed_conditions
                    == len(progress_values)
                )
            }

        if route_mode == "SUM":
            current = sum(
                progress_values.values()
            )

            return {
                "current": current,
                "target": route_target,
                "progress_fraction": round(
                    min(
                        current / route_target,
                        1.0
                    ),
                    12
                ),
                "ready": current >= route_target
            }

        if route_mode == "N_OF":
            if require_unique:
                current = sum(
                    1
                    for value in progress_values.values()
                    if value > 0
                )
            else:
                current = sum(
                    progress_values.values()
                )

            return {
                "current": current,
                "target": route_target,
                "progress_fraction": round(
                    min(
                        current / route_target,
                        1.0
                    ),
                    12
                ),
                "ready": current >= route_target
            }

        raise ValueError(
            f"Unsupported snapshot route mode: "
            f"{route_mode}"
        )

    before = evaluate_route(progress)

    progress[condition_id] += amount

    after = evaluate_route(progress)

    route_contribution = round(
        max(
            0.0,
            after["progress_fraction"]
            - before["progress_fraction"]
        ),
        12
    )

    return {
        "condition_id": condition_id,
        "completion_path": completion_path,
        "route_mode": route_mode,
        "route_target": route_target,
        "require_unique": require_unique,
        "amount": amount,
        "raw_progress": progress[condition_id],
        "before": before,
        "after": after,
        "route_contribution": route_contribution
    }


def _calculate_manual_evidence_potential_contribution(
    cursor,
    evidence_id
):
    cursor.execute(
        '''
        SELECT
            team_id,
            tile_id,
            amount,
            submitted_at,
            banked_total_at_submission
        FROM manual_evidence
        WHERE evidence_id = %s
        ''',
        (evidence_id,)
    )

    evidence = cursor.fetchone()

    if evidence is None:
        raise ValueError(
            f"Manual evidence {evidence_id} does not exist."
        )

    (
        team_id,
        tile_id,
        amount,
        submitted_at,
        banked_total_at_submission
    ) = evidence

    if team_id is None or tile_id is None:
        return {
            "available": False,
            "reason": "MISSING_FROZEN_CONTEXT",
            "message": (
                "The original team or tile for this submission "
                "no longer exists, so its potential contribution "
                "cannot be calculated reliably."
            )
        }

    if banked_total_at_submission is None:
        return {
            "available": False,
            "reason": "UNKNOWN_BANKED_TOTAL",
            "message": (
                "This submission predates banked-contribution "
                "snapshots, so its potential contribution cannot "
                "be reconstructed reliably."
            )
        }

    banked_total_at_submission = round(
        float(banked_total_at_submission),
        12
    )

    # Find earlier submissions for the same team/tile which
    # were still unresolved when this submission took its
    # snapshot, but were later accepted.
    #
    # If an earlier submission had already been accepted before
    # this one was submitted, its progress and contribution are
    # already represented in this submission's frozen state and
    # must not be replayed.
    cursor.execute(
        '''
        SELECT
            earlier.evidence_id,
            earlier.amount,
            selected.condition_id,
            progress.potential_contribution
        FROM manual_evidence AS earlier
        JOIN staff_review_decisions AS decision
          ON decision.subject_type = 'MANUAL_EVIDENCE'
         AND decision.subject_id = earlier.evidence_id
         AND decision.decision = 'ACCEPT'
        JOIN manual_evidence_progress AS progress
          ON progress.evidence_id = earlier.evidence_id
        JOIN manual_evidence_condition_snapshots AS selected
          ON selected.evidence_id = earlier.evidence_id
         AND selected.selected_condition = TRUE
        WHERE earlier.team_id = %s
          AND earlier.tile_id = %s
          AND earlier.status = 'ACCEPTED'
          AND (
                earlier.submitted_at < %s
                OR (
                    earlier.submitted_at = %s
                    AND earlier.evidence_id < %s
                )
              )
          AND decision.decided_at > %s
        ORDER BY
            earlier.submitted_at,
            earlier.evidence_id
        ''',
        (
            team_id,
            tile_id,
            submitted_at,
            submitted_at,
            evidence_id,
            submitted_at
        )
    )

    earlier_rows = cursor.fetchall()

    progress_adjustments = {}
    replayed_evidence_ids = []
    replayed_potential_contribution = 0.0

    for (
        earlier_evidence_id,
        earlier_amount,
        earlier_condition_id,
        earlier_potential_contribution
    ) in earlier_rows:
        earlier_condition_id = int(
            earlier_condition_id
        )

        progress_adjustments[
            earlier_condition_id
        ] = (
            progress_adjustments.get(
                earlier_condition_id,
                0
            )
            + int(earlier_amount)
        )

        replayed_evidence_ids.append(
            int(earlier_evidence_id)
        )

        replayed_potential_contribution = round(
            replayed_potential_contribution
            + float(earlier_potential_contribution),
            12
        )

    snapshot_result = (
        _evaluate_manual_evidence_snapshot_route(
            cursor=cursor,
            evidence_id=evidence_id,
            amount=amount,
            progress_adjustments=progress_adjustments
        )
    )

    hypothetical_banked_before = round(
        min(
            1.0,
            banked_total_at_submission
            + replayed_potential_contribution
        ),
        12
    )

    remaining_personal_share = round(
        max(
            0.0,
            1.0 - hypothetical_banked_before
        ),
        12
    )

    route_contribution = round(
        float(
            snapshot_result[
                "route_contribution"
            ]
        ),
        12
    )

    potential_contribution = round(
        min(
            route_contribution,
            remaining_personal_share
        ),
        12
    )

    return {
        "available": True,
        "evidence_id": int(evidence_id),
        "banked_total_at_submission":
            banked_total_at_submission,
        "replayed_evidence_ids":
            replayed_evidence_ids,
        "replayed_potential_contribution":
            replayed_potential_contribution,
        "progress_adjustments":
            progress_adjustments,
        "hypothetical_banked_before":
            hypothetical_banked_before,
        "remaining_personal_share":
            remaining_personal_share,
        "route_contribution":
            route_contribution,
        "potential_contribution":
            potential_contribution,
        "snapshot_route":
            snapshot_result
    }


def _check_manual_evidence_live_compatibility(
    cursor,
    evidence_id,
    tile_id
):
    cursor.execute(
        '''
        SELECT
            condition_id,
            completion_path,
            condition_type,
            condition_trigger,
            target
        FROM manual_evidence_condition_snapshots
        WHERE evidence_id = %s
          AND selected_condition = TRUE
        ''',
        (evidence_id,)
    )

    snapshot_condition = cursor.fetchone()

    if snapshot_condition is None:
        return {
            "compatible": False,
            "reason": "MISSING_CONDITION_SNAPSHOT",
            "message": (
                "The saved tile details for this submission "
                "are incomplete, so it cannot be accepted "
                "normally."
            )
        }

    (
        condition_id,
        completion_path,
        condition_type,
        condition_trigger,
        condition_target
    ) = snapshot_condition

    cursor.execute(
        '''
        SELECT
            tile_id,
            completion_path,
            condition_type,
            condition_trigger,
            target
        FROM tile_conditions
        WHERE condition_id = %s
        ''',
        (condition_id,)
    )

    live_condition = cursor.fetchone()

    if live_condition is None:
        return {
            "compatible": False,
            "reason": "CONDITION_DELETED",
            "message": (
                "This tile changed after the submission was "
                "made. The selected part no longer exists, "
                "so it cannot be accepted normally."
            )
        }

    (
        live_tile_id,
        live_completion_path,
        live_condition_type,
        live_condition_trigger,
        live_condition_target
    ) = live_condition

    snapshot_condition_definition = (
        int(tile_id),
        int(completion_path),
        str(condition_type),
        condition_trigger,
        int(condition_target)
    )

    live_condition_definition = (
        int(live_tile_id),
        int(live_completion_path),
        str(live_condition_type),
        live_condition_trigger,
        int(live_condition_target)
    )

    if (
        live_condition_definition
        != snapshot_condition_definition
    ):
        return {
            "compatible": False,
            "reason": "CONDITION_CHANGED",
            "message": (
                "This tile changed after the submission was "
                "made. The selected part is no longer the "
                "same, so it cannot be accepted normally."
            )
        }

    cursor.execute(
        '''
        SELECT
            route_mode,
            route_target,
            require_unique
        FROM manual_evidence_path_snapshots
        WHERE evidence_id = %s
          AND completion_path = %s
        ''',
        (
            evidence_id,
            completion_path
        )
    )

    snapshot_path = cursor.fetchone()

    if snapshot_path is None:
        return {
            "compatible": False,
            "reason": "MISSING_PATH_SNAPSHOT",
            "message": (
                "The saved tile details for this submission "
                "are incomplete, so it cannot be accepted "
                "normally."
            )
        }

    cursor.execute(
        '''
        SELECT
            route_mode,
            route_target,
            require_unique
        FROM tile_completion_paths
        WHERE tile_id = %s
          AND completion_path = %s
        ''',
        (
            tile_id,
            completion_path
        )
    )

    live_path = cursor.fetchone()

    if live_path is None:
        return {
            "compatible": False,
            "reason": "PATH_DELETED",
            "message": (
                "This tile changed after the submission was "
                "made. Its completion route no longer exists, "
                "so it cannot be accepted normally."
            )
        }

    snapshot_path_definition = (
        str(snapshot_path[0]),
        (
            None
            if snapshot_path[1] is None
            else int(snapshot_path[1])
        ),
        bool(snapshot_path[2])
    )

    live_path_definition = (
        str(live_path[0]),
        (
            None
            if live_path[1] is None
            else int(live_path[1])
        ),
        bool(live_path[2])
    )

    if live_path_definition != snapshot_path_definition:
        return {
            "compatible": False,
            "reason": "PATH_CHANGED",
            "message": (
                "This tile changed after the submission was "
                "made. Its completion route is no longer the "
                "same, so it cannot be accepted normally."
            )
        }

    return {
        "compatible": True,
        "condition_id": int(condition_id),
        "completion_path": int(completion_path),
        "condition_type": str(condition_type),
        "condition_trigger": condition_trigger,
        "target": int(condition_target),
        "route_mode": str(snapshot_path[0]),
        "route_target": (
            None
            if snapshot_path[1] is None
            else int(snapshot_path[1])
        ),
        "require_unique": bool(snapshot_path[2])
    }


def _get_earlier_pending_manual_evidence(
    cursor,
    evidence_id,
    team_id,
    tile_id,
    submitted_at,
    for_update=True
):
    query = '''
        SELECT evidence_id
        FROM manual_evidence
        WHERE team_id = %s
          AND tile_id = %s
          AND status = 'PENDING'
          AND (
              submitted_at < %s
              OR (
                  submitted_at = %s
                  AND evidence_id < %s
              )
          )
        ORDER BY
            submitted_at,
            evidence_id
        LIMIT 1
    '''

    if for_update:
        query += ' FOR UPDATE'

    cursor.execute(
        query,
        (
            team_id,
            tile_id,
            submitted_at,
            submitted_at,
            evidence_id
        )
    )

    earlier_evidence = cursor.fetchone()

    if earlier_evidence is None:
        return None

    return int(earlier_evidence[0])


def _get_player_team_tile_personal_credit_total(
    cursor,
    player_id,
    team_id,
    tile_id
):
    if player_id is None:
        return 0.0

    cursor.execute(
        '''
        SELECT COALESCE(
            SUM(contribution),
            0
        )
        FROM player_tile_credits
        WHERE player_id = %s
          AND team_id = %s
          AND tile_id = %s
        ''',
        (
            player_id,
            team_id,
            tile_id
        )
    )

    finalised_credit = float(
        cursor.fetchone()[0]
    )

    cursor.execute(
        '''
        SELECT COALESCE(
            SUM(partial_completion),
            0
        )
        FROM partial_completions
        WHERE player_id = %s
          AND team_id = %s
          AND tile_id = %s
        ''',
        (
            player_id,
            team_id,
            tile_id
        )
    )

    banked_credit = float(
        cursor.fetchone()[0]
    )

    return round(
        min(
            1.0,
            finalised_credit + banked_credit
        ),
        12
    )



def get_manual_evidence_lost_mvp_preflight(evidence_id):
    """
    Return a read-only preview of whether accepting pending manual
    evidence could offer discretionary lost MVP credit.

    This preview does not lock or modify bingo state.
    accept_pending_manual_evidence() remains authoritative and
    re-checks the live state when the organiser makes a decision.
    """
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                team_id,
                tile_id,
                amount,
                tile_points_at_submission,
                status,
                submitted_at
            FROM manual_evidence
            WHERE evidence_id = %s
            ''',
            (evidence_id,)
        )

        evidence = cursor.fetchone()

        if evidence is None:
            return {
                "status": "EVIDENCE_NOT_FOUND",
                "lost_mvp_available": False
            }

        (
            player_id,
            team_id,
            tile_id,
            amount,
            tile_points_at_submission,
            status,
            submitted_at
        ) = evidence

        if status != "PENDING":
            return {
                "status": "INVALID_STATUS",
                "current_status": status,
                "lost_mvp_available": False
            }

        if team_id is None or tile_id is None:
            return {
                "status": "MISSING_FROZEN_CONTEXT",
                "lost_mvp_available": False
            }

        earlier_evidence_id = (
            _get_earlier_pending_manual_evidence(
                cursor=cursor,
                evidence_id=evidence_id,
                team_id=team_id,
                tile_id=tile_id,
                submitted_at=submitted_at,
                for_update=False
            )
        )

        if earlier_evidence_id is not None:
            return {
                "status": "EARLIER_PENDING_EVIDENCE",
                "earlier_evidence_id":
                    earlier_evidence_id,
                "lost_mvp_available": False
            }

        player_exists = False

        if player_id is not None:
            cursor.execute(
                '''
                SELECT 1
                FROM players
                WHERE player_id = %s
                ''',
                (player_id,)
            )

            player_exists = (
                cursor.fetchone() is not None
            )

        cursor.execute(
            '''
            SELECT 1
            FROM tiles
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        if cursor.fetchone() is None:
            return {
                "status": "TILE_NOT_FOUND",
                "lost_mvp_available": False
            }

        cursor.execute(
            '''
            SELECT completed_at
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        completed_tile = cursor.fetchone()

        completed_at = (
            None
            if completed_tile is None
            else completed_tile[0]
        )

        compatibility = (
            _check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        if not compatibility["compatible"]:
            return {
                "status": "TILE_CHANGED",
                "reason": compatibility["reason"],
                "message": compatibility["message"],
                "lost_mvp_available": False
            }

        potential = (
            _calculate_manual_evidence_potential_contribution(
                cursor=cursor,
                evidence_id=evidence_id
            )
        )

        if not potential["available"]:
            return {
                "status": "POTENTIAL_UNAVAILABLE",
                "reason": potential["reason"],
                "message": potential["message"],
                "lost_mvp_available": False
            }

        potential_contribution = round(
            float(
                potential["potential_contribution"]
            ),
            12
        )

        if completed_at is not None:
            if submitted_at > completed_at:
                return {
                    "status": "SUBMITTED_AFTER_COMPLETION",
                    "completed_at": completed_at,
                    "lost_mvp_available": False
                }

            lost_mvp_contribution = (
                potential_contribution
            )

            existing_personal_credit = 0.0
            remaining_personal_credit = 0.0

            if player_exists:
                existing_personal_credit = (
                    _get_player_team_tile_personal_credit_total(
                        cursor=cursor,
                        player_id=player_id,
                        team_id=team_id,
                        tile_id=tile_id
                    )
                )

                remaining_personal_credit = round(
                    max(
                        0.0,
                        1.0 - existing_personal_credit
                    ),
                    12
                )

            maximum_lost_mvp_contribution = round(
                min(
                    lost_mvp_contribution,
                    remaining_personal_credit
                ),
                12
            )

            if (
                not player_exists
                or maximum_lost_mvp_contribution <= 0
                or tile_points_at_submission is None
            ):
                return {
                    "status": "READY",
                    "lost_mvp_available": False,
                    "tile_already_completed": True,
                    "would_complete_tile": False,
                    "potential_contribution":
                        potential_contribution,
                    "predicted_actual_contribution": 0.0,
                    "lost_mvp_contribution":
                        lost_mvp_contribution,
                    "existing_personal_credit":
                        existing_personal_credit,
                    "remaining_personal_credit":
                        remaining_personal_credit,
                    "maximum_lost_mvp_contribution": 0.0,
                    "maximum_lost_mvp_points": 0.0
                }

            maximum_lost_mvp_points = round(
                maximum_lost_mvp_contribution
                * float(tile_points_at_submission),
                12
            )

            return {
                "status": "READY",
                "lost_mvp_available": True,
                "tile_already_completed": True,
                "would_complete_tile": False,
                "potential_contribution":
                    potential_contribution,
                "predicted_actual_contribution": 0.0,
                "lost_mvp_contribution":
                    lost_mvp_contribution,
                "existing_personal_credit":
                    existing_personal_credit,
                "remaining_personal_credit":
                    remaining_personal_credit,
                "maximum_lost_mvp_contribution":
                    maximum_lost_mvp_contribution,
                "maximum_lost_mvp_points":
                    maximum_lost_mvp_points
            }

        condition_id = int(
            compatibility["condition_id"]
        )

        completion_path = int(
            compatibility["completion_path"]
        )

        cursor.execute(
            '''
            SELECT
                c.condition_id,
                c.target,
                COALESCE(p.progress, 0)
            FROM tile_conditions c
            LEFT JOIN tile_condition_progress p
              ON p.condition_id = c.condition_id
             AND p.team_id = %s
            WHERE c.tile_id = %s
              AND c.completion_path = %s
            ORDER BY c.condition_id
            ''',
            (
                team_id,
                tile_id,
                completion_path
            )
        )

        conditions = cursor.fetchall()

        before = _evaluate_completion_path_conditions(
            route_mode=compatibility["route_mode"],
            route_target=compatibility["route_target"],
            require_unique=compatibility["require_unique"],
            conditions=conditions
        )

        hypothetical_conditions = []

        for (
            live_condition_id,
            target,
            progress
        ) in conditions:
            hypothetical_progress = int(progress)

            if int(live_condition_id) == condition_id:
                hypothetical_progress += int(amount)

            hypothetical_conditions.append(
                (
                    live_condition_id,
                    target,
                    hypothetical_progress
                )
            )

        after = _evaluate_completion_path_conditions(
            route_mode=compatibility["route_mode"],
            route_target=compatibility["route_target"],
            require_unique=compatibility["require_unique"],
            conditions=hypothetical_conditions
        )

        route_progress_delta = round(
            max(
                0.0,
                after["progress_fraction"]
                - before["progress_fraction"]
            ),
            12
        )

        cursor.execute(
            '''
            SELECT COALESCE(
                SUM(partial_completion),
                0
            )
            FROM partial_completions
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        banked_before = float(
            cursor.fetchone()[0]
        )

        remaining_team_contribution = round(
            max(
                0.0,
                1.0 - banked_before
            ),
            12
        )

        actual_contribution = round(
            min(
                remaining_team_contribution,
                route_progress_delta
            ),
            12
        )

        would_complete_tile = bool(
            after["ready"]
        )

        if would_complete_tile:
            lost_mvp_contribution = round(
                max(
                    0.0,
                    potential_contribution
                    - actual_contribution
                ),
                12
            )
        else:
            lost_mvp_contribution = 0.0

        existing_personal_credit = 0.0
        predicted_personal_credit = 0.0
        remaining_personal_credit = 0.0
        completion_remainder = 0.0

        if player_exists:
            existing_personal_credit = (
                _get_player_team_tile_personal_credit_total(
                    cursor=cursor,
                    player_id=player_id,
                    team_id=team_id,
                    tile_id=tile_id
                )
            )

            if would_complete_tile:
                banked_after = round(
                    min(
                        1.0,
                        banked_before
                        + actual_contribution
                    ),
                    12
                )

                completion_remainder = round(
                    max(
                        0.0,
                        1.0 - banked_after
                    ),
                    12
                )

                predicted_personal_credit = round(
                    min(
                        1.0,
                        existing_personal_credit
                        + actual_contribution
                        + completion_remainder
                    ),
                    12
                )
            else:
                predicted_personal_credit = round(
                    min(
                        1.0,
                        existing_personal_credit
                        + actual_contribution
                    ),
                    12
                )

            remaining_personal_credit = round(
                max(
                    0.0,
                    1.0 - predicted_personal_credit
                ),
                12
            )

        maximum_lost_mvp_contribution = round(
            min(
                lost_mvp_contribution,
                remaining_personal_credit
            ),
            12
        )

        lost_mvp_available = bool(
            would_complete_tile
            and player_exists
            and maximum_lost_mvp_contribution > 0
            and tile_points_at_submission is not None
        )

        maximum_lost_mvp_points = 0.0

        if lost_mvp_available:
            maximum_lost_mvp_points = round(
                maximum_lost_mvp_contribution
                * float(tile_points_at_submission),
                12
            )

        return {
            "status": "READY",
            "lost_mvp_available":
                lost_mvp_available,
            "tile_already_completed": False,
            "would_complete_tile":
                would_complete_tile,
            "potential_contribution":
                potential_contribution,
            "route_progress_delta":
                route_progress_delta,
            "predicted_actual_contribution":
                actual_contribution,
            "completion_remainder":
                completion_remainder,
            "lost_mvp_contribution":
                lost_mvp_contribution,
            "existing_personal_credit":
                existing_personal_credit,
            "predicted_personal_credit":
                predicted_personal_credit,
            "remaining_personal_credit":
                remaining_personal_credit,
            "maximum_lost_mvp_contribution":
                maximum_lost_mvp_contribution,
            "maximum_lost_mvp_points":
                maximum_lost_mvp_points
        }


def accept_pending_manual_evidence(
    evidence_id,
    review_source,
    reviewer_id,
    reviewer_name,
    award_lost_mvp=False
):
    with connect() as conn:
        cursor = conn.cursor()

        # Lock the submission itself first. This serialises two
        # staff members attempting to review the same evidence.
        cursor.execute(
            '''
            SELECT
                player_id,
                credited_player_name,
                team_id,
                tile_id,
                amount,
                tile_points_at_submission,
                status,
                submitted_at
            FROM manual_evidence
            WHERE evidence_id = %s
            FOR UPDATE
            ''',
            (evidence_id,)
        )

        evidence = cursor.fetchone()

        if evidence is None:
            return {
                "status": "EVIDENCE_NOT_FOUND"
            }

        (
            player_id,
            credited_player_name,
            team_id,
            tile_id,
            amount,
            tile_points_at_submission,
            status,
            submitted_at
        ) = evidence

        if status != "PENDING":
            return {
                "status": "INVALID_STATUS",
                "current_status": status
            }

        if team_id is None or tile_id is None:
            return {
                "status": "MISSING_FROZEN_CONTEXT",
                "message": (
                    "The original team or tile for this "
                    "submission no longer exists, so it cannot "
                    "be accepted normally."
                )
            }

        # Manual submissions for the same team/tile must be
        # reviewed in their original submission order.
        earlier_evidence_id = (
            _get_earlier_pending_manual_evidence(
                cursor=cursor,
                evidence_id=evidence_id,
                team_id=team_id,
                tile_id=tile_id,
                submitted_at=submitted_at
            )
        )

        if earlier_evidence_id is not None:
            return {
                "status": "EARLIER_PENDING_EVIDENCE",
                "earlier_evidence_id": earlier_evidence_id,
                "message": (
                    "An earlier submission for this tile is "
                    "still waiting for review. Review that "
                    "submission first."
                )
            }

        # If the credited player still exists, hold their row
        # for the remainder of the review. Moving teams does not
        # change the frozen team this evidence belongs to.
        player_exists = False

        if player_id is not None:
            cursor.execute(
                '''
                SELECT player_id
                FROM players
                WHERE player_id = %s
                FOR UPDATE
                ''',
                (player_id,)
            )

            player_exists = (
                cursor.fetchone() is not None
            )

        # Use the same tile-level serialisation as automatic
        # progress.
        cursor.execute(
            '''
            SELECT tile_id
            FROM tiles
            WHERE tile_id = %s
            FOR UPDATE
            ''',
            (tile_id,)
        )

        if cursor.fetchone() is None:
            return {
                "status": "TILE_NOT_FOUND",
                "message": (
                    "The tile for this submission no longer "
                    "exists, so it cannot be accepted normally."
                )
            }

        cursor.execute(
            '''
            SELECT completed_at
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        completed_tile = cursor.fetchone()

        completed_at = (
            None
            if completed_tile is None
            else completed_tile[0]
        )

        compatibility = (
            _check_manual_evidence_live_compatibility(
                cursor=cursor,
                evidence_id=evidence_id,
                tile_id=tile_id
            )
        )

        if not compatibility["compatible"]:
            # An incompatible edit still blocks normal scoring.
            # However, if the tile completed after this evidence
            # was submitted, staff may accept the evidence for
            # audit purposes only.
            if completed_at is None:
                return {
                    "status": "TILE_CHANGED",
                    "reason": compatibility["reason"],
                    "message": compatibility["message"]
                }

            if submitted_at > completed_at:
                return {
                    "status": "SUBMITTED_AFTER_COMPLETION",
                    "completed_at": completed_at,
                    "message": (
                        "This submission was made after the tile "
                        "had already completed, so it cannot be "
                        "accepted."
                    )
                }

            cursor.execute(
                '''
                UPDATE manual_evidence
                SET status = 'ACCEPTED'
                WHERE evidence_id = %s
                ''',
                (evidence_id,)
            )

            decision_id = _record_staff_review_decision(
                cursor=cursor,
                subject_type="MANUAL_EVIDENCE",
                subject_id=evidence_id,
                decision="ACCEPT",
                review_source=review_source,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                reason=(
                    "Accepted for audit only because the tile "
                    "changed after this submission was made. "
                    "No points were awarded."
                ),
                audit_only=True
            )

            conn.commit()

            return {
                "status": "ACCEPTED",
                "decision_id": decision_id,
                "evidence_id": evidence_id,
                "player_id": (
                    player_id
                    if player_exists
                    else None
                ),
                "credited_player_name":
                    credited_player_name,
                "team_id": team_id,
                "tile_id": tile_id,
                "amount": int(amount),
                "audit_only": True,
                "tile_changed": True,
                "compatibility_reason":
                    compatibility["reason"],
                "completed_at": completed_at,
                "submitted_before_completion": True,
                "actual_contribution": 0.0,
                "completion_remainder": 0.0,
                "normal_player_credit": 0.0,
                "potential_contribution": 0.0,
                "lost_mvp_contribution": 0.0,
                "award_lost_mvp_requested":
                    bool(award_lost_mvp),
                "late_review_contribution": 0.0,
                "late_review_points": 0.0,
                "player_deleted": not player_exists
            }

        potential = (
            _calculate_manual_evidence_potential_contribution(
                cursor=cursor,
                evidence_id=evidence_id
            )
        )

        if not potential["available"]:
            return {
                "status": "POTENTIAL_UNAVAILABLE",
                "reason": potential["reason"],
                "message": potential["message"]
            }

        if completed_at is not None:
            submitted_before_completion = (
                submitted_at <= completed_at
            )

            if not submitted_before_completion:
                return {
                    "status": "SUBMITTED_AFTER_COMPLETION",
                    "completed_at": completed_at,
                    "message": (
                        "This submission was made after the tile "
                        "had already completed, so it cannot be "
                        "accepted."
                    )
                }

            condition_id = int(
                compatibility["condition_id"]
            )

            completion_path = int(
                compatibility["completion_path"]
            )

            current_route = _evaluate_completion_path(
                cursor=cursor,
                team_id=team_id,
                tile_id=tile_id,
                completion_path=completion_path
            )

            cursor.execute(
                '''
                SELECT COALESCE(progress, 0)
                FROM tile_condition_progress
                WHERE team_id = %s
                  AND condition_id = %s
                ''',
                (
                    team_id,
                    condition_id
                )
            )

            raw_progress_row = cursor.fetchone()

            current_raw_progress = (
                0
                if raw_progress_row is None
                else int(raw_progress_row[0])
            )

            potential_contribution = round(
                float(
                    potential[
                        "potential_contribution"
                    ]
                ),
                12
            )

            # The tile is already complete, so this evidence
            # cannot add any further live team contribution.
            actual_contribution = 0.0

            lost_mvp_contribution = round(
                max(
                    0.0,
                    potential_contribution
                    - actual_contribution
                ),
                12
            )

            existing_personal_credit = 0.0
            remaining_personal_credit = 0.0
            late_review_contribution = 0.0
            late_review_points = 0.0

            if player_exists:
                existing_personal_credit = (
                    _get_player_team_tile_personal_credit_total(
                        cursor=cursor,
                        player_id=player_id,
                        team_id=team_id,
                        tile_id=tile_id
                    )
                )

                remaining_personal_credit = round(
                    max(
                        0.0,
                        1.0 - existing_personal_credit
                    ),
                    12
                )

            # Lost MVP is never automatic. Staff must explicitly
            # opt in, and the award is still capped so this player
            # cannot exceed 100% personal credit for this team/tile.
            if (
                award_lost_mvp
                and player_exists
                and lost_mvp_contribution > 0
                and remaining_personal_credit > 0
            ):
                late_review_contribution = round(
                    min(
                        lost_mvp_contribution,
                        remaining_personal_credit
                    ),
                    12
                )

                if tile_points_at_submission is None:
                    return {
                        "status": "POTENTIAL_UNAVAILABLE",
                        "reason": "UNKNOWN_TILE_POINTS",
                        "message": (
                            "The tile's point value at submission "
                            "is unavailable, so discretionary MVP "
                            "cannot be awarded reliably."
                        )
                    }

                late_review_points = round(
                    late_review_contribution
                    * float(tile_points_at_submission),
                    12
                )

                cursor.execute(
                    '''
                    UPDATE players
                    SET player_points =
                        COALESCE(player_points, 0) + %s
                    WHERE player_id = %s
                    RETURNING player_id
                    ''',
                    (
                        late_review_points,
                        player_id
                    )
                )

                if cursor.fetchone() is None:
                    raise ValueError(
                        "The credited player disappeared during "
                        "late-review processing."
                    )

                cursor.execute(
                    '''
                    INSERT INTO player_tile_credits (
                        player_id,
                        team_id,
                        tile_id,
                        contribution,
                        points_awarded,
                        credit_type,
                        evidence_id,
                        awarded_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'LATE_REVIEW',
                        %s,
                        clock_timestamp()
                    )
                    ''',
                    (
                        player_id,
                        team_id,
                        tile_id,
                        late_review_contribution,
                        late_review_points,
                        evidence_id
                    )
                )

            cursor.execute(
                '''
                INSERT INTO manual_evidence_progress (
                    evidence_id,
                    condition_id,
                    tile_id,
                    completion_path,
                    amount,
                    counted_amount,
                    raw_progress,
                    route_progress,
                    actual_contribution,
                    completion_remainder,
                    normal_player_credit,
                    potential_contribution,
                    lost_mvp_contribution,
                    banked_total,
                    ready,
                    completed,
                    processed_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s,
                    clock_timestamp()
                )
                ''',
                (
                    evidence_id,
                    condition_id,
                    tile_id,
                    completion_path,
                    amount,
                    0,
                    current_raw_progress,
                    current_route["progress_fraction"],
                    0.0,
                    0.0,
                    0.0,
                    potential_contribution,
                    lost_mvp_contribution,
                    1.0,
                    current_route["ready"],
                    True
                )
            )

            cursor.execute(
                '''
                UPDATE manual_evidence
                SET status = 'ACCEPTED'
                WHERE evidence_id = %s
                ''',
                (evidence_id,)
            )

            decision_id = _record_staff_review_decision(
                cursor=cursor,
                subject_type="MANUAL_EVIDENCE",
                subject_id=evidence_id,
                decision="ACCEPT",
                review_source=review_source,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name
            )

            conn.commit()

            return {
                "status": "ACCEPTED",
                "decision_id": decision_id,
                "evidence_id": evidence_id,
                "player_id": (
                    player_id
                    if player_exists
                    else None
                ),
                "credited_player_name":
                    credited_player_name,
                "team_id": team_id,
                "tile_id": tile_id,
                "condition_id": condition_id,
                "completion_path": completion_path,
                "amount": int(amount),
                "late_review": True,
                "completed_at": completed_at,
                "submitted_before_completion": True,
                "actual_contribution": 0.0,
                "completion_remainder": 0.0,
                "normal_player_credit": 0.0,
                "potential_contribution":
                    potential_contribution,
                "lost_mvp_contribution":
                    lost_mvp_contribution,
                "award_lost_mvp_requested":
                    bool(award_lost_mvp),
                "existing_personal_credit":
                    existing_personal_credit,
                "remaining_personal_credit":
                    remaining_personal_credit,
                "late_review_contribution":
                    late_review_contribution,
                "late_review_points":
                    late_review_points,
                "player_deleted": not player_exists,
                "ready": bool(
                    current_route["ready"]
                ),
                "completed": True,
                "newly_completed": False
            }

        condition_id = int(
            compatibility["condition_id"]
        )

        completion_path = int(
            compatibility["completion_path"]
        )

        before = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        raw_progress = _add_tile_condition_progress(
            cursor=cursor,
            team_id=team_id,
            condition_id=condition_id,
            amount=amount
        )

        counted_amount = _calculate_counted_drop_amount(
            condition_type=compatibility["condition_type"],
            amount=amount,
            condition_target=compatibility["target"],
            condition_progress_before=(
                raw_progress - amount
            ),
            route_state=before
        )

        after = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        route_progress_delta = round(
            max(
                0.0,
                after["progress_fraction"]
                - before["progress_fraction"]
            ),
            12
        )

        # Deleted players still leave valid team contribution
        # behind, but receive no personal MVP credit.
        bank_player_id = (
            player_id
            if player_exists
            else None
        )

        (
            actual_contribution,
            banked_total
        ) = _bank_partial_contribution(
            cursor=cursor,
            player_id=bank_player_id,
            team_id=team_id,
            tile_id=tile_id,
            requested_contribution=route_progress_delta
        )

        completion_details = None
        completed = False

        if after["ready"]:
            completion_details = (
                _complete_tile_with_contributions(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id,
                    finisher_player_id=(
                        player_id
                        if player_exists
                        else None
                    ),
                    return_details=True,
                    uncredited_finisher=(
                        not player_exists
                    )
                )
            )

            completed = bool(
                completion_details["completed"]
            )

        completion_remainder = 0.0

        if (
            completed
            and player_exists
            and completion_details is not None
        ):
            completion_remainder = round(
                float(
                    completion_details[
                        "finisher_remainder"
                    ]
                ),
                12
            )

        if player_exists:
            normal_player_credit = round(
                actual_contribution
                + completion_remainder,
                12
            )
        else:
            normal_player_credit = 0.0

        potential_contribution = round(
            float(
                potential[
                    "potential_contribution"
                ]
            ),
            12
        )

        # Lost MVP only exists when this review completes the
        # tile and completion prevents the evidence from receiving
        # all of the normal contribution it could have earned.
        #
        # If the tile remains incomplete, the queued evidence can
        # still receive its full normal MVP contribution, even if
        # automatic progress was added while it was waiting.
        if completed:
            lost_mvp_contribution = round(
                max(
                    0.0,
                    potential_contribution
                    - actual_contribution
                ),
                12
            )
        else:
            lost_mvp_contribution = 0.0
        existing_personal_credit = 0.0
        remaining_personal_credit = 0.0
        late_review_contribution = 0.0
        late_review_points = 0.0

        if player_exists:
            existing_personal_credit = (
                _get_player_team_tile_personal_credit_total(
                    cursor=cursor,
                    player_id=player_id,
                    team_id=team_id,
                    tile_id=tile_id
                )
            )

            remaining_personal_credit = round(
                max(
                    0.0,
                    1.0 - existing_personal_credit
                ),
                12
            )

        # Discretionary lost MVP is only possible when this
        # review has completed the tile and therefore truncated
        # otherwise-valid queued evidence.
        if (
            award_lost_mvp
            and completed
            and player_exists
            and lost_mvp_contribution > 0
            and remaining_personal_credit > 0
        ):
            late_review_contribution = round(
                min(
                    lost_mvp_contribution,
                    remaining_personal_credit
                ),
                12
            )

            if tile_points_at_submission is None:
                raise ValueError(
                    "The tile's point value at submission is "
                    "unavailable, so discretionary MVP cannot "
                    "be awarded reliably."
                )

            late_review_points = round(
                late_review_contribution
                * float(tile_points_at_submission),
                12
            )

            cursor.execute(
                '''
                UPDATE players
                SET player_points =
                    COALESCE(player_points, 0) + %s
                WHERE player_id = %s
                RETURNING player_id
                ''',
                (
                    late_review_points,
                    player_id
                )
            )

            if cursor.fetchone() is None:
                raise ValueError(
                    "The credited player disappeared during "
                    "late-review processing."
                )

            cursor.execute(
                '''
                INSERT INTO player_tile_credits (
                    player_id,
                    team_id,
                    tile_id,
                    contribution,
                    points_awarded,
                    credit_type,
                    evidence_id,
                    awarded_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'LATE_REVIEW',
                    %s,
                    clock_timestamp()
                )
                ''',
                (
                    player_id,
                    team_id,
                    tile_id,
                    late_review_contribution,
                    late_review_points,
                    evidence_id
                )
            )

        cursor.execute(
            '''
            INSERT INTO manual_evidence_progress (
                evidence_id,
                condition_id,
                tile_id,
                completion_path,
                amount,
                counted_amount,
                raw_progress,
                route_progress,
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                banked_total,
                ready,
                completed,
                processed_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s,
                clock_timestamp()
            )
            ''',
            (
                evidence_id,
                condition_id,
                tile_id,
                completion_path,
                amount,
                counted_amount,
                raw_progress,
                after["progress_fraction"],
                actual_contribution,
                completion_remainder,
                normal_player_credit,
                potential_contribution,
                lost_mvp_contribution,
                banked_total,
                after["ready"],
                completed
            )
        )

        cursor.execute(
            '''
            UPDATE manual_evidence
            SET status = 'ACCEPTED'
            WHERE evidence_id = %s
            ''',
            (evidence_id,)
        )

        decision_id = _record_staff_review_decision(
            cursor=cursor,
            subject_type="MANUAL_EVIDENCE",
            subject_id=evidence_id,
            decision="ACCEPT",
            review_source=review_source,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name
        )

        conn.commit()

        return {
            "status": "ACCEPTED",
            "decision_id": decision_id,
            "evidence_id": evidence_id,
            "player_id": (
                player_id
                if player_exists
                else None
            ),
            "credited_player_name":
                credited_player_name,
            "team_id": team_id,
            "tile_id": tile_id,
            "condition_id": condition_id,
            "completion_path": completion_path,
            "amount": int(amount),
            "raw_progress": raw_progress,
            "route_progress":
                after["progress_fraction"],
            "route_progress_delta":
                route_progress_delta,
            "actual_contribution":
                actual_contribution,
            "completion_remainder":
                completion_remainder,
            "normal_player_credit":
                normal_player_credit,
            "potential_contribution":
                potential_contribution,
            "lost_mvp_contribution":
                lost_mvp_contribution,
            "award_lost_mvp_requested":
                bool(award_lost_mvp),
            "existing_personal_credit":
                existing_personal_credit,
            "remaining_personal_credit":
                remaining_personal_credit,
            "late_review_contribution":
                late_review_contribution,
            "late_review_points":
                late_review_points,
            "banked_total": banked_total,
            "ready": bool(after["ready"]),
            "completed": completed,
            "newly_completed": bool(completed),
            "player_deleted": not player_exists
        }


def reject_pending_manual_evidence(
    evidence_id,
    review_source,
    reviewer_id,
    reviewer_name,
    reason=None,
    reason_code=None
):
    valid_reason_codes = {
        "INSUFFICIENT_EVIDENCE",
        "WRONG_ITEM_OR_ACTIVITY",
        "DUPLICATE_EVIDENCE",
        "WRONG_PLAYER_OR_ACCOUNT",
        "WRONG_TILE_OR_CONDITION",
        "DOES_NOT_MEET_REQUIREMENTS",
        "OTHER"
    }

    if reason_code is None:
        reason_code = ""
    else:
        reason_code = str(reason_code).strip()

    if reason_code not in valid_reason_codes:
        raise ValueError(
            f"Unsupported rejection reason code: {reason_code}"
        )

    if reason is not None:
        reason = str(reason).strip()

        if not reason:
            reason = None

    if reason is not None and len(reason) > 500:
        raise ValueError(
            "Additional rejection details cannot exceed "
            "500 characters."
        )

    if reason_code == "OTHER" and reason is None:
        raise ValueError(
            "Additional details are required when the "
            "rejection reason is Other."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                team_id,
                tile_id,
                status,
                submitted_at
            FROM manual_evidence
            WHERE evidence_id = %s
            FOR UPDATE
            ''',
            (evidence_id,)
        )

        evidence = cursor.fetchone()

        if evidence is None:
            return {
                "status": "EVIDENCE_NOT_FOUND"
            }

        team_id = evidence[0]
        tile_id = evidence[1]
        status = evidence[2]
        submitted_at = evidence[3]

        if status != "PENDING":
            return {
                "status": "INVALID_STATUS",
                "current_status": status
            }

        earlier_evidence_id = (
            _get_earlier_pending_manual_evidence(
                cursor=cursor,
                evidence_id=evidence_id,
                team_id=team_id,
                tile_id=tile_id,
                submitted_at=submitted_at
            )
        )

        if earlier_evidence_id is not None:
            return {
                "status": "EARLIER_PENDING_EVIDENCE",
                "earlier_evidence_id": earlier_evidence_id,
                "message": (
                    "An earlier submission for this tile is "
                    "still waiting for review. Review that "
                    "submission first."
                )
            }

        cursor.execute(
            '''
            UPDATE manual_evidence
            SET status = 'REJECTED'
            WHERE evidence_id = %s
            ''',
            (evidence_id,)
        )

        decision_id = _record_staff_review_decision(
            cursor=cursor,
            subject_type="MANUAL_EVIDENCE",
            subject_id=evidence_id,
            decision="REJECT",
            review_source=review_source,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reason=reason,
            reason_code=reason_code
        )

        conn.commit()

        return {
            "status": "REJECTED",
            "decision_id": decision_id
        }


def get_staff_review_decision(
    subject_type,
    subject_id
):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                decision_id,
                subject_type,
                subject_id,
                decision,
                review_source,
                reviewer_id,
                reviewer_name,
                reason,
                decided_at
            FROM staff_review_decisions
            WHERE subject_type = %s
              AND subject_id = %s
            ''',
            (
                subject_type,
                subject_id
            )
        )

        return cursor.fetchone()


def reject_pending_dink_event(
    event_id,
    review_source,
    reviewer_id,
    reviewer_name,
    reason=None,
    reason_code=None
):
    valid_reason_codes = {
        "INSUFFICIENT_EVIDENCE",
        "WRONG_ITEM_OR_ACTIVITY",
        "DUPLICATE_EVIDENCE",
        "WRONG_PLAYER_OR_ACCOUNT",
        "WRONG_TILE_OR_CONDITION",
        "DOES_NOT_MEET_REQUIREMENTS",
        "OTHER"
    }

    if reason_code is None:
        reason_code = ""
    else:
        reason_code = str(
            reason_code
        ).strip()

    if reason_code not in valid_reason_codes:
        raise ValueError(
            f"Unsupported rejection reason code: {reason_code}"
        )

    if reason is not None:
        reason = str(
            reason
        ).strip()

        if not reason:
            reason = None

    if reason is not None and len(reason) > 500:
        raise ValueError(
            "Additional rejection details cannot exceed 500 characters."
        )

    if reason_code == "OTHER" and reason is None:
        raise ValueError(
            "Additional details are required when the rejection reason is Other."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                status,
                duplicate_of_event_id
            FROM dink_events
            WHERE event_id = %s
            FOR UPDATE
            ''',
            (event_id,)
        )

        event = cursor.fetchone()

        if event is None:
            return {
                'status': 'EVENT_NOT_FOUND'
            }

        (
            player_id,
            status,
            duplicate_of_event_id
        ) = event

        if duplicate_of_event_id is not None:
            return {
                'status': 'DUPLICATE_EVENT'
            }

        if status != 'PENDING_IDENTITY':
            return {
                'status': 'INVALID_STATUS',
                'current_status': status
            }

        _update_dink_event_identity(
            cursor=cursor,
            event_id=event_id,
            player_id=player_id,
            status='REJECTED'
        )

        decision_id = _record_staff_review_decision(
            cursor=cursor,
            subject_type='DINK_EVENT',
            subject_id=event_id,
            decision='REJECT',
            review_source=review_source,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reason=reason,
            reason_code=reason_code
        )

        conn.commit()

        return {
            'status': 'REJECTED',
            'decision_id': decision_id
        }


def get_pending_manual_evidence_review_rows(limit=25):
    limit = int(limit)

    if limit < 1 or limit > 25:
        raise ValueError(
            "Manual evidence review limit must be between "
            "1 and 25."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                evidence.evidence_id,
                evidence.player_id,
                evidence.credited_player_name,
                evidence.team_id,
                team.team_name,
                evidence.tile_id,
                tile.tile_name,
                evidence.condition_id,

                selected.completion_path,
                selected.condition_type,
                selected.condition_trigger,
                selected.target,
                selected.progress,

                evidence.amount,
                evidence.description,
                evidence.evidence_path,
                evidence.submission_source,
                evidence.submitter_id,
                evidence.submitter_name,

                evidence.discord_guild_id,
                evidence.discord_channel_id,
                evidence.discord_message_id,

                evidence.evidence_author_id,
                evidence.evidence_author_name,

                evidence.evidence_codeword_at_submission,
                evidence.submitted_at,

                player.discord_user_id

            FROM manual_evidence AS evidence

            LEFT JOIN manual_evidence_condition_snapshots
                AS selected
              ON selected.evidence_id =
                    evidence.evidence_id
             AND selected.selected_condition = TRUE

            LEFT JOIN players AS player
              ON player.player_id = evidence.player_id

            LEFT JOIN teams AS team
              ON team.team_id = evidence.team_id

            LEFT JOIN tiles AS tile
              ON tile.tile_id = evidence.tile_id

            WHERE evidence.status = 'PENDING'

            ORDER BY
                evidence.submitted_at,
                evidence.evidence_id

            LIMIT %s
            ''',
            (limit,)
        )

        rows = cursor.fetchall()

    columns = (
        "evidence_id",
        "player_id",
        "credited_player_name",
        "team_id",
        "team_name",
        "tile_id",
        "tile_name",
        "condition_id",
        "completion_path",
        "condition_type",
        "condition_trigger",
        "condition_target",
        "condition_progress_at_submission",
        "amount",
        "description",
        "evidence_path",
        "submission_source",
        "submitter_id",
        "submitter_name",
        "discord_guild_id",
        "discord_channel_id",
        "discord_message_id",
        "evidence_author_id",
        "evidence_author_name",
        "evidence_codeword_at_submission",
        "submitted_at",
        "credited_discord_user_id"
    )

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def get_accepted_manual_evidence_invalidation_rows(
    limit=25
):
    limit = int(limit)

    if limit < 1 or limit > 25:
        raise ValueError(
            "Manual evidence invalidation review limit must be "
            "between 1 and 25."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                evidence.evidence_id,
                evidence.player_id,
                evidence.credited_player_name,
                evidence.team_id,
                team.team_name,
                evidence.tile_id,
                tile.tile_name,
                evidence.condition_id,

                selected.completion_path,
                selected.condition_type,
                selected.condition_trigger,
                selected.target,
                selected.progress,

                evidence.amount,
                evidence.description,
                evidence.evidence_path,
                evidence.submission_source,
                evidence.submitter_id,
                evidence.submitter_name,

                evidence.discord_guild_id,
                evidence.discord_channel_id,
                evidence.discord_message_id,

                evidence.evidence_author_id,
                evidence.evidence_author_name,

                evidence.evidence_codeword_at_submission,
                evidence.submitted_at,

                player.discord_user_id

            FROM manual_evidence AS evidence

            LEFT JOIN manual_evidence_condition_snapshots
                AS selected
              ON selected.evidence_id =
                    evidence.evidence_id
             AND selected.selected_condition = TRUE

            LEFT JOIN players AS player
              ON player.player_id = evidence.player_id

            LEFT JOIN teams AS team
              ON team.team_id = evidence.team_id

            LEFT JOIN tiles AS tile
              ON tile.tile_id = evidence.tile_id

            WHERE evidence.status = 'ACCEPTED'
              AND NOT EXISTS (
                    SELECT 1
                    FROM evidence_invalidations AS invalidation
                    WHERE invalidation.subject_type =
                          'MANUAL_EVIDENCE'
                      AND invalidation.subject_id =
                          evidence.evidence_id
              )

            ORDER BY
                evidence.submitted_at,
                evidence.evidence_id

            LIMIT %s
            ''',
            (limit,)
        )

        rows = cursor.fetchall()

    columns = (
        "evidence_id",
        "player_id",
        "credited_player_name",
        "team_id",
        "team_name",
        "tile_id",
        "tile_name",
        "condition_id",
        "completion_path",
        "condition_type",
        "condition_trigger",
        "condition_target",
        "condition_progress_at_submission",
        "amount",
        "description",
        "evidence_path",
        "submission_source",
        "submitter_id",
        "submitter_name",
        "discord_guild_id",
        "discord_channel_id",
        "discord_message_id",
        "evidence_author_id",
        "evidence_author_name",
        "evidence_codeword_at_submission",
        "submitted_at",
        "credited_discord_user_id"
    )

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def get_pending_dink_event_review_rows():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                event.event_id,
                event.dink_account_hash,
                event.player_name,
                event.event_type,
                event.raw_payload,
                event.screenshot_path,
                event.received_at,

                identity.status,
                identity.observed_rsn,
                identity.player_id,

                linked_player.player_name,
                linked_team.team_name

            FROM dink_events event

            LEFT JOIN dink_identities identity
                ON identity.dink_account_hash
                    = event.dink_account_hash

            LEFT JOIN players linked_player
                ON linked_player.player_id
                    = identity.player_id

            LEFT JOIN teams linked_team
                ON linked_team.team_id
                    = linked_player.team_id

            WHERE event.status = 'PENDING_IDENTITY'
              AND event.duplicate_of_event_id IS NULL

            ORDER BY
                CASE
                    WHEN identity.status = 'LINKED' THEN 1
                    WHEN identity.status = 'CONFLICT' THEN 2
                    WHEN identity.status = 'PENDING' THEN 3
                    ELSE 4
                END,
                event.received_at,
                event.event_id
            '''
        )

        return cursor.fetchall()



def get_pending_dink_events_by_hash(dink_account_hash):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                event_id,
                event_type,
                raw_payload,
                received_at
            FROM dink_events
            WHERE dink_account_hash = %s
              AND status = 'PENDING_IDENTITY'
              AND duplicate_of_event_id IS NULL
            ORDER BY
                received_at,
                event_id
            ''',
            (dink_account_hash,)
        )

        return cursor.fetchall()

def _add_dink_event_progress(
    cursor,
    event_id,
    trigger,
    amount,
    progress_results
):
    if not progress_results:
        return 0

    for result in progress_results:
        cursor.execute(
            '''
            INSERT INTO dink_event_progress (
                event_id,
                team_id,
                condition_id,
                tile_id,
                completion_path,
                trigger,
                amount,
                counted_amount,
                raw_progress,
                route_progress,
                credited,
                banked_total,
                ready,
                completed,
                condition_type_snapshot,
                condition_trigger_snapshot,
                condition_target_snapshot,
                route_mode_snapshot,
                route_target_snapshot,
                require_unique_snapshot,
                state
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ''',
            (
                event_id,
                result["team_id"],
                result["condition_id"],
                result["tile_id"],
                result["completion_path"],
                trigger,
                amount,
                result["counted_amount"],
                result["raw_progress"],
                result["route_progress"],
                result["credited"],
                result["banked_total"],
                result["ready"],
                result["completed"],
                result.get(
                    "condition_type_snapshot"
                ),
                result.get(
                    "condition_trigger_snapshot"
                ),
                result.get(
                    "condition_target_snapshot"
                ),
                result.get(
                    "route_mode_snapshot"
                ),
                result.get(
                    "route_target_snapshot"
                ),
                result.get(
                    "require_unique_snapshot"
                ),
                result.get(
                    "state",
                    "APPLIED"
                )
            )
        )

    return len(progress_results)


def add_dink_event_progress(
    event_id,
    trigger,
    amount,
    progress_results
):
    with connect() as conn:
        cursor = conn.cursor()

        rows_stored = _add_dink_event_progress(
            cursor=cursor,
            event_id=event_id,
            trigger=trigger,
            amount=amount,
            progress_results=progress_results
        )

        conn.commit()

    return rows_stored

def get_dink_event_progress_by_event_id(event_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                progress_id,
                event_id,
                condition_id,
                tile_id,
                completion_path,
                trigger,
                amount,
                raw_progress,
                route_progress,
                credited,
                banked_total,
                ready,
                completed,
                processed_at,
                team_id,
                counted_amount
            FROM dink_event_progress
            WHERE event_id = %s
            ORDER BY progress_id
            ''',
            (event_id,)
        )

        return cursor.fetchall()

def process_dink_event_progress(
    event_id,
    player_id,
    event_progress,
    review_source=None,
    reviewer_id=None,
    reviewer_name=None,
    reason=None
):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                player_id,
                status,
                duplicate_of_event_id,
                dink_account_hash
            FROM dink_events
            WHERE event_id = %s
            FOR UPDATE
            ''',
            (event_id,)
        )

        event = cursor.fetchone()

        if event is None:
            raise ValueError(
                f"Dink event {event_id} was not found."
            )

        (
            stored_player_id,
            status,
            duplicate_of_event_id,
            dink_account_hash
        ) = event

        if duplicate_of_event_id is not None:
            raise ValueError(
                f"Dink event {event_id} is a duplicate."
            )

        if status == 'RECEIVED':
            if stored_player_id != player_id:
                raise ValueError(
                    f"Dink event {event_id} is not linked "
                    f"to player {player_id}."
                )

        elif status == 'PENDING_IDENTITY':
            cursor.execute(
                '''
                SELECT
                    player_id,
                    status
                FROM dink_identities
                WHERE dink_account_hash = %s
                FOR SHARE
                ''',
                (dink_account_hash,)
            )

            identity = cursor.fetchone()

            if (
                identity is None
                or identity[1] != 'LINKED'
                or identity[0] != player_id
            ):
                raise ValueError(
                    f"Dink event {event_id} does not have "
                    f"a linked identity for player {player_id}."
                )

        else:
            raise ValueError(
                f"Dink event {event_id} cannot be processed "
                f"from status {status}."
            )

        all_results = []

        for progress_item in event_progress:
            condition_type = progress_item["condition_type"]
            trigger = progress_item["trigger"]
            amount = progress_item.get("amount", 1)

            results = _apply_event_condition_progress(
                cursor=cursor,
                player_id=player_id,
                condition_type=condition_type,
                trigger=trigger,
                amount=amount
            )

            _add_dink_event_progress(
                cursor=cursor,
                event_id=event_id,
                trigger=trigger,
                amount=amount,
                progress_results=results
            )

            all_results.extend(results)

        final_status = (
            'PROCESSED'
            if all_results
            else 'IGNORED'
        )

        _update_dink_event_identity(
            cursor=cursor,
            event_id=event_id,
            player_id=player_id,
            status=final_status
        )

        review_values = (
            review_source,
            reviewer_id,
            reviewer_name
        )

        has_review_metadata = any(
            value is not None
            for value in review_values
        )

        if has_review_metadata:
            if not all(
                value is not None
                for value in review_values
            ):
                raise ValueError(
                    "Incomplete staff review metadata."
                )

            if status != 'PENDING_IDENTITY':
                raise ValueError(
                    "Staff review decisions can only be "
                    "recorded for pending historical events."
                )

            decision_id = _record_staff_review_decision(
                cursor=cursor,
                subject_type='DINK_EVENT',
                subject_id=event_id,
                decision='ACCEPT',
                review_source=review_source,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                reason=reason
            )
        else:
            decision_id = None

        conn.commit()

        return {
            "status": final_status,
            "progress": all_results,
            "decision_id": decision_id
        }

# Functions for 'drops' table
def add_drop(team_id, player_id, player_name, drop_name, drop_value, drop_quantity, drop_source):
    with connect() as conn:
        cursor = conn.cursor()

        # Insert the new drop and return the primary key
        cursor.execute('''
            INSERT INTO drops (team_id, player_id, player_name, drop_name, drop_value, drop_quantity, drop_source) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING drops_pk
        ''', (team_id, player_id, player_name, drop_name, drop_value, drop_quantity, drop_source))

        # Fetch the newly created primary key
        drop_pk = cursor.fetchone()[0]

        # Update the player's gp_gained based on the drop
        cursor.execute('''
            UPDATE Players 
            SET gp_gained = gp_gained + %s 
            WHERE player_id = %s
        ''', (drop_value * drop_quantity, player_id))

        # Commit the transaction
        conn.commit()

        # Return the primary key of the new drop
        return drop_pk


def remove_drop_by_pk(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE drops_pk = %s", (drop_pk,))

def remove_drop(player_id, drop_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE player_id = %s AND lower(drop_name) = lower(%s)", (player_id, drop_name))


def get_drops():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops")
        return cursor.fetchall()


def get_drops_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE team_id = %s", (team_id,))
        return cursor.fetchall()


def get_drops_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE player_id = %s", (player_id,))
        return cursor.fetchall()


# Functions for 'killcount' table
def add_killcount(player_id, team_id, boss_name, kills):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO killcount (player_id, team_id, boss_name, kills) VALUES (%s, %s, %s, %s)",
                       (player_id, team_id, boss_name, kills))


def remove_killcount(player_id, boss_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM killcount WHERE player_id = %s AND lower(boss_name) = lower(%s)", (player_id, boss_name))


def get_killcounts():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount")
        return cursor.fetchall()


# Functions for 'drop_whitelist' table
def add_drop_whitelist(drop_name, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO drop_whitelist (drop_name, tile_id) VALUES (%s, %s)",
                           (drop_name, tile_id,))
        except:
            print("Warning! Duplicate trigger found! " + drop_name)

def update_drop_whitelist_name(old_name, new_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE drop_whitelist SET drop_name = %s WHERE drop_name = %s",
                     (new_name, old_name,))


def remove_drop_whitelist(drop_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drop_whitelist WHERE lower(drop_name) = lower(%s)", (drop_name,))

def remove_drop_whitelist_by_tile_id(tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drop_whitelist WHERE tile_id = %s", (tile_id,))

def get_drop_whitelist():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drop_whitelist")
        return cursor.fetchall()


def get_drop_whitelist_by_item_name(item_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drop_whitelist WHERE lower(drop_name) = lower(%s)", (item_name,))
        return cursor.fetchone()


# Functions for 'completed_tiles' table
def add_completed_tile(tile_id, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO completed_tiles (
                tile_id,
                team_id,
                completed_at
            )
            VALUES (
                %s,
                %s,
                clock_timestamp()
            )
            ''',
            (
                tile_id,
                team_id
            )
        )



def remove_completed_tile(tile_id, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        completed_tile = db_entities.CompletedTile(
            cursor.execute("SELECT * FROM completed_tiles WHERE lower(tile_name) = lower(%s) and team_id = %s",
                           (tile_id, team_id)).fetchone())
        cursor.execute("DELETE FROM completed_tiles WHERE completed_tile_pk = %s", (completed_tile.completed_tile_pk))


def get_completed_tiles():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tiles")
        return cursor.fetchall()

def get_completed_tiles_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tiles where team_id = %s", (team_id,))
        return cursor.fetchall()

def get_completed_tiles_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tiles where team_id = %s and tile_id = %s", (team_id, tile_id))
        return cursor.fetchall()


MAX_BINGO_TILES = 25


def _ensure_tile_capacity(cursor):
    cursor.execute(
        "LOCK TABLE tiles IN SHARE ROW EXCLUSIVE MODE"
    )

    cursor.execute(
        "SELECT COUNT(*) FROM tiles"
    )

    tile_count = cursor.fetchone()[0]

    if tile_count >= MAX_BINGO_TILES:
        raise ValueError(
            "A bingo board can contain a maximum of 25 tiles. "
            "Unassigned tiles also count towards this limit."
        )


def add_tile(tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
             tile_repetition, tile_points, tile_rules):
    with connect() as conn:
        cursor = conn.cursor()

        _ensure_tile_capacity(cursor)

        # Start at 1 and increment upwards until we find an unused tile_id
        available_id = 1
        while True:
            cursor.execute("SELECT 1 FROM tiles WHERE tile_id = %s", (available_id,))
            if not cursor.fetchone():
                break
            available_id += 1

        if tile_unique_drops == "N/A" or tile_unique_drops == "":
            tile_unique_drops = "FALSE"
        if tile_triggers_required == "N/A" or tile_triggers_required == "":
            tile_triggers_required = 0

        cursor.execute(
            "INSERT INTO tiles (tile_id, tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required, tile_repetition, tile_points, tile_rules) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (available_id, tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops,
             tile_triggers_required, tile_repetition, tile_points, tile_rules))
        conn.commit()
    if tile_type == "DROP":
        for x in tile_triggers.split(','):
            for trigger in x.split('/'):
                add_drop_whitelist(trigger.strip(), available_id)
    return available_id


def _normalise_completion_paths(
    conditions,
    completion_paths=None
):
    condition_path_numbers = {
        int(condition["completion_path"])
        for condition in conditions
    }

    if completion_paths is None:
        return [
            {
                "completion_path": path_number,
                "route_mode": "ALL",
                "route_target": None,
                "require_unique": False
            }
            for path_number
            in sorted(condition_path_numbers)
        ]

    valid_modes = {
        "ALL",
        "SUM",
        "N_OF"
    }

    normalised_paths = []

    for path in completion_paths:
        path_number = int(
            path["completion_path"]
        )

        route_mode = str(
            path.get("route_mode", "ALL")
        ).strip().upper()

        route_target = path.get(
            "route_target"
        )

        require_unique = bool(
            path.get("require_unique", False)
        )

        if path_number < 1:
            raise ValueError(
                "Completion paths must start at 1."
            )

        if route_mode not in valid_modes:
            raise ValueError(
                f"Invalid route mode: {route_mode}"
            )

        if route_mode == "ALL":
            route_target = None
            require_unique = False

        else:
            if route_target in {
                None,
                ""
            }:
                raise ValueError(
                    f"{route_mode} routes require a target."
                )

            route_target = int(
                route_target
            )

            if route_target < 1:
                raise ValueError(
                    "Route targets must be greater than 0."
                )

            if route_mode != "N_OF":
                require_unique = False

        normalised_paths.append(
            {
                "completion_path": path_number,
                "route_mode": route_mode,
                "route_target": route_target,
                "require_unique": require_unique
            }
        )

    supplied_path_numbers = {
        path["completion_path"]
        for path in normalised_paths
    }

    if supplied_path_numbers != condition_path_numbers:
        raise ValueError(
            "Completion route metadata must match "
            "the tile's condition routes."
        )

    if (
        len(supplied_path_numbers)
        != len(normalised_paths)
    ):
        raise ValueError(
            "Each completion route can only be defined once."
        )

    return sorted(
        normalised_paths,
        key=lambda path: path["completion_path"]
    )


def _validate_unique_drop_triggers(
    cursor,
    normalised_conditions,
    excluding_tile_id=None
):
    seen_triggers = {}

    for condition in normalised_conditions:
        if condition["condition_type"] != "DROP":
            continue

        condition_trigger = condition["condition_trigger"]

        if condition_trigger is None:
            continue

        trigger_key = condition_trigger.casefold()

        if trigger_key in seen_triggers:
            raise ValueError(
                f"DROP trigger '{condition_trigger}' is already "
                "used more than once on this tile."
            )

        seen_triggers[trigger_key] = condition_trigger

    for condition_trigger in seen_triggers.values():
        query = '''
            SELECT
                tiles.tile_id,
                tiles.tile_name
            FROM tile_conditions
            JOIN tiles
              ON tiles.tile_id = tile_conditions.tile_id
            WHERE tile_conditions.condition_type = 'DROP'
              AND LOWER(tile_conditions.condition_trigger) = LOWER(%s)
        '''

        params = [
            condition_trigger
        ]

        if excluding_tile_id is not None:
            query += '''
              AND tile_conditions.tile_id <> %s
            '''

            params.append(
                excluding_tile_id
            )

        query += '''
            ORDER BY tiles.tile_id
            LIMIT 1
        '''

        cursor.execute(
            query,
            params
        )

        duplicate_tile = cursor.fetchone()

        if duplicate_tile is not None:
            raise ValueError(
                f"DROP trigger '{condition_trigger}' is already "
                f"used by tile '{duplicate_tile[1]}'."
            )


def update_tile_with_conditions(
    tile_id,
    tile_name,
    tile_points,
    tile_rules,
    conditions,
    completion_paths=None
):
    if not conditions:
        raise ValueError(
            "A tile must have at least one completion condition."
        )

    valid_types = {
        "KILLCOUNT",
        "EXPERIENCE",
        "DROP",
        "METRIC",
        "PET",
        "MANUAL"
    }

    normalised_conditions = []

    for condition in conditions:
        completion_path = int(
            condition["completion_path"]
        )

        condition_type = str(
            condition["condition_type"]
        ).strip().upper()

        condition_trigger = condition.get(
            "condition_trigger"
        )

        target = int(
            condition.get("target", 1)
        )

        if completion_path < 1:
            raise ValueError(
                "Completion paths must start at 1."
            )

        if condition_type not in valid_types:
            raise ValueError(
                f"Invalid condition type: {condition_type}"
            )

        if target < 1:
            raise ValueError(
                "Condition targets must be greater than 0."
            )

        if condition_trigger is not None:
            condition_trigger = str(
                condition_trigger
            ).strip()

            if condition_trigger == "":
                condition_trigger = None

        if (
            condition_type != "MANUAL"
            and condition_trigger is None
        ):
            raise ValueError(
                f"{condition_type} conditions require a trigger."
            )

        normalised_conditions.append(
            {
                "completion_path": completion_path,
                "condition_type": condition_type,
                "condition_trigger": condition_trigger,
                "target": target
            }
        )

    normalised_paths = _normalise_completion_paths(
        normalised_conditions,
        completion_paths
    )

    condition_types = {
        condition["condition_type"]
        for condition in normalised_conditions
    }

    if len(condition_types) == 1:
        tile_type = next(iter(condition_types))
    else:
        tile_type = "MIXED"

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT tile_points
            FROM tiles
            WHERE tile_id = %s
            FOR UPDATE
            ''',
            (tile_id,)
        )

        tile_row = cursor.fetchone()

        if tile_row is None:
            raise ValueError(
                f"Tile {tile_id} does not exist."
            )

        if _tile_has_recorded_activity(
            cursor,
            tile_id
        ):
            raise ValueError(
                "This tile cannot be edited because progress "
                "or evidence has already been recorded for it."
            )

        _validate_unique_drop_triggers(
            cursor,
            normalised_conditions,
            excluding_tile_id=tile_id
        )


        existing_tile_points = float(tile_row[0])

        new_tile_points = float(tile_points)

        if abs(
            new_tile_points - existing_tile_points
        ) > 1e-9:
            cursor.execute(
                '''
                SELECT EXISTS (
                    SELECT 1
                    FROM completed_tiles
                    WHERE tile_id = %s
                )
                ''',
                (tile_id,)
            )

            if cursor.fetchone()[0]:
                raise ValueError(
                    "Tile points cannot be changed "
                    "after this tile has been completed."
                )

        cursor.execute(
            '''
            SELECT
                completion_path,
                condition_type,
                condition_trigger,
                target
            FROM tile_conditions
            WHERE tile_id = %s
            ORDER BY
                completion_path,
                condition_id
            ''',
            (tile_id,)
        )

        existing_conditions = [
            {
                "completion_path": int(row[0]),
                "condition_type":
                    str(row[1]).strip().upper(),
                "condition_trigger": (
                    str(row[2]).strip()
                    if row[2] is not None
                    else None
                ),
                "target": int(row[3])
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(
            '''
            SELECT
                completion_path,
                route_mode,
                route_target,
                require_unique
            FROM tile_completion_paths
            WHERE tile_id = %s
            ORDER BY completion_path
            ''',
            (tile_id,)
        )

        existing_paths = [
            {
                "completion_path": int(row[0]),
                "route_mode":
                    str(row[1]).strip().upper(),
                "route_target": (
                    int(row[2])
                    if row[2] is not None
                    else None
                ),
                "require_unique": bool(row[3])
            }
            for row in cursor.fetchall()
        ]

        if completion_paths is None:
            condition_path_numbers = {
                condition["completion_path"]
                for condition in normalised_conditions
            }

            existing_path_numbers = {
                path["completion_path"]
                for path in existing_paths
            }

            if (
                condition_path_numbers
                != existing_path_numbers
            ):
                raise ValueError(
                    "Completion path definitions are required "
                    "when adding or removing completion paths."
                )

            normalised_paths = existing_paths

        paths_changed = (
            existing_paths
            != normalised_paths
        )

        conditions_changed = (
            existing_conditions
            != normalised_conditions
        )

        if conditions_changed or paths_changed:
            cursor.execute(
                '''
                SELECT EXISTS (
                    SELECT 1
                    FROM partial_completions
                    WHERE tile_id = %s
                )
                OR EXISTS (
                    SELECT 1
                    FROM tile_condition_progress p
                    JOIN tile_conditions c
                      ON c.condition_id = p.condition_id
                    WHERE c.tile_id = %s
                )
                OR EXISTS (
                    SELECT 1
                    FROM completed_tiles
                    WHERE tile_id = %s
                )
                ''',
                (
                    tile_id,
                    tile_id,
                    tile_id
                )
            )

            has_progress = cursor.fetchone()[0]

            if has_progress:
                raise ValueError(
                    "Completion conditions cannot be changed "
                    "after progress has been recorded for this tile."
                )

        cursor.execute(
            '''
            UPDATE tiles
            SET
                tile_name = %s,
                tile_type = %s,
                tile_triggers = %s,
                tile_trigger_weights = %s,
                tile_unique_drops = %s,
                tile_triggers_required = %s,
                tile_repetition = %s,
                tile_points = %s,
                tile_rules = %s
            WHERE tile_id = %s
            ''',
            (
                tile_name,
                tile_type,
                "",
                None,
                False,
                0,
                1,
                tile_points,
                tile_rules,
                tile_id
            )
        )

        if conditions_changed or paths_changed:
            cursor.execute(
                '''
                DELETE FROM drop_whitelist
                WHERE tile_id = %s
                ''',
                (tile_id,)
            )

            cursor.execute(
                '''
                DELETE FROM tile_completion_paths
                WHERE tile_id = %s
                ''',
                (tile_id,)
            )

            cursor.execute(
                '''
                DELETE FROM tile_conditions
                WHERE tile_id = %s
                ''',
                (tile_id,)
            )

            for path in normalised_paths:
                cursor.execute(
                    '''
                    INSERT INTO tile_completion_paths (
                        tile_id,
                        completion_path,
                        route_mode,
                        route_target,
                        require_unique
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ''',
                    (
                        tile_id,
                        path["completion_path"],
                        path["route_mode"],
                        path["route_target"],
                        path["require_unique"]
                    )
                )

            for condition in normalised_conditions:
                cursor.execute(
                    '''
                    INSERT INTO tile_conditions (
                        tile_id,
                        completion_path,
                        condition_type,
                        condition_trigger,
                        target
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ''',
                    (
                        tile_id,
                        condition["completion_path"],
                        condition["condition_type"],
                        condition["condition_trigger"],
                        condition["target"]
                    )
                )

                if condition["condition_type"] == "DROP":
                    cursor.execute(
                        '''
                        INSERT INTO drop_whitelist (
                            drop_name,
                            tile_id
                        )
                        VALUES (%s, %s)
                        ON CONFLICT (drop_name)
                        DO NOTHING
                        ''',
                        (
                            condition["condition_trigger"],
                            tile_id
                        )
                    )

        conn.commit()


def add_tile_with_conditions(
    tile_name,
    tile_points,
    tile_rules,
    conditions,
    completion_paths=None
):
    if not conditions:
        raise ValueError(
            "A tile must have at least one completion condition."
        )

    valid_types = {
        "KILLCOUNT",
        "EXPERIENCE",
        "METRIC",
        "DROP",
        "PET",
        "MANUAL"
    }

    normalised_conditions = []

    for condition in conditions:
        completion_path = int(
            condition["completion_path"]
        )
        condition_type = str(
            condition["condition_type"]
        ).strip().upper()
        condition_trigger = condition.get(
            "condition_trigger"
        )
        target = int(condition.get("target", 1))

        if completion_path < 1:
            raise ValueError(
                "Completion paths must start at 1."
            )

        if condition_type not in valid_types:
            raise ValueError(
                f"Invalid condition type: {condition_type}"
            )

        if target < 1:
            raise ValueError(
                "Condition targets must be greater than 0."
            )

        if condition_trigger is not None:
            condition_trigger = str(
                condition_trigger
            ).strip()

            if condition_trigger == "":
                condition_trigger = None

        if (
            condition_type != "MANUAL"
            and condition_trigger is None
        ):
            raise ValueError(
                f"{condition_type} conditions require a trigger."
            )

        normalised_conditions.append(
            {
                "completion_path": completion_path,
                "condition_type": condition_type,
                "condition_trigger": condition_trigger,
                "target": target
            }
        )

    normalised_paths = _normalise_completion_paths(
        normalised_conditions,
        completion_paths
    )

    condition_types = {
        condition["condition_type"]
        for condition in normalised_conditions
    }

    if len(condition_types) == 1:
        tile_type = next(iter(condition_types))
    else:
        tile_type = "MIXED"

    with connect() as conn:
        cursor = conn.cursor()

        _validate_unique_drop_triggers(
            cursor,
            normalised_conditions
        )

        _ensure_tile_capacity(cursor)

        available_id = 1

        while True:
            cursor.execute(
                "SELECT 1 FROM tiles WHERE tile_id = %s",
                (available_id,)
            )

            if cursor.fetchone() is None:
                break

            available_id += 1

        cursor.execute(
            '''
            INSERT INTO tiles (
                tile_id,
                tile_name,
                tile_type,
                tile_triggers,
                tile_trigger_weights,
                tile_unique_drops,
                tile_triggers_required,
                tile_repetition,
                tile_points,
                tile_rules
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ''',
            (
                available_id,
                tile_name,
                tile_type,
                "",
                None,
                False,
                0,
                1,
                tile_points,
                tile_rules
            )
        )

        for path in normalised_paths:
            cursor.execute(
                '''
                INSERT INTO tile_completion_paths (
                    tile_id,
                    completion_path,
                    route_mode,
                    route_target,
                    require_unique
                )
                VALUES (%s, %s, %s, %s, %s)
                ''',
                (
                    available_id,
                    path["completion_path"],
                    path["route_mode"],
                    path["route_target"],
                    path["require_unique"]
                )
            )

        for condition in normalised_conditions:
            cursor.execute(
                '''
                INSERT INTO tile_conditions (
                    tile_id,
                    completion_path,
                    condition_type,
                    condition_trigger,
                    target
                )
                VALUES (%s, %s, %s, %s, %s)
                ''',
                (
                    available_id,
                    condition["completion_path"],
                    condition["condition_type"],
                    condition["condition_trigger"],
                    condition["target"]
                )
            )

            if condition["condition_type"] == "DROP":
                cursor.execute(
                    '''
                    INSERT INTO drop_whitelist (
                        drop_name,
                        tile_id
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (drop_name)
                    DO NOTHING
                    ''',
                    (
                        condition["condition_trigger"],
                        available_id
                    )
                )

        conn.commit()

    return available_id


def add_tile_condition(
    tile_id,
    completion_path,
    condition_type,
    condition_trigger,
    target=1
):
    condition_type = str(condition_type).strip().upper()

    if condition_trigger is not None:
        condition_trigger = str(condition_trigger).strip()

        if condition_trigger == "":
            condition_trigger = None

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO tile_conditions (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING condition_id
            ''',
            (
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            )
        )
        condition_id = cursor.fetchone()[0]
        conn.commit()

    return condition_id


def get_tile_completion_paths(tile_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                tile_id,
                completion_path,
                route_mode,
                route_target,
                require_unique
            FROM tile_completion_paths
            WHERE tile_id = %s
            ORDER BY completion_path
            ''',
            (tile_id,)
        )

        return cursor.fetchall()

def get_tile_condition_progress(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                c.condition_id,
                c.completion_path,
                c.condition_type,
                c.condition_trigger,
                c.target,
                COALESCE(p.progress, 0)
            FROM tile_conditions c
            LEFT JOIN tile_condition_progress p
              ON p.condition_id = c.condition_id
             AND p.team_id = %s
            WHERE c.tile_id = %s
            ORDER BY
                c.completion_path,
                c.condition_id
            ''',
            (
                team_id,
                tile_id
            )
        )

        return cursor.fetchall()


def _add_tile_condition_progress(
    cursor,
    team_id,
    condition_id,
    amount=1
):
    amount = int(amount)

    if amount < 1:
        raise ValueError(
            "Condition progress must be greater than 0."
        )

    cursor.execute(
        '''
        INSERT INTO tile_condition_progress (
            team_id,
            condition_id,
            progress
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (
            team_id,
            condition_id
        )
        DO UPDATE SET
            progress =
                tile_condition_progress.progress
                + EXCLUDED.progress
        RETURNING progress
        ''',
        (
            team_id,
            condition_id,
            amount
        )
    )

    return int(
        cursor.fetchone()[0]
    )


def add_tile_condition_progress(
    team_id,
    condition_id,
    amount=1
):
    with connect() as conn:
        cursor = conn.cursor()

        new_progress = _add_tile_condition_progress(
            cursor=cursor,
            team_id=team_id,
            condition_id=condition_id,
            amount=amount
        )

        conn.commit()

    return new_progress

def _evaluate_completion_path_conditions(
    route_mode,
    route_target,
    require_unique,
    conditions
):
    if not conditions:
        raise ValueError(
            "Completion path has no conditions."
        )

    if route_mode == "ALL":
        completed_conditions = sum(
            1
            for _, target, progress in conditions
            if int(progress) >= int(target)
        )

        progress_fraction = sum(
            min(
                int(progress) / int(target),
                1.0
            )
            for _, target, progress in conditions
        ) / len(conditions)

        return {
            "route_mode": "ALL",
            "current": completed_conditions,
            "target": len(conditions),
            "progress_fraction": round(
                progress_fraction,
                12
            ),
            "ready":
                completed_conditions == len(conditions)
        }

    if route_mode == "SUM":
        current = sum(
            int(progress)
            for _, _, progress in conditions
        )
        target = int(route_target)

        return {
            "route_mode": "SUM",
            "current": current,
            "target": target,
            "progress_fraction": round(
                min(
                    current / target,
                    1.0
                ),
                12
            ),
            "ready": current >= target
        }

    if route_mode == "N_OF":
        if require_unique:
            current = sum(
                1
                for _, _, progress in conditions
                if int(progress) > 0
            )
        else:
            current = sum(
                int(progress)
                for _, _, progress in conditions
            )

        target = int(route_target)

        return {
            "route_mode": "N_OF",
            "current": current,
            "target": target,
            "progress_fraction": round(
                min(
                    current / target,
                    1.0
                ),
                12
            ),
            "require_unique": require_unique,
            "ready": current >= target
        }

    raise ValueError(
        f"Unsupported route mode: {route_mode}"
    )


def _evaluate_completion_path(
    cursor,
    team_id,
    tile_id,
    completion_path
):
    cursor.execute(
        '''
        SELECT
            route_mode,
            route_target,
            require_unique
        FROM tile_completion_paths
        WHERE tile_id = %s
          AND completion_path = %s
        ''',
        (
            tile_id,
            completion_path
        )
    )

    path = cursor.fetchone()

    if path is None:
        raise ValueError(
            "Completion path does not exist."
        )

    route_mode = path[0]
    route_target = path[1]
    require_unique = bool(path[2])

    cursor.execute(
        '''
        SELECT
            c.condition_id,
            c.target,
            COALESCE(p.progress, 0)
        FROM tile_conditions c
        LEFT JOIN tile_condition_progress p
          ON p.condition_id = c.condition_id
         AND p.team_id = %s
        WHERE c.tile_id = %s
          AND c.completion_path = %s
        ORDER BY c.condition_id
        ''',
        (
            team_id,
            tile_id,
            completion_path
        )
    )

    conditions = cursor.fetchall()

    return _evaluate_completion_path_conditions(
        route_mode=route_mode,
        route_target=route_target,
        require_unique=require_unique,
        conditions=conditions
    )

def _calculate_counted_drop_amount(
    condition_type,
    amount,
    condition_target,
    condition_progress_before,
    route_state
):
    if str(condition_type).strip().upper() != "DROP":
        return 0

    amount = int(amount)
    condition_target = int(condition_target)
    condition_progress_before = int(
        condition_progress_before
    )

    route_mode = route_state["route_mode"]

    if route_mode == "ALL":
        remaining = max(
            condition_target - condition_progress_before,
            0
        )

        return min(amount, remaining)

    route_remaining = max(
        int(route_state["target"])
        - int(route_state["current"]),
        0
    )

    if route_mode == "SUM":
        return min(amount, route_remaining)

    if route_mode == "N_OF":
        if route_state.get("require_unique"):
            if (
                route_remaining > 0
                and condition_progress_before <= 0
            ):
                return 1

            return 0

        return min(amount, route_remaining)

    raise ValueError(
        f"Unsupported route mode: {route_mode}"
    )


def get_manual_evidence_submission_options(player_id):
    """
    Return the manual-evidence choices that are currently sensible
    to show for a player.

    This is a read-only convenience helper for participant-facing
    interfaces. add_manual_evidence() remains the authoritative,
    transaction-safe submission validator.
    """
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                team_id,
                player_name
            FROM players
            WHERE player_id = %s
            ''',
            (player_id,)
        )

        player = cursor.fetchone()

        if player is None:
            raise ValueError(
                f"Player {player_id} does not exist."
            )

        team_id = player[0]
        player_name = player[1]

        if team_id is None:
            raise ValueError(
                f"Player {player_id} is not on a team."
            )

        cursor.execute(
            '''
            SELECT
                t.tile_id,
                t.tile_name,
                t.tile_points,
                t.tile_rules,
                c.condition_id,
                c.completion_path,
                c.condition_type,
                c.condition_trigger,
                c.target,
                COALESCE(p.progress, 0)
            FROM tiles t
            JOIN tile_conditions c
              ON c.tile_id = t.tile_id
            LEFT JOIN tile_condition_progress p
              ON p.condition_id = c.condition_id
             AND p.team_id = %s
            LEFT JOIN completed_tiles completed
              ON completed.tile_id = t.tile_id
             AND completed.team_id = %s
            WHERE completed.tile_id IS NULL
            ORDER BY
                t.tile_id,
                c.completion_path,
                c.condition_id
            ''',
            (
                team_id,
                team_id
            )
        )

        rows = cursor.fetchall()

        manual_condition_types = {
            "DROP",
            "PET",
            "METRIC",
            "MANUAL"
        }

        path_states = {}
        tile_options = {}

        for row in rows:
            (
                tile_id,
                tile_name,
                tile_points,
                tile_rules,
                condition_id,
                completion_path,
                condition_type,
                condition_trigger,
                condition_target,
                condition_progress
            ) = row

            condition_type = str(
                condition_type
            ).strip().upper()

            if condition_type not in manual_condition_types:
                continue

            # add_manual_evidence() requires a point value, so there
            # is no useful reason to offer a tile that cannot yet be
            # submitted successfully.
            if tile_points is None:
                continue

            path_key = (
                int(tile_id),
                int(completion_path)
            )

            if path_key not in path_states:
                path_states[path_key] = (
                    _evaluate_completion_path(
                        cursor=cursor,
                        team_id=team_id,
                        tile_id=tile_id,
                        completion_path=completion_path
                    )
                )

            path_state = path_states[path_key]

            if path_state["ready"]:
                continue

            route_mode = path_state["route_mode"]

            if (
                route_mode == "ALL"
                and int(condition_progress)
                >= int(condition_target)
            ):
                continue

            if (
                route_mode == "N_OF"
                and path_state.get(
                    "require_unique",
                    False
                )
                and int(condition_progress) > 0
            ):
                continue

            if tile_id not in tile_options:
                tile_options[tile_id] = {
                    "tile_id": int(tile_id),
                    "tile_name": tile_name,
                    "tile_points": float(
                        tile_points
                    ),
                    "tile_rules": tile_rules,
                    "conditions": []
                }

            tile_options[tile_id][
                "conditions"
            ].append(
                {
                    "condition_id":
                        int(condition_id),
                    "condition_type":
                        condition_type,
                    "condition_trigger":
                        condition_trigger,
                    "target":
                        int(condition_target),
                    "progress":
                        int(condition_progress)
                }
            )

        return {
            "player_id": int(player_id),
            "player_name": player_name,
            "team_id": int(team_id),
            "tiles": list(
                tile_options.values()
            )
        }


def evaluate_completion_path(
    team_id,
    tile_id,
    completion_path
):
    with connect() as conn:
        cursor = conn.cursor()

        return _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

def _apply_event_condition_progress(
    cursor,
    player_id,
    condition_type,
    trigger,
    amount=1
):
    condition_type = str(
        condition_type
    ).strip().upper()

    trigger = str(
        trigger
    ).strip()

    amount = int(amount)

    if condition_type not in {
        "DROP",
        "PET"
    }:
        raise ValueError(
            "Event progress can only be applied "
            "to DROP or PET conditions."
        )

    if not trigger:
        raise ValueError(
            "Event progress requires a trigger."
        )

    if amount < 1:
        raise ValueError(
            "Event progress must be greater than 0."
        )

    cursor.execute(
        '''
        SELECT team_id
        FROM players
        WHERE player_id = %s
        FOR UPDATE
        ''',
        (player_id,)
    )

    player_row = cursor.fetchone()

    if player_row is None:
        raise ValueError(
            f"Player {player_id} does not exist."
        )

    team_id = player_row[0]

    if team_id is None:
        raise ValueError(
            f"Player {player_id} is not on a team."
        )

    cursor.execute(
        '''
        SELECT
            condition.condition_id,
            condition.tile_id,
            condition.completion_path,
            condition.target,
            condition.condition_type,
            condition.condition_trigger,
            path.route_mode,
            path.route_target,
            path.require_unique
        FROM tile_conditions AS condition
        JOIN tile_completion_paths AS path
          ON path.tile_id = condition.tile_id
         AND path.completion_path =
             condition.completion_path
        WHERE condition.condition_type = %s
          AND lower(condition.condition_trigger) = lower(%s)
        ORDER BY
            condition.tile_id,
            condition.completion_path,
            condition.condition_id
        ''',
        (
            condition_type,
            trigger
        )
    )

    conditions = cursor.fetchall()

    results = []

    for (
        condition_id,
        tile_id,
        completion_path,
        condition_target,
        condition_type_snapshot,
        condition_trigger_snapshot,
        route_mode_snapshot,
        route_target_snapshot,
        require_unique_snapshot
    ) in conditions:
        # Serialise all progress against this tile so two
        # simultaneous events cannot both claim the same
        # remaining contribution.
        cursor.execute(
            '''
            SELECT tile_id
            FROM tiles
            WHERE tile_id = %s
            FOR UPDATE
            ''',
            (tile_id,)
        )

        if cursor.fetchone() is None:
            continue

        cursor.execute(
            '''
            SELECT 1
            FROM completed_tiles
            WHERE team_id = %s
              AND tile_id = %s
            ''',
            (
                team_id,
                tile_id
            )
        )

        if cursor.fetchone() is not None:
            cursor.execute(
                '''
                SELECT COALESCE(progress, 0)
                FROM tile_condition_progress
                WHERE team_id = %s
                  AND condition_id = %s
                ''',
                (
                    team_id,
                    condition_id
                )
            )

            raw_progress_row = cursor.fetchone()

            raw_progress = (
                int(raw_progress_row[0])
                if raw_progress_row is not None
                else 0
            )

            route_state = _evaluate_completion_path(
                cursor=cursor,
                team_id=team_id,
                tile_id=tile_id,
                completion_path=completion_path
            )

            results.append(
                {
                    "team_id": team_id,
                    "condition_id": condition_id,
                    "tile_id": tile_id,
                    "completion_path": completion_path,
                    "counted_amount": 0,
                    "raw_progress": raw_progress,
                    "route_progress":
                        route_state["progress_fraction"],
                    "credited": 0.0,
                    "banked_total": 0.0,
                    "ready": route_state["ready"],
                    "completed": False,
                    "condition_type_snapshot":
                        condition_type_snapshot,
                    "condition_trigger_snapshot":
                        condition_trigger_snapshot,
                    "condition_target_snapshot":
                        condition_target,
                    "route_mode_snapshot":
                        route_mode_snapshot,
                    "route_target_snapshot":
                        route_target_snapshot,
                    "require_unique_snapshot":
                        require_unique_snapshot,
                    "state": "SUPPRESSED_COMPLETED"
                }
            )

            continue

        before = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        raw_progress = _add_tile_condition_progress(
            cursor=cursor,
            team_id=team_id,
            condition_id=condition_id,
            amount=amount
        )

        counted_amount = _calculate_counted_drop_amount(
            condition_type=condition_type,
            amount=amount,
            condition_target=condition_target,
            condition_progress_before=(
                raw_progress - amount
            ),
            route_state=before
        )

        after = _evaluate_completion_path(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            completion_path=completion_path
        )

        progress_delta = round(
            max(
                0.0,
                after["progress_fraction"]
                - before["progress_fraction"]
            ),
            12
        )

        contribution, banked_after = (
            _bank_partial_contribution(
                cursor=cursor,
                player_id=player_id,
                team_id=team_id,
                tile_id=tile_id,
                requested_contribution=progress_delta
            )
        )

        completed = False

        # Tile readiness is determined by an actual completion
        # path, never merely by total banked contribution.
        if after["ready"]:
            completed = (
                _complete_tile_with_contributions(
                    cursor=cursor,
                    team_id=team_id,
                    tile_id=tile_id
                )
            )

        results.append(
            {
                "team_id": team_id,
                "condition_id": condition_id,
                "tile_id": tile_id,
                "completion_path": completion_path,
                "counted_amount": counted_amount,
                "raw_progress": raw_progress,
                "route_progress":
                    after["progress_fraction"],
                "credited": contribution,
                "banked_total": banked_after,
                "ready": after["ready"],
                "completed": completed,
                "condition_type_snapshot":
                    condition_type_snapshot,
                "condition_trigger_snapshot":
                    condition_trigger_snapshot,
                "condition_target_snapshot":
                    condition_target,
                "route_mode_snapshot":
                    route_mode_snapshot,
                "route_target_snapshot":
                    route_target_snapshot,
                "require_unique_snapshot":
                    require_unique_snapshot,
                "state": "APPLIED"
            }
        )

    return results


def apply_event_condition_progress(
    player_id,
    condition_type,
    trigger,
    amount=1
):
    with connect() as conn:
        cursor = conn.cursor()

        results = _apply_event_condition_progress(
            cursor=cursor,
            player_id=player_id,
            condition_type=condition_type,
            trigger=trigger,
            amount=amount
        )

        conn.commit()

    return results

def get_tile_conditions(tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                condition_id,
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            FROM tile_conditions
            WHERE tile_id = %s
            ORDER BY
                completion_path,
                condition_id
            ''',
            (tile_id,)
        )
        return cursor.fetchall()


def get_wom_tile_conditions():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                condition_id,
                tile_id,
                completion_path,
                condition_type,
                condition_trigger,
                target
            FROM tile_conditions AS condition
            WHERE condition.condition_type IN (
                'KILLCOUNT',
                'EXPERIENCE',
                'METRIC'
            )
              AND EXISTS (
                  SELECT 1
                  FROM teams AS team
                  WHERE NOT EXISTS (
                      SELECT 1
                      FROM completed_tiles AS completed
                      WHERE completed.team_id = team.team_id
                        AND completed.tile_id = condition.tile_id
                  )
              )
            ORDER BY
                condition.tile_id,
                condition.completion_path,
                condition.condition_id
            '''
        )
        return cursor.fetchall()


# ... Repeat similar functions for 'drops', 'killcount', 'drop_whitelist', and 'completed_tiles' tables ...

def set_tile_board_coordinate(tile_id, board_coordinate):
    if board_coordinate is not None:
        board_coordinate = str(
            board_coordinate
        ).strip().upper()

        if board_coordinate == "":
            board_coordinate = None

    valid_coordinates = {
        f"{row}{column}"
        for row in "ABCDE"
        for column in range(1, 6)
    }

    if (
        board_coordinate is not None
        and board_coordinate not in valid_coordinates
    ):
        raise ValueError(
            "Board coordinate must be between A1 and E5."
        )

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT board_coordinate
            FROM tiles
            WHERE tile_id = %s
            FOR UPDATE
            ''',
            (tile_id,)
        )

        tile_row = cursor.fetchone()

        if tile_row is None:
            raise ValueError(
                f"Tile {tile_id} does not exist."
            )

        old_coordinate = tile_row[0]

        if old_coordinate == board_coordinate:
            return

        displaced_tile = None

        if board_coordinate is not None:
            cursor.execute(
                '''
                SELECT
                    tile_id,
                    board_coordinate
                FROM tiles
                WHERE board_coordinate = %s
                  AND tile_id <> %s
                FOR UPDATE
                ''',
                (
                    board_coordinate,
                    tile_id
                )
            )

            displaced_tile = cursor.fetchone()

        # Free the moving tile's current position first so an
        # occupied destination can safely be swapped into it.
        cursor.execute(
            '''
            UPDATE tiles
            SET board_coordinate = NULL
            WHERE tile_id = %s
            ''',
            (tile_id,)
        )

        if displaced_tile is not None:
            cursor.execute(
                '''
                UPDATE tiles
                SET board_coordinate = %s
                WHERE tile_id = %s
                ''',
                (
                    old_coordinate,
                    displaced_tile[0]
                )
            )

        cursor.execute(
            '''
            UPDATE tiles
            SET board_coordinate = %s
            WHERE tile_id = %s
            ''',
            (
                board_coordinate,
                tile_id
            )
        )


def get_tiles():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles ORDER BY tile_id")
        return cursor.fetchall()


def get_niche_tiles():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles WHERE tile_type = %s", ("NICHE",))
        return cursor.fetchall()


def get_tile_by_drop(drop_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drop_whitelist where lower(drop_name) = lower(%s)", (drop_name,))
        try:
            tile_id = cursor.fetchone()[1]
        except:
            return None
        cursor.execute("SELECT * FROM tiles where tile_id = %s", (tile_id,))
        return cursor.fetchone()

def get_tile_by_id(tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where tile_id = %s", (tile_id,))
        return cursor.fetchone()

def get_tile_by_name(tile_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where lower(tile_name) = lower(%s)", (tile_name,))
        return cursor.fetchone()

def get_tile_by_type(tile_type):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where tile_type = %s", (tile_type,))
        return cursor.fetchall()

def get_drops_by_item_name_and_team_id(item_name, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops where team_id = %s and lower(drop_name) = lower(%s)", (team_id, item_name,))
        return cursor.fetchall()

def update_player(player_id, player_name, deaths, gp_gained, tiles_completed, team_id, pet_count):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE players
            SET player_name = %s, deaths = %s, gp_gained = %s, tiles_completed = %s, team_id = %s, pet_count = %s
            WHERE player_id = %s
        ''', (player_name, deaths, gp_gained, tiles_completed, team_id, pet_count, player_id))
        conn.commit()


def update_team_webhook(team_id, team_webhook):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE teams set team_webhook = %s where team_id = %s", (team_webhook, team_id,))
        conn.commit()

def get_drops_by_item_name(item_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE lower(drop_name) = lower(%s)", (item_name,))
        return cursor.fetchall()
# Functions for 'killcount' table
def add_killcount(player_id, team_id, bossname, kills):
    with connect() as conn:
        cursor = conn.cursor()

        # Check if the row already exists
        cursor.execute("SELECT * FROM KillCount WHERE player_id = %s AND team_id = %s AND lower(boss_name) = lower(%s)",
                       (player_id, team_id, bossname))
        row = cursor.fetchone()

        if row is not None:
            # If the row exists, update the kills
            cursor.execute(
                "UPDATE KillCount SET kills = kills + %s WHERE player_id = %s AND team_id = %s AND lower(boss_name) = lower(%s)",
                (kills, player_id, team_id, bossname))
        else:
            # If the row doesn't exist, insert a new row
            cursor.execute("INSERT INTO KillCount (player_id, team_id, boss_name, kills) VALUES (%s, %s, %s, %s)",
                           (player_id, team_id, bossname, kills))

        # Commit the changes
        conn.commit()

def get_partial_completions():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM partial_completions")
        return cursor.fetchall()

def add_player_partial_completions(player_id, team_id, tile_id, value):
    with connect() as conn:
        cursor = conn.cursor()

        # Check if the row already exists
        cursor.execute("SELECT * FROM partial_completions WHERE player_id = %s AND team_id = %s AND tile_id = %s",
                       (player_id, team_id, tile_id))
        row = cursor.fetchone()

        if row is not None:
            # If the row exists, update the kills
            cursor.execute(
                "UPDATE partial_completions SET partial_completion = partial_completion + %s WHERE player_id = %s AND team_id = %s AND tile_id = %s",
                (value, player_id, team_id, tile_id))
        else:
            cursor.execute("INSERT INTO partial_completions (player_id, team_id, tile_id, partial_completion) VALUES (%s, %s, %s, %s)",
                           (player_id, team_id, tile_id, value))

        conn.commit()

def get_partial_completions_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM partial_completions WHERE team_id = %s AND tile_id = %s", (team_id, tile_id))
        return cursor.fetchall()

def get_partial_completions_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM partial_completions WHERE team_id = %s", (team_id,))
        return cursor.fetchall()

def get_partial_completions_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM partial_completions WHERE player_id = %s", (player_id,))
        return cursor.fetchall()


def _complete_tile_with_contributions(
    cursor,
    team_id,
    tile_id,
    finisher_player_id=None,
    return_details=False,
    uncredited_finisher=False
):

    cursor.execute(
        '''
        SELECT tile_points
        FROM tiles
        WHERE tile_id = %s
        ''',
        (tile_id,)
    )
    tile_row = cursor.fetchone()

    if tile_row is None:
        raise ValueError(
            f"Tile {tile_id} does not exist."
        )

    tile_points = float(tile_row[0])

    # Claim the completion first. The unique index means that
    # only one process can ever successfully complete this tile
    # for this team.
    cursor.execute(
        '''
        INSERT INTO completed_tiles (
            tile_id,
            team_id,
            completed_at,
            points_awarded
        )
        VALUES (
            %s,
            %s,
            clock_timestamp(),
            %s
        )
        ON CONFLICT (team_id, tile_id)
        DO NOTHING
        RETURNING completed_tile_pk
        ''',
        (
            tile_id,
            team_id,
            tile_points
        )
    )

    completion_row = cursor.fetchone()

    if completion_row is None:
        if return_details:
            return {
                "completed": False,
                "tile_points": tile_points,
                "contributions": {},
                "banked_total_before_finisher": 0.0,
                "finisher_player_id": finisher_player_id,
                "finisher_remainder": 0.0,
                "finisher_contribution": 0.0
            }

        return False

    completed_tile_pk = int(completion_row[0])

    cursor.execute(
        '''
        SELECT
            player_id,
            partial_completion
        FROM partial_completions
        WHERE team_id = %s
          AND tile_id = %s
        ORDER BY partial_completion_pk
        FOR UPDATE
        ''',
        (
            team_id,
            tile_id
        )
    )

    contributions = {}
    uncredited_contribution = 0.0

    for player_id, partial_completion in cursor.fetchall():
        contribution = float(
            partial_completion
        )

        if player_id is None:
            uncredited_contribution += contribution
            continue

        contributions[player_id] = (
            contributions.get(
                player_id,
                0.0
            )
            + contribution
        )

    uncredited_contribution = round(
        uncredited_contribution,
        12
    )

    banked_total = (
        sum(contributions.values())
        + uncredited_contribution
    )

    if banked_total < 0:
        raise ValueError(
            "Tile contribution cannot be negative."
        )

    # Allow only tiny floating-point rounding differences.
    if banked_total > 1.000001:
        raise ValueError(
            "Banked tile contribution exceeds 100%."
        )

    if banked_total > 1:
        scale = 1 / banked_total

        contributions = {
            player_id: contribution * scale
            for player_id, contribution
            in contributions.items()
        }

        uncredited_contribution = (
            uncredited_contribution * scale
        )

        banked_total = 1.0

    banked_total_before_finisher = round(
        banked_total,
        12
    )

    finisher_remainder = 0.0

    if finisher_player_id is not None:
        remaining = round(
            max(
                0.0,
                1.0 - banked_total
            ),
            12
        )

        finisher_remainder = remaining

        contributions[finisher_player_id] = round(
            contributions.get(
                finisher_player_id,
                0.0
            )
            + remaining,
            12
        )

    elif uncredited_finisher:
        remaining = round(
            max(
                0.0,
                1.0 - banked_total
            ),
            12
        )

        finisher_remainder = remaining

        uncredited_contribution = round(
            uncredited_contribution
            + remaining,
            12
        )

    elif banked_total < 0.999999:
        raise ValueError(
            "Tile has not reached 100% contribution."
        )

    elif banked_total != 1.0:
        scale = 1 / banked_total

        contributions = {
            player_id: contribution * scale
            for player_id, contribution
            in contributions.items()
        }

        uncredited_contribution = (
            uncredited_contribution * scale
        )

    for player_id, contribution in contributions.items():
        if contribution <= 0:
            continue

        points_awarded = round(
            contribution * tile_points,
            12
        )

        cursor.execute(
            '''
            UPDATE players
            SET
                tiles_completed =
                    COALESCE(tiles_completed, 0) + %s,
                player_points =
                    COALESCE(player_points, 0) + %s
            WHERE player_id = %s
            RETURNING player_id
            ''',
            (
                contribution,
                points_awarded,
                player_id
            )
        )

        # A player may have moved teams since earning this
        # contribution. They still receive the personal credit,
        # recorded against the original team.
        #
        # If the player has since been deleted, their banked work
        # still benefits the team but no personal credit is awarded.
        if cursor.fetchone() is None:
            continue

        cursor.execute(
            '''
            INSERT INTO player_tile_credits (
                player_id,
                team_id,
                tile_id,
                contribution,
                points_awarded,
                credit_type
            )
            VALUES (%s, %s, %s, %s, %s, 'TILE_COMPLETION')
            ''',
            (
                player_id,
                team_id,
                tile_id,
                contribution,
                points_awarded
            )
        )

    cursor.execute(
        '''
        UPDATE teams
        SET team_points = team_points + %s
        WHERE team_id = %s
        RETURNING team_id
        ''',
        (
            tile_points,
            team_id
        )
    )

    if cursor.fetchone() is None:
        raise ValueError(
            f"Team {team_id} does not exist."
        )

    cursor.execute(
        '''
        INSERT INTO completed_tile_partial_snapshot (
            completed_tile_pk,
            player_id,
            partial_completion
        )
        SELECT
            %s,
            player_id,
            partial_completion
        FROM partial_completions
        WHERE team_id = %s
          AND tile_id = %s
        ORDER BY partial_completion_pk
        ''',
        (
            completed_tile_pk,
            team_id,
            tile_id
        )
    )

    cursor.execute(
        '''
        DELETE FROM partial_completions
        WHERE team_id = %s
          AND tile_id = %s
        ''',
        (
            team_id,
            tile_id
        )
    )

    if return_details:
        final_contributions = {
            int(player_id): round(
                float(contribution),
                12
            )
            for player_id, contribution
            in contributions.items()
            if contribution > 0
        }

        finisher_contribution = 0.0

        if finisher_player_id is not None:
            finisher_contribution = final_contributions.get(
                int(finisher_player_id),
                0.0
            )

        return {
            "completed": True,
            "tile_points": tile_points,
            "contributions": final_contributions,
            "uncredited_contribution": round(
                uncredited_contribution,
                12
            ),
            "banked_total_before_finisher":
                banked_total_before_finisher,
            "finisher_player_id": finisher_player_id,
            "finisher_remainder": finisher_remainder,
            "finisher_contribution":
                finisher_contribution
        }

    return True


def complete_tile_with_contributions(
    team_id,
    tile_id,
    finisher_player_id=None
):
    with connect() as conn:
        cursor = conn.cursor()

        completed = _complete_tile_with_contributions(
            cursor=cursor,
            team_id=team_id,
            tile_id=tile_id,
            finisher_player_id=finisher_player_id
        )

        conn.commit()

    return completed


def remove_partial_completion(partial_completion_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM partial_completions WHERE partial_completion_pk = %s", (partial_completion_pk,))

def get_killcount_by_team_id_and_boss_name(team_id, boss_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount WHERE team_id = %s AND lower(boss_name) = lower(%s)", (team_id, boss_name))
        return cursor.fetchall()


def get_killcount_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount WHERE team_id = %s", (team_id,))
        return cursor.fetchall()


def get_killcount_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount WHERE player_id = %s", (player_id,))
        return cursor.fetchall()


def add_manual_progress(tile_name, player_name, progress):
    with connect() as conn:
        cursor = conn.cursor()

        # Find the player
        cursor.execute("SELECT * FROM players WHERE lower(player_name) = lower(%s)", (player_name,))
        player = db_entities.Player(cursor.fetchone())

        # Find the team
        cursor.execute("SELECT * FROM teams where team_id = %s", (player.team_id,))
        team = db_entities.Team(cursor.fetchone())

        # Find the tile
        cursor.execute("SELECT * FROM tiles WHERE lower(tile_name) = lower(%s)", (tile_name,))
        tile = db_entities.Tile(cursor.fetchone())

        # Check if the row already exists
        cursor.execute("SELECT * FROM manual_tile_progress WHERE team_id = %s AND tile_id = %s AND player_id = %s",
                       (team.team_id, tile.tile_id, player.player_id))
        row = cursor.fetchone()

        if row is not None:
            # If the row exists, update the kills
            cursor.execute(
                "UPDATE manual_tile_progress SET progress = progress + %s WHERE team_id = %s AND tile_id = %s AND player_id = %s",
                (progress, team.team_id, tile.tile_id, player.player_id))
        else:
            # If the row doesn't exist, insert a new row
            cursor.execute("INSERT INTO manual_tile_progress (tile_id, team_id, progress, player_id) VALUES (%s, %s, %s, %s)",
                           (tile.tile_id, team.team_id, progress, player.player_id))


def get_manual_progress_by_tile_name_and_team_name(tile_name, team_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams where lower(team_name) = lower(%s)", (team_name,))
        team = db_entities.Team(cursor.fetchone())

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where lower(tile_name) = lower(%s)", (tile_name,))
        tile = db_entities.Tile(cursor.fetchone())

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manual_tile_progress WHERE team_id = %s AND tile_id = %s",
                       (team.team_id, tile.tile_id,))

        progress = 0
        for x in cursor.fetchall():
            progress += x[3]

        return progress


def get_manual_progress_by_tile_id_and_team_id(tile_id, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manual_tile_progress WHERE team_id = %s and tile_id = %s", (team_id, tile_id,))
        try:
            progress = 0
            for item in cursor.fetchall():
                progress = progress + item[3]
            return progress
        except:
            return 0


def add_request(team_name, player_name, tile_name, item_description, image):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO requests (team_name, player_name, tile_name, item_name, evidence) VALUES (%s, %s, %s, %s, %s)", (team_name, player_name, tile_name, item_description, image,))


def get_request():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests")
        return cursor.fetchone()


def delete_request(request_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requests WHERE request_id = %s", (request_id,))


def add_chats(player_id, team_id, tile_id, chat):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chats (player_id, team_id, tile_id, chat) VALUES (%s, %s, %s, %s)", (player_id, team_id, tile_id, chat))


def get_chats(chats_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE chats_pk = %s", (chats_pk,))
        return cursor.fetchall()


def get_chats_by_player_id_and_tile_id(player_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE player_id = %s and tile_id = %s", (player_id, tile_id))
        return cursor.fetchall()


def get_chats_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE team_id = %s and tile_id = %s", (team_id, tile_id))
        return cursor.fetchall()


def delete_chat(chats_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chats WHERE chats_pk = %s", (chats_pk,))

def add_relevant_drop(team_id, player_id, tile_id, tile_name, drop_name, player_name, drops_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO relevant_drops (team_id, player_id, tile_id, tile_name, drop_name, player_name, drops_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (team_id, player_id, tile_id, tile_name, drop_name, player_name, drops_pk))
        conn.commit()

def get_relevant_drop_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE player_id = %s", (player_id,))
        return cursor.fetchall()

def get_player_relevant_drop_summary(player_id):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            WITH relevant_drop_progress AS (
                SELECT
                    dep.trigger AS drop_name,
                    dep.counted_amount AS quantity
                FROM dink_event_progress AS dep
                JOIN dink_events AS de
                  ON de.event_id = dep.event_id
                WHERE de.player_id = %s
                  AND de.status = 'PROCESSED'
                  AND dep.counted_amount > 0
                  AND NOT EXISTS (
                      SELECT 1
                      FROM evidence_invalidations AS invalidation
                      WHERE invalidation.subject_type =
                            'DINK_EVENT'
                        AND invalidation.subject_id =
                            de.event_id
                  )

                UNION ALL

                SELECT
                    snapshot.condition_trigger AS drop_name,
                    progress.counted_amount AS quantity
                FROM manual_evidence_progress AS progress
                JOIN manual_evidence AS evidence
                  ON evidence.evidence_id =
                     progress.evidence_id
                JOIN manual_evidence_condition_snapshots
                    AS snapshot
                  ON snapshot.evidence_id =
                     evidence.evidence_id
                 AND snapshot.selected_condition = TRUE
                WHERE evidence.player_id = %s
                  AND evidence.status = 'ACCEPTED'
                  AND UPPER(
                      BTRIM(snapshot.condition_type)
                  ) = 'DROP'
                  AND progress.counted_amount > 0
                  AND NOT EXISTS (
                      SELECT 1
                      FROM evidence_invalidations AS invalidation
                      WHERE invalidation.subject_type =
                            'MANUAL_EVIDENCE'
                        AND invalidation.subject_id =
                            evidence.evidence_id
                  )
            )
            SELECT
                MIN(BTRIM(drop_name)) AS drop_name,
                SUM(quantity)::INTEGER AS quantity
            FROM relevant_drop_progress
            WHERE drop_name IS NOT NULL
              AND BTRIM(drop_name) <> ''
            GROUP BY LOWER(BTRIM(drop_name))
            ORDER BY LOWER(MIN(BTRIM(drop_name)))
            ''',
            (
                player_id,
                player_id
            )
        )

        drops = [
            {
                "drop_name": row[0],
                "quantity": int(row[1])
            }
            for row in cursor.fetchall()
        ]

    return {
        "total_quantity": sum(
            drop["quantity"]
            for drop in drops
        ),
        "drops": drops
    }

def get_player_bingo_evidence(player_id):
    evidence_rows = []

    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT
                de.event_id,
                dep.tile_id,
                t.tile_name,
                SUM(dep.credited)::NUMERIC(18, 12),
                EXISTS (
                    SELECT 1
                    FROM completed_tiles AS completed
                    WHERE completed.tile_id = dep.tile_id
                      AND completed.team_id = COALESCE(
                          dep.team_id,
                          player.team_id
                      )
                ),
                de.screenshot_path,
                de.received_at
            FROM dink_events AS de
            JOIN dink_event_progress AS dep
              ON dep.event_id = de.event_id
            JOIN tiles AS t
              ON t.tile_id = dep.tile_id
            JOIN players AS player
              ON player.player_id = de.player_id
            WHERE de.player_id = %s
              AND de.status = 'PROCESSED'
              AND de.screenshot_path IS NOT NULL
            GROUP BY
                de.event_id,
                dep.tile_id,
                t.tile_name,
                player.team_id,
                dep.team_id,
                de.screenshot_path,
                de.received_at
            ''',
            (player_id,)
        )

        for row in cursor.fetchall():
            evidence_rows.append(
                {
                    "date": row[6],
                    "tile_name": row[2],
                    "contribution": float(row[3]),
                    "source": "Automatic submission",
                    "evidence_type": "dink",
                    "evidence_id": int(row[0]),
                    "screenshot_path": row[5],
                    "status": (
                        "Tile completed"
                        if bool(row[4])
                        else "In progress"
                    )
                }
            )

        cursor.execute(
            '''
            SELECT
                me.evidence_id,
                COALESCE(
                    me.tile_name_at_submission,
                    t.tile_name,
                    'Former/removed tile'
                ),
                me.status,
                me.evidence_path,
                me.submitted_at,
                srd.decision,
                srd.reason,
                srd.audit_only,
                mep.actual_contribution,
                mep.completed,
                EXISTS (
                    SELECT 1
                    FROM player_tile_credits AS ptc
                    WHERE ptc.evidence_id = me.evidence_id
                      AND ptc.credit_type = 'LATE_REVIEW'
                      AND ptc.points_awarded > 0
                ) AS late_review_mvp_awarded
            FROM manual_evidence AS me
            LEFT JOIN tiles AS t
              ON t.tile_id = me.tile_id
            JOIN staff_review_decisions AS srd
              ON srd.subject_type = 'MANUAL_EVIDENCE'
             AND srd.subject_id = me.evidence_id
            LEFT JOIN manual_evidence_progress AS mep
              ON mep.evidence_id = me.evidence_id
            WHERE me.player_id = %s
              AND me.status IN ('ACCEPTED', 'REJECTED')
              AND me.evidence_path IS NOT NULL
            ''',
            (player_id,)
        )

        for row in cursor.fetchall():
            decision = row[5]
            reason = row[6]
            audit_only = bool(row[7])
            completed = bool(row[9]) if row[9] is not None else False
            late_review_mvp_awarded = bool(row[10])

            if decision == "REJECT":
                contribution = None
                status = "Not accepted"

                if reason:
                    status = f"{status} — {reason}"
            elif audit_only:
                contribution = 0.0
                status = "Accepted — audit only"
            else:
                contribution = (
                    float(row[8])
                    if row[8] is not None
                    else 0.0
                )

                if contribution == 0.0 and late_review_mvp_awarded:
                    status = "Accepted — MVP awarded"
                elif completed and contribution > 0.0:
                    status = "Accepted — tile completed"
                else:
                    status = "Accepted — progress recorded"

            evidence_rows.append(
                {
                    "date": row[4],
                    "tile_name": row[1],
                    "contribution": contribution,
                    "source": "Manual evidence",
                    "evidence_type": "manual",
                    "evidence_id": int(row[0]),
                    "screenshot_path": row[3],
                    "status": status
                }
            )

    evidence_rows.sort(
        key=lambda evidence: evidence["date"],
        reverse=True
    )

    return evidence_rows


def get_relevant_drop_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE team_id = %s", (team_id,))
        return cursor.fetchall()

def get_relevant_drop_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE team_id = %s AND tile_id = %s", (team_id, tile_id,))
        return cursor.fetchall()

def delete_relevant_drop(relevant_drops_pk):
    with connect() as conn:
        cursor = conn.cursor()

        # Fetch the relevant drop details: player_name, tile_id, drop_name
        cursor.execute('''
            SELECT player_name, tile_id, drop_name 
            FROM relevant_drops 
            WHERE relevant_drops_pk = %s
        ''', (relevant_drops_pk,))
        relevant_drop = cursor.fetchone()

        if not relevant_drop:
            raise ValueError(f"Relevant drop with ID {relevant_drops_pk} does not exist.")

        player_name = relevant_drop[0]
        tile_id = relevant_drop[1]
        drop_name = relevant_drop[2]

        # Fetch the trigger values and weights for the relevant tile
        cursor.execute('''
            SELECT tile_triggers, tile_trigger_weights, tile_triggers_required
            FROM tiles 
            WHERE tile_id = %s
        ''', (tile_id,))
        tile_data = cursor.fetchone()

        if not tile_data:
            raise ValueError(f"Tile with ID {tile_id} does not exist.")

        tile_triggers = tile_data[0].split(',')
        tile_trigger_weights = list(map(float, tile_data[1].split(',')))
        tile_triggers_required = tile_data[2]

        # Ensure the drop name exists in the tile triggers
        if drop_name not in tile_triggers:
            raise ValueError(f"Drop '{drop_name}' is not a valid trigger for tile ID {tile_id}.")

        # Calculate the reduction amount using the drop trigger weight
        drop_index = tile_triggers.index(drop_name)
        drop_weight = tile_trigger_weights[drop_index]
        reduction_amount = drop_weight / tile_triggers_required

        # Update the player's partial completion, reducing by the calculated amount
        cursor.execute('''
            UPDATE partial_completions 
            SET partial_completion = partial_completion - %s 
            WHERE player_id = (
                SELECT player_id FROM players WHERE lower(player_name) = lower(%s)
            ) AND tile_id = %s
        ''', (reduction_amount, player_name, tile_id))

        # Delete the relevant drop
        cursor.execute("DELETE FROM relevant_drops WHERE relevant_drops_pk = %s", (relevant_drops_pk,))

        # Delete the associated drop in the drops table
        cursor.execute("DELETE FROM drops WHERE drops_pk = (SELECT drops_pk FROM relevant_drops WHERE relevant_drops_pk = %s)", (relevant_drops_pk,))

        # Commit



def change_player_team(player_id, new_team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chats SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE drops SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE killcount SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        # Banked tile contribution stays with the team it was
        # earned for, even if the player later changes teams.
        cursor.execute("UPDATE relevant_drops SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE players SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE manual_tile_progress SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        conn.commit()


def reset_tables():
    # Drop all tables
    print("connecting to db")
    conn = connect()
    print("connected")
    cursor = conn.cursor()
    # Get the list of all tables
    cursor.execute(
        "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';")
    tables = cursor.fetchall()

    # Drop each table
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table[0]} CASCADE;")

    print("All tables dropped successfully.")
    print("Recreating now...")
    cursor.execute('''
        CREATE TABLE users (
            user_id SERIAL PRIMARY KEY,
            username text NOT NULL,
            email text UNIQUE,
            password text NOT NULL,
            is_admin boolean NOT NULL DEFAULT FALSE,
            account_role TEXT NOT NULL DEFAULT 'PLAYER',
            player_id INTEGER,
            CONSTRAINT users_account_role_check
                CHECK (
                    account_role IN (
                        'PLAYER',
                        'ADMIN',
                        'ORGANISER'
                    )
                )
        )
        ''')

    cursor.execute('''
        CREATE TABLE dashboard_link_codes (
            user_id INTEGER PRIMARY KEY,
            code_hash TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMPTZ NOT NULL,
            FOREIGN KEY (user_id)
                REFERENCES users(user_id)
                ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE UNIQUE INDEX idx_users_username_ci
        ON users (LOWER(BTRIM(username)))
    ''')

    cursor.execute('''
        CREATE UNIQUE INDEX idx_users_player_id
        ON users (player_id)
        WHERE player_id IS NOT NULL
    ''')

    cursor.execute('''
        CREATE TABLE bingo_config (
            config_id SMALLINT PRIMARY KEY
                CHECK (config_id = 1),
            wom_competition_id BIGINT,
            wom_competition_starts_at TIMESTAMPTZ,
            wom_competition_ends_at TIMESTAMPTZ,
            evidence_codeword TEXT
        )
        ''')


    cursor.execute('''
        CREATE TABLE wom_refresh_audit (
            refresh_id BIGSERIAL PRIMARY KEY,
            requested_by_user_id INTEGER,
            requested_by_username TEXT,
            requested_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            competition_id BIGINT,
            metrics_processed INTEGER NOT NULL DEFAULT 0,
            players_processed INTEGER NOT NULL DEFAULT 0,
            tiles_completed INTEGER NOT NULL DEFAULT 0,
            warning_count INTEGER NOT NULL DEFAULT 0,
            no_competition BOOLEAN NOT NULL DEFAULT FALSE,
            FOREIGN KEY (requested_by_user_id)
                REFERENCES users(user_id)
                ON DELETE SET NULL,
            CHECK (metrics_processed >= 0),
            CHECK (players_processed >= 0),
            CHECK (tiles_completed >= 0),
            CHECK (warning_count >= 0)
        )
        ''')


    # Create the 'drops' table

    cursor.execute('''
            CREATE TABLE teams (
                team_name text,
                team_points real,
                team_webhook text,
                team_id SERIAL PRIMARY KEY,
                discord_role_id BIGINT,
                team_photo_path TEXT
            )
            ''')

    cursor.execute('''
            CREATE UNIQUE INDEX idx_teams_discord_role_id
            ON teams (discord_role_id)
            WHERE discord_role_id IS NOT NULL
        ''')

    cursor.execute('''
            CREATE TABLE players (
                player_id SERIAL PRIMARY KEY,
                player_name text,
                deaths integer,
                gp_gained integer,
                tiles_completed real,
                team_id integer,
                pet_count integer,
                discord_user_id BIGINT,
                player_points DOUBLE PRECISION NOT NULL DEFAULT 0,
                wom_player_id BIGINT,
                discord_display_name TEXT,
                discord_username TEXT,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE UNIQUE INDEX idx_players_discord_user_id
            ON players (discord_user_id)
            WHERE discord_user_id IS NOT NULL
            ''')


    cursor.execute('''
            CREATE UNIQUE INDEX idx_players_wom_player_id
            ON players (wom_player_id)
            WHERE wom_player_id IS NOT NULL
            ''')

    cursor.execute('''
        ALTER TABLE users
        ADD CONSTRAINT users_player_id_fkey
        FOREIGN KEY (player_id)
        REFERENCES players(player_id)
        ON DELETE SET NULL
    ''')

    cursor.execute('''
        CREATE TABLE dink_identities (
            dink_account_hash TEXT PRIMARY KEY,
            player_id INTEGER,
            observed_rsn TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            first_seen TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            linked_at TIMESTAMPTZ,
            FOREIGN KEY (player_id)
                REFERENCES players(player_id)
                ON DELETE SET NULL,
            CHECK (
                status IN (
                    'PENDING',
                    'LINKED',
                    'CONFLICT'
                )
            ),
            CHECK (
                (
                    status = 'LINKED'
                    AND player_id IS NOT NULL
                    AND linked_at IS NOT NULL
                )
                OR status != 'LINKED'
            )
        )
    ''')

    cursor.execute('''
        CREATE UNIQUE INDEX
            idx_dink_identities_linked_player
        ON dink_identities (player_id)
        WHERE
            status = 'LINKED'
            AND player_id IS NOT NULL
    ''')

    cursor.execute('''
        CREATE TABLE dink_events (
            event_id BIGSERIAL PRIMARY KEY,
            event_fingerprint TEXT NOT NULL,
            duplicate_of_event_id BIGINT,
            dink_account_hash TEXT,
            player_name TEXT,
            player_id INTEGER,
            event_type TEXT,
            raw_payload JSONB NOT NULL,
            screenshot_path TEXT,
            screenshot_sha256 TEXT,
            status TEXT NOT NULL DEFAULT 'RECEIVED',
            received_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMPTZ,
            FOREIGN KEY (duplicate_of_event_id)
                REFERENCES dink_events(event_id)
                ON DELETE SET NULL,
            FOREIGN KEY (player_id)
                REFERENCES players(player_id)
                ON DELETE SET NULL,
            CHECK (
                status IN (
                    'RECEIVED',
                    'PENDING_IDENTITY',
                    'PROCESSED',
                    'IGNORED',
                    'REJECTED',
                    'ERROR'
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_dink_events_fingerprint
        ON dink_events (
            event_fingerprint,
            received_at
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_dink_events_identity
        ON dink_events (
            dink_account_hash,
            player_name,
            received_at
        )
    ''')

    cursor.execute('''
        CREATE TABLE staff_review_decisions (
            decision_id BIGSERIAL PRIMARY KEY,
            subject_type TEXT NOT NULL,
            subject_id BIGINT NOT NULL,
            decision TEXT NOT NULL,
            review_source TEXT NOT NULL,
            reviewer_id BIGINT NOT NULL,
            reviewer_name TEXT NOT NULL,
            reason TEXT,
            reason_code TEXT,
            audit_only BOOLEAN NOT NULL DEFAULT FALSE,
            decided_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                subject_type,
                subject_id
            ),
            CHECK (
                subject_type IN (
                    'DINK_EVENT',
                    'MANUAL_EVIDENCE'
                )
            ),
            CHECK (
                decision IN (
                    'ACCEPT',
                    'REJECT'
                )
            ),
            CHECK (
                review_source IN (
                    'WEB',
                    'DISCORD'
                )
            ),
            CHECK (
                reason_code IN (
                    'INSUFFICIENT_EVIDENCE',
                    'WRONG_ITEM_OR_ACTIVITY',
                    'DUPLICATE_EVIDENCE',
                    'WRONG_PLAYER_OR_ACCOUNT',
                    'WRONG_TILE_OR_CONDITION',
                    'DOES_NOT_MEET_REQUIREMENTS',
                    'OTHER'
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE TABLE dink_auth_audit (
            audit_id BIGSERIAL PRIMARY KEY,
            failure_reason TEXT NOT NULL,
            claimed_player_name TEXT,
            claimed_dink_account_hash TEXT,
            claimed_event_type TEXT,
            request_format TEXT NOT NULL,
            source_ip TEXT,
            user_agent TEXT,
            received_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            CHECK (
                failure_reason IN (
                    'MISSING_SECRET',
                    'INVALID_SECRET',
                    'SERVER_MISCONFIGURED'
                )
            ),
            CHECK (
                request_format IN (
                    'JSON',
                    'MULTIPART',
                    'OTHER'
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_dink_auth_audit_received_at
        ON dink_auth_audit (received_at DESC)
    ''')


    cursor.execute('''
            CREATE TABLE wom_metric_state (
                competition_id BIGINT NOT NULL,
                player_id INTEGER NOT NULL,
                metric TEXT NOT NULL,
                last_processed_gain BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (
                    competition_id,
                    player_id,
                    metric
                ),
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE TABLE drops (
                team_id integer,
                player_id integer,
                player_name text,
                drop_name text,
                drop_value real,
                drop_quantity integer,
                drop_source text,
                drops_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )
        ''')

    cursor.execute('''
            CREATE TABLE killcount (
                player_id integer,
                team_id integer,
                boss_name text,
                kills integer,
                killcount_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )''')

    cursor.execute('''
            CREATE TABLE tiles (
                tile_id SERIAL PRIMARY KEY,
                tile_name text,
                tile_type text,
                tile_triggers text,
                tile_trigger_weights text,
                tile_unique_drops boolean,
                tile_triggers_required int,
                tile_repetition int,
                tile_points real,
                tile_rules text,
                board_coordinate text,
                CONSTRAINT tiles_board_coordinate_check
                CHECK (
                    board_coordinate IS NULL
                    OR board_coordinate ~ '^[A-E][1-5]$'
                ),
                CONSTRAINT tiles_board_coordinate_unique
                UNIQUE (board_coordinate)
            )
            ''')

    cursor.execute('''
            CREATE TABLE tile_conditions (
                condition_id SERIAL PRIMARY KEY,
                tile_id INTEGER NOT NULL,
                completion_path INTEGER NOT NULL,
                condition_type TEXT NOT NULL,
                condition_trigger TEXT,
                target BIGINT NOT NULL DEFAULT 1,
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE CASCADE,
                CHECK (completion_path >= 1),
                CHECK (target > 0),
                CHECK (
                    condition_type IN (
                        'KILLCOUNT',
                        'EXPERIENCE',
                        'METRIC',
                        'DROP',
                        'PET',
                        'MANUAL'
                    )
                )
            )
        ''')

    cursor.execute('''
            CREATE TABLE wom_condition_state (
                competition_id BIGINT NOT NULL,
                player_id INTEGER NOT NULL,
                condition_id INTEGER NOT NULL,
                last_processed_gain BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (
                    competition_id,
                    player_id,
                    condition_id
                ),
                FOREIGN KEY (player_id)
                    REFERENCES players(player_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE CASCADE
            )
        ''')

    cursor.execute('''
            CREATE TABLE tile_completion_paths (
                tile_id INTEGER NOT NULL,
                completion_path INTEGER NOT NULL,
                route_mode TEXT NOT NULL DEFAULT 'ALL',
                route_target BIGINT,
                require_unique BOOLEAN NOT NULL DEFAULT FALSE,
                PRIMARY KEY (
                    tile_id,
                    completion_path
                ),
                FOREIGN KEY (tile_id)
                    REFERENCES tiles(tile_id)
                    ON DELETE CASCADE,
                CHECK (completion_path >= 1),
                CHECK (
                    route_mode IN (
                        'ALL',
                        'SUM',
                        'N_OF'
                    )
                ),
                CHECK (
                    (
                        route_mode = 'ALL'
                        AND route_target IS NULL
                    )
                    OR
                    (
                        route_mode IN ('SUM', 'N_OF')
                        AND route_target > 0
                    )
                ),
                CHECK (
                    route_mode = 'N_OF'
                    OR require_unique = FALSE
                )
            )
        ''')

    cursor.execute('''
            CREATE TABLE tile_condition_progress (
                team_id INTEGER NOT NULL,
                condition_id INTEGER NOT NULL,
                progress BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (
                    team_id,
                    condition_id
                ),
                FOREIGN KEY (team_id)
                    REFERENCES teams(team_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (condition_id)
                    REFERENCES tile_conditions(condition_id)
                    ON DELETE CASCADE,
                CHECK (progress >= 0)
            )
        ''')

    cursor.execute('''
        CREATE TABLE manual_evidence (
            evidence_id BIGSERIAL PRIMARY KEY,
            player_id INTEGER,
            credited_player_name TEXT,
            team_id INTEGER,
            tile_id INTEGER,
            condition_id INTEGER,
            amount BIGINT NOT NULL DEFAULT 1,
            tile_points_at_submission REAL,
            banked_total_at_submission NUMERIC(18,12),
            tile_name_at_submission TEXT,
            evidence_codeword_at_submission TEXT,
            description TEXT,
            evidence_path TEXT NOT NULL,
            evidence_sha256 TEXT NOT NULL,
            submission_source TEXT NOT NULL,
            submitter_id BIGINT NOT NULL,
            submitter_name TEXT NOT NULL,
            discord_guild_id BIGINT,
            discord_channel_id BIGINT,
            discord_message_id BIGINT,
            evidence_author_id BIGINT,
            evidence_author_name TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            submitted_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id)
                REFERENCES players(player_id)
                ON DELETE SET NULL,
            FOREIGN KEY (team_id)
                REFERENCES teams(team_id)
                ON DELETE SET NULL,
            FOREIGN KEY (tile_id)
                REFERENCES tiles(tile_id)
                ON DELETE SET NULL,
            FOREIGN KEY (condition_id)
                REFERENCES tile_conditions(condition_id)
                ON DELETE SET NULL,
            CHECK (amount > 0),
            CHECK (
                submission_source IN (
                    'DISCORD',
                    'WEB'
                )
            ),
            CHECK (
                status IN (
                    'PENDING',
                    'ACCEPTED',
                    'REJECTED'
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE TABLE manual_evidence_path_snapshots (
            evidence_id BIGINT NOT NULL,
            completion_path INTEGER NOT NULL,
            route_mode TEXT NOT NULL,
            route_target BIGINT,
            require_unique BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (
                evidence_id,
                completion_path
            ),
            FOREIGN KEY (evidence_id)
                REFERENCES manual_evidence(evidence_id)
                ON DELETE CASCADE,
            CHECK (completion_path >= 1),
            CHECK (
                route_mode IN (
                    'ALL',
                    'SUM',
                    'N_OF'
                )
            ),
            CHECK (
                (
                    route_mode = 'ALL'
                    AND route_target IS NULL
                )
                OR
                (
                    route_mode IN ('SUM', 'N_OF')
                    AND route_target > 0
                )
            ),
            CHECK (
                route_mode = 'N_OF'
                OR require_unique = FALSE
            )
        )
    ''')

    cursor.execute('''
        CREATE TABLE manual_evidence_condition_snapshots (
            evidence_id BIGINT NOT NULL,
            condition_id INTEGER NOT NULL,
            completion_path INTEGER NOT NULL,
            condition_type TEXT NOT NULL,
            condition_trigger TEXT,
            target BIGINT NOT NULL,
            progress BIGINT NOT NULL,
            selected_condition BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (
                evidence_id,
                condition_id
            ),
            FOREIGN KEY (evidence_id)
                REFERENCES manual_evidence(evidence_id)
                ON DELETE CASCADE,
            CHECK (completion_path >= 1),
            CHECK (target > 0),
            CHECK (progress >= 0),
            CHECK (
                condition_type IN (
                    'KILLCOUNT',
                    'EXPERIENCE',
                    'METRIC',
                    'DROP',
                    'PET',
                    'MANUAL'
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE UNIQUE INDEX
            idx_manual_evidence_snapshot_selected_condition
        ON manual_evidence_condition_snapshots (
            evidence_id
        )
        WHERE selected_condition = TRUE
    ''')

    cursor.execute('''
        CREATE TABLE dink_event_progress (
            progress_id BIGSERIAL PRIMARY KEY,
            event_id BIGINT NOT NULL,
            team_id INTEGER,
            condition_id INTEGER NOT NULL,
            tile_id INTEGER NOT NULL,
            completion_path INTEGER NOT NULL,
            trigger TEXT NOT NULL,
            amount BIGINT NOT NULL,
            counted_amount BIGINT NOT NULL DEFAULT 0,
            raw_progress BIGINT NOT NULL,
            route_progress NUMERIC(18, 12) NOT NULL,
            credited NUMERIC(18, 12) NOT NULL,
            banked_total NUMERIC(18, 12) NOT NULL,
            ready BOOLEAN NOT NULL,
            completed BOOLEAN NOT NULL,
            condition_type_snapshot TEXT,
            condition_trigger_snapshot TEXT,
            condition_target_snapshot BIGINT,
            route_mode_snapshot TEXT,
            route_target_snapshot BIGINT,
            require_unique_snapshot BOOLEAN,
            state TEXT NOT NULL DEFAULT 'APPLIED',
            processed_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id)
                REFERENCES dink_events(event_id)
                ON DELETE CASCADE,
            FOREIGN KEY (condition_id)
                REFERENCES tile_conditions(condition_id)
                ON DELETE CASCADE,
            FOREIGN KEY (tile_id)
                REFERENCES tiles(tile_id)
                ON DELETE CASCADE,
            CHECK (amount > 0),
            CHECK (counted_amount >= 0),
            CHECK (
                state IN (
                    'APPLIED',
                    'SUPPRESSED_COMPLETED',
                    'INVALIDATED'
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_dink_event_progress_event
        ON dink_event_progress (event_id)
    ''')

    cursor.execute('''
        CREATE TABLE manual_evidence_progress (
            progress_id BIGSERIAL PRIMARY KEY,
            evidence_id BIGINT NOT NULL UNIQUE,
            condition_id INTEGER,
            tile_id INTEGER,
            completion_path INTEGER NOT NULL,
            amount BIGINT NOT NULL,
            counted_amount BIGINT NOT NULL DEFAULT 0,
            raw_progress BIGINT NOT NULL,
            route_progress NUMERIC(18, 12) NOT NULL,
            actual_contribution NUMERIC(18, 12) NOT NULL
                DEFAULT 0,
            completion_remainder NUMERIC(18, 12) NOT NULL
                DEFAULT 0,
            normal_player_credit NUMERIC(18, 12) NOT NULL
                DEFAULT 0,
            potential_contribution NUMERIC(18, 12) NOT NULL
                DEFAULT 0,
            lost_mvp_contribution NUMERIC(18, 12) NOT NULL
                DEFAULT 0,
            banked_total NUMERIC(18, 12) NOT NULL,
            ready BOOLEAN NOT NULL,
            completed BOOLEAN NOT NULL,
            processed_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id)
                REFERENCES manual_evidence(evidence_id)
                ON DELETE CASCADE,
            FOREIGN KEY (condition_id)
                REFERENCES tile_conditions(condition_id)
                ON DELETE SET NULL,
            FOREIGN KEY (tile_id)
                REFERENCES tiles(tile_id)
                ON DELETE SET NULL,
            CHECK (amount > 0),
            CHECK (counted_amount >= 0)
        )
    ''')

    cursor.execute('''
        CREATE TABLE player_tile_credits (
            credit_id BIGSERIAL PRIMARY KEY,
            player_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            tile_id INTEGER NOT NULL,
            contribution NUMERIC(18, 12) NOT NULL,
            points_awarded NUMERIC(18, 12) NOT NULL,
            credit_type TEXT NOT NULL,
            evidence_id BIGINT,
            awarded_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            CHECK (
                contribution > 0
                AND contribution <= 1
            ),
            CHECK (points_awarded >= 0),
            CHECK (
                credit_type IN (
                    'TILE_COMPLETION',
                    'LATE_REVIEW'
                )
            ),
            CHECK (
                (
                    credit_type = 'TILE_COMPLETION'
                    AND evidence_id IS NULL
                )
                OR
                (
                    credit_type = 'LATE_REVIEW'
                    AND evidence_id IS NOT NULL
                )
            )
        )
    ''')

    cursor.execute('''
        CREATE UNIQUE INDEX
            idx_player_tile_credits_evidence
        ON player_tile_credits (evidence_id)
        WHERE evidence_id IS NOT NULL
    ''')

    cursor.execute('''
        CREATE INDEX
            idx_player_tile_credits_player_tile
        ON player_tile_credits (
            player_id,
            team_id,
            tile_id
        )
    ''')

    cursor.execute('''
            CREATE TABLE drop_whitelist (
                drop_name text PRIMARY KEY,
                tile_id int,
                FOREIGN KEY (tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE
            )''')

    cursor.execute('''
        CREATE TABLE evidence_invalidations (
            invalidation_id BIGSERIAL PRIMARY KEY,
            subject_type TEXT NOT NULL,
            subject_id BIGINT NOT NULL,
            reason_code TEXT NOT NULL,
            details TEXT,
            review_source TEXT NOT NULL,
            reviewer_id BIGINT NOT NULL,
            reviewer_name TEXT NOT NULL,
            invalidated_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                subject_type,
                subject_id
            ),
            CHECK (
                subject_type IN (
                    'DINK_EVENT',
                    'MANUAL_EVIDENCE'
                )
            ),
            CHECK (
                reason_code IN (
                    'INCORRECT_EVIDENCE',
                    'WRONG_ITEM_OR_ACTIVITY',
                    'DUPLICATE_EVIDENCE',
                    'WRONG_PLAYER_OR_ACCOUNT',
                    'WRONG_TILE_OR_CONDITION',
                    'ADMINISTRATIVE_TEST_CORRECTION',
                    'OTHER'
                )
            ),
            CHECK (
                review_source IN (
                    'WEB',
                    'DISCORD'
                )
            )
        )
    ''')

    cursor.execute('''
            CREATE TABLE completed_tiles (
                team_id integer,
                tile_id integer,
                completed_tile_pk SERIAL PRIMARY KEY,
                completed_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                points_awarded NUMERIC(18, 12),
                FOREIGN KEY (tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE UNIQUE INDEX
                idx_completed_tiles_team_tile
            ON completed_tiles (
                team_id,
                tile_id
            )
            ''')

    cursor.execute('''
        CREATE TABLE completed_tile_partial_snapshot (
            snapshot_id BIGSERIAL PRIMARY KEY,
            completed_tile_pk INTEGER NOT NULL,
            player_id INTEGER,
            partial_completion NUMERIC(18, 12) NOT NULL,
            FOREIGN KEY (completed_tile_pk)
                REFERENCES completed_tiles(completed_tile_pk)
                ON DELETE CASCADE,
            CHECK (partial_completion > 0)
        )
    ''')

    cursor.execute('''
        CREATE INDEX
            idx_completed_tile_partial_snapshot_completion
        ON completed_tile_partial_snapshot (
            completed_tile_pk
        )
    ''')

    cursor.execute('''
            CREATE TABLE manual_tile_progress (
                player_id integer,
                team_id integer,
                tile_id integer,
                progress real,
                manual_tile_progress_pk SERIAL PRIMARY KEY,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY (tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE TABLE requests (
                request_id SERIAL PRIMARY KEY,
                team_name text,
                player_name text,
                tile_name text, 
                item_name text,
                evidence text
            )
            ''')

    cursor.execute('''
            CREATE TABLE chats (
                player_id integer,
                team_id integer,
                tile_id integer,
                chat text,
                chats_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE,
                FOREIGN KEY(tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE                
            )
            ''')

    cursor.execute('''
            CREATE TABLE partial_completions (
                team_id integer,
                tile_id integer,
                player_id integer,
                partial_completion NUMERIC(18, 12),
                partial_completion_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY(tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE SET NULL
            )
            ''')

    cursor.execute('''
            CREATE UNIQUE INDEX
                idx_partial_completions_player_team_tile
            ON partial_completions (
                player_id,
                team_id,
                tile_id
            )
            ''')

    cursor.execute('''
            CREATE TABLE relevant_drops (
                team_id integer,
                player_id integer,
                tile_id integer,
                tile_name text,
                drop_name text,
                player_name text,
                drops_pk INTEGER,
                relevant_drops_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(drops_pk) REFERENCES  drops(drops_pk) ON DELETE CASCADE,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY(tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE
            )
            ''')

    # Save (commit) the changes
    conn.commit()
    print("Finished creating!")

    # Close the connection
    conn.close()


def read_tiles(file_name):
    tiles = []
    with open(file_name, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            tiles.append(row)

    for i in range(1, len(tiles)):
        whitelist_items = []
        tile = tiles[i]
        tile_name = tile[0]
        tile_type = tile[1]
        tile_triggers = tile[2]
        for a in tile_triggers.split('/'):
            for b in a.split(','):
                whitelist_items.append(b)
        tile_trigger_weights = tile[3]
        tile_unique_drops = tile[4]
        tile_triggers_required = tile[5]
        tile_repetition = tile[6]
        tile_points = tile[7]
        tile_rules = tile[8]
        add_tile(tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
                 tile_repetition, tile_points, tile_rules)
        tile = Tile(get_tile_by_name(tile_name))
        for item in whitelist_items:
            if item.strip() == "":
                continue
            add_drop_whitelist(item.strip(), tile.tile_id)


def read_teams(file_name):
    teams = []
    with open(file_name, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            teams.append(row)

    for i in range(1, len(teams)):
        team = teams[i]
        team_name = team[0]
        team_webhook = team[1]
        players = team[2:]
        add_team(team_name, 0, team_webhook)
        team_obj = db_entities.Team(get_team_by_name(team_name))
        for player in players:
            player = player.strip()
            if player == "":
                continue
            add_player(player, 0, 0, 0, team_obj.team_id, 0)

    return teams

def get_relevant_drop_by_id(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE relevant_drops_pk = %s", (drop_pk,))
        return cursor.fetchone()


def update_relevant_drop(relevant_drops_pk, new_tile_name, new_drop_name, new_player_name):
    with connect() as conn:
        cursor = conn.cursor()

        # Fetch tile_id from the new tile_name
        cursor.execute("SELECT tile_id FROM tiles WHERE lower(tile_name) = lower(%s)", (new_tile_name,))
        tile = cursor.fetchone()
        if not tile:
            raise ValueError(f"Tile with name {new_tile_name} does not exist.")
        new_tile_id = tile[0]

        # Get the trigger value and trigger weight for the tile
        cursor.execute('''
            SELECT tile_triggers, tile_trigger_weights, tile_triggers_required
            FROM tiles 
            WHERE tile_id = %s
        ''', (new_tile_id,))
        tile_data = cursor.fetchone()
        tile_triggers = tile_data[0].split(',')  # Each trigger can be a group
        tile_trigger_weights = list(map(float, tile_data[1].split(',')))
        tile_trigger_weight_required = tile_data[2]

        # Parse triggers and associate them with weights
        trigger_to_weight_map = {}
        for i, trigger_group in enumerate(tile_triggers):
            triggers = [t.strip() for t in trigger_group.split('/')]  # Split by '/'
            weight = tile_trigger_weights[i]
            for trigger in triggers:
                trigger_to_weight_map[trigger] = weight

        # Ensure the new drop name exists in the tile triggers
        if new_drop_name not in trigger_to_weight_map:
            raise ValueError(f"Drop '{new_drop_name}' is not a valid trigger for tile '{new_tile_name}'.")

        # Get the trigger weight for this drop
        drop_weight = trigger_to_weight_map[new_drop_name]

        # Fetch the old player associated with this relevant drop and the old tile
        cursor.execute('''
            SELECT player_name, tile_id, player_id 
            FROM relevant_drops 
            WHERE relevant_drops_pk = %s
        ''', (relevant_drops_pk,))
        old_relevant_drop = cursor.fetchone()
        old_player_name = old_relevant_drop[0]
        old_tile_id = old_relevant_drop[1]
        old_player_id = old_relevant_drop[2]

        # Calculate the reduction amount for the old player's partial completion
        reduction_amount = drop_weight / tile_trigger_weight_required

        # Reduce the old player's partial completion for the tile
        cursor.execute('''
            UPDATE partial_completions 
            SET partial_completion = partial_completion - %s 
            WHERE player_id = %s AND tile_id = %s
        ''', (reduction_amount, old_player_id, old_tile_id))

        # Fetch the new player's player_id and team_id
        cursor.execute('''
            SELECT player_id, team_id 
            FROM players 
            WHERE lower(player_name) = lower(%s)
        ''', (new_player_name,))
        new_player = cursor.fetchone()
        if not new_player:
            raise ValueError(f"Player with name {new_player_name} does not exist.")
        new_player_id, new_team_id = new_player

        # Add the completion amount to the new player
        cursor.execute('''
            UPDATE partial_completions 
            SET partial_completion = partial_completion + %s 
            WHERE player_id = %s AND tile_id = %s
        ''', (reduction_amount, new_player_id, new_tile_id))

        # Fetch the drop details (quantity and value) for calculating the gold gained
        cursor.execute('''
            SELECT drop_quantity, drop_value 
            FROM drops 
            WHERE drops_pk = (
                SELECT drops_pk FROM relevant_drops WHERE relevant_drops_pk = %s
            )
        ''', (relevant_drops_pk,))
        drop_data = cursor.fetchone()
        drop_quantity, drop_value = drop_data

        # Calculate the total gold for this drop
        gold_gained = drop_quantity * drop_value

        # Remove the gold gained from the old player
        cursor.execute('''
            UPDATE players 
            SET gp_gained = gp_gained - %s 
            WHERE player_id = %s
        ''', (gold_gained, old_player_id))

        # Add the gold gained to the new player
        cursor.execute('''
            UPDATE players 
            SET gp_gained = gp_gained + %s 
            WHERE player_id = %s
        ''', (gold_gained, new_player_id))

        # Update the relevant drop record with the new details (player_id, team_id, tile_id, tile_name, drop_name, player_name)
        cursor.execute('''
            UPDATE relevant_drops
            SET tile_id = %s, tile_name = %s, drop_name = %s, player_name = %s, player_id = %s, team_id = %s
            WHERE relevant_drops_pk = %s
        ''', (new_tile_id, new_tile_name, new_drop_name, new_player_name, new_player_id, new_team_id, relevant_drops_pk))

        # Also update the drop name, player, and team in the drops table for the relevant player
        cursor.execute('''
            UPDATE drops
            SET drop_name = %s, team_id = %s, player_id = %s
            WHERE drops_pk = (
                SELECT drops_pk FROM relevant_drops WHERE relevant_drops_pk = %s
            )
        ''', (new_drop_name, new_team_id, new_player_id, relevant_drops_pk))

        conn.commit()




def get_tile_triggers():
    """
    Fetches all tiles and their associated triggers from the database and
    returns them as a dictionary where the key is the tile name and the value is a list of triggers.
    """
    with connect() as conn:
        cursor = conn.cursor()

        # Query to fetch tile names and their associated triggers
        cursor.execute("SELECT tile_name, tile_triggers FROM tiles")

        # Fetch all rows from the result
        rows = cursor.fetchall()

        # Create a dictionary mapping tile_name to a list of triggers
        tile_triggers = {}
        for row in rows:
            tile_name = row[0]
            triggers = [trigger.strip() for trigger in row[1].replace('/', ',').split(',') if trigger]  # Split and strip
            tile_triggers[tile_name] = triggers

    return tile_triggers


def get_tile_types():
    """
    Fetches all tiles and their types from the database.
    Returns a dictionary where the key is the tile name and the value is its type.
    """
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tile_name, tile_type FROM tiles")
        rows = cursor.fetchall()

        tile_types = {}
        for row in rows:
            tile_name = row[0]
            tile_type = row[1]
            tile_types[tile_name] = tile_type

    return tile_types


def get_drop_by_id(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE drops_pk = %s", (drop_pk,))
        return cursor.fetchone()


def update_drop(drop_pk, new_tile_name, new_drop_name, new_player_name, new_quantity, new_value):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE drops
            SET tile_name = %s, drop_name = %s, player_name = %s, drop_quantity = %s, drop_value = %s
            WHERE drops_pk = %s
        ''', (new_tile_name, new_drop_name, new_player_name, new_quantity, new_value, drop_pk))
        conn.commit()

def delete_drop(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE drops_pk = %s", (drop_pk,))
        conn.commit()


def get_relevant_drops_by_item_name_and_team_id(item, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops where team_id = %s and lower(drop_name) = lower(%s)", (team_id, item,))
        return cursor.fetchall()