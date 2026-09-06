import os
from collections import defaultdict

import discord
from discord.ext import commands

from utils import (
    bingo,
    database,
    db_entities,
    manual_evidence_files,
    scapify
)

from utils.autocomplete import player_names, team_names, tile_names, fuzzy_autocomplete

from utils.wom import WiseOldManError, get_group_member

ftext = "\u001b["

fnormal = "0;"
fbolt = "1;"
funderline = "4;"

fred = "31m"
fgreen = "32m"
fyellow = "33m"
fblue = "34m"
fwhite = "37m"
fend = ftext + "0m"



class ManualEvidenceSubmissionState:
    def __init__(
        self,
        submitter_id,
        submitter_name,
        player_id,
        player_name,
        screenshot,
        evidence_codeword,
        guild_id=None,
        channel_id=None
    ):
        self.submitter_id = int(
            submitter_id
        )

        self.submitter_name = str(
            submitter_name
        ).strip()

        self.player_id = int(
            player_id
        )

        self.player_name = str(
            player_name
        ).strip()

        self.screenshot = screenshot

        self.evidence_codeword = str(
            evidence_codeword
        ).strip()

        self.guild_id = (
            int(guild_id)
            if guild_id is not None
            else None
        )

        self.channel_id = (
            int(channel_id)
            if channel_id is not None
            else None
        )

        self.tile_id = None
        self.tile_name = None
        self.condition_id = None
        self.condition_label = None
        self.submitted = False


def _is_bingo_organiser(member):
    organiser_role_id = os.getenv(
        "BINGO_ORGANISER_ROLE_ID"
    )

    if organiser_role_id is None:
        return False

    return any(
        str(role.id) == organiser_role_id
        for role in getattr(member, "roles", [])
    )


def _truncate_discord_option_text(
    value,
    max_length=100
):
    text = str(
        value or ''
    ).strip()

    if len(text) <= max_length:
        return text

    return (
        text[:max_length - 3].rstrip()
        + "..."
    )


def _get_manual_evidence_condition_label(
    condition
):
    trigger = str(
        condition.get(
            "condition_trigger"
        ) or ''
    ).strip()

    if trigger:
        trigger = trigger.replace(
            '_',
            ' '
        )

        return _truncate_discord_option_text(
            trigger.title()
        )

    return "This part of the tile"


def _get_manual_evidence_condition_description(
    condition
):
    progress = int(
        condition.get(
            "progress",
            0
        )
    )

    target = int(
        condition.get(
            "target",
            1
        )
    )

    return _truncate_discord_option_text(
        f"Current progress: {progress} / {target}"
    )


def _get_manual_evidence_prompt_text(
    state,
    instruction
):
    return (
        f"Submitting evidence for "
        f"**{state.player_name}**.\n\n"
        f"**Evidence codeword:** "
        f"{state.evidence_codeword}\n"
        "Make sure this codeword is clearly visible "
        "in the screenshot.\n\n"
        f"{instruction}"
    )


async def _check_manual_evidence_submitter(
    interaction,
    state
):
    if int(interaction.user.id) != state.submitter_id:
        await interaction.response.send_message(
            "Only the person who started this submission "
            "can use these controls.",
            ephemeral=True
        )
        return False

    if state.submitted:
        await interaction.response.send_message(
            "This evidence has already been submitted.",
            ephemeral=True
        )
        return False

    return True


def _get_manual_evidence_error_message(
    error
):
    error_text = str(error).lower()

    if (
        "already complete" in error_text
        or "already contributed" in error_text
        or "completion route is already complete" in error_text
    ):
        return (
            "The bingo progressed while you were completing "
            "this submission, so this evidence can no longer "
            "be submitted for that tile. Please check the "
            "current board."
        )

    if (
        "does not exist" in error_text
        or "no completion paths" in error_text
        or "no conditions" in error_text
        or "no point value" in error_text
        or "killcount or experience" in error_text
    ):
        return (
            "The tile setup changed while you were completing "
            "this submission. Please start again."
        )

    if "not on a team" in error_text:
        return (
            "The selected player is no longer on a bingo team."
        )

    return (
        "DanBot could not submit this evidence. "
        "Please check the current bingo progress and try again."
    )


class ManualEvidenceDetailsModal(
    discord.ui.Modal
):
    def __init__(self, state):
        super().__init__(
            title="Evidence Details"
        )

        self.state = state

        self.amount = discord.ui.InputText(
            label="Amount",
            style=discord.InputTextStyle.short,
            value="1",
            min_length=1,
            max_length=12,
            required=True
        )

        self.description = discord.ui.InputText(
            label="Description or notes (optional)",
            style=discord.InputTextStyle.long,
            placeholder=(
                "Add anything that may help staff "
                "review the evidence."
            ),
            max_length=500,
            required=False
        )

        self.add_item(
            self.amount
        )

        self.add_item(
            self.description
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_manual_evidence_submitter(
            interaction,
            self.state
        ):
            return

        try:
            amount = int(
                self.amount.value.strip()
            )
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Amount must be a whole number greater than 0.",
                ephemeral=True
            )
            return

        if amount < 1:
            await interaction.response.send_message(
                "Amount must be a whole number greater than 0.",
                ephemeral=True
            )
            return

        current_codeword = (
            database.get_evidence_codeword()
        )

        if (
            current_codeword is None
            or str(current_codeword).strip()
            != self.state.evidence_codeword
        ):
            await interaction.response.send_message(
                "The bingo evidence codeword changed while "
                "you were completing this submission. "
                "Please start again using the current codeword.",
                ephemeral=True
            )
            return

        description = (
            self.description.value.strip()
            if self.description.value
            else None
        )

        evidence_path = None

        try:
            screenshot_bytes = await (
                self.state.screenshot.read()
            )

            saved_file = (
                manual_evidence_files
                .save_manual_evidence_file(
                    screenshot_bytes,
                    self.state.screenshot.filename
                )
            )

            evidence_path = saved_file[
                "evidence_path"
            ]

            result = database.add_manual_evidence(
                player_id=self.state.player_id,
                condition_id=self.state.condition_id,
                amount=amount,
                evidence_path=evidence_path,
                evidence_sha256=saved_file[
                    "evidence_sha256"
                ],
                submission_source="DISCORD",
                submitter_id=self.state.submitter_id,
                submitter_name=(
                    self.state.submitter_name
                ),
                description=description,
                discord_guild_id=(
                    self.state.guild_id
                ),
                discord_channel_id=(
                    self.state.channel_id
                ),
                discord_message_id=None,
                evidence_author_id=(
                    self.state.submitter_id
                ),
                evidence_author_name=(
                    self.state.submitter_name
                )
            )

        except ValueError as error:
            if evidence_path is not None:
                manual_evidence_files.delete_manual_evidence_file(
                    evidence_path
                )

            await interaction.response.send_message(
                _get_manual_evidence_error_message(
                    error
                ),
                ephemeral=True
            )
            return

        except Exception as error:
            if evidence_path is not None:
                manual_evidence_files.delete_manual_evidence_file(
                    evidence_path
                )

            print(
                "Manual evidence submission failed:",
                error
            )

            await interaction.response.send_message(
                "Something went wrong while submitting your "
                "evidence. Nothing was submitted. "
                "Please try again.",
                ephemeral=True
            )
            return

        self.state.submitted = True

        message = (
            "✅ **Evidence submitted**\n\n"
            f"Player: **{self.state.player_name}**\n"
            f"Tile: **{self.state.tile_name}**\n"
            f"Amount: **{amount}**\n\n"
            "Your submission is now waiting for review."
        )

        if result.get("pending_warning"):
            message += (
                "\n\n⚠️ "
                + result["pending_warning"]
            )

        await interaction.response.send_message(
            message,
            ephemeral=True
        )


class ManualEvidenceConditionSelect(
    discord.ui.Select
):
    def __init__(
        self,
        state,
        conditions
    ):
        self.state = state

        self.conditions = {
            int(condition["condition_id"]):
                condition
            for condition in conditions
        }

        options = []

        for condition in conditions:
            condition_id = int(
                condition["condition_id"]
            )

            options.append(
                discord.SelectOption(
                    label=(
                        _get_manual_evidence_condition_label(
                            condition
                        )
                    ),
                    value=str(condition_id),
                    description=(
                        _get_manual_evidence_condition_description(
                            condition
                        )
                    )
                )
            )

        super().__init__(
            placeholder="Choose the part of the tile",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_manual_evidence_submitter(
            interaction,
            self.state
        ):
            return

        condition_id = int(
            self.values[0]
        )

        condition = self.conditions.get(
            condition_id
        )

        if condition is None:
            await interaction.response.send_message(
                "That choice is no longer available. "
                "Please start the submission again.",
                ephemeral=True
            )
            return

        self.state.condition_id = condition_id
        self.state.condition_label = (
            _get_manual_evidence_condition_label(
                condition
            )
        )

        await interaction.response.send_modal(
            ManualEvidenceDetailsModal(
                self.state
            )
        )


class ManualEvidenceConditionView(
    discord.ui.View
):
    def __init__(
        self,
        state,
        conditions
    ):
        super().__init__(
            timeout=900
        )

        self.add_item(
            ManualEvidenceConditionSelect(
                state=state,
                conditions=conditions
            )
        )


class ManualEvidenceTileSelect(
    discord.ui.Select
):
    def __init__(
        self,
        state,
        tiles
    ):
        self.state = state

        self.tiles = {
            int(tile["tile_id"]):
                tile
            for tile in tiles
        }

        options = []

        for tile in tiles:
            tile_id = int(
                tile["tile_id"]
            )

            conditions = (
                tile.get("conditions")
                or []
            )

            available_count = len(
                conditions
            )

            description = (
                f"{available_count} available "
                f"{'choice' if available_count == 1 else 'choices'}"
            )

            options.append(
                discord.SelectOption(
                    label=_truncate_discord_option_text(
                        tile["tile_name"]
                    ),
                    value=str(tile_id),
                    description=(
                        _truncate_discord_option_text(
                            description
                        )
                    )
                )
            )

        super().__init__(
            placeholder="Choose a tile",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not await _check_manual_evidence_submitter(
            interaction,
            self.state
        ):
            return

        tile_id = int(
            self.values[0]
        )

        tile = self.tiles.get(
            tile_id
        )

        if tile is None:
            await interaction.response.send_message(
                "That tile is no longer available. "
                "Please start the submission again.",
                ephemeral=True
            )
            return

        conditions = (
            tile.get("conditions")
            or []
        )

        if not conditions:
            await interaction.response.send_message(
                "That tile no longer has anything that can "
                "be submitted manually. Please check the "
                "current board.",
                ephemeral=True
            )
            return

        self.state.tile_id = tile_id
        self.state.tile_name = str(
            tile["tile_name"]
        ).strip()

        if len(conditions) == 1:
            condition = conditions[0]

            self.state.condition_id = int(
                condition["condition_id"]
            )

            self.state.condition_label = (
                _get_manual_evidence_condition_label(
                    condition
                )
            )

            await interaction.response.send_modal(
                ManualEvidenceDetailsModal(
                    self.state
                )
            )
            return

        if len(conditions) > 25:
            await interaction.response.send_message(
                "That tile currently has too many separate "
                "evidence choices to show in Discord. "
                "Please ask staff to review the tile setup.",
                ephemeral=True
            )
            return

        view = ManualEvidenceConditionView(
            state=self.state,
            conditions=conditions
        )

        await interaction.response.edit_message(
            content=_get_manual_evidence_prompt_text(
                self.state,
                (
                    f"You selected **{self.state.tile_name}**. "
                    "Choose which part of the tile your "
                    "screenshot proves."
                )
            ),
            view=view
        )


class ManualEvidenceTileView(
    discord.ui.View
):
    def __init__(
        self,
        state,
        tiles
    ):
        super().__init__(
            timeout=900
        )

        self.add_item(
            ManualEvidenceTileSelect(
                state=state,
                tiles=tiles
            )
        )


class UserCog(commands.Cog):
    submit = discord.SlashCommandGroup(
        "submit",
        "Submit bingo evidence"
    )
    def __init__(self, bot):
        self.bot = bot
    
    @submit.command(
        name="evidence",
        description="Submit screenshot evidence for the bingo"
    )
    async def submit_evidence(
        self,
        ctx: discord.ApplicationContext,
        screenshot: discord.Option(
            discord.Attachment,
            "Screenshot showing your bingo evidence"
        ),
        player: discord.Option(
            str,
            (
                "Player to credit "
                "(organisers only)"
            ),
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                player_names()
            ),
            default=None
        )
    ):
        await ctx.defer(
            ephemeral=True
        )

        evidence_codeword = (
            database.get_evidence_codeword()
        )

        if (
            evidence_codeword is None
            or not str(evidence_codeword).strip()
        ):
            await ctx.respond(
                "Manual evidence submissions are not "
                "currently available because the bingo "
                "evidence codeword has not been set.",
                ephemeral=True
            )
            return

        extension = os.path.splitext(
            screenshot.filename or ''
        )[1].lower()

        if (
            extension
            not in manual_evidence_files
            .ALLOWED_EVIDENCE_EXTENSIONS
        ):
            await ctx.respond(
                "Evidence must be a PNG, JPG, JPEG, "
                "or WebP image.",
                ephemeral=True
            )
            return

        is_organiser = _is_bingo_organiser(
            ctx.author
        )

        if player is not None:
            player = str(
                player
            ).strip()

            if not is_organiser:
                await ctx.respond(
                    "Only bingo organisers can submit "
                    "evidence on behalf of another player.",
                    ephemeral=True
                )
                return

            player_data = (
                database.get_player_by_name(
                    player
                )
            )

            if player_data is None:
                await ctx.respond(
                    f"Unable to find the player "
                    f"**{player}**.",
                    ephemeral=True
                )
                return

        else:
            player_data = (
                database
                .get_player_by_discord_user_id(
                    ctx.author.id
                )
            )

            if player_data is None:
                if is_organiser:
                    await ctx.respond(
                        "Your Discord account is not linked "
                        "to a bingo player. Choose a player "
                        "with the `player` option if you are "
                        "submitting on their behalf.",
                        ephemeral=True
                    )
                else:
                    await ctx.respond(
                        "Your Discord account is not "
                        "registered. Use `/register` first.",
                        ephemeral=True
                    )

                return

        credited_player = db_entities.Player(
            player_data
        )

        try:
            submission_options = (
                database
                .get_manual_evidence_submission_options(
                    credited_player.player_id
                )
            )
        except ValueError:
            await ctx.respond(
                "That player is not currently able to "
                "submit evidence for this bingo.",
                ephemeral=True
            )
            return

        tiles = (
            submission_options.get("tiles")
            or []
        )

        if not tiles:
            await ctx.respond(
                f"There are currently no incomplete tiles "
                f"or tile parts that **"
                f"{credited_player.player_name}** can submit "
                f"manual evidence towards.",
                ephemeral=True
            )
            return

        if len(tiles) > 25:
            await ctx.respond(
                "There are currently too many eligible tiles "
                "to show in Discord. Please ask staff to "
                "review the bingo setup.",
                ephemeral=True
            )
            return

        state = ManualEvidenceSubmissionState(
            submitter_id=ctx.author.id,
            submitter_name=(
                ctx.author.display_name
            ),
            player_id=(
                credited_player.player_id
            ),
            player_name=(
                credited_player.player_name
            ),
            screenshot=screenshot,
            evidence_codeword=(
                evidence_codeword
            ),
            guild_id=(
                ctx.guild.id
                if ctx.guild is not None
                else None
            ),
            channel_id=(
                ctx.channel.id
                if ctx.channel is not None
                else None
            )
        )

        view = ManualEvidenceTileView(
            state=state,
            tiles=tiles
        )

        await ctx.respond(
            _get_manual_evidence_prompt_text(
                state,
                (
                    "Choose the tile that your "
                    "screenshot provides evidence for."
                )
            ),
            view=view,
            ephemeral=True
        )

    @discord.slash_command(
        name="register",
        description="Link your Discord account to your OSRS account"
    )
    async def register(
        self,
        ctx: discord.ApplicationContext,
        rsn: discord.Option(str, "Your Old School RuneScape name")
    ):
        await ctx.defer(ephemeral=True)

        existing_link = database.get_player_by_discord_user_id(ctx.author.id)
        if existing_link is not None:
            player = db_entities.Player(existing_link)
            await ctx.respond(
                f"Your Discord account is already linked to "
                f"**{player.player_name}**.",
                ephemeral=True
            )
            return

        matched_teams = []

        for role in ctx.author.roles:
            team_data = database.get_team_by_discord_role_id(role.id)

            if team_data is not None:
                matched_teams.append(db_entities.Team(team_data))

        if len(matched_teams) == 0:
            await ctx.respond(
                "You do not have a recognised bingo team role.",
                ephemeral=True
            )
            return

        if len(matched_teams) > 1:
            await ctx.respond(
                "You have more than one bingo team role. "
                "Please ask an administrator to correct this.",
                ephemeral=True
            )
            return

        team = matched_teams[0]

        try:
            wom_player = get_group_member(rsn)
        except WiseOldManError as error:
            await ctx.respond(str(error), ephemeral=True)
            return

        if wom_player is None:
            await ctx.respond(
                f"**{rsn}** was not found in the configured "
                f"Wise Old Man group.",
                ephemeral=True
            )
            return

        display_name = wom_player["displayName"]
        player_data = database.get_player_by_name(display_name)

        if player_data is None:
            database.add_player(
                display_name,
                0,
                0,
                0,
                team.team_id,
                0
            )
            player_data = database.get_player_by_name(display_name)

        player = db_entities.Player(player_data)

        if player.team_id != team.team_id:
            current_team = db_entities.Team(
                database.get_team_by_id(player.team_id)
            )

            await ctx.respond(
                f"**{display_name}** is currently assigned to "
                f"**{current_team.team_name}**, but your Discord role "
                f"is for **{team.team_name}**. Please contact an "
                f"administrator.",
                ephemeral=True
            )
            return

        if player.discord_user_id is not None:
            await ctx.respond(
                f"**{display_name}** is already linked to another "
                f"Discord account.",
                ephemeral=True
            )
            return

        database.link_player_to_discord(
            player.player_id,
            ctx.author.id
        )

        await ctx.respond(
            f"Registration complete. Your Discord account is now "
            f"linked to **{display_name}** on **{team.team_name}**.",
            ephemeral=True
        )
    @discord.slash_command(name="help", description="A list of all my cool commands!")
    async def help(self, ctx: discord.ApplicationContext):
        commands_info = {
            "help": (
                "Show this list of available commands."
            ),
            "register": (
                "Link your Discord account to your OSRS account."
            ),
            "dink": (
                "Get help setting up the Dink RuneLite plugin."
            ),
            "player": (
                "View a player's bingo statistics."
            ),
            "team": (
                "View a team's bingo statistics."
            ),
            "progress": (
                "Check your team's progress on a specific tile."
            ),
            "board": (
                "View your Discord-role team's board. "
                "Bingo Organisers may inspect another team."
            ),
            "leaderboard": (
                "Show the current team and player standings."
            )
        }

        response = "**Here are all my available commands:**\n\n"
        for command, description in commands_info.items():
            response += f"/{command} - {description}\n"

        await ctx.respond(response)

    @discord.slash_command(
        name="dink",
        description="Get help setting up the Dink RuneLite plugin"
    )
    async def dink(
        self,
        ctx: discord.ApplicationContext
    ):
        await ctx.respond(
            "Dink tracking is not currently enabled on this "
            "development server.\n\n"
            "Once DanBot is publicly hosted, Bingo Organisers will "
            "provide the correct Dink import settings."
        )

    @discord.slash_command(
        name="player",
        description="View a player's bingo statistics"
    )
    async def player(
        self,
        ctx: discord.ApplicationContext,
        player_name: discord.Option(
            str,
            "Which player would you like to view?",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                player_names()
            )
        )
    ):
        await ctx.defer()

        player_data = database.get_player_by_name(player_name)

        if player_data is None:
            await ctx.respond(
                f"Unable to find the player **{player_name}**."
            )
            return

        player = db_entities.Player(player_data)

        team_data = database.get_team_by_id(player.team_id)

        if team_data is None:
            team_name = "Unknown team"
        else:
            team_name = db_entities.Team(team_data).team_name

        tile_count = round(float(player.tiles_completed), 2)

        if tile_count.is_integer():
            tile_count = int(tile_count)

        partial_progress = 0

        for partial_data in (
            database.get_partial_completions_by_player_id(
                player.player_id
            )
        ):
            partial = db_entities.PartialCompletion(partial_data)
            partial_progress += float(
                partial.partial_completion
            )

        partial_progress = round(partial_progress, 2)

        drop_totals = defaultdict(
            lambda: {
                "quantity": 0,
                "value": 0
            }
        )

        for drop_data in database.get_drops_by_player_id(
            player.player_id
        ):
            drop = db_entities.Drop(drop_data)

            drop_totals[drop.drop_name]["quantity"] += (
                drop.drop_quantity
            )
            drop_totals[drop.drop_name]["value"] += (
                drop.drop_value * drop.drop_quantity
            )

        sorted_drops = sorted(
            drop_totals.items(),
            key=lambda item: item[1]["value"],
            reverse=True
        )

        drop_lines = []

        for drop_name, drop_details in sorted_drops[:10]:
            drop_lines.append(
                f"**{drop_name}** x"
                f"{drop_details['quantity']} - "
                f"{scapify.int_to_gp(drop_details['value'])}"
            )

        killcounts = []

        for killcount_data in (
            database.get_killcount_by_player_id(
                player.player_id
            )
        ):
            killcounts.append(
                db_entities.Killcount(killcount_data)
            )

        killcounts.sort(
            key=lambda killcount: killcount.kills,
            reverse=True
        )

        killcount_lines = [
            f"**{killcount.boss_name}:** {killcount.kills}"
            for killcount in killcounts[:10]
        ]

        relevant_drop_lines = []

        for relevant_drop_data in (
            database.get_relevant_drop_by_player_id(
                player.player_id
            )
        ):
            relevant_drop = db_entities.RelevantDrop(
                relevant_drop_data
            )

            relevant_drop_lines.append(
                f"**{relevant_drop.tile_name}:** "
                f"{relevant_drop.drop_name}"
            )

        embed = discord.Embed(
            title=player.player_name,
            description=f"Team: **{team_name}**"
        )

        embed.add_field(
            name="Bingo statistics",
            value=(
                f"Tiles completed: **{tile_count}**\n"
                f"Partial progress: **{partial_progress}**\n"
                f"GP gained: **"
                f"{scapify.int_to_gp(player.gp_gained)}**\n"
                f"Pets: **{player.pet_count}**\n"
                f"Deaths: **{player.deaths}**"
            ),
            inline=False
        )

        embed.add_field(
            name="Top drops",
            value=(
                "\n".join(drop_lines)
                if drop_lines
                else "No drops recorded."
            ),
            inline=False
        )

        embed.add_field(
            name="Kill counts",
            value=(
                "\n".join(killcount_lines)
                if killcount_lines
                else "No kill counts recorded."
            ),
            inline=False
        )

        if relevant_drop_lines:
            embed.add_field(
                name="Bingo-related drops",
                value="\n".join(relevant_drop_lines[:10]),
                inline=False
            )

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="team",
        description="View a team's bingo statistics"
    )
    async def team(
        self,
        ctx: discord.ApplicationContext,
        team_name: discord.Option(
            str,
            "Which team would you like to view?",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                team_names()
            )
        )
    ):
        await ctx.defer()

        team_data = database.get_team_by_name(team_name)

        if team_data is None:
            await ctx.respond(
                f"Unable to find the team **{team_name}**."
            )
            return

        team = db_entities.Team(team_data)

        players = [
            db_entities.Player(player_data)
            for player_data in database.get_players_by_team_id(
                team.team_id
            )
        ]

        players.sort(
            key=lambda player: (
                player.tiles_completed,
                player.gp_gained
            ),
            reverse=True
        )

        total_gp = sum(player.gp_gained for player in players)
        total_deaths = sum(player.deaths for player in players)
        total_pets = sum(player.pet_count for player in players)
        total_tiles = sum(
            float(player.tiles_completed)
            for player in players
        )

        total_tiles = round(total_tiles, 2)

        if total_tiles.is_integer():
            total_tiles = int(total_tiles)

        partial_progress = 0

        for partial_data in (
            database.get_partial_completions_by_team_id(
                team.team_id
            )
        ):
            partial = db_entities.PartialCompletion(partial_data)
            partial_progress += float(
                partial.partial_completion
            )

        partial_progress = round(partial_progress, 2)

        player_lines = []

        for position, player in enumerate(players[:10], start=1):
            tile_count = round(
                float(player.tiles_completed),
                2
            )

            if tile_count.is_integer():
                tile_count = int(tile_count)

            tile_label = (
                "tile"
                if tile_count == 1
                else "tiles"
            )

            player_lines.append(
                f"**{position}. {player.player_name}** - "
                f"{tile_count} tiles | "
                f"{scapify.int_to_gp(player.gp_gained)}"
            )

        drop_totals = defaultdict(
            lambda: {
                "quantity": 0,
                "value": 0
            }
        )

        for drop_data in database.get_drops_by_team_id(
            team.team_id
        ):
            drop = db_entities.Drop(drop_data)

            drop_totals[drop.drop_name]["quantity"] += (
                drop.drop_quantity
            )
            drop_totals[drop.drop_name]["value"] += (
                drop.drop_value * drop.drop_quantity
            )

        sorted_drops = sorted(
            drop_totals.items(),
            key=lambda item: item[1]["value"],
            reverse=True
        )

        drop_lines = []

        for drop_name, drop_details in sorted_drops[:10]:
            drop_lines.append(
                f"**{drop_name}** x"
                f"{drop_details['quantity']} - "
                f"{scapify.int_to_gp(drop_details['value'])}"
            )

        killcount_totals = defaultdict(int)

        for killcount_data in database.get_killcount_by_team_id(
            team.team_id
        ):
            killcount = db_entities.Killcount(
                killcount_data
            )

            killcount_totals[killcount.boss_name] += (
                killcount.kills
            )

        sorted_killcounts = sorted(
            killcount_totals.items(),
            key=lambda item: item[1],
            reverse=True
        )

        killcount_lines = [
            f"**{boss_name}:** {kills}"
            for boss_name, kills in sorted_killcounts[:10]
        ]

        relevant_drop_lines = []

        for relevant_drop_data in (
            database.get_relevant_drop_by_team_id(
                team.team_id
            )
        ):
            relevant_drop = db_entities.RelevantDrop(
                relevant_drop_data
            )

            relevant_drop_lines.append(
                f"**{relevant_drop.tile_name}:** "
                f"{relevant_drop.drop_name} "
                f"({relevant_drop.player_name})"
            )

        team_points = round(float(team.team_points), 2)

        if team_points.is_integer():
            team_points = int(team_points)

        embed = discord.Embed(
            title=team.team_name,
            description=f"Bingo points: **{team_points}**"
        )

        embed.add_field(
            name="Team statistics",
            value=(
                f"Players: **{len(players)}**\n"
                f"Tiles completed: **{total_tiles}**\n"
                f"Partial progress: **{partial_progress}**\n"
                f"GP gained: **"
                f"{scapify.int_to_gp(total_gp)}**\n"
                f"Pets: **{total_pets}**\n"
                f"Deaths: **{total_deaths}**"
            ),
            inline=False
        )

        embed.add_field(
            name="Player standings",
            value=(
                "\n".join(player_lines)
                if player_lines
                else "No players are assigned to this team."
            ),
            inline=False
        )

        embed.add_field(
            name="Top drops",
            value=(
                "\n".join(drop_lines)
                if drop_lines
                else "No drops recorded."
            ),
            inline=False
        )

        embed.add_field(
            name="Kill counts",
            value=(
                "\n".join(killcount_lines)
                if killcount_lines
                else "No kill counts recorded."
            ),
            inline=False
        )

        if relevant_drop_lines:
            embed.add_field(
                name="Bingo-related drops",
                value="\n".join(relevant_drop_lines[:10]),
                inline=False
            )

        await ctx.respond(embed=embed)


    @discord.slash_command(
        name="progress",
        description="Check your team's progress on a specific tile"
    )
    async def progress(
        self,
        ctx: discord.ApplicationContext,
        tile_name: discord.Option(
            str,
            "Which tile are you checking?",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                tile_names()
            )
        )
    ):
        await ctx.defer()

        player_data = database.get_player_by_discord_user_id(
            ctx.author.id
        )

        if player_data is None:
            await ctx.respond(
                "Your Discord account is not registered. "
                "Use `/register` first."
            )
            return

        player = db_entities.Player(player_data)

        team_data = database.get_team_by_id(player.team_id)
        if team_data is None:
            await ctx.respond(
                "Your registered bingo team could not be found. "
                "Please contact an administrator."
            )
            return

        team = db_entities.Team(team_data)

        tile_data = database.get_tile_by_name(tile_name)
        if tile_data is None:
            await ctx.respond(
                f"Unable to find the tile **{tile_name}**."
            )
            return

        tile = db_entities.Tile(tile_data)
        tile_progress = bingo.get_progress(
            team.team_id,
            tile.tile_id
        )

        await ctx.respond(tile_progress.status_text)

    @discord.slash_command(
        name="board",
        description="View your team's bingo board"
    )
    async def board(
        self,
        ctx: discord.ApplicationContext,
        board_type: discord.Option(
            str,
            "Which version of the board would you like?",
            autocomplete=discord.utils.basic_autocomplete(
                [
                    "All Tiles",
                    "Completed Tiles",
                    "Incomplete Tiles",
                    "Partial Tiles"
                ]
            )
        ),
        team_name: discord.Option(
            str,
            "Team to inspect — Bingo Organisers only",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                team_names()
            ),
            default=None
        )
    ):

        await ctx.defer()

        player_data = database.get_player_by_discord_user_id(
            ctx.author.id
        )

        organiser_role_id = os.getenv(
            "BINGO_ORGANISER_ROLE_ID"
        )

        is_organiser = (
            organiser_role_id is not None
            and any(
                str(role.id) == organiser_role_id
                for role in ctx.author.roles
            )
        )

        if team_name is not None:
            if not is_organiser:
                await ctx.respond(
                    "Only Bingo Organisers can inspect another "
                    "team's board."
                )
                return

            team_data = database.get_team_by_name(team_name)

            if team_data is None:
                await ctx.respond(
                    f"Unable to find the team **{team_name}**."
                )
                return

            team = db_entities.Team(team_data)

        else:
            matched_teams = []

            for role in ctx.author.roles:
                team_data = (
                    database.get_team_by_discord_role_id(
                        role.id
                    )
                )

                if team_data is not None:
                    matched_teams.append(
                        db_entities.Team(team_data)
                    )

            if len(matched_teams) == 0:
                if is_organiser:
                    await ctx.respond(
                        "You do not have a bingo team role. "
                        "Choose a team using the optional "
                        "`team_name` field."
                    )
                else:
                    await ctx.respond(
                        "You do not have a recognised bingo "
                        "team role."
                    )
                return

            if len(matched_teams) > 1:
                await ctx.respond(
                    "You have more than one bingo team role. "
                    "Please ask an administrator to correct this."
                )
                return

            team = matched_teams[0]
        tiles = database.get_tiles()
        completed_tiles = database.get_completed_tiles()

        completion_counts = defaultdict(int)

        for completed_tile_data in completed_tiles:
            completed_tile = db_entities.CompletedTile(
                completed_tile_data
            )

            if completed_tile.team_id == team.team_id:
                completion_counts[completed_tile.tile_id] += 1

        lines = []

        for tile_data in tiles:
            tile = db_entities.Tile(tile_data)
            completions = completion_counts[tile.tile_id]

            if board_type == "All Tiles":
                completed_icons = (
                    ":white_check_mark:"
                    * min(completions, tile.tile_repetition)
                )
                incomplete_icons = (
                    ":x:"
                    * max(tile.tile_repetition - completions, 0)
                )

                lines.append(
                    f"**{tile.tile_name}:** "
                    f"{completed_icons}{incomplete_icons}"
                )

            elif board_type == "Completed Tiles":
                if completions > 0:
                    completed_icons = (
                        ":white_check_mark:"
                        * min(completions, tile.tile_repetition)
                    )
                    incomplete_icons = (
                        ":x:"
                        * max(tile.tile_repetition - completions, 0)
                    )

                    lines.append(
                        f"**{tile.tile_name}:** "
                        f"{completed_icons}{incomplete_icons}"
                    )

            elif board_type == "Incomplete Tiles":
                if completions == 0:
                    lines.append(
                        f"**{tile.tile_name}:** "
                        f"{':x:' * tile.tile_repetition}"
                    )

            elif board_type == "Partial Tiles":
                if completions >= tile.tile_repetition:
                    continue

                tile_progress = bingo.get_progress(
                    team.team_id,
                    tile.tile_id
                )

                if (
                    tile_progress is not None
                    and tile_progress.progress_value > 0
                ):
                    status_text = tile_progress.status_text

                    status_text = (
                        status_text
                        .replace("<p>", "")
                        .replace("</p>", "")
                        .replace("<ul>", "\n")
                        .replace("</ul>", "")
                        .replace("<li>", "• ")
                        .replace("</li>", "\n")
                        .strip()
                    )

                    lines.append(
                        f"**{tile.tile_name}**\n{status_text}"
                    )

        if not lines:
            lines.append(
                "There are no tiles matching this board view."
            )

        header = f"## {board_type} for {team.team_name}"
        messages = []
        current_message = header

        for line in lines:
            addition = f"\n{line}"

            if len(current_message) + len(addition) > 1900:
                messages.append(current_message)
                current_message = line
            else:
                current_message += addition

        messages.append(current_message)

        await ctx.respond(messages[0])

        for message in messages[1:]:
            await ctx.followup.send(message)

    @discord.slash_command(
        name="leaderboard",
        description="Show the current team and player standings"
    )
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext
    ):
        await ctx.defer()

        players = [
            db_entities.Player(player_data)
            for player_data in database.get_players()
        ]

        teams = [
            db_entities.Team(team_data)
            for team_data in database.get_teams()
        ]

        team_gp = defaultdict(int)

        for player in players:
            team_gp[player.team_id] += player.gp_gained

        teams.sort(
            key=lambda team: (
                team.team_points,
                team_gp[team.team_id]
            ),
            reverse=True
        )

        players.sort(
            key=lambda player: (
                player.tiles_completed,
                player.gp_gained
            ),
            reverse=True
        )

        team_lines = []

        for position, team in enumerate(teams, start=1):
            team_points = round(float(team.team_points), 2)

            if team_points.is_integer():
                team_points = int(team_points)

            point_label = (
                "point"
                if team_points == 1
                else "points"
            )

            team_lines.append(
                f"**{position}. {team.team_name}** - "
                f"{team_points} {point_label} | "
                f"{scapify.int_to_gp(team_gp[team.team_id])}"
            )

        player_lines = []

        for position, player in enumerate(players, start=1):
            tile_count = round(float(player.tiles_completed), 2)

            if tile_count.is_integer():
                tile_count = int(tile_count)

            tile_label = (
                "tile"
                if tile_count == 1
                else "tiles"
            )

            player_lines.append(
                f"**{position}. {player.player_name}** - "
                f"{tile_count} {tile_label} | "
                f"{scapify.int_to_gp(player.gp_gained)}"
            )

        if not team_lines:
            team_lines.append("No teams have been created.")

        if not player_lines:
            player_lines.append("No players have been registered.")

        sections = [
            "## Team Standings\n" + "\n".join(team_lines),
            "## Player Standings\n" + "\n".join(player_lines)
        ]

        messages = []
        current_message = ""

        for section in sections:
            for line in section.splitlines():
                addition = line + "\n"

                if len(current_message) + len(addition) > 1900:
                    messages.append(current_message.rstrip())
                    current_message = addition
                else:
                    current_message += addition

        if current_message:
            messages.append(current_message.rstrip())

        await ctx.respond(messages[0])

        for message in messages[1:]:
            await ctx.followup.send(message)