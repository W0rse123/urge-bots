import os
import json
import random
import asyncio
import time
import io
import re
from typing import Dict, Optional, Set

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

# -------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MANAGER_ROLE_ID = os.getenv("GIVEAWAY_MANAGER_ROLE_ID")
if MANAGER_ROLE_ID:
    MANAGER_ROLE_ID = int(MANAGER_ROLE_ID)

TICKET_CATEGORY_ID = os.getenv("TICKET_CATEGORY_ID")
if TICKET_CATEGORY_ID:
    TICKET_CATEGORY_ID = int(TICKET_CATEGORY_ID)

TRANSCRIPT_CHANNEL_ID = os.getenv("TRANSCRIPT_CHANNEL_ID")
if TRANSCRIPT_CHANNEL_ID:
    TRANSCRIPT_CHANNEL_ID = int(TRANSCRIPT_CHANNEL_ID)

DATA_FILE = "giveaways.json"
giveaways: Dict[int, dict] = {}

# -------------------------------------------------------------------
def parse_duration(dur_str: str) -> int:
    dur_str = dur_str.strip().lower()
    if not dur_str:
        raise ValueError("Empty duration")
    if dur_str.isdigit():
        return int(dur_str)
    unit = dur_str[-1]
    if unit not in ('s', 'm', 'h', 'd'):
        raise ValueError(f"Unknown time unit: {unit}")
    try:
        amount = int(dur_str[:-1])
    except ValueError:
        raise ValueError(f"Invalid number: {dur_str[:-1]}")
    if amount <= 0:
        raise ValueError("Duration must be positive")
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return amount * multipliers[unit]

def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins} minute{'s' if mins != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"

def sanitize_channel_name(name: str) -> str:
    name = re.sub(r'[^a-zA-Z0-9\-]', '-', name.lower().replace(' ', '-'))
    name = re.sub(r'-+', '-', name)
    name = name.strip('-')
    return name[:100]

# -------------------------------------------------------------------
def save_giveaways():
    data = {}
    for msg_id, gw in giveaways.items():
        gw_copy = gw.copy()
        gw_copy['entries'] = list(gw['entries'])
        gw_copy['winners_list'] = list(gw.get('winners_list', []))
        gw_copy['claimed'] = list(gw.get('claimed', []))
        data[str(msg_id)] = gw_copy
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_giveaways():
    global giveaways
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    for msg_id_str, gw_data in data.items():
        msg_id = int(msg_id_str)
        gw_data['entries'] = set(gw_data['entries'])
        gw_data['winners_list'] = set(gw_data.get('winners_list', []))
        gw_data['claimed'] = set(gw_data.get('claimed', []))
        giveaways[msg_id] = gw_data

# -------------------------------------------------------------------
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# -------------------------------------------------------------------
async def can_manage_giveaway(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    if MANAGER_ROLE_ID is None:
        return False
    role = interaction.guild.get_role(MANAGER_ROLE_ID)
    if role is None:
        return False
    return role in interaction.user.roles

# -------------------------------------------------------------------
class JoinGiveawayButton(discord.ui.Button):
    def __init__(self, message_id: int):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Join Giveaway",
            emoji="🎟️",
            custom_id=f"giveaway_join_{message_id}"
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        gw = giveaways.get(self.message_id)
        if not gw or gw.get('ended', False):
            await interaction.response.send_message("This giveaway is no longer active.", ephemeral=True)
            return
        if interaction.user.id in gw['entries']:
            await interaction.response.send_message("You're already entered!", ephemeral=True)
            return

        gw['entries'].add(interaction.user.id)
        save_giveaways()

        message = interaction.message
        if message and message.embeds:
            embed = message.embeds[0]
            for i, field in enumerate(embed.fields):
                if field.name == "Entries":
                    embed.set_field_at(i, name="Entries", value=str(len(gw['entries'])), inline=False)
                    break
            else:
                embed.add_field(name="Entries", value=str(len(gw['entries'])), inline=False)
            await message.edit(embed=embed)

        await interaction.response.send_message("You've entered the giveaway!", ephemeral=True)

class GiveawayView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.add_item(JoinGiveawayButton(message_id))

# -------------------------------------------------------------------
class GiveawayModal(discord.ui.Modal, title="Create a Giveaway"):
    duration_input = discord.ui.TextInput(
        label="Duration",
        placeholder="e.g. 30s, 5m, 2h, 1d (or just a number for seconds)",
        required=True,
        max_length=20
    )
    winners_input = discord.ui.TextInput(
        label="Number of Winners",
        placeholder="1",
        default="1",
        required=True,
        max_length=3
    )
    prize_input = discord.ui.TextInput(
        label="Prize",
        placeholder="e.g. Discord Nitro",
        required=True,
        max_length=100
    )
    description_input = discord.ui.TextInput(
        label="Description",
        placeholder="Optional description shown in the embed",
        required=False,
        max_length=200,
        style=discord.TextStyle.long
    )
    claim_time_input = discord.ui.TextInput(
        label="Claim Time (optional)",
        placeholder="e.g. 5m, 1h – time winners have to claim",
        required=False,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not await can_manage_giveaway(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        dur_str = self.duration_input.value
        try:
            seconds = parse_duration(dur_str)
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid duration: {e}", ephemeral=True)
            return

        winners_str = self.winners_input.value
        if not winners_str.isdigit() or int(winners_str) < 1:
            await interaction.response.send_message("❌ Number of winners must be a positive integer.", ephemeral=True)
            return
        winners = int(winners_str)

        prize = self.prize_input.value
        description = self.description_input.value.strip() or None

        claim_seconds = None
        claim_str = self.claim_time_input.value.strip()
        if claim_str:
            try:
                claim_seconds = parse_duration(claim_str)
            except ValueError as e:
                await interaction.response.send_message(f"❌ Invalid claim time: {e}", ephemeral=True)
                return

        end_time = time.time() + seconds

        embed = discord.Embed(title=prize, color=discord.Color.gold())
        desc_lines = []
        if description:
            desc_lines.append(description)
            desc_lines.append("")
        desc_lines.append(f"**Ends:** <t:{int(end_time)}:R> (<t:{int(end_time)}:F>)")
        desc_lines.append(f"**Winners:** {winners}")
        if claim_seconds:
            desc_lines.append(f"**Claim Time:** {format_duration(claim_seconds)}")
        desc_lines.append("")
        desc_lines.append("Click the button below to enter!")
        embed.description = "\n".join(desc_lines)
        embed.add_field(name="Entries", value="0", inline=False)
        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")

        msg = await interaction.channel.send(embed=embed, view=GiveawayView(0))
        new_view = GiveawayView(msg.id)
        await msg.edit(view=new_view)
        bot.add_view(new_view)

        giveaways[msg.id] = {
            'channel_id': msg.channel.id,
            'guild_id': interaction.guild_id,
            'host_id': interaction.user.id,
            'end_time': end_time,
            'winners': winners,
            'prize': prize,
            'description': description,
            'claim_time': claim_seconds,
            'entries': set(),
            'ended': False,
            'winners_list': set(),
            'claimed': set(),
            'reroll_button_added': False
        }
        save_giveaways()

        await interaction.response.send_message("✅ Giveaway created!", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("Something went wrong.", ephemeral=True)

# -------------------------------------------------------------------
@tree.command(name="gcreate", description="Create a new giveaway (opens a form)")
async def gcreate(interaction: discord.Interaction):
    if not await can_manage_giveaway(interaction):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return
    await interaction.response.send_modal(GiveawayModal())

@tree.command(name="greroll", description="Reroll a winner from an ended giveaway")
@app_commands.describe(message_id="ID of the giveaway message (optional, picks the last ended in this channel)")
async def greroll(interaction: discord.Interaction, message_id: Optional[int] = None):
    if not await can_manage_giveaway(interaction):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return

    if message_id is None:
        possible = [mid for mid, gw in giveaways.items() if gw.get('ended') and gw['channel_id'] == interaction.channel_id]
        if not possible:
            await interaction.response.send_message("No ended giveaways in this channel.", ephemeral=True)
            return
        message_id = max(possible)
    else:
        gw = giveaways.get(message_id)
        if not gw or not gw.get('ended'):
            await interaction.response.send_message("That giveaway isn't ended or doesn't exist.", ephemeral=True)
            return

    gw = giveaways.get(message_id)
    participant_ids = gw['entries'] - gw.get('winners_list', set())
    if not participant_ids:
        await interaction.response.send_message("No eligible participants for a reroll.", ephemeral=True)
        return

    new_winner_id = random.choice(list(participant_ids))
    gw.setdefault('winners_list', set()).add(new_winner_id)
    save_giveaways()
    await interaction.response.send_message(f"🎉 New winner from the giveaway **{gw['prize']}**: <@{new_winner_id}>!")

# -------------------------------------------------------------------
class CloseTicketButton(discord.ui.Button):
    def __init__(self, channel_id: int):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Close Ticket",
            emoji="🔒",
            custom_id=f"close_ticket_{channel_id}"
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not channel or channel.id != self.channel_id:
            await interaction.response.send_message("This button is for a different channel.", ephemeral=True)
            return

        topic = channel.topic
        if not topic or not topic.isdigit():
            await interaction.response.send_message("Cannot identify the giveaway.", ephemeral=True)
            return
        msg_id = int(topic)
        gw = giveaways.get(msg_id)
        if not gw:
            await interaction.response.send_message("Giveaway data not found.", ephemeral=True)
            return

        allowed_ids = set(gw.get('winners_list', set()))
        allowed_ids.add(gw['host_id'])
        if not (interaction.user.guild_permissions.administrator or interaction.user.id in allowed_ids):
            await interaction.response.send_message("Only the winner or host can close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Closing ticket and generating transcript...", ephemeral=True)

        messages = []
        async for msg in channel.history(limit=200, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = msg.author.display_name
            content = msg.content if msg.content else "*[no text]*"
            messages.append(f"[{timestamp}] {author}: {content}")

        transcript_text = "\n".join(messages)
        if len(transcript_text) > 1900:
            transcript_file = discord.File(io.StringIO(transcript_text), filename="transcript.txt")
            transcript_content = "Transcript is too long, see attached file."
        else:
            transcript_file = None
            transcript_content = f"```\n{transcript_text}\n```"

        if TRANSCRIPT_CHANNEL_ID:
            transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL_ID)
            if transcript_channel:
                embed = discord.Embed(
                    title=f"Ticket Closed – {gw['prize']}",
                    description=f"**Winner(s):** {', '.join(f'<@{uid}>' for uid in gw.get('winners_list', set()))}\n**Host:** <@{gw['host_id']}>",
                    color=discord.Color.red()
                )
                if transcript_file:
                    await transcript_channel.send(embed=embed, file=transcript_file)
                else:
                    await transcript_channel.send(embed=embed, content=transcript_content)

        try:
            await channel.delete()
        except discord.Forbidden:
            await interaction.followup.send("I couldn't delete the channel – please check permissions.", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton(channel_id))

# -------------------------------------------------------------------
class ClaimTicketButton(discord.ui.Button):
    def __init__(self, message_id: int, winner_id: int):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Claim Prize",
            emoji="🎫",
            custom_id=f"claim_{message_id}_{winner_id}"
        )
        self.message_id = message_id
        self.winner_id = winner_id

    async def callback(self, interaction: discord.Interaction):
        gw = giveaways.get(self.message_id)
        if not gw:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return

        if interaction.user.id != self.winner_id:
            await interaction.response.send_message("You are not a winner.", ephemeral=True)
            return

        if self.winner_id in gw.get('claimed', set()):
            await interaction.response.send_message("You have already claimed your prize.", ephemeral=True)
            return

        guild = interaction.guild
        category = None
        if TICKET_CATEGORY_ID:
            category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            category = interaction.channel.category

        winner = guild.get_member(self.winner_id) or await guild.fetch_member(self.winner_id)
        host_id = gw['host_id']
        host = guild.get_member(host_id)
        host_mention = host.mention if host else f"<@{host_id}>"

        prize_sanitized = sanitize_channel_name(gw['prize'])
        winner_sanitized = sanitize_channel_name(winner.display_name)
        channel_name = f"{winner_sanitized}-{prize_sanitized}"
        if len(channel_name) > 100:
            channel_name = channel_name[:100].rstrip('-')

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            winner: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if host:
            overwrites[host] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            ticket_channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Giveaway ticket for {gw['prize']}",
                topic=str(self.message_id)
            )

            # Pings + embed ticket message
            pings = f"{winner.mention} {host_mention}"
            embed = discord.Embed(
                title="Ticket Created",
                description=(
                    "Welcome, thank you for reaching out to our support team!\n"
                    "Your giveaway prize will be paid soon."
                ),
                color=discord.Color.gold()
            )
            view = TicketControlView(ticket_channel.id)
            await ticket_channel.send(content=pings, embed=embed, view=view)
            bot.add_view(view)

        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to create a ticket channel.", ephemeral=True)
            return

        gw.setdefault('claimed', set()).add(self.winner_id)
        save_giveaways()

        self.disabled = True
        self.label = f"Claimed by {winner.display_name}"
        self.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)

class ClaimView(discord.ui.View):
    def __init__(self, message_id: int, winners: Set[int]):
        super().__init__(timeout=None)
        for winner_id in winners:
            self.add_item(ClaimTicketButton(message_id, winner_id))

# -------------------------------------------------------------------
class RerollButton(discord.ui.Button):
    def __init__(self, message_id: int):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Reroll Unclaimed",
            emoji="🔄",
            custom_id=f"reroll_unclaimed_{message_id}"
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        gw = giveaways.get(self.message_id)
        if not gw or not gw.get('ended'):
            await interaction.response.send_message("Giveaway not found or not ended.", ephemeral=True)
            return

        if interaction.user.id != gw['host_id'] and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only the giveaway host can reroll.", ephemeral=True)
            return

        unclaimed = gw['winners_list'] - gw.get('claimed', set())
        if not unclaimed:
            await interaction.response.send_message("All winners have already claimed.", ephemeral=True)
            return

        eligible = gw['entries'] - gw['winners_list']
        if len(eligible) < len(unclaimed):
            await interaction.response.send_message("Not enough eligible participants to replace all unclaimed winners.", ephemeral=True)
            return

        new_winners = set(random.sample(list(eligible), len(unclaimed)))
        gw['winners_list'] = (gw['winners_list'] - unclaimed) | new_winners
        gw['claimed'] = gw['claimed'] - unclaimed
        gw['reroll_button_added'] = True
        save_giveaways()

        channel = bot.get_channel(gw['channel_id'])
        if channel:
            try:
                message = await channel.fetch_message(self.message_id)
                embed = message.embeds[0]
                winners_mention = ", ".join(f"<@{uid}>" for uid in gw['winners_list'])
                for i, field in enumerate(embed.fields):
                    if field.name == "Winners":
                        embed.set_field_at(i, name="Winners", value=winners_mention, inline=False)
                        break
                else:
                    embed.add_field(name="Winners", value=winners_mention, inline=False)

                view = ClaimView(self.message_id, gw['winners_list'])
                for child in view.children:
                    if child.winner_id in gw.get('claimed', set()):
                        child.disabled = True
                        child.label = "Claimed"
                        child.style = discord.ButtonStyle.secondary
                await message.edit(embed=embed, view=view)
                bot.add_view(view)
            except discord.NotFound:
                pass

        await interaction.response.send_message(f"Rerolled! New winners: {', '.join(f'<@{uid}>' for uid in new_winners)}", ephemeral=True)

# -------------------------------------------------------------------
async def end_giveaway(msg_id: int):
    gw = giveaways.get(msg_id)
    if not gw or gw.get('ended'):
        return

    channel = bot.get_channel(gw['channel_id'])
    if not channel:
        return

    try:
        message = await channel.fetch_message(msg_id)
    except discord.NotFound:
        return

    guild = bot.get_guild(gw['guild_id'])
    if not guild:
        return

    participant_ids = list(gw['entries'])
    total_entries = len(participant_ids)
    winners_count = min(gw['winners'], total_entries)
    winner_ids = set(random.sample(participant_ids, winners_count)) if winners_count > 0 else set()

    embed = message.embeds[0] if message.embeds else discord.Embed()
    embed.title = f"{gw['prize']} – Ended"
    embed.description = "**Status:** Ended"
    embed.clear_fields()

    if winner_ids:
        winners_mention = ", ".join(f"<@{uid}>" for uid in winner_ids)
        embed.add_field(name="Winners", value=winners_mention, inline=False)
    else:
        embed.add_field(name="Winners", value="No one entered 😢", inline=False)
    embed.add_field(name="Entries", value=str(total_entries), inline=False)
    if gw.get('claim_time'):
        embed.add_field(name="Claim Time", value=format_duration(gw['claim_time']), inline=False)
    embed.color = discord.Color.dark_grey()

    claim_view = None
    if winner_ids:
        claim_view = ClaimView(msg_id, winner_ids)

    try:
        await message.edit(embed=embed, view=claim_view)
        if claim_view:
            bot.add_view(claim_view)
    except discord.HTTPException:
        pass

    gw['ended'] = True
    gw['winners_list'] = winner_ids
    save_giveaways()

    if winner_ids:
        host = guild.get_member(gw['host_id'])
        host_mention = host.mention if host else f"<@{gw['host_id']}>"
        winner_mentions = " ".join(f"<@{uid}>" for uid in winner_ids)

        announce_embed = discord.Embed(
            title="🎉 Giveaway Winners!",
            color=discord.Color.gold()
        )
        announce_embed.add_field(name="Prize", value=gw['prize'], inline=False)
        if gw.get('claim_time'):
            announce_embed.add_field(name="Claim Time", value=format_duration(gw['claim_time']), inline=False)
        announce_embed.add_field(name="Winners", value=winner_mentions, inline=False)
        announce_embed.add_field(name="Host", value=host_mention, inline=False)
        announce_embed.add_field(name="Total Entries", value=str(total_entries), inline=False)
        announce_embed.set_footer(text="Click the Claim Prize button on the original giveaway message to open your ticket.")

        await channel.send(embed=announce_embed)

# -------------------------------------------------------------------
async def check_claim_expiry():
    now = time.time()
    for msg_id, gw in list(giveaways.items()):
        if not gw.get('ended') or not gw.get('claim_time'):
            continue
        if gw.get('reroll_button_added'):
            continue
        if now < gw['end_time'] + gw['claim_time']:
            continue
        unclaimed = gw['winners_list'] - gw.get('claimed', set())
        if not unclaimed:
            gw['reroll_button_added'] = True
            save_giveaways()
            continue

        channel = bot.get_channel(gw['channel_id'])
        if not channel:
            continue
        try:
            message = await channel.fetch_message(msg_id)
            view = discord.ui.View(timeout=None)
            for wid in gw['winners_list']:
                btn = ClaimTicketButton(msg_id, wid)
                if wid in gw.get('claimed', set()):
                    btn.disabled = True
                    member = channel.guild.get_member(wid)
                    btn.label = f"Claimed by {member.display_name if member else 'Unknown'}"
                    btn.style = discord.ButtonStyle.secondary
                view.add_item(btn)
            view.add_item(RerollButton(msg_id))
            await message.edit(view=view)
            bot.add_view(view)
            gw['reroll_button_added'] = True
            save_giveaways()
        except discord.NotFound:
            pass

async def main_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        for msg_id, gw in list(giveaways.items()):
            if not gw.get('ended') and now >= gw['end_time']:
                await end_giveaway(msg_id)
        await check_claim_expiry()
        await asyncio.sleep(5)

# -------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    load_giveaways()
    print(f"Loaded {len(giveaways)} giveaway(s).")

    # Set static presence
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="Managing giveaways")
    )

    for msg_id, gw in giveaways.items():
        if not gw.get('ended'):
            view = GiveawayView(msg_id)
            bot.add_view(view)
        else:
            winners = gw.get('winners_list', set())
            if winners:
                if gw.get('reroll_button_added'):
                    view = discord.ui.View(timeout=None)
                    for wid in winners:
                        btn = ClaimTicketButton(msg_id, wid)
                        if wid in gw.get('claimed', set()):
                            btn.disabled = True
                            btn.label = "Claimed"
                            btn.style = discord.ButtonStyle.secondary
                        view.add_item(btn)
                    view.add_item(RerollButton(msg_id))
                else:
                    view = ClaimView(msg_id, winners)
                    for child in view.children:
                        if child.winner_id in gw.get('claimed', set()):
                            child.disabled = True
                            child.label = "Claimed"
                            child.style = discord.ButtonStyle.secondary
                bot.add_view(view)

    bot.loop.create_task(main_loop())

    try:
        await tree.sync()
        print("Slash commands synced globally.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

if __name__ == "__main__":
    if TOKEN is None:
        raise ValueError("No DISCORD_TOKEN found in .env")
    bot.run(TOKEN)
