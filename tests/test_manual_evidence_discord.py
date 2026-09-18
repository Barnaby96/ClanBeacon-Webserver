import asyncio
from types import SimpleNamespace

import pytest

from cogs.AdminCog import AdminCog
from cogs.UserCog import (
    ManualEvidenceConditionSelect,
    ManualEvidenceConditionView,
    ManualEvidenceDetailsModal,
    ManualEvidenceSubmissionState,
    ManualEvidenceTileSelect,
    UserCog
)

from utils import database, manual_evidence_files
from utils.branding import BOT_NAME


class FakeContext:
    def __init__(
        self,
        author_id=12345,
        display_name="Discord Tester",
        roles=None
    ):
        self.author = SimpleNamespace(
            id=author_id,
            display_name=display_name,
            roles=roles or []
        )

        self.guild = SimpleNamespace(
            id=111
        )

        self.channel = SimpleNamespace(
            id=222
        )

        self.deferred = False
        self.responses = []

    async def defer(
        self,
        ephemeral=False
    ):
        self.deferred = True
        self.defer_ephemeral = ephemeral

    async def respond(
        self,
        content=None,
        **kwargs
    ):
        self.responses.append({
            "content": content,
            **kwargs
        })


class FakeAttachment:
    def __init__(
        self,
        filename,
        data=b"fake attachment bytes"
    ):
        self.filename = filename
        self.data = data
        self.read_calls = 0

    async def read(self):
        self.read_calls += 1
        return self.data


def run_submit_evidence(
    ctx,
    screenshot,
    player=None
):
    cog = UserCog(
        bot=None
    )

    return asyncio.run(
        UserCog.submit_evidence.callback(
            cog,
            ctx,
            screenshot,
            player
        )
    )


def run_review_submission(ctx):
    cog = AdminCog(
        bot=None
    )

    return asyncio.run(
        AdminCog.review_submission.callback(
            cog,
            ctx
        )
    )


def run_review_invalidation(ctx):
    cog = AdminCog(
        bot=None
    )

    return asyncio.run(
        AdminCog.review_invalidation.callback(
            cog,
            ctx
        )
    )


def test_review_invalidation_rejects_non_organiser(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: pytest.fail(
            "A non-organiser should be refused "
            "before the invalidation queue is queried."
        )
    )

    ctx = FakeContext()

    run_review_invalidation(
        ctx
    )

    assert ctx.deferred is False
    assert len(ctx.responses) == 1
    assert (
        ctx.responses[0]["content"]
        == (
            "Only bingo organisers can "
            "invalidate submissions."
        )
    )
    assert ctx.responses[0]["ephemeral"] is True


def test_review_invalidation_organiser_sees_empty_queue(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    queue_queries = []

    def get_invalidation_rows():
        queue_queries.append(
            True
        )
        return []

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        get_invalidation_rows
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    assert queue_queries == [True]
    assert ctx.deferred is True
    assert ctx.defer_ephemeral is True
    assert len(ctx.responses) == 1
    assert (
        ctx.responses[0]["content"]
        == (
            "There are no accepted submissions "
            "available to invalidate."
        )
    )
    assert ctx.responses[0]["ephemeral"] is True


def test_review_submission_rejects_non_organiser(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: pytest.fail(
            "A non-organiser should be refused "
            "before the review queue is queried."
        )
    )

    ctx = FakeContext()

    run_review_submission(
        ctx
    )

    assert ctx.deferred is False
    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert (
        response["content"]
        == "Only bingo organisers can review submissions."
    )


def test_review_submission_organiser_sees_empty_queue(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    queue_queries = []

    def get_review_rows():
        queue_queries.append(True)
        return []

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        get_review_rows
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    assert queue_queries == [True]
    assert ctx.deferred is True
    assert ctx.defer_ephemeral is True
    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert (
        response["content"]
        == "There are no submissions ready for review."
    )


def test_review_submission_shows_first_pending_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "First Player",
            "team_name": "Team Zamorak",
            "tile_name": "First Test Tile",
            "condition_trigger": "FIRST_TEST_DROP",
            "amount": 2,
            "description": "First submission notes",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        },
        {
            "evidence_id": 502,
            "credited_player_name": "Second Player",
            "team_name": "Team Saradomin",
            "tile_name": "Second Test Tile",
            "condition_trigger": "SECOND_TEST_DROP",
            "amount": 1,
            "description": "Second submission notes",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 88888,
            "evidence_codeword_at_submission": (
                "Different Word"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    assert ctx.deferred is True
    assert ctx.defer_ephemeral is True
    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert response["view"].selected_evidence_id == 501
    assert "file" not in response

    embed_fields = {
        field.name: field.value
        for field in response["embed"].fields
    }

    assert embed_fields["Player"] == "First Player"
    assert embed_fields["Team"] == "Team Zamorak"
    assert embed_fields["Amount"] == "2"
    assert embed_fields["Tile"] == "First Test Tile"
    assert embed_fields["Part"] == "First Test Drop"
    assert (
        embed_fields["Evidence codeword"]
        == "Blackout Sky"
    )
    assert (
        embed_fields["Notes"]
        == "First submission notes"
    )
    assert (
        embed_fields["Submitted by"]
        == "Discord Tester on behalf of First Player"
    )


def test_review_invalidation_shows_first_accepted_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "First Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "First Accepted Tile",
            "condition_trigger": "FIRST_ACCEPTED_DROP",
            "amount": 2,
            "description": "First accepted evidence.",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        },
        {
            "evidence_id": 602,
            "credited_player_name": "Second Accepted Player",
            "team_name": "Team Seren",
            "tile_name": "Second Accepted Tile",
            "condition_trigger": "SECOND_ACCEPTED_DROP",
            "amount": 1,
            "description": "Second accepted evidence.",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 88888,
            "evidence_codeword_at_submission": (
                "Different Word"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    assert ctx.deferred is True
    assert ctx.defer_ephemeral is True
    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert response["view"].selected_evidence_id == 601
    assert "file" not in response

    embed_fields = {
        field.name: field.value
        for field in response["embed"].fields
    }

    assert embed_fields["Player"] == "First Accepted Player"
    assert embed_fields["Team"] == "Team Guthix"
    assert embed_fields["Amount"] == "2"
    assert embed_fields["Tile"] == "First Accepted Tile"
    assert embed_fields["Part"] == "First Accepted Drop"
    assert (
        embed_fields["Notes"]
        == "First accepted evidence."
    )


def test_review_invalidation_dropdown_selects_accepted_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "First Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "First Accepted Tile",
            "condition_trigger": "FIRST_ACCEPTED_DROP",
            "amount": 2,
            "description": "First accepted evidence.",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        },
        {
            "evidence_id": 602,
            "credited_player_name": "Second Accepted Player",
            "team_name": "Team Seren",
            "tile_name": "Second Accepted Tile",
            "condition_trigger": "SECOND_ACCEPTED_DROP",
            "amount": 1,
            "description": "Second accepted evidence.",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 88888,
            "evidence_codeword_at_submission": (
                "Different Word"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    select = next(
        child
        for child in review_view.children
        if hasattr(child, "options")
    )

    assert [
        option.value
        for option in select.options
    ] == [
        "601",
        "602"
    ]

    interaction = FakeInteraction(
        user_id=12345,
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    select._interaction = interaction
    select._selected_values = [
        "602"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert len(
        interaction.response.messages
    ) == 0

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert (
        edit["view"].selected_evidence_id
        == 602
    )

    assert edit["attachments"] == []
    assert "file" not in edit

    embed_fields = {
        field.name: field.value
        for field in edit["embed"].fields
    }

    assert (
        embed_fields["Player"]
        == "Second Accepted Player"
    )

    assert (
        embed_fields["Team"]
        == "Team Seren"
    )

    assert (
        embed_fields["Tile"]
        == "Second Accepted Tile"
    )

    assert (
        embed_fields["Part"]
        == "Second Accepted Drop"
    )

    assert (
        embed_fields["Evidence codeword"]
        == "Different Word"
    )

    assert (
        embed_fields["Notes"]
        == "Second accepted evidence."
    )


def test_review_submission_dropdown_selects_manual_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "First Player",
            "team_name": "Team Zamorak",
            "tile_name": "First Test Tile",
            "condition_trigger": "FIRST_TEST_DROP",
            "amount": 2,
            "description": "First submission notes",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        },
        {
            "evidence_id": 502,
            "credited_player_name": "Second Player",
            "team_name": "Team Saradomin",
            "tile_name": "Second Test Tile",
            "condition_trigger": "SECOND_TEST_DROP",
            "amount": 1,
            "description": "Second submission notes",
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 88888,
            "evidence_codeword_at_submission": (
                "Different Word"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    select = next(
        child
        for child in review_view.children
        if hasattr(child, "options")
    )

    assert [
        option.value
        for option in select.options
    ] == [
        "501",
        "502"
    ]

    interaction = FakeInteraction(
        user_id=12345,
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    select._interaction = interaction
    select._selected_values = [
        "502"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert len(
        interaction.response.messages
    ) == 0

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert (
        edit["view"].selected_evidence_id
        == 502
    )

    assert edit["attachments"] == []
    assert "file" not in edit

    embed_fields = {
        field.name: field.value
        for field in edit["embed"].fields
    }

    assert (
        embed_fields["Player"]
        == "Second Player"
    )

    assert (
        embed_fields["Team"]
        == "Team Saradomin"
    )

    assert (
        embed_fields["Tile"]
        == "Second Test Tile"
    )

    assert (
        embed_fields["Part"]
        == "Second Test Drop"
    )

    assert (
        embed_fields["Evidence codeword"]
        == "Different Word"
    )

    assert (
        embed_fields["Notes"]
        == "Second submission notes"
    )


def test_review_submission_rejects_different_reviewer(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    ctx = FakeContext(
        author_id=12345,
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    select = next(
        child
        for child in review_view.children
        if hasattr(child, "options")
    )

    interaction = FakeInteraction(
        user_id=54321,
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    select._interaction = interaction
    select._selected_values = [
        "501"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert len(
        interaction.response.messages
    ) == 1

    assert len(
        interaction.response.edits
    ) == 0

    response = interaction.response.messages[0]

    assert response["ephemeral"] is True
    assert (
        response["content"]
        == "This review panel belongs to another staff member."
    )


def test_review_submission_rejects_reviewer_after_role_removed(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 12345,
            "submitter_name": "Discord Tester",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    ctx = FakeContext(
        author_id=12345,
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    select = next(
        child
        for child in review_view.children
        if hasattr(child, "options")
    )

    interaction = FakeInteraction(
        user_id=12345,
        roles=[]
    )

    select._interaction = interaction
    select._selected_values = [
        "501"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert len(
        interaction.response.messages
    ) == 1

    assert len(
        interaction.response.edits
    ) == 0

    response = interaction.response.messages[0]

    assert response["ephemeral"] is True
    assert (
        response["content"]
        == "You no longer have permission to review submissions."
    )


def test_review_submission_accepts_manual_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    accept_calls = []

    from utils import completion_notifications

    notification_calls = []

    monkeypatch.setattr(
        completion_notifications,
        "notify_progress_completions",
        lambda progress_results: notification_calls.append(
            progress_results
        )
    )

    def accept_manual_evidence(**kwargs):
        accept_calls.append(
            kwargs
        )

        return {
            "status": "ACCEPTED",
            "audit_only": False,
            "late_review": False,
            "team_id": 2,
            "tile_id": 20,
            "newly_completed": True
        }

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        accept_manual_evidence
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert accept_calls == [
        {
            "evidence_id": 501,
            "review_source": "DISCORD",
            "reviewer_id": 12345,
            "reviewer_name": "Review Organiser",
            "award_lost_mvp": False
        }
    ]

    assert notification_calls == [
        [
            {
                "team_id": 2,
                "tile_id": 20,
                "completed": True
            }
        ]
    ]

    assert len(
        interaction.response.messages
    ) == 0

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        "✅ **Submission accepted**\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_accepts_audit_only_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: {
            "status": "ACCEPTED",
            "audit_only": True,
            "late_review": False
        }
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        "✅ **Submission accepted**\n\n"
        "Accepted for audit only because the tile changed "
        "after this submission was made. No points were "
        "awarded.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_accepts_late_review_without_mvp(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    from utils import completion_notifications

    notification_calls = []

    monkeypatch.setattr(
        completion_notifications,
        "notify_progress_completions",
        lambda progress_results: notification_calls.append(
            progress_results
        )
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: {
            "status": "ACCEPTED",
            "audit_only": False,
            "late_review": True,
            "lost_mvp_contribution": 2.5,
            "newly_completed": False
        }
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        "✅ **Submission accepted**\n\n"
        "The tile had already completed before this "
        "submission was reviewed.\n\n"
        "No discretionary MVP points were awarded.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []
    assert notification_calls == []


def test_review_submission_prompts_when_lost_mvp_available(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    preflight_calls = []

    def lost_mvp_preflight(evidence_id):
        preflight_calls.append(
            evidence_id
        )

        return {
            "status": "READY",
            "lost_mvp_available": True,
            "maximum_lost_mvp_contribution": 0.3,
            "maximum_lost_mvp_points": 1.2
        }

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lost_mvp_preflight
    )

    accept_calls = []

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: accept_calls.append(
            kwargs
        )
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert preflight_calls == [
        501
    ]

    assert accept_calls == []

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert (
        "Discretionary MVP available"
        in edit["content"]
    )

    assert (
        "**1.2 MVP points**"
        in edit["content"]
    )

    assert (
        "30% of the tile's personal credit"
        in edit["content"]
    )

    confirmation_view = edit["view"]

    assert confirmation_view is not None

    button_labels = {
        child.label
        for child in confirmation_view.children
    }

    assert button_labels == {
        "No - accept without MVP",
        "Yes - award MVP"
    }


def test_review_submission_preflight_failure_does_not_accept(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    def failed_preflight(evidence_id):
        raise ValueError(
            "Test preflight failure"
        )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        failed_preflight
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: pytest.fail(
            "Acceptance must not run when "
            "lost-MVP preflight fails."
        )
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert (
        interaction.response.messages
        == []
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        f"{BOT_NAME} could not safely determine whether "
        "discretionary MVP is available. The "
        "submission has not been accepted."
    )

    assert edit["view"] is None


def test_review_submission_lost_mvp_no_accepts_without_mvp(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": True,
            "maximum_lost_mvp_contribution": 0.3,
            "maximum_lost_mvp_points": 1.2
        }
    )

    accept_calls = []

    def accept_manual_evidence(**kwargs):
        accept_calls.append(
            kwargs
        )

        return {
            "status": "ACCEPTED",
            "audit_only": False,
            "late_review": True,
            "lost_mvp_contribution": 0.3,
            "late_review_points": 0
        }

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        accept_manual_evidence
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    prompt_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            prompt_interaction
        )
    )

    confirmation_view = (
        prompt_interaction
        .response
        .edits[0]["view"]
    )

    no_button = next(
        child
        for child in confirmation_view.children
        if getattr(
            child,
            "label",
            None
        ) == "No - accept without MVP"
    )

    decision_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        no_button.callback(
            decision_interaction
        )
    )

    assert accept_calls == [
        {
            "evidence_id": 501,
            "review_source": "DISCORD",
            "reviewer_id": 12345,
            "reviewer_name": "Review Organiser",
            "award_lost_mvp": False
        }
    ]

    assert len(
        decision_interaction.response.edits
    ) == 1

    edit = decision_interaction.response.edits[0]

    assert edit["content"] == (
        "✅ **Submission accepted**\n\n"
        "The tile had already completed before this "
        "submission was reviewed.\n\n"
        "No discretionary MVP points were awarded.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_lost_mvp_yes_awards_mvp(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": True,
            "maximum_lost_mvp_contribution": 0.3,
            "maximum_lost_mvp_points": 1.2
        }
    )

    accept_calls = []

    def accept_manual_evidence(**kwargs):
        accept_calls.append(
            kwargs
        )

        return {
            "status": "ACCEPTED",
            "audit_only": False,
            "late_review": True,
            "lost_mvp_contribution": 0.3,
            "late_review_points": 1.2
        }

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        accept_manual_evidence
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    prompt_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            prompt_interaction
        )
    )

    confirmation_view = (
        prompt_interaction
        .response
        .edits[0]["view"]
    )

    yes_button = next(
        child
        for child in confirmation_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Yes - award MVP"
    )

    decision_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        yes_button.callback(
            decision_interaction
        )
    )

    assert accept_calls == [
        {
            "evidence_id": 501,
            "review_source": "DISCORD",
            "reviewer_id": 12345,
            "reviewer_name": "Review Organiser",
            "award_lost_mvp": True
        }
    ]

    assert len(
        decision_interaction.response.edits
    ) == 1

    edit = decision_interaction.response.edits[0]

    assert edit["content"] == (
        "✅ **Submission accepted**\n\n"
        "The tile had already completed before this "
        "submission was reviewed.\n\n"
        "1.2 discretionary MVP points were awarded.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_completion_award_reports_mvp(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": True,
            "maximum_lost_mvp_contribution": 0.3,
            "maximum_lost_mvp_points": 1.2
        }
    )

    accept_calls = []

    def accept_manual_evidence(**kwargs):
        accept_calls.append(
            kwargs
        )

        return {
            "status": "ACCEPTED",
            "audit_only": False,
            "late_review": False,
            "lost_mvp_contribution": 0.3,
            "late_review_points": 1.2
        }

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        accept_manual_evidence
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    prompt_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            prompt_interaction
        )
    )

    confirmation_view = (
        prompt_interaction
        .response
        .edits[0]["view"]
    )

    yes_button = next(
        child
        for child in confirmation_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Yes - award MVP"
    )

    decision_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        yes_button.callback(
            decision_interaction
        )
    )

    assert accept_calls == [
        {
            "evidence_id": 501,
            "review_source": "DISCORD",
            "reviewer_id": 12345,
            "reviewer_name": "Review Organiser",
            "award_lost_mvp": True
        }
    ]

    assert len(
        decision_interaction.response.edits
    ) == 1

    edit = decision_interaction.response.edits[0]

    assert edit["content"] == (
        "✅ **Submission accepted**\n\n"
        "1.2 discretionary MVP points were awarded.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_lost_mvp_rechecks_reviewer_permission(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": True,
            "maximum_lost_mvp_contribution": 0.3,
            "maximum_lost_mvp_points": 1.2
        }
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: pytest.fail(
            "Acceptance should not run after "
            "reviewer permission was removed."
        )
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    prompt_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            prompt_interaction
        )
    )

    confirmation_view = (
        prompt_interaction
        .response
        .edits[0]["view"]
    )

    yes_button = next(
        child
        for child in confirmation_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Yes - award MVP"
    )

    decision_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[]
    )

    asyncio.run(
        yes_button.callback(
            decision_interaction
        )
    )

    assert len(
        decision_interaction.response.messages
    ) == 1

    assert (
        decision_interaction.response.edits
        == []
    )

    response = (
        decision_interaction
        .response
        .messages[0]
    )

    assert response["ephemeral"] is True

    assert response["content"] == (
        "You no longer have permission "
        "to review submissions."
    )


def test_review_submission_accept_blocks_for_earlier_pending_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: {
            "status": "EARLIER_PENDING_EVIDENCE",
            "message": (
                "An earlier submission for this tile "
                "must be reviewed first."
            )
        }
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        "An earlier submission for this tile "
        "must be reviewed first."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_accept_rejects_already_reviewed_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: {
            "status": "INVALID_STATUS"
        }
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        "This submission has already been reviewed."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_accept_handles_missing_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: {
            "status": "EVIDENCE_NOT_FOUND"
        }
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == (
        "This submission is no longer available."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


@pytest.mark.parametrize(
    "status",
    [
        "MISSING_FROZEN_CONTEXT",
        "TILE_NOT_FOUND",
        "TILE_CHANGED",
        "SUBMITTED_AFTER_COMPLETION",
        "POTENTIAL_UNAVAILABLE"
    ]
)
def test_review_submission_accept_surfaces_blocked_status_message(
    monkeypatch,
    status
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    blocked_message = (
        f"Backend blocked acceptance: {status}"
    )

    monkeypatch.setattr(
        database,
        "accept_pending_manual_evidence",
        lambda **kwargs: {
            "status": status,
            "message": blocked_message
        }
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_lost_mvp_preflight",
        lambda evidence_id: {
            "status": "READY",
            "lost_mvp_available": False
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    accept_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Accept"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        accept_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert edit["content"] == blocked_message
    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_reject_opens_reason_modal(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        lambda **kwargs: pytest.fail(
            "Reject backend should not run until "
            "the modal is submitted."
        )
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    reject_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Reject"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        reject_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.messages
    ) == 0

    assert len(
        interaction.response.edits
    ) == 0

    assert len(
        interaction.response.modals
    ) == 1

    modal = interaction.response.modals[0]

    assert modal.title == "Not Accepting Submission"
    assert modal.evidence_id == 501
    assert modal.reviewer_id == 12345

    assert modal.reason.label == (
        "Why wasn't this accepted?"
    )
    assert modal.reason.required is True
    assert modal.reason.min_length == 3
    assert modal.reason.max_length == 500


def test_review_invalidation_opens_reason_modal(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "Accepted Tile",
            "condition_trigger": "ACCEPTED_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "invalidate_bingo_evidence",
        lambda **kwargs: pytest.fail(
            "Invalidation backend should not run until "
            "the modal is submitted."
        )
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    invalidate_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Invalidate"
    )

    interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        invalidate_button.callback(
            interaction
        )
    )

    assert len(
        interaction.response.messages
    ) == 0

    assert len(
        interaction.response.edits
    ) == 0

    assert len(
        interaction.response.modals
    ) == 1

    modal = interaction.response.modals[0]

    assert modal.title == "Invalidate Submission"
    assert modal.evidence_id == 601
    assert modal.reviewer_id == 12345

    assert modal.reason.label == (
        "Why should this evidence be invalidated?"
    )
    assert modal.reason.required is True
    assert modal.reason.min_length == 3
    assert modal.reason.max_length == 500


def test_review_submission_rejects_manual_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    reject_calls = []

    def reject_manual_evidence(**kwargs):
        reject_calls.append(
            kwargs
        )

        return {
            "status": "REJECTED"
        }

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        reject_manual_evidence
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    reject_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Reject"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        reject_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    rejection_reason = (
        "The screenshot does not clearly show the drop."
    )

    modal.reason._input_value = rejection_reason

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert reject_calls == [
        {
            "evidence_id": 501,
            "review_source": "DISCORD",
            "reviewer_id": 12345,
            "reviewer_name": "Review Organiser",
            "reason": rejection_reason
        }
    ]

    assert len(
        submit_interaction.response.messages
    ) == 0

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert edit["content"] == (
        "❌ **Submission not accepted**\n\n"
        "**Reason:** The screenshot does not clearly "
        "show the drop.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_invalidation_invalidates_manual_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "Accepted Tile",
            "condition_trigger": "ACCEPTED_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    invalidation_calls = []

    def invalidate_manual_evidence(**kwargs):
        invalidation_calls.append(
            kwargs
        )

        return {
            "status": "INVALIDATED",
            "invalidation_id": 123,
            "reopened_tiles": [],
            "replayed_manual_evidence": []
        }

    monkeypatch.setattr(
        database,
        "invalidate_bingo_evidence",
        invalidate_manual_evidence
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    invalidate_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Invalidate"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        invalidate_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    invalidation_reason = (
        "The evidence was accepted against the wrong drop."
    )

    modal.reason._input_value = invalidation_reason

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert invalidation_calls == [
        {
            "subject_type": "MANUAL_EVIDENCE",
            "subject_id": 601,
            "reason_code": "INCORRECT_EVIDENCE",
            "review_source": "DISCORD",
            "reviewer_id": 12345,
            "reviewer_name": "Review Organiser",
            "details": invalidation_reason
        }
    ]

    assert len(
        submit_interaction.response.messages
    ) == 0

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert edit["content"] == (
        "⚠️ **Submission invalidated**\n\n"
        "**Reason:** The evidence was accepted against "
        "the wrong drop.\n\n"
        "Reviewed by Review Organiser."
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_invalidation_reports_reconciliation(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "Accepted Tile",
            "condition_trigger": "ACCEPTED_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "invalidate_bingo_evidence",
        lambda **kwargs: {
            "status": "INVALIDATED",
            "invalidation_id": 123,
            "reopened_tiles": [
                {
                    "team_id": 1,
                    "tile_id": 2
                }
            ],
            "replayed_manual_evidence": [
                {
                    "evidence_id": 999,
                    "team_id": 1,
                    "tile_id": 2,
                    "actual_contribution": 0.5,
                    "completed": False
                }
            ]
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    invalidate_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Invalidate"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        invalidate_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "This evidence was accepted incorrectly."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert (
        "1 later accepted manual submission was replayed."
        in edit["content"]
    )

    assert (
        "1 affected tile remains open after reconciliation."
        in edit["content"]
    )


def test_review_invalidation_surfaces_backend_refusal(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "Accepted Tile",
            "condition_trigger": "ACCEPTED_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    refusal_message = (
        "Accepted manual evidence cannot be invalidated "
        "because the tile changed after submission: "
        "CONDITION_CHANGED."
    )

    def refuse_invalidation(**kwargs):
        raise ValueError(
            refusal_message
        )

    monkeypatch.setattr(
        database,
        "invalidate_bingo_evidence",
        refuse_invalidation
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    invalidate_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Invalidate"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        invalidate_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "This evidence was accepted incorrectly."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.messages
    ) == 0

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert edit["content"] == (
        f"{BOT_NAME} could not safely invalidate "
        "this submission.\n\n"
        f"{refusal_message}"
    )

    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_reject_blocks_for_earlier_pending_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    blocked_message = (
        "An earlier submission for this tile "
        "must be reviewed first."
    )

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        lambda **kwargs: {
            "status": "EARLIER_PENDING_EVIDENCE",
            "message": blocked_message
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    reject_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Reject"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        reject_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "Valid rejection reason."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert edit["content"] == blocked_message
    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_reject_handles_missing_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        lambda **kwargs: {
            "status": "EVIDENCE_NOT_FOUND"
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    reject_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Reject"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        reject_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "Valid rejection reason."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert edit["content"] == (
        "This submission is no longer available."
    )
    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_reject_handles_already_reviewed_evidence(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        lambda **kwargs: {
            "status": "INVALID_STATUS"
        }
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    reject_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Reject"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        reject_button.callback(
            open_interaction
        )
    )

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "Valid rejection reason."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.edits
    ) == 1

    edit = submit_interaction.response.edits[0]

    assert edit["content"] == (
        "This submission has already been reviewed."
    )
    assert edit["embed"] is None
    assert edit["view"] is None
    assert edit["attachments"] == []


def test_review_submission_shows_self_submitted_evidence_file(
    monkeypatch,
    tmp_path
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    evidence_file_path = (
        tmp_path
        / "stored_evidence.png"
    )

    evidence_file_path.write_bytes(
        b"test image data"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": "Self-submitted evidence",
            "evidence_path": (
                "manual/evidence/stored_evidence.png"
            ),
            "submitter_id": 77777,
            "submitter_name": "Test Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    resolved_paths = []

    def resolve_evidence_path(stored_path):
        resolved_paths.append(
            stored_path
        )

        return str(
            evidence_file_path
        )

    monkeypatch.setattr(
        "cogs.AdminCog.resolve_manual_evidence_path",
        resolve_evidence_path
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    assert resolved_paths == [
        "manual/evidence/stored_evidence.png"
    ]

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert response["file"].filename == (
        "manual_evidence_501.png"
    )

    embed = response["embed"]

    assert embed.image.url == (
        "attachment://manual_evidence_501.png"
    )

    fields = {
        field.name: field.value
        for field in embed.fields
    }

    assert fields["Submitted by"] == (
        "Test Player"
    )

    assert "Evidence" not in fields

    assert embed.footer.text == (
        "Manual evidence | Submission #501"
    )

    response["file"].close()


def test_review_submission_reject_rechecks_role_on_modal_submit(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 501,
            "credited_player_name": "Test Player",
            "team_name": "Team Zamorak",
            "tile_name": "Test Tile",
            "condition_trigger": "TEST_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_pending_manual_evidence_review_rows",
        lambda: review_rows
    )

    def reject_should_not_run(**kwargs):
        pytest.fail(
            "Rejection backend was called after "
            "reviewer permission was removed."
        )

    monkeypatch.setattr(
        database,
        "reject_pending_manual_evidence",
        reject_should_not_run
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_submission(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    reject_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Reject"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        reject_button.callback(
            open_interaction
        )
    )

    assert len(
        open_interaction.response.modals
    ) == 1

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "Valid rejection reason."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.messages
    ) == 1

    message = (
        submit_interaction.response.messages[0]
    )

    assert message["content"] == (
        "You no longer have permission "
        "to review submissions."
    )
    assert message["ephemeral"] is True
    assert (
        submit_interaction.response.edits
        == []
    )


def test_review_invalidation_rechecks_role_on_modal_submit(
    monkeypatch
):
    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    review_rows = [
        {
            "evidence_id": 601,
            "credited_player_name": "Accepted Player",
            "team_name": "Team Guthix",
            "tile_name": "Accepted Tile",
            "condition_trigger": "ACCEPTED_DROP",
            "amount": 1,
            "description": None,
            "evidence_path": None,
            "submitter_id": 77777,
            "submitter_name": "Submitting Player",
            "credited_discord_user_id": 77777,
            "evidence_codeword_at_submission": (
                "Blackout Sky"
            ),
            "submitted_at": None
        }
    ]

    monkeypatch.setattr(
        database,
        "get_accepted_manual_evidence_invalidation_rows",
        lambda: review_rows
    )

    def invalidation_should_not_run(**kwargs):
        pytest.fail(
            "Invalidation backend was called after "
            "reviewer permission was removed."
        )

    monkeypatch.setattr(
        database,
        "invalidate_bingo_evidence",
        invalidation_should_not_run
    )

    ctx = FakeContext(
        author_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_review_invalidation(
        ctx
    )

    review_view = ctx.responses[0]["view"]

    invalidate_button = next(
        child
        for child in review_view.children
        if getattr(
            child,
            "label",
            None
        ) == "Invalidate"
    )

    open_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    asyncio.run(
        invalidate_button.callback(
            open_interaction
        )
    )

    assert len(
        open_interaction.response.modals
    ) == 1

    modal = open_interaction.response.modals[0]

    modal.reason._input_value = (
        "Valid invalidation reason."
    )

    submit_interaction = FakeInteraction(
        user_id=12345,
        display_name="Review Organiser",
        roles=[]
    )

    asyncio.run(
        modal.callback(
            submit_interaction
        )
    )

    assert len(
        submit_interaction.response.messages
    ) == 1

    message = (
        submit_interaction.response.messages[0]
    )

    assert message["content"] == (
        "You no longer have permission "
        "to review submissions."
    )
    assert message["ephemeral"] is True
    assert (
        submit_interaction.response.edits
        == []
    )


def test_submit_evidence_requires_configured_codeword(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: None
    )

    ctx = FakeContext()

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        )
    )

    assert ctx.deferred is True
    assert ctx.defer_ephemeral is True
    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True

    assert (
        "evidence codeword has not been set"
        in response["content"]
    )


def test_submit_evidence_rejects_unsupported_file_type(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    ctx = FakeContext()

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.pdf"
        )
    )

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True

    assert response["content"] == (
        "Evidence must be a PNG, JPG, JPEG, "
        "or WebP image."
    )


def test_submit_evidence_uses_linked_player_for_participant(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    linked_player = (
        42,
        "Linked Player",
        0,
        0,
        0,
        7,
        0,
        12345
    )

    monkeypatch.setattr(
        database,
        "get_player_by_discord_user_id",
        lambda discord_user_id: linked_player
    )

    requested_player_ids = []

    def get_submission_options(player_id):
        requested_player_ids.append(
            player_id
        )

        return {
            "player_id": player_id,
            "player_name": "Linked Player",
            "team_id": 7,
            "tiles": [
                {
                    "tile_id": 100,
                    "tile_name": "Test Tile",
                    "tile_points": 1,
                    "tile_rules": "",
                    "conditions": [
                        {
                            "condition_id": 200,
                            "condition_type": "DROP",
                            "condition_trigger": "Test Drop",
                            "target": 1,
                            "progress": 0
                        }
                    ]
                }
            ]
        }

    monkeypatch.setattr(
        database,
        "get_manual_evidence_submission_options",
        get_submission_options
    )

    ctx = FakeContext(
        author_id=12345
    )

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        )
    )

    assert requested_player_ids == [42]
    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert response["view"] is not None

    assert (
        "Submitting evidence for **Linked Player**."
        in response["content"]
    )


def test_submit_evidence_blocks_non_organiser_player_option(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    monkeypatch.delenv(
        "BINGO_ORGANISER_ROLE_ID",
        raising=False
    )

    monkeypatch.setattr(
        database,
        "get_player_by_name",
        lambda player_name: pytest.fail(
            "Player lookup should not run for "
            "a non-organiser."
        )
    )

    ctx = FakeContext()

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        ),
        player="Other Player"
    )

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True

    assert response["content"] == (
        "Only bingo organisers can submit "
        "evidence on behalf of another player."
    )


def test_submit_evidence_allows_organiser_on_behalf_submission(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    selected_player = (
        84,
        "Selected Player",
        0,
        0,
        0,
        9,
        0,
        None
    )

    requested_player_names = []
    requested_player_ids = []

    def get_player_by_name(player_name):
        requested_player_names.append(
            player_name
        )
        return selected_player

    def get_submission_options(player_id):
        requested_player_ids.append(
            player_id
        )

        return {
            "player_id": player_id,
            "player_name": "Selected Player",
            "team_id": 9,
            "tiles": [
                {
                    "tile_id": 300,
                    "tile_name": "Organiser Test Tile",
                    "tile_points": 1,
                    "tile_rules": "",
                    "conditions": [
                        {
                            "condition_id": 400,
                            "condition_type": "PET",
                            "condition_trigger": "Test Pet",
                            "target": 1,
                            "progress": 0
                        }
                    ]
                }
            ]
        }

    monkeypatch.setattr(
        database,
        "get_player_by_name",
        get_player_by_name
    )

    monkeypatch.setattr(
        database,
        "get_player_by_discord_user_id",
        lambda discord_user_id: pytest.fail(
            "An organiser submitting on behalf of "
            "another player should not need their "
            "own linked account."
        )
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_submission_options",
        get_submission_options
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        ),
        player="Selected Player"
    )

    assert requested_player_names == [
        "Selected Player"
    ]

    assert requested_player_ids == [84]

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True
    assert response["view"] is not None

    assert (
        "Submitting evidence for **Selected Player**."
        in response["content"]
    )


def test_submit_evidence_organiser_player_must_exist(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    monkeypatch.setenv(
        "BINGO_ORGANISER_ROLE_ID",
        "999"
    )

    monkeypatch.setattr(
        database,
        "get_player_by_name",
        lambda player_name: None
    )

    ctx = FakeContext(
        roles=[
            SimpleNamespace(
                id=999
            )
        ]
    )

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        ),
        player="Missing Player"
    )

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True

    assert response["content"] == (
        "Unable to find the player "
        "**Missing Player**."
    )


def test_submit_evidence_requires_linked_player_for_participant(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    monkeypatch.delenv(
        "BINGO_ORGANISER_ROLE_ID",
        raising=False
    )

    monkeypatch.setattr(
        database,
        "get_player_by_discord_user_id",
        lambda discord_user_id: None
    )

    ctx = FakeContext()

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        )
    )

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True

    assert response["content"] == (
        "Your Discord account is not "
        "registered. Use `/register` first."
    )


def test_submit_evidence_refuses_when_nothing_is_eligible(
    monkeypatch
):
    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    linked_player = (
        42,
        "Finished Player",
        0,
        0,
        0,
        7,
        0,
        12345
    )

    monkeypatch.setattr(
        database,
        "get_player_by_discord_user_id",
        lambda discord_user_id: linked_player
    )

    monkeypatch.setattr(
        database,
        "get_manual_evidence_submission_options",
        lambda player_id: {
            "player_id": player_id,
            "player_name": "Finished Player",
            "team_id": 7,
            "tiles": []
        }
    )

    ctx = FakeContext(
        author_id=12345
    )

    run_submit_evidence(
        ctx,
        FakeAttachment(
            "evidence.png"
        )
    )

    assert len(ctx.responses) == 1

    response = ctx.responses[0]

    assert response["ephemeral"] is True

    assert response["content"] == (
        "There are currently no incomplete tiles "
        "or tile parts that **Finished Player** can "
        "submit manual evidence towards."
    )


class FakeInteractionResponse:
    def __init__(self):
        self.messages = []
        self.modals = []
        self.edits = []

    async def send_message(
        self,
        content=None,
        **kwargs
    ):
        self.messages.append({
            "content": content,
            **kwargs
        })

    async def send_modal(
        self,
        modal
    ):
        self.modals.append(
            modal
        )

    async def edit_message(
        self,
        content=None,
        **kwargs
    ):
        self.edits.append({
            "content": content,
            **kwargs
        })


class FakeInteraction:
    def __init__(
        self,
        user_id=12345,
        display_name="Discord Tester",
        roles=None
    ):
        self.user = SimpleNamespace(
            id=user_id,
            display_name=display_name,
            roles=roles or []
        )

        self.response = (
            FakeInteractionResponse()
        )


def test_tile_select_single_condition_opens_details_modal():
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    tiles = [
        {
            "tile_id": 100,
            "tile_name": "Single Part Tile",
            "tile_points": 1,
            "tile_rules": "",
            "conditions": [
                {
                    "condition_id": 200,
                    "condition_type": "DROP",
                    "condition_trigger": "Test Drop",
                    "target": 1,
                    "progress": 0
                }
            ]
        }
    ]

    select = ManualEvidenceTileSelect(
        state=state,
        tiles=tiles
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    select._interaction = interaction
    select._selected_values = [
        "100"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert state.tile_id == 100
    assert state.tile_name == "Single Part Tile"
    assert state.condition_id == 200
    assert state.condition_label == "Test Drop"

    assert len(
        interaction.response.modals
    ) == 1

    assert isinstance(
        interaction.response.modals[0],
        ManualEvidenceDetailsModal
    )

    assert (
        interaction.response.modals[0].state
        is state
    )

    assert interaction.response.messages == []
    assert interaction.response.edits == []


def test_tile_select_multiple_conditions_shows_condition_selector():
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    tiles = [
        {
            "tile_id": 100,
            "tile_name": "Multiple Part Tile",
            "tile_points": 2,
            "tile_rules": "",
            "conditions": [
                {
                    "condition_id": 200,
                    "condition_type": "DROP",
                    "condition_trigger": "First Drop",
                    "target": 1,
                    "progress": 0
                },
                {
                    "condition_id": 201,
                    "condition_type": "DROP",
                    "condition_trigger": "Second Drop",
                    "target": 1,
                    "progress": 0
                }
            ]
        }
    ]

    select = ManualEvidenceTileSelect(
        state=state,
        tiles=tiles
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    select._interaction = interaction
    select._selected_values = [
        "100"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert state.tile_id == 100
    assert state.tile_name == "Multiple Part Tile"

    assert state.condition_id is None
    assert state.condition_label is None

    assert interaction.response.modals == []
    assert interaction.response.messages == []

    assert len(
        interaction.response.edits
    ) == 1

    edit = interaction.response.edits[0]

    assert isinstance(
        edit["view"],
        ManualEvidenceConditionView
    )

    assert (
        "You selected **Multiple Part Tile**."
        in edit["content"]
    )

    assert (
        "Choose which part of the tile your "
        "screenshot proves."
        in edit["content"]
    )


def test_condition_select_opens_details_modal():
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    conditions = [
        {
            "condition_id": 200,
            "condition_type": "DROP",
            "condition_trigger": "First Drop",
            "target": 1,
            "progress": 0
        },
        {
            "condition_id": 201,
            "condition_type": "DROP",
            "condition_trigger": "Second Drop",
            "target": 1,
            "progress": 0
        }
    ]

    select = ManualEvidenceConditionSelect(
        state=state,
        conditions=conditions
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    select._interaction = interaction
    select._selected_values = [
        "201"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert state.condition_id == 201
    assert state.condition_label == "Second Drop"

    assert len(
        interaction.response.modals
    ) == 1

    assert isinstance(
        interaction.response.modals[0],
        ManualEvidenceDetailsModal
    )

    assert (
        interaction.response.modals[0].state
        is state
    )

    assert interaction.response.messages == []
    assert interaction.response.edits == []


def test_tile_select_blocks_different_user():
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    tiles = [
        {
            "tile_id": 100,
            "tile_name": "Protected Tile",
            "tile_points": 1,
            "tile_rules": "",
            "conditions": [
                {
                    "condition_id": 200,
                    "condition_type": "DROP",
                    "condition_trigger": "Test Drop",
                    "target": 1,
                    "progress": 0
                }
            ]
        }
    ]

    select = ManualEvidenceTileSelect(
        state=state,
        tiles=tiles
    )

    interaction = FakeInteraction(
        user_id=99999
    )

    select._interaction = interaction
    select._selected_values = [
        "100"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert state.tile_id is None
    assert state.tile_name is None
    assert state.condition_id is None
    assert state.condition_label is None

    assert interaction.response.modals == []
    assert interaction.response.edits == []

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "Only the person who started this submission "
        "can use these controls."
    )


def test_tile_select_blocks_already_submitted_state():
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.submitted = True

    tiles = [
        {
            "tile_id": 100,
            "tile_name": "Already Submitted Tile",
            "tile_points": 1,
            "tile_rules": "",
            "conditions": [
                {
                    "condition_id": 200,
                    "condition_type": "DROP",
                    "condition_trigger": "Test Drop",
                    "target": 1,
                    "progress": 0
                }
            ]
        }
    ]

    select = ManualEvidenceTileSelect(
        state=state,
        tiles=tiles
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    select._interaction = interaction
    select._selected_values = [
        "100"
    ]

    asyncio.run(
        select.callback(
            interaction
        )
    )

    assert state.tile_id is None
    assert state.tile_name is None
    assert state.condition_id is None
    assert state.condition_label is None

    assert interaction.response.modals == []
    assert interaction.response.edits == []

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "This evidence has already been submitted."
    )


def test_details_modal_rejects_zero_amount_before_processing(
    monkeypatch
):
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.tile_id = 100
    state.tile_name = "Test Tile"
    state.condition_id = 200
    state.condition_label = "Test Drop"

    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: pytest.fail(
            "Codeword lookup should not run "
            "for an invalid amount."
        )
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    async def run_modal():
        modal = ManualEvidenceDetailsModal(
            state
        )

        modal.amount._input_value = "0"

        await modal.callback(
            interaction
        )

    asyncio.run(
        run_modal()
    )

    assert state.submitted is False

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "Amount must be a whole number greater than 0."
    )

    assert interaction.response.modals == []
    assert interaction.response.edits == []


def test_details_modal_rejects_changed_codeword_before_processing(
    monkeypatch
):
    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=FakeAttachment(
            "evidence.png"
        ),
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.tile_id = 100
    state.tile_name = "Test Tile"
    state.condition_id = 200
    state.condition_label = "Test Drop"

    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "New Codeword"
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    async def run_modal():
        modal = ManualEvidenceDetailsModal(
            state
        )

        modal.amount._input_value = "1"

        await modal.callback(
            interaction
        )

    asyncio.run(
        run_modal()
    )

    assert state.submitted is False

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "The bingo evidence codeword changed while "
        "you were completing this submission. "
        "Please start again using the current codeword."
    )

    assert interaction.response.modals == []
    assert interaction.response.edits == []


def test_details_modal_success_submits_evidence(
    monkeypatch
):
    screenshot = FakeAttachment(
        "proof.png",
        data=b"fake screenshot bytes"
    )

    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=screenshot,
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.tile_id = 100
    state.tile_name = "Test Tile"
    state.condition_id = 200
    state.condition_label = "Test Drop"

    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    saved_files = []

    def save_evidence_file(
        file_bytes,
        filename
    ):
        saved_files.append({
            "file_bytes": file_bytes,
            "filename": filename
        })

        return {
            "evidence_path": (
                "uploads/manual_evidence/"
                "12345678-1234-1234-1234-123456789abc.png"
            ),
            "evidence_sha256": "abc123"
        }

    monkeypatch.setattr(
        manual_evidence_files,
        "save_manual_evidence_file",
        save_evidence_file
    )

    database_calls = []

    def add_manual_evidence(
        **kwargs
    ):
        database_calls.append(
            kwargs
        )

        return {
            "evidence_id": 999,
            "status": "PENDING",
            "pending_warning": None
        }

    monkeypatch.setattr(
        database,
        "add_manual_evidence",
        add_manual_evidence
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    async def run_modal():
        modal = ManualEvidenceDetailsModal(
            state
        )

        modal.amount._input_value = "3"
        modal.description._input_value = (
            "Boss drop visible in screenshot"
        )

        await modal.callback(
            interaction
        )

    asyncio.run(
        run_modal()
    )

    assert screenshot.read_calls == 1

    assert saved_files == [
        {
            "file_bytes": b"fake screenshot bytes",
            "filename": "proof.png"
        }
    ]

    assert len(
        database_calls
    ) == 1

    call = database_calls[0]

    assert call == {
        "player_id": 42,
        "condition_id": 200,
        "amount": 3,
        "evidence_path": (
            "uploads/manual_evidence/"
            "12345678-1234-1234-1234-123456789abc.png"
        ),
        "evidence_sha256": "abc123",
        "submission_source": "DISCORD",
        "submitter_id": 12345,
        "submitter_name": "Discord Tester",
        "description": (
            "Boss drop visible in screenshot"
        ),
        "discord_guild_id": 111,
        "discord_channel_id": 222,
        "discord_message_id": None,
        "evidence_author_id": 12345,
        "evidence_author_name": "Discord Tester"
    }

    assert state.submitted is True

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "✅ **Evidence submitted**\n\n"
        "Player: **Linked Player**\n"
        "Tile: **Test Tile**\n"
        "Amount: **3**\n\n"
        "Your submission is now waiting for review."
    )

    assert interaction.response.modals == []
    assert interaction.response.edits == []


def test_details_modal_database_refusal_deletes_saved_file(
    monkeypatch
):
    screenshot = FakeAttachment(
        "proof.png",
        data=b"fake screenshot bytes"
    )

    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=screenshot,
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.tile_id = 100
    state.tile_name = "Test Tile"
    state.condition_id = 200
    state.condition_label = "Test Drop"

    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    evidence_path = (
        "uploads/manual_evidence/"
        "12345678-1234-1234-1234-123456789abc.png"
    )

    monkeypatch.setattr(
        manual_evidence_files,
        "save_manual_evidence_file",
        lambda file_bytes, filename: {
            "evidence_path": evidence_path,
            "evidence_sha256": "abc123"
        }
    )

    monkeypatch.setattr(
        database,
        "add_manual_evidence",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                ValueError(
                    "Tile is already complete."
                )
            )
        )
    )

    deleted_paths = []

    monkeypatch.setattr(
        manual_evidence_files,
        "delete_manual_evidence_file",
        lambda path: deleted_paths.append(
            path
        )
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    async def run_modal():
        modal = ManualEvidenceDetailsModal(
            state
        )

        modal.amount._input_value = "1"

        await modal.callback(
            interaction
        )

    asyncio.run(
        run_modal()
    )

    assert screenshot.read_calls == 1

    assert deleted_paths == [
        evidence_path
    ]

    assert state.submitted is False

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "The bingo progressed while you were completing "
        "this submission, so this evidence can no longer "
        "be submitted for that tile. Please check the "
        "current board."
    )

    assert interaction.response.modals == []
    assert interaction.response.edits == []


def test_details_modal_success_includes_pending_warning(
    monkeypatch
):
    screenshot = FakeAttachment(
        "proof.png",
        data=b"fake screenshot bytes"
    )

    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=screenshot,
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.tile_id = 100
    state.tile_name = "Test Tile"
    state.condition_id = 200
    state.condition_label = "Test Drop"

    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    monkeypatch.setattr(
        manual_evidence_files,
        "save_manual_evidence_file",
        lambda file_bytes, filename: {
            "evidence_path": (
                "uploads/manual_evidence/"
                "12345678-1234-1234-1234-123456789abc.png"
            ),
            "evidence_sha256": "abc123"
        }
    )

    pending_warning = (
        "Another submission for this tile is already "
        "waiting for review. If that earlier submission "
        "is accepted, it may reduce or remove the MVP "
        "points available for this submission. This will "
        "not affect the team's tile points."
    )

    monkeypatch.setattr(
        database,
        "add_manual_evidence",
        lambda **kwargs: {
            "evidence_id": 999,
            "status": "PENDING",
            "pending_warning": pending_warning
        }
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    async def run_modal():
        modal = ManualEvidenceDetailsModal(
            state
        )

        modal.amount._input_value = "1"

        await modal.callback(
            interaction
        )

    asyncio.run(
        run_modal()
    )

    assert state.submitted is True

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "✅ **Evidence submitted**\n\n"
        "Player: **Linked Player**\n"
        "Tile: **Test Tile**\n"
        "Amount: **1**\n\n"
        "Your submission is now waiting for review."
        "\n\n⚠️ "
        + pending_warning
    )


def test_details_modal_unexpected_error_deletes_saved_file(
    monkeypatch
):
    screenshot = FakeAttachment(
        "proof.png",
        data=b"fake screenshot bytes"
    )

    state = ManualEvidenceSubmissionState(
        submitter_id=12345,
        submitter_name="Discord Tester",
        player_id=42,
        player_name="Linked Player",
        screenshot=screenshot,
        evidence_codeword="Blackout Sky",
        guild_id=111,
        channel_id=222
    )

    state.tile_id = 100
    state.tile_name = "Test Tile"
    state.condition_id = 200
    state.condition_label = "Test Drop"

    monkeypatch.setattr(
        database,
        "get_evidence_codeword",
        lambda: "Blackout Sky"
    )

    evidence_path = (
        "uploads/manual_evidence/"
        "12345678-1234-1234-1234-123456789abc.png"
    )

    monkeypatch.setattr(
        manual_evidence_files,
        "save_manual_evidence_file",
        lambda file_bytes, filename: {
            "evidence_path": evidence_path,
            "evidence_sha256": "abc123"
        }
    )

    def raise_database_error(
        **kwargs
    ):
        raise RuntimeError(
            "Simulated database failure"
        )

    monkeypatch.setattr(
        database,
        "add_manual_evidence",
        raise_database_error
    )

    deleted_paths = []

    monkeypatch.setattr(
        manual_evidence_files,
        "delete_manual_evidence_file",
        lambda path: deleted_paths.append(
            path
        )
    )

    interaction = FakeInteraction(
        user_id=12345
    )

    async def run_modal():
        modal = ManualEvidenceDetailsModal(
            state
        )

        modal.amount._input_value = "1"

        await modal.callback(
            interaction
        )

    asyncio.run(
        run_modal()
    )

    assert screenshot.read_calls == 1

    assert deleted_paths == [
        evidence_path
    ]

    assert state.submitted is False

    assert len(
        interaction.response.messages
    ) == 1

    message = interaction.response.messages[0]

    assert message["ephemeral"] is True

    assert message["content"] == (
        "Something went wrong while submitting your "
        "evidence. Nothing was submitted. "
        "Please try again."
    )

    assert interaction.response.modals == []
    assert interaction.response.edits == []
