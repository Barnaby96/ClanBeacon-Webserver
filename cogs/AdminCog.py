import os
import sqlite3
import discord

from discord.ext import commands
from discord import default_permissions, guild_only

from routes import dink
from utils import (
    completion_notifications,
    database,
    db_entities,
    scapify
)
from utils.branding import BOT_NAME
from utils.manual_evidence_files import (
    resolve_manual_evidence_path
)
from utils.spoofed_jsons import spoof_drop
from utils.autocomplete import *
from utils.send_webhook import send_webhook

def _get_submission_summary(row):
    trigger = str(
        row.get(
            "condition_trigger"
        ) or ""
    ).strip()

    if trigger:
        summary = trigger.replace(
            "_",
            " "
        ).title()
    else:
        summary = str(
            row.get(
                "tile_name"
            ) or "This part of the tile"
        ).strip()

    amount = int(
        row.get(
            "amount",
            1
        ) or 1
    )

    if amount > 1:
        return f"{amount} x {summary}"

    return summary


def _get_submission_evidence_file(row):
    evidence_id = int(
        row["evidence_id"]
    )

    absolute_path = resolve_manual_evidence_path(
        row.get(
            "evidence_path"
        )
    )

    if absolute_path is None:
        return None, None

    extension = os.path.splitext(
        absolute_path
    )[1].lower()

    filename = (
        f"manual_evidence_{evidence_id}"
        f"{extension}"
    )

    return (
        discord.File(
            absolute_path,
            filename=filename
        ),
        filename
    )

def _build_submission_review_embed(
    row,
    evidence_filename=None
):
    evidence_id = int(
        row["evidence_id"]
    )

    player_name = (
        row.get("credited_player_name")
        or "Unknown player"
    )

    team_name = (
        row.get("team_name")
        or "Original team unavailable"
    )

    tile_name = (
        row.get("tile_name")
        or "Original tile unavailable"
    )

    trigger = str(
        row.get(
            "condition_trigger"
        ) or ""
    ).strip()

    if trigger:
        part_name = trigger.replace(
            "_",
            " "
        ).title()
    else:
        part_name = "This part of the tile"

    submitter_name = (
        row.get("submitter_name")
        or "Unknown submitter"
    )

    submitter_id = row.get(
        "submitter_id"
    )

    credited_discord_user_id = row.get(
        "credited_discord_user_id"
    )

    submitted_for_self = (
        credited_discord_user_id is not None
        and submitter_id is not None
        and int(credited_discord_user_id)
        == int(submitter_id)
    )

    if submitted_for_self:
        submitted_by_text = submitter_name
    else:
        submitted_by_text = (
            f"{submitter_name} on behalf of "
            f"{player_name}"
        )

    evidence_codeword = (
        row.get(
            "evidence_codeword_at_submission"
        )
        or "Not recorded"
    )

    notes = (
        row.get("description")
        or "None provided"
    )

    submitted_at = row.get(
        "submitted_at"
    )

    if submitted_at is not None:
        submitted_timestamp = int(
            submitted_at.timestamp()
        )

        submitted_text = (
            f"<t:{submitted_timestamp}:f>\n"
            f"<t:{submitted_timestamp}:R>"
        )
    else:
        submitted_text = "Unknown"

    embed = discord.Embed(
        title="Review Submission",
        description=_get_submission_summary(
            row
        )
    )

    embed.add_field(
        name="Player",
        value=player_name,
        inline=True
    )

    embed.add_field(
        name="Team",
        value=team_name,
        inline=True
    )

    embed.add_field(
        name="Amount",
        value=str(
            row.get(
                "amount",
                1
            )
        ),
        inline=True
    )

    embed.add_field(
        name="Tile",
        value=tile_name,
        inline=False
    )

    embed.add_field(
        name="Part",
        value=part_name,
        inline=False
    )

    embed.add_field(
        name="Submitted by",
        value=submitted_by_text,
        inline=False
    )

    embed.add_field(
        name="Evidence codeword",
        value=evidence_codeword,
        inline=False
    )

    embed.add_field(
        name="Notes",
        value=notes,
        inline=False
    )

    embed.add_field(
        name="Submitted",
        value=submitted_text,
        inline=False
    )

    if evidence_filename:
        embed.set_image(
            url=(
                "attachment://"
                f"{evidence_filename}"
            )
        )
    else:
        embed.add_field(
            name="Evidence",
            value="No screenshot available",
            inline=False
        )

    embed.set_footer(
        text=(
            "Manual evidence"
            f" | Submission #{evidence_id}"
        )
    )

    return embed


def _is_bingo_organiser(member):
    organiser_role_id = os.getenv(
        "BINGO_ORGANISER_ROLE_ID"
    )

    if organiser_role_id is None:
        return False

    return any(
        str(role.id) == organiser_role_id
        for role in getattr(
            member,
            "roles",
            []
        )
    )


async def _check_submission_reviewer(
    interaction,
    reviewer_id
):
    if (
        interaction.user.id
        != int(reviewer_id)
    ):
        await interaction.response.send_message(
            (
                "This review panel belongs "
                "to another staff member."
            ),
            ephemeral=True
        )
        return False

    if not _is_bingo_organiser(
        interaction.user
    ):
        await interaction.response.send_message(
            (
                "You no longer have permission "
                "to review submissions."
            ),
            ephemeral=True
        )
        return False

    return True


class SubmissionReviewSelect(
    discord.ui.Select
):
    def __init__(
        self,
        review_rows,
        selected_evidence_id,
        reviewer_id
    ):
        self.review_rows = {
            int(row["evidence_id"]): row
            for row in review_rows
        }

        self.reviewer_id = int(
            reviewer_id
        )

        options = []

        for row in review_rows[:25]:
            evidence_id = int(
                row["evidence_id"]
            )

            player_name = (
                row.get("credited_player_name")
                or "Unknown player"
            )

            team_name = (
                row.get("team_name")
                or "Original team unavailable"
            )

            submission_summary = (
                _get_submission_summary(
                    row
                )
            )

            label = (
                f"{player_name} - "
                f"{submission_summary}"
            )[:100]

            description = (
                f"Team: {team_name}"
            )[:100]

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(evidence_id),
                    description=description,
                    default=(
                        evidence_id
                        == selected_evidence_id
                    )
                )
            )

        super().__init__(
            placeholder=(
                "Choose a submission to review"
            ),
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_submission_reviewer(
            interaction=interaction,
            reviewer_id=self.reviewer_id
        ):
            return

        evidence_id = int(
            self.values[0]
        )

        row = self.review_rows.get(
            evidence_id
        )

        if row is None:
            await interaction.response.send_message(
                (
                    "That submission is no "
                    "longer available."
                ),
                ephemeral=True
            )
            return

        view = SubmissionReviewView(
            review_rows=list(
                self.review_rows.values()
            ),
            selected_evidence_id=evidence_id,
            reviewer_id=self.reviewer_id
        )

        evidence_file, evidence_filename = (
            _get_submission_evidence_file(
                row
            )
        )

        embed = _build_submission_review_embed(
            row,
            evidence_filename=evidence_filename
        )

        if evidence_file is not None:
            await interaction.response.edit_message(
                embed=embed,
                view=view,
                attachments=[],
                file=evidence_file
            )
        else:
            await interaction.response.edit_message(
                embed=embed,
                view=view,
                attachments=[]
            )


class SubmissionRejectionModal(
    discord.ui.Modal
):
    def __init__(
        self,
        evidence_id,
        reviewer_id
    ):
        super().__init__(
            title="Not Accepting Submission"
        )

        self.evidence_id = int(
            evidence_id
        )

        self.reviewer_id = int(
            reviewer_id
        )

        self.reason = discord.ui.InputText(
            label="Why wasn't this accepted?",
            style=discord.InputTextStyle.long,
            placeholder=(
                "For example: the screenshot "
                "doesn't clearly show the drop."
            ),
            min_length=3,
            max_length=500,
            required=True
        )

        self.add_item(
            self.reason
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_submission_reviewer(
            interaction=interaction,
            reviewer_id=self.reviewer_id
        ):
            return

        result = (
            database.reject_pending_manual_evidence(
                evidence_id=self.evidence_id,
                review_source="DISCORD",
                reviewer_id=(
                    interaction.user.id
                ),
                reviewer_name=(
                    interaction.user.display_name
                ),
                reason=self.reason.value
            )
        )

        if result["status"] == "REJECTED":
            await interaction.response.edit_message(
                content=(
                    "❌ **Submission not accepted**"
                    "\n\n"
                    f"**Reason:** {self.reason.value}"
                    "\n\n"
                    f"Reviewed by "
                    f"{interaction.user.display_name}."
                ),
                embed=None,
                view=None,
                attachments=[]
            )
            return

        if result["status"] == "EVIDENCE_NOT_FOUND":
            message = (
                "This submission is no "
                "longer available."
            )
        elif (
            result["status"]
            == "EARLIER_PENDING_EVIDENCE"
        ):
            message = result.get(
                "message",
                (
                    "An earlier submission for this tile "
                    "must be reviewed first."
                )
            )
        else:
            message = (
                "This submission has already "
                "been reviewed."
            )

        await interaction.response.edit_message(
            content=message,
            embed=None,
            view=None,
            attachments=[]
        )


class SubmissionLostMvpConfirmationView(
    discord.ui.View
):
    def __init__(
        self,
        review_view
    ):
        super().__init__(
            timeout=300
        )

        self.review_view = review_view

    @discord.ui.button(
        label="No - accept without MVP",
        style=discord.ButtonStyle.secondary
    )
    async def accept_without_mvp(
        self,
        button,
        interaction
    ):
        if not await self.review_view._check_reviewer(
            interaction
        ):
            return

        await self.review_view._accept_selected(
            interaction=interaction,
            award_lost_mvp=False
        )

    @discord.ui.button(
        label="Yes - award MVP",
        style=discord.ButtonStyle.success
    )
    async def accept_with_mvp(
        self,
        button,
        interaction
    ):
        if not await self.review_view._check_reviewer(
            interaction
        ):
            return

        await self.review_view._accept_selected(
            interaction=interaction,
            award_lost_mvp=True
        )


class SubmissionReviewView(
    discord.ui.View
):
    def __init__(
        self,
        review_rows,
        selected_evidence_id,
        reviewer_id
    ):
        super().__init__(
            timeout=900
        )

        self.review_rows = review_rows
        self.selected_evidence_id = int(
            selected_evidence_id
        )
        self.reviewer_id = int(
            reviewer_id
        )

        self.add_item(
            SubmissionReviewSelect(
                review_rows=review_rows,
                selected_evidence_id=(
                    self.selected_evidence_id
                ),
                reviewer_id=(
                    self.reviewer_id
                )
            )
        )

    async def _check_reviewer(
        self,
        interaction
    ):
        return await _check_submission_reviewer(
            interaction=interaction,
            reviewer_id=self.reviewer_id
        )

    async def _accept_selected(
        self,
        interaction,
        award_lost_mvp=False
    ):
        try:
            result = (
                database.accept_pending_manual_evidence(
                    evidence_id=(
                        self.selected_evidence_id
                    ),
                    review_source="DISCORD",
                    reviewer_id=(
                        interaction.user.id
                    ),
                    reviewer_name=(
                        interaction.user.display_name
                    ),
                    award_lost_mvp=award_lost_mvp
                )
            )
        except ValueError:
            await interaction.response.edit_message(
                content=(
                    "This submission could not be "
                    "accepted. It may no longer be "
                    "eligible for review."
                ),
                embed=None,
                view=None,
                attachments=[]
            )
            return

        if result.get(
            "newly_completed",
            False
        ):
            completion_notifications.notify_progress_completions(
                [
                    {
                        "team_id": result["team_id"],
                        "tile_id": result["tile_id"],
                        "completed": True
                    }
                ]
            )

        status = result.get(
            "status"
        )

        if status == "ACCEPTED":
            if result.get(
                "audit_only",
                False
            ):
                result_text = (
                    "✅ **Submission accepted**\n\n"
                    "Accepted for audit only because the "
                    "tile changed after this submission was "
                    "made. No points were awarded."
                )

            else:
                if result.get(
                    "late_review",
                    False
                ):
                    result_text = (
                        "✅ **Submission accepted**\n\n"
                        "The tile had already completed before "
                        "this submission was reviewed."
                    )
                else:
                    result_text = (
                        "✅ **Submission accepted**"
                    )

                lost_mvp = float(
                    result.get(
                        "lost_mvp_contribution",
                        0
                    )
                    or 0
                )

                late_review_points = float(
                    result.get(
                        "late_review_points",
                        0
                    )
                    or 0
                )

                if late_review_points > 0:
                    result_text += (
                        "\n\n"
                        f"{late_review_points:g} discretionary "
                        "MVP points were awarded."
                    )

                elif lost_mvp > 0:
                    result_text += (
                        "\n\nNo discretionary MVP points "
                        "were awarded."
                    )

            await interaction.response.edit_message(
                content=(
                    f"{result_text}\n\n"
                    f"Reviewed by "
                    f"{interaction.user.display_name}."
                ),
                embed=None,
                view=None,
                attachments=[]
            )
            return

        if status == "EVIDENCE_NOT_FOUND":
            message = (
                "This submission is no "
                "longer available."
            )

        elif status == "INVALID_STATUS":
            message = (
                "This submission has already "
                "been reviewed."
            )

        elif status == "EARLIER_PENDING_EVIDENCE":
            message = result.get(
                "message",
                (
                    "An earlier submission for this tile "
                    "must be reviewed first."
                )
            )

        elif status in (
            "MISSING_FROZEN_CONTEXT",
            "TILE_NOT_FOUND",
            "TILE_CHANGED",
            "SUBMITTED_AFTER_COMPLETION",
            "POTENTIAL_UNAVAILABLE"
        ):
            message = result.get(
                "message",
                (
                    "This submission cannot currently "
                    "be accepted."
                )
            )

        else:
            message = (
                "This submission could not "
                "be accepted."
            )

        await interaction.response.edit_message(
            content=message,
            embed=None,
            view=None,
            attachments=[]
        )

    @discord.ui.button(
        label="Accept",
        emoji="✅",
        style=discord.ButtonStyle.success,
        row=1
    )
    async def accept_submission(
        self,
        button,
        interaction
    ):
        if not await self._check_reviewer(
            interaction
        ):
            return

        try:
            preflight = (
                database
                .get_manual_evidence_lost_mvp_preflight(
                    self.selected_evidence_id
                )
            )
        except ValueError:
            await interaction.response.edit_message(
                content=(
                    f"{BOT_NAME} could not safely determine whether "
                    "discretionary MVP is available. The "
                    "submission has not been accepted."
                ),
                view=None
            )
            return

        if preflight.get(
            "lost_mvp_available",
            False
        ):
            lost_mvp_contribution = float(
                preflight.get(
                    "maximum_lost_mvp_contribution",
                    0
                )
                or 0
            )

            lost_mvp_points = float(
                preflight.get(
                    "maximum_lost_mvp_points",
                    0
                )
                or 0
            )

            await interaction.response.edit_message(
                content=(
                    "⚠️ **Discretionary MVP available**\n\n"
                    "Some otherwise-valid contribution cannot "
                    "receive normal MVP credit because of tile "
                    "completion.\n\n"
                    f"This submission can receive up to "
                    f"**{lost_mvp_points:g} MVP points** "
                    f"({lost_mvp_contribution * 100:g}% of the "
                    "tile's personal credit).\n\n"
                    "Award these discretionary MVP points when "
                    "accepting the submission?"
                ),
                view=SubmissionLostMvpConfirmationView(
                    review_view=self
                )
            )
            return

        await self._accept_selected(
            interaction=interaction,
            award_lost_mvp=False
        )

    @discord.ui.button(
        label="Reject",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        row=1
    )
    async def reject_submission(
        self,
        button,
        interaction
    ):
        if not await self._check_reviewer(
            interaction
        ):
            return

        modal = SubmissionRejectionModal(
            evidence_id=self.selected_evidence_id,
            reviewer_id=self.reviewer_id
        )

        await interaction.response.send_modal(
            modal
        )

class SubmissionInvalidationSelect(
    discord.ui.Select
):
    def __init__(
        self,
        review_rows,
        selected_evidence_id,
        reviewer_id
    ):
        self.review_rows = {
            int(row["evidence_id"]): row
            for row in review_rows
        }

        self.reviewer_id = int(
            reviewer_id
        )

        options = []

        for row in review_rows[:25]:
            evidence_id = int(
                row["evidence_id"]
            )

            player_name = (
                row.get("credited_player_name")
                or "Unknown player"
            )

            team_name = (
                row.get("team_name")
                or "Original team unavailable"
            )

            submission_summary = (
                _get_submission_summary(
                    row
                )
            )

            label = (
                f"{player_name} - "
                f"{submission_summary}"
            )[:100]

            description = (
                f"Team: {team_name}"
            )[:100]

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(evidence_id),
                    description=description,
                    default=(
                        evidence_id
                        == selected_evidence_id
                    )
                )
            )

        super().__init__(
            placeholder=(
                "Choose an accepted submission"
            ),
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_submission_reviewer(
            interaction=interaction,
            reviewer_id=self.reviewer_id
        ):
            return

        evidence_id = int(
            self.values[0]
        )

        row = self.review_rows.get(
            evidence_id
        )

        if row is None:
            await interaction.response.send_message(
                (
                    "That submission is no "
                    "longer available."
                ),
                ephemeral=True
            )
            return

        view = SubmissionInvalidationView(
            review_rows=list(
                self.review_rows.values()
            ),
            selected_evidence_id=evidence_id,
            reviewer_id=self.reviewer_id
        )

        evidence_file, evidence_filename = (
            _get_submission_evidence_file(
                row
            )
        )

        embed = _build_submission_review_embed(
            row,
            evidence_filename=evidence_filename
        )

        if evidence_file is not None:
            await interaction.response.edit_message(
                embed=embed,
                view=view,
                attachments=[],
                file=evidence_file
            )
        else:
            await interaction.response.edit_message(
                embed=embed,
                view=view,
                attachments=[]
            )


class SubmissionInvalidationView(
    discord.ui.View
):
    def __init__(
        self,
        review_rows,
        selected_evidence_id,
        reviewer_id
    ):
        super().__init__(
            timeout=900
        )

        self.review_rows = review_rows
        self.selected_evidence_id = int(
            selected_evidence_id
        )
        self.reviewer_id = int(
            reviewer_id
        )

        self.add_item(
            SubmissionInvalidationSelect(
                review_rows=review_rows,
                selected_evidence_id=(
                    self.selected_evidence_id
                ),
                reviewer_id=(
                    self.reviewer_id
                )
            )
        )


    @discord.ui.button(
        label="Invalidate",
        emoji="⚠️",
        style=discord.ButtonStyle.danger,
        row=1
    )
    async def invalidate_submission(
        self,
        button,
        interaction
    ):
        if not await _check_submission_reviewer(
            interaction=interaction,
            reviewer_id=self.reviewer_id
        ):
            return

        modal = SubmissionInvalidationModal(
            evidence_id=self.selected_evidence_id,
            reviewer_id=self.reviewer_id
        )

        await interaction.response.send_modal(
            modal
        )


class SubmissionInvalidationModal(
    discord.ui.Modal
):
    def __init__(
        self,
        evidence_id,
        reviewer_id
    ):
        super().__init__(
            title="Invalidate Submission"
        )

        self.evidence_id = int(
            evidence_id
        )

        self.reviewer_id = int(
            reviewer_id
        )

        self.reason = discord.ui.InputText(
            label="Why should this evidence be invalidated?",
            style=discord.InputTextStyle.long,
            placeholder=(
                "For example: the screenshot was accepted "
                "against the wrong drop."
            ),
            min_length=3,
            max_length=500,
            required=True
        )

        self.add_item(
            self.reason
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_submission_reviewer(
            interaction=interaction,
            reviewer_id=self.reviewer_id
        ):
            return

        try:
            result = database.invalidate_bingo_evidence(
                subject_type="MANUAL_EVIDENCE",
                subject_id=self.evidence_id,
                reason_code="INCORRECT_EVIDENCE",
                review_source="DISCORD",
                reviewer_id=interaction.user.id,
                reviewer_name=interaction.user.display_name,
                details=self.reason.value
            )
        except ValueError as error:
            await interaction.response.edit_message(
                content=(
                    f"{BOT_NAME} could not safely invalidate "
                    "this submission.\n\n"
                    f"{error}"
                ),
                embed=None,
                view=None,
                attachments=[]
            )
            return

        if result["status"] == "INVALIDATED":
            success_message = (
                "⚠️ **Submission invalidated**"
                "\n\n"
                f"**Reason:** {self.reason.value}"
            )

            replayed_count = len(
                result.get(
                    "replayed_manual_evidence",
                    []
                )
            )

            if replayed_count:
                if replayed_count == 1:
                    success_message += (
                        "\n\n"
                        "1 later accepted manual "
                        "submission was replayed."
                    )
                else:
                    success_message += (
                        "\n\n"
                        f"{replayed_count} later accepted "
                        "manual submissions were replayed."
                    )

            reopened_count = len(
                result.get(
                    "reopened_tiles",
                    []
                )
            )

            if reopened_count:
                if reopened_count == 1:
                    success_message += (
                        "\n\n"
                        "1 affected tile remains open "
                        "after reconciliation."
                    )
                else:
                    success_message += (
                        "\n\n"
                        f"{reopened_count} affected tiles "
                        "remain open after reconciliation."
                    )

            success_message += (
                "\n\n"
                f"Reviewed by "
                f"{interaction.user.display_name}."
            )

            await interaction.response.edit_message(
                content=success_message,
                embed=None,
                view=None,
                attachments=[]
            )
            return

        await interaction.response.edit_message(
            content=(
                "This submission could not be invalidated."
            ),
            embed=None,
            view=None,
            attachments=[]
        )

class AdminCog(commands.Cog):
    review = discord.SlashCommandGroup(
        "review",
        "Review bingo submissions"
    )

    def __init__(self, bot):
        self.bot = bot

    @review.command(
        name="invalidation",
        description="Invalidate accepted bingo submissions"
    )
    @guild_only()
    async def review_invalidation(
        self,
        ctx: discord.ApplicationContext
    ):

        if not _is_bingo_organiser(
            ctx.author
        ):
            await ctx.respond(
                (
                    "Only bingo organisers can "
                    "invalidate submissions."
                ),
                ephemeral=True
            )
            return

        await ctx.defer(
            ephemeral=True
        )

        review_rows = (
            database
            .get_accepted_manual_evidence_invalidation_rows()
        )

        if not review_rows:
            await ctx.respond(
                (
                    "There are no accepted submissions "
                    "available to invalidate."
                ),
                ephemeral=True
            )
            return

        selected_row = review_rows[0]

        view = SubmissionInvalidationView(
            review_rows=review_rows,
            selected_evidence_id=int(
                selected_row["evidence_id"]
            ),
            reviewer_id=ctx.author.id
        )

        evidence_file, evidence_filename = (
            _get_submission_evidence_file(
                selected_row
            )
        )

        embed = _build_submission_review_embed(
            selected_row,
            evidence_filename=evidence_filename
        )

        if evidence_file is not None:
            await ctx.respond(
                embed=embed,
                view=view,
                file=evidence_file,
                ephemeral=True
            )
        else:
            await ctx.respond(
                embed=embed,
                view=view,
                ephemeral=True
            )

    @review.command(
        name="submission",
        description="Review bingo submissions"
    )
    @guild_only()
    async def review_submission(
        self,
        ctx: discord.ApplicationContext
    ):

        if not _is_bingo_organiser(
            ctx.author
        ):
            await ctx.respond(
                (
                    "Only bingo organisers can "
                    "review submissions."
                ),
                ephemeral=True
            )
            return

        await ctx.defer(
            ephemeral=True
        )

        review_rows = (
            database.get_pending_manual_evidence_review_rows()
        )

        if not review_rows:
            await ctx.respond(
                (
                    "There are no submissions "
                    "ready for review."
                ),
                ephemeral=True
            )
            return

        selected_row = review_rows[0]

        view = SubmissionReviewView(
            review_rows=review_rows,
            selected_evidence_id=int(
                selected_row["evidence_id"]
            ),
            reviewer_id=ctx.author.id
        )

        evidence_file, evidence_filename = (
            _get_submission_evidence_file(
                selected_row
            )
        )

        embed = _build_submission_review_embed(
            selected_row,
            evidence_filename=evidence_filename
        )

        if evidence_file is not None:
            await ctx.respond(
                embed=embed,
                view=view,
                file=evidence_file,
                ephemeral=True
            )
        else:
            await ctx.respond(
                embed=embed,
                view=view,
                ephemeral=True
            )

    @discord.slash_command(
        name="set_team_role",
        description="Links a Discord role to a bingo team"
    )
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def set_team_role(
        self,
        ctx: discord.ApplicationContext,
        team_name: discord.Option(
            str,
            "Which bingo team is this role for?",
            autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())
        ),
        role: discord.Option(
            discord.Role,
            "Which Discord role belongs to this team?"
        )
    ):
        await ctx.defer()

        team_data = database.get_team_by_name(team_name)
        if team_data is None:
            await ctx.respond(f"Unable to find team: {team_name}")
            return

        team = db_entities.Team(team_data)

        existing_team_data = database.get_team_by_discord_role_id(role.id)
        if existing_team_data is not None:
            existing_team = db_entities.Team(existing_team_data)

            if existing_team.team_id != team.team_id:
                await ctx.respond(
                    f"{role.mention} is already linked to "
                    f"{existing_team.team_name}."
                )
                return

        database.set_team_discord_role_id(team.team_id, role.id)

        await ctx.respond(
            f"{role.mention} is now linked to {team.team_name}."
        )

    @discord.slash_command(name="add_player", description="Adds a player to the bingo")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def add_player(self, ctx:discord.ApplicationContext,
                         player_name: discord.Option(str, "What is the players username?"),
                         team_name: discord.Option(str, "What team should this player be on?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names()))):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is not None:
            team = db_entities.Team(team)
        else:
            await ctx.respond(f"Team name {team_name} not found.")
            return

        database.add_player(player_name, 0, 0, 0, team.team_id, 0)
        await ctx.respond(f"{player_name} has been added to team {team.team_name}")

    @discord.slash_command(name="remove_player", description="Removes a player from the bingo")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_player(self, ctx:discord.ApplicationContext,
                            player_name: discord.Option(str, "What is the players username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names()))):
        await ctx.defer()
        player = database.get_player_by_name(player_name)
        if player is not None:
            player = db_entities.Player(player)
        else:
            await ctx.respond(f"{player_name} was not found.")
            return
        database.remove_player(player.player_id)
        await ctx.respond(f"Removed {player.player_name} from the bingo.")


    @discord.slash_command(name="change_player_team", description="Moves a player from one team to another")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def change_player_team(self, ctx:discord.ApplicationContext,
                                 player_name: discord.Option(str, "What is the players username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                                 new_team_name: discord.Option(str, "What team should this player be on?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names()))):
        await ctx.defer()
        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)

        new_team = database.get_team_by_name(new_team_name)
        if new_team is None:
            await ctx.respond(f"Unable to find team, {new_team_name}")
            return False
        team = db_entities.Team(new_team)

        database.change_player_team(player.player_id, team.team_id)
        await ctx.respond(f"Succesfully moved all data from {player.player_name} to {team.team_name}")

    @discord.slash_command(name="award_drop", description="Manually award a drop")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def award_drop(self, ctx:discord.ApplicationContext,
                         player_name: discord.Option(str, "What is the username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                         drop_name: discord.Option(str, "What is the drop name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, drop_names())),
                         quantity: discord.Option(int, "How many drops did they get?", default=1),
                         drop_value: discord.Option(int, "How much is each drop worth?", default=0)):
        await ctx.defer()

        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)

        json_data = spoof_drop.award_drop_json(player.player_name, drop_name, drop_value, quantity)
        result = dink.parse_loot(json_data, None)

        if result:
            await ctx.respond(f"Successfully awarded {player.player_name} with {quantity} x {drop_name} at {scapify.int_to_gp(drop_value)} each")
        else:
            await ctx.respond(f"Something went wrong. Check my console or contact Danbis before attempting again.")

    @discord.slash_command(name="add_team_points", description="Add points to a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def add_team_points(self,
                              ctx:discord.ApplicationContext,
                              team_name: discord.Option(str, "What team are you awarding points to?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                              points: discord.Option(int, "How many points would you like to award?")):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        database.add_team_points(team.team_id, points)
        await ctx.respond(f"Successfully awarded {team.team_name} {points} points!")

    @discord.slash_command(name="remove_team_points", description="Add points to a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_team_points(self,
                              ctx:discord.ApplicationContext,
                              team_name: discord.Option(str, "What team are you removing points from?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                              points: discord.Option(int, "How many points would you like to remove?")):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        database.add_team_points(team.team_id, -points)
        await ctx.respond(f"Successfully removed {team.team_name} {points} points!")


    @discord.slash_command(name="remove_tile_completion", description="Mark a tile as completed for a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_tile_completion(self,
                                  ctx:discord.ApplicationContext,
                                  team_name: discord.Option(str, "What team is completing a tile?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                                  tile_name: discord.Option(str, "What tile are they completing", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names()))):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)
        database.remove_completed_tile(tile.tile_id, team.team_id)
        await ctx.respond(f"I've remove a tile completion for {team.team_name} on tile {tile.tile_name}."
                          f"NOTE: I did not remove any points during this operation! Please use /remove_team_points if required")



    @discord.slash_command(name="remove_manual_progress", description="Remove tile progress from a tile")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_manual_progress(self,
                                     ctx: discord.ApplicationContext,
                                     player_name: discord.Option(str, "What is the players name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                                     tile_name: discord.Option(str, "What is the tile_name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names())),
                                     progress: discord.Option(int, "What trigger value would you like to remove?")):
        await ctx.defer()

        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)

        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)

        team = db_entities.Team(database.get_team_by_id(player.team_id))

        database.add_manual_progress(tile.tile_name, player.player_name, -progress)
        database.add_player_tile_completions(player.player_id, -progress / tile.tile_triggers_required)
        await ctx.respond(f"Successfully removed manual progress from {team.team_name} for tile {tile.tile_name}. I've also removed {progress/tile.tile_triggers_reuired} from {player.player_name}'s tile completions")

    @discord.slash_command(name="award_manual_progress", description="Add tile progress to a tile")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def award_manual_progress(self,
                                    ctx: discord.ApplicationContext,
                                    player_name: discord.Option(str, "What is the players name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                                    tile_name: discord.Option(str, "What is the tile_name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names())),
                                    progress: discord.Option(int, "What trigger value would you like to add?")):
        await ctx.defer()

        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)

        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)
        team = db_entities.Team(database.get_team_by_id(player.team_id))

        tile_completions = len(database.get_completed_tiles_by_team_id_and_tile_id(player.team_id, tile.tile_id))
        if tile_completions >= tile.tile_repetition:
            response = f"This tile has already been completed {tile.tile_repetition} times. There is no point in awarding more progress."
            ctx.respond(response)
            return

        database.add_manual_progress(tile.tile_name, player.player_name, progress)

        database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id, progress / tile.tile_triggers_required)
        response = f"Successfully added {progress} manual progress/trigger weight to {tile.tile_name} for {player.player_name}'s team. Additionally I've given {player.player_name} {round(progress/tile.tile_triggers_required, 2)} partial completions"
        progress = database.get_manual_progress_by_tile_id_and_team_id(tile.tile_id, player.team_id)
        if progress >= (tile_completions + 1) * tile.tile_triggers_required:
            database.add_completed_tile(tile.tile_id, player.team_id)
            database.add_team_points(player.team_id, tile.tile_points)
            if int(progress % tile.tile_triggers_required) == tile.tile_triggers_required:
                progress = 0
            send_webhook(team.team_webhook, title=f"{tile.tile_name} completed!", description=f"You now have {tile_completions + 1} completions and are {int(progress % tile.tile_triggers_required)}/{tile.tile_triggers_required} from your next completion", color=65280, image=None)
            response = response + f"\nIt seems they have also completed this tile so I've awarded them {tile.tile_points} points and sent them a message letting them know! They now have {tile_completions + 1} completions for this tile"
            current_trigger_rewards = 0
            for partial_completion in database.get_partial_completions_by_team_id_and_tile_id(team.team_id,
                                                                                              tile.tile_id):
                partial_completion = db_entities.PartialCompletion(partial_completion)
                database.remove_partial_completion(partial_completion.partial_completion_pk)
                database.add_player_tile_completions(partial_completion.player_id,
                                                     min(partial_completion.partial_completion,
                                                         1 - current_trigger_rewards))
                if round(partial_completion.partial_completion, 2) > round(1 - current_trigger_rewards,
                                                                           2) and tile_completions + 1 < tile.tile_repetition:
                    database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id,
                                                            partial_completion.partial_completion - (1 - current_trigger_rewards))
                else:
                    current_trigger_rewards += partial_completion.partial_completion
        else:
            send_webhook(team.team_webhook, title=f"Request approved for {tile.tile_name}!", description=f"You are now {int(progress % tile.tile_triggers_required)}/{tile.tile_triggers_required} away from completing this tile", color=16776960, image=None)

        await ctx.respond(response)

    @discord.slash_command(name="rename_team", description="Rename a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def rename_team(self,
                    ctx: discord.ApplicationContext,
                    old_team_name: discord.Option(str, "What is the old team name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                    new_team_name: discord.Option(str, "What is the new team name?")):
        await ctx.defer()

        team = database.get_team_by_name(old_team_name)

        if team is None:
            await ctx.respond(f"Unable to find team, {old_team_name}")
            return False

        database.rename_team(old_team_name, new_team_name)
        await ctx.respond(f"Updated {old_team_name}'s name to {new_team_name}")

    @discord.slash_command(name="rename_player", description="Rename a player")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def rename_player(self,
                    ctx: discord.ApplicationContext,
                    old_player_name: discord.Option(str, "What is the old player name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                    new_player_name: discord.Option(str, "What is the new player name?")):
        await ctx.defer()

        player = database.get_player_by_name(old_player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {old_player_name}")
            return False

        database.rename_player(old_player_name, new_player_name)
        await ctx.respond(f"Updated {old_player_name}'s name to {new_player_name}")
