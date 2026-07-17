import io
import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ---------- Configuration ----------
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = int(os.getenv("TICKET_STAFF_ROLE_ID", 0))

CATEGORY_IDS = {
    "support":          int(os.getenv("TICKET_CATEGORY_SUPPORT", 0)),
    "building_service": int(os.getenv("TICKET_CATEGORY_BUILDING_SERVICE", 0)),
    "spawners":         int(os.getenv("TICKET_CATEGORY_SPAWNERS", 0)),
    "giveaway":         int(os.getenv("TICKET_CATEGORY_GIVEAWAY", 0)),
}

LOG_CHANNEL_ID = int(os.getenv("TRANSCRIPT_LOG_CHANNEL_ID", 0))

TICKET_DESC = os.getenv("TICKET_DESCRIPTION", "A staff member will assist you shortly.")
PANEL_DESC = os.getenv("PANEL_DESCRIPTION", "Choose the category below that matches your request. Staff will assist you shortly.")
COLOR_STR = os.getenv("TICKET_COLOR", "#3498db")

try:
    EMBED_COLOR = int(COLOR_STR.strip("#"), 16)
except ValueError:
    EMBED_COLOR = 0x3498db

CLOSE_EMBED_COLOR = 0xFF0000  # Red for close embeds

TYPE_PREFIXES = {
    "support":          "support",
    "building_service": "buildingservice",
    "spawners":         "spawners",
    "giveaway":         "giveaway",
}

# ---------- Bot Setup ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- MODAL for Close Reason ----------
class CloseReasonModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(
        label="Reason for closing",
        style=discord.TextStyle.paragraph,
        placeholder="E.g., resolved, duplicate, invalid request...",
        required=True,
        max_length=1000
    )

    def __init__(self, channel: discord.TextChannel, ticket_type: str, opener_id: int):
        super().__init__()
        self.channel = channel
        self.ticket_type = ticket_type
        self.opener_id = opener_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Generate transcript
        transcript = await self.generate_transcript()

        guild = interaction.guild
        opener = guild.get_member(self.opener_id)
        if opener is None:
            try:
                opener = await bot.fetch_user(self.opener_id)
            except:
                opener = None

        closer = interaction.user

        # DM the opener (red embed)
        if opener:
            embed_dm = discord.Embed(
                title=f"Ticket Closed – {self.channel.name}",
                color=CLOSE_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            embed_dm.add_field(name="Closed by", value=closer.mention, inline=True)
            embed_dm.add_field(name="Opened by", value=opener.mention, inline=True)
            embed_dm.add_field(name="Reason", value=self.reason.value, inline=False)

            transcript_file = discord.File(
                io.BytesIO(transcript.encode()),
                filename=f"transcript-{self.channel.name}.txt"
            )
            try:
                await opener.send(
                    content=f"Here is your ticket transcript from **#{self.channel.name}**:",
                    embed=embed_dm,
                    file=transcript_file
                )
            except discord.Forbidden:
                pass

        # Log channel (red embed)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title=f"Ticket Closed – {self.channel.name}",
                color=CLOSE_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Opened by", value=opener.mention if opener else f"ID {self.opener_id}", inline=True)
            log_embed.add_field(name="Closed by", value=closer.mention, inline=True)
            log_embed.add_field(name="Reason", value=self.reason.value, inline=False)
            log_embed.add_field(name="Category", value=self.ticket_type.replace("_", " ").title(), inline=True)

            if len(transcript) > 1900:
                file = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"log-{self.channel.name}.txt"
                )
                await log_channel.send(embed=log_embed, file=file)
            else:
                await log_channel.send(content=f"```\n{transcript}\n```", embed=log_embed)

        # Delete ticket channel
        try:
            await self.channel.delete(reason=f"Closed by {closer} – {self.reason.value}")
        except discord.Forbidden:
            pass

        await interaction.followup.send("Ticket closed.", ephemeral=True)

    async def generate_transcript(self) -> str:
        lines = []
        async for msg in self.channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = msg.author.display_name
            content = msg.content if msg.content else ""
            if msg.attachments:
                content += f" [Attachments: {', '.join(a.filename for a in msg.attachments)}]"
            lines.append(f"[{timestamp}] {author}: {content}")
        return "\n".join(lines)


# ---------- Ticket Actions View (Close first, then Claim) ----------
class TicketActionsView(discord.ui.View):
    def __init__(self, ticket_type: str = None, opener_id: int = 0):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        self.opener_id = opener_id
        self.claimed_by = None

    # Close button FIRST
    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket",
        emoji="🔒"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.get_role(STAFF_ROLE_ID):
            await interaction.response.send_message(
                "❌ You need the staff role to close tickets.", ephemeral=True
            )
            return

        channel = interaction.channel

        # Fallback data recovery after restart
        if self.ticket_type is None or self.opener_id == 0:
            for ttype, prefix in TYPE_PREFIXES.items():
                if channel.name.startswith(prefix + "-"):
                    self.ticket_type = ttype
                    break
            else:
                self.ticket_type = "unknown"

            staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Member) and overwrite.view_channel is True:
                    if target != interaction.guild.me and (staff_role is None or not target.get_role(STAFF_ROLE_ID)):
                        self.opener_id = target.id
                        break
            if self.opener_id == 0:
                await interaction.response.send_message(
                    "Could not determine ticket opener.", ephemeral=True
                )
                return

        modal = CloseReasonModal(
            channel=channel,
            ticket_type=self.ticket_type,
            opener_id=self.opener_id
        )
        await interaction.response.send_modal(modal)

    # Claim button SECOND (green)
    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.success,
        custom_id="claim_ticket",
        emoji="✅"
    )
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.get_role(STAFF_ROLE_ID):
            await interaction.response.send_message(
                "❌ You need the staff role to claim tickets.", ephemeral=True
            )
            return

        self.claimed_by = interaction.user.mention
        button.disabled = True  # disable claim button after claim

        # Update the embed to show claimed by
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed by", value=self.claimed_by, inline=False)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("Ticket claimed!", ephemeral=True)


# ---------- Panel View (4 ticket type buttons) ----------
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Support", style=discord.ButtonStyle.success, custom_id="ticket_support", emoji="🎫")
    async def ticket_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "support")

    @discord.ui.button(label="Building Service", style=discord.ButtonStyle.danger, custom_id="ticket_building_service", emoji="🏠")
    async def ticket_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "building_service")

    @discord.ui.button(label="Buy/Sell Spawners", style=discord.ButtonStyle.primary, custom_id="ticket_spawners", emoji="🛒")
    async def ticket_spawners(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "spawners")

    @discord.ui.button(label="Giveaway Claim", style=discord.ButtonStyle.secondary, custom_id="ticket_giveaway", emoji="🎉")
    async def ticket_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "giveaway")

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        staff_role = guild.get_role(STAFF_ROLE_ID)
        category_id = CATEGORY_IDS[ticket_type]
        category = guild.get_channel(category_id)

        if staff_role is None:
            await interaction.followup.send("❌ Staff role not found. Check .env.", ephemeral=True)
            return
        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(f"❌ Category for '{ticket_type}' not found. Check .env.", ephemeral=True)
            return

        prefix = TYPE_PREFIXES[ticket_type]
        channel_name = f"{prefix}-{interaction.user.name}".lower().replace(" ", "-")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            staff_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            bot.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
        }

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"{ticket_type} ticket by {interaction.user}"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to create channels.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
            return

        # Welcome embed
        embed = discord.Embed(
            title="Ticket Created",
            description=TICKET_DESC,
            color=EMBED_COLOR
        )
        content = f"{staff_role.mention} {interaction.user.mention}"
        allowed = discord.AllowedMentions(roles=True, users=True)

        # Actions view with Close before Claim
        actions_view = TicketActionsView(ticket_type=ticket_type, opener_id=interaction.user.id)
        await ticket_channel.send(content=content, embed=embed, view=actions_view, allowed_mentions=allowed)

        await interaction.followup.send(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)


# ---------- Bot Events ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Register persistent views
    bot.add_view(TicketPanelView())
    bot.add_view(TicketActionsView())  # dummy, data recovered if needed
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# ---------- Staff command: send panel ----------
@bot.tree.command(name="ticketpanel", description="Send the ticket panel with four category buttons (staff only)")
@app_commands.checks.has_role(STAFF_ROLE_ID)
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Open a Ticket",
        description=PANEL_DESC,  # editable in .env
        color=EMBED_COLOR
    )
    view = TicketPanelView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Panel sent!", ephemeral=True)

@ticketpanel.error
async def ticketpanel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message("❌ You need the staff role to use this command.", ephemeral=True)


# ---------- Optional: slash close command ----------
@bot.tree.command(name="close", description="Close the current ticket (staff only)")
@app_commands.checks.has_role(STAFF_ROLE_ID)
async def close(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel.name.startswith(("support-", "buildingservice-", "spawners-", "giveaway-")):
        await interaction.response.send_message("This command can only be used in a ticket channel.", ephemeral=True)
        return

    ticket_type = "unknown"
    for ttype, prefix in TYPE_PREFIXES.items():
        if channel.name.startswith(prefix + "-"):
            ticket_type = ttype
            break

    opener_id = 0
    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    for target, overwrite in channel.overwrites.items():
        if isinstance(target, discord.Member) and overwrite.view_channel is True:
            if target != interaction.guild.me and (staff_role is None or not target.get_role(STAFF_ROLE_ID)):
                opener_id = target.id
                break

    if opener_id == 0:
        await interaction.response.send_message("Could not determine ticket opener.", ephemeral=True)
        return

    modal = CloseReasonModal(channel=channel, ticket_type=ticket_type, opener_id=opener_id)
    await interaction.response.send_modal(modal)

@close.error
async def close_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message("❌ You need the staff role to use this command.", ephemeral=True)


# ---------- Run ----------
bot.run(TOKEN)
