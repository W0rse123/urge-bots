import os
import json
import random
import asyncio
import time
import io
import re
import traceback
import aiohttp
import base64
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from TikTokLive import TikTokLiveClient

def parse_price(price_str: str) -> float:
    p = price_str.lower().replace('$', '').replace(',', '').strip()
    multiplier = 1
    if p.endswith('k'):
        multiplier = 1000
        p = p[:-1]
    elif p.endswith('m'):
        multiplier = 1000000
        p = p[:-1]
    elif p.endswith('b'):
        multiplier = 1000000000
        p = p[:-1]
    try:
        return float(p) * multiplier
    except ValueError:
        return 0.0

def format_price(amount: float) -> str:
    if amount >= 1000000000:
        return f"${amount/1000000000:g}b"
    elif amount >= 1000000:
        return f"${amount/1000000:g}m"
    elif amount >= 1000:
        return f"${amount/1000:g}k"
    return f"${amount:g}"

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from google import genai

# -------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
ENABLE_AI = os.getenv("ENABLE_AI", "0") == "1"
PARTNERSHIP_RANGES = os.getenv("PARTNERSHIP_RANGES")
MANAGER_ROLE_ID = os.getenv("GIVEAWAY_MANAGER_ROLE_ID")
if MANAGER_ROLE_ID:
    MANAGER_ROLE_ID = int(MANAGER_ROLE_ID)

# Map their old TICKET_CATEGORY_ID to our new GIVEAWAY_CATEGORY_ID
TICKET_CATEGORY_ID = os.getenv("GIVEAWAY_CATEGORY_ID")
if TICKET_CATEGORY_ID:
    TICKET_CATEGORY_ID = int(TICKET_CATEGORY_ID)

TRANSCRIPT_CHANNEL_ID = os.getenv("TRANSCRIPT_CHANNEL_ID")
if TRANSCRIPT_CHANNEL_ID:
    TRANSCRIPT_CHANNEL_ID = int(TRANSCRIPT_CHANNEL_ID)

# TICKET PANEL VARIABLES
SUPPORT_CATEGORY_ID = os.getenv('SUPPORT_CATEGORY_ID')
PARTNERSHIP_CATEGORY_ID = os.getenv('PARTNERSHIP_CATEGORY_ID')
GIVEAWAY_CATEGORY_ID = os.getenv('GIVEAWAY_CATEGORY_ID')
BAN_APPEAL_CHANNEL_ID = os.getenv('BAN_APPEAL_CHANNEL_ID')
BANNED_ROLE_ID = os.getenv('BANNED_ROLE_ID')
SPAWNER_CATEGORY_ID = os.getenv('SPAWNER_CATEGORY_ID')
BUILDER_CATEGORY_ID = os.getenv('BUILDER_CATEGORY_ID')
TICKET_ROLE_ID = os.getenv('TICKET_ROLE_ID')
HIGH_PERMS_ROLE_ID = os.getenv('HIGH_PERMS_ROLE_ID')
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')
TICKET_PANEL_TITLE = os.getenv('TICKET_PANEL_TITLE', '🎫 Support Tickets')
TICKET_PANEL_TEXT = os.getenv('TICKET_PANEL_TEXT', 'Pick a category from the buttons below to open your ticket.').replace('\\n', '\n')
SPAWNER_ROLE_ID = os.getenv('SPAWNER_ROLE_ID')
VOUCH_CHANNEL_ID = os.getenv('VOUCH_CHANNEL_ID')
GIVEAWAY_PROOF_CHANNEL_ID = os.getenv('GIVEAWAY_PROOF_CHANNEL_ID')
LIVE_PING_ROLE_ID = os.getenv('LIVE_PING_ROLE_ID')
APPLICATION_REVIEW_CHANNEL_ID = os.getenv('APPLICATION_REVIEW_CHANNEL_ID')

async def is_high_staff(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    if HIGH_PERMS_ROLE_ID and HIGH_PERMS_ROLE_ID.isdigit():
        role = interaction.guild.get_role(int(HIGH_PERMS_ROLE_ID))
        if role and role in interaction.user.roles:
            return True
    return False

async def is_spawner_staff(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    if SPAWNER_ROLE_ID and SPAWNER_ROLE_ID.isdigit():
        role = interaction.guild.get_role(int(SPAWNER_ROLE_ID))
        if role and role in interaction.user.roles:
            return True
    return False

DATA_FILE = "data/giveaways.json"
giveaways: Dict[int, dict] = {}
ticket_proofs: Dict[int, str] = {}

SPAWNER_FILE = "data/spawner_prices.json"
spawner_prices: Dict[str, dict] = {}
SPAWNER_LOGS_FILE = "logs/spawner_logs.json"

SERVER_CONFIG_FILE = "data/server_config.json"
server_config: dict = {}

VOUCH_DATA_FILE = "data/vouch_data.json"
vouch_data: dict = {}

TIKTOK_DATA_FILE = "data/tiktok_live.json"
tiktok_data: dict = {}

def load_tiktok_data():
    global tiktok_data
    if os.path.exists(TIKTOK_DATA_FILE):
        try:
            with open(TIKTOK_DATA_FILE, "r") as f:
                tiktok_data = json.load(f)
        except Exception as e:
            print(f"Error loading {TIKTOK_DATA_FILE}: {e}")
            tiktok_data = {}
    else:
        tiktok_data = {}

def save_tiktok_data():
    os.makedirs(os.path.dirname(TIKTOK_DATA_FILE), exist_ok=True)
    with open(TIKTOK_DATA_FILE, "w") as f:
        json.dump(tiktok_data, f, indent=4)

APPLICATIONS_DATA_FILE = "data/applications.json"
applications_data: dict = {}

def load_applications_data():
    global applications_data
    if os.path.exists(APPLICATIONS_DATA_FILE):
        try:
            with open(APPLICATIONS_DATA_FILE, "r") as f:
                applications_data = json.load(f)
        except Exception as e:
            print(f"Error loading {APPLICATIONS_DATA_FILE}: {e}")
            applications_data = {}
    else:
        applications_data = {}

def save_applications_data():
    os.makedirs(os.path.dirname(APPLICATIONS_DATA_FILE), exist_ok=True)
    with open(APPLICATIONS_DATA_FILE, "w") as f:
        json.dump(applications_data, f, indent=4)

LEVELS_DATA_FILE = "data/levels.json"
levels_data: dict = {}

def load_levels_data():
    global levels_data
    if os.path.exists(LEVELS_DATA_FILE):
        try:
            with open(LEVELS_DATA_FILE, "r") as f:
                levels_data = json.load(f)
        except Exception as e:
            print(f"Error loading {LEVELS_DATA_FILE}: {e}")
            levels_data = {}
    else:
        levels_data = {}

def save_levels_data():
    os.makedirs(os.path.dirname(LEVELS_DATA_FILE), exist_ok=True)
    with open(LEVELS_DATA_FILE, "w") as f:
        json.dump(levels_data, f, indent=4)

def xp_for_level(level):
    return 5 * (level ** 2) + 50 * level + 100

def load_vouch_data():
    global vouch_data
    if os.path.exists(VOUCH_DATA_FILE):
        try:
            with open(VOUCH_DATA_FILE, "r") as f:
                vouch_data = json.load(f)
        except Exception as e:
            print(f"Error loading {VOUCH_DATA_FILE}: {e}")

def save_vouch_data():
    os.makedirs(os.path.dirname(VOUCH_DATA_FILE), exist_ok=True)
    with open(VOUCH_DATA_FILE, "w") as f:
        json.dump(vouch_data, f, indent=4)

def load_server_config():
    global server_config
    if os.path.exists(SERVER_CONFIG_FILE):
        try:
            with open(SERVER_CONFIG_FILE, "r") as f:
                server_config = json.load(f)
        except Exception:
            server_config = {}
    else:
        server_config = {}

def save_server_config():
    os.makedirs(os.path.dirname(SERVER_CONFIG_FILE), exist_ok=True)
    with open(SERVER_CONFIG_FILE, "w") as f:
        json.dump(server_config, f, indent=4)

def log_spawner_transaction(user: discord.Member, action: str, spawner_name: str, quantity: int, total_price: str):
    import os
    logs = []
    
    os.makedirs(os.path.dirname(SPAWNER_LOGS_FILE), exist_ok=True)
    if os.path.exists(SPAWNER_LOGS_FILE):
        try:
            with open(SPAWNER_LOGS_FILE, 'r') as f:
                logs = json.load(f)
        except Exception:
            pass
            
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id,
        "user_name": str(user),
        "action": action,
        "spawner": spawner_name,
        "quantity": quantity,
        "total_price": total_price
    }
    logs.append(entry)
    
    with open(SPAWNER_LOGS_FILE, 'w') as f:
        json.dump(logs, f, indent=4)

def save_spawner_prices():
    os.makedirs(os.path.dirname(SPAWNER_FILE), exist_ok=True)
    with open(SPAWNER_FILE, 'w') as f:
        json.dump(spawner_prices, f, indent=2)

def load_spawner_prices():
    global spawner_prices
    if os.path.exists(SPAWNER_FILE):
        try:
            with open(SPAWNER_FILE, 'r') as f:
                data = json.load(f)
                spawner_prices.clear()
                spawner_prices.update(data)
        except Exception as e:
            print(f"Error loading {SPAWNER_FILE}: {e}")
    else:
        save_spawner_prices()

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
        gw_copy['all_time_winners'] = list(gw.get('all_time_winners', []))
        data[str(msg_id)] = gw_copy
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
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
        gw_data['entries'] = set(gw_data.get('entries', gw_data.get('participants', [])))
        gw_data['winners_list'] = set(gw_data.get('winners_list', []))
        gw_data['claimed'] = set(gw_data.get('claimed', []))
        gw_data['all_time_winners'] = set(gw_data.get('all_time_winners', []))
        giveaways[msg_id] = gw_data

# -------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
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
class LeaveGiveawayView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        gw = giveaways.get(self.message_id)
        if not gw:
            await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)
            return

        if interaction.user.id in gw['entries']:
            gw['entries'].remove(interaction.user.id)
            save_giveaways()

            try:
                channel = interaction.guild.get_channel(gw['channel_id'])
                if channel:
                    orig_message = await channel.fetch_message(self.message_id)
                    if orig_message and orig_message.embeds:
                        embed = orig_message.embeds[0]
                        for i, field in enumerate(embed.fields):
                            if field.name == "Entries":
                                embed.set_field_at(i, name="Entries", value=str(len(gw['entries'])), inline=False)
                                break
                        else:
                            embed.add_field(name="Entries", value=str(len(gw['entries'])), inline=False)
                        await orig_message.edit(embed=embed)
            except Exception as e:
                pass
            
            await interaction.response.edit_message(content="You have left the giveaway!", view=None)
        else:
            await interaction.response.edit_message(content="You are not in this giveaway.", view=None)

class JoinGiveawayButton(discord.ui.Button):
    def __init__(self, message_id: int):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="🎉 Join Giveaway",
            custom_id=f"giveaway_join_{message_id}"
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            gw = giveaways.get(self.message_id)
            if not gw:
                await interaction.followup.send("This giveaway no longer exists.", ephemeral=True)
                return
            if gw.get('ended'):
                await interaction.followup.send("This giveaway is no longer active.", ephemeral=True)
                return
            if interaction.user.id in gw['entries']:
                view = LeaveGiveawayView(self.message_id)
                await interaction.followup.send("You have already entered this giveaway", view=view, ephemeral=True)
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

            await interaction.followup.send("You've entered the giveaway!", ephemeral=True)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"JoinGiveawayButton error: {e}")

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
            'reroll_button_added': False,
            'reroll_performed': False,
            'all_time_winners': set()
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

async def perform_reroll(interaction: discord.Interaction, msg_id: int, gw: dict):
    unclaimed = gw['winners_list'] - gw.get('claimed', set())
    if not unclaimed:
        await interaction.followup.send("All winners have already claimed their prize. There is no one to reroll!", ephemeral=True)
        return

    all_winners = gw.get('all_time_winners', set())
    eligible = gw['entries'] - all_winners
    if len(eligible) < len(unclaimed):
        await interaction.followup.send("Not enough eligible participants to replace all unclaimed winners.", ephemeral=True)
        return

    new_winners = set(random.sample(list(eligible), len(unclaimed)))
    gw['winners_list'] = (gw['winners_list'] - unclaimed) | new_winners
    gw.setdefault('all_time_winners', set()).update(new_winners)
    gw['claimed'] = gw['claimed'] - unclaimed
    gw['reroll_performed'] = True
    gw['end_time'] = time.time()
    gw['reroll_button_added'] = False
    save_giveaways()

    try:
        await interaction.message.delete()
    except Exception as e:
        print(f"Failed to delete original message on reroll: {e}")

    channel = interaction.channel
    old_mentions = " ".join(f"<@{uid}>" for uid in unclaimed)
    new_mentions = " ".join(f"<@{uid}>" for uid in new_winners)

    embed = discord.Embed(
        title="🔄 Giveaway Rerolled!",
        description=f"**Prize:** {gw['prize']}\n\n**Old Winner(s):** {old_mentions}\n**New Winner(s):** {new_mentions}",
        color=discord.Color.red()
    )
    embed.set_footer(text="New winners: click the button below to claim your prize!")

    new_claim_view = ClaimView(msg_id, new_winners)
    try:
        ping_msg = await channel.send(f"Congratulations {new_mentions}! You won **{gw['prize']}**!")
        await asyncio.sleep(2)
        await ping_msg.delete()
    except Exception:
        pass
    await channel.send(embed=embed, view=new_claim_view)
    bot.add_view(new_claim_view)

    # DM the new winners
    for uid in new_winners:
        try:
            user = await bot.fetch_user(uid)
            if user:
                await user.send(f"🎉 **Congratulations!** You were chosen in a reroll and won **{gw['prize']}**! Please go to the server to claim your prize.")
        except Exception as e:
            print(f"Failed to DM new winner {uid}: {e}")

    await interaction.followup.send("Reroll complete!", ephemeral=True)


@tree.command(name="greroll", description="Reroll a winner from an ended giveaway")
@app_commands.describe(message_id="ID of the giveaway message (optional, picks the last ended in this channel)")
async def greroll(interaction: discord.Interaction, message_id: Optional[int] = None):
    if not await can_manage_giveaway(interaction):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if message_id is None:
        possible = [mid for mid, gw in giveaways.items() if gw.get('ended') and gw['channel_id'] == interaction.channel_id]
        if not possible:
            await interaction.followup.send("No ended giveaways in this channel.", ephemeral=True)
            return
        message_id = max(possible)
    else:
        gw = giveaways.get(message_id)
        if not gw or not gw.get('ended'):
            await interaction.followup.send("That giveaway isn't ended or doesn't exist.", ephemeral=True)
            return

    gw = giveaways.get(message_id)
    await perform_reroll(interaction, message_id, gw)

@tree.command(name="proof", description="Upload a proof image to be featured at the top of the transcript")
@app_commands.describe(proof_file="The image/video file to upload", proof_link="Or paste a link to the proof")
async def proof(interaction: discord.Interaction, proof_file: discord.Attachment = None, proof_link: str = None):
    if not proof_file and not proof_link:
        await interaction.response.send_message("You must provide either a `proof_file` or a `proof_link`!", ephemeral=True)
        return

    await interaction.response.defer()

    img_url = proof_link
    
    if proof_file:
        if proof_file.content_type and proof_file.content_type.startswith('image/') and IMGBB_API_KEY and IMGBB_API_KEY != 'your_imgbb_api_key_here':
            try:
                file_data = await proof_file.read()
                b64_image = base64.b64encode(file_data).decode('utf-8')
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}",
                        data={"image": b64_image}
                    ) as resp:
                        if resp.status == 200:
                            json_resp = await resp.json()
                            img_url = json_resp['data']['url']
            except Exception as e:
                print(f"ImgBB upload error: {e}")
        else:
            try:
                file_data = await proof_file.read()
                data = aiohttp.FormData()
                data.add_field('reqtype', 'fileupload')
                data.add_field('fileToUpload', file_data, filename=proof_file.filename)
                
                async with aiohttp.ClientSession() as session:
                    async with session.post("https://catbox.moe/user/api.php", data=data) as resp:
                        if resp.status == 200:
                            img_url = await resp.text()
            except Exception as e:
                print(f"Catbox upload error: {e}")

    if not img_url and proof_file:
        img_url = proof_file.url

    if img_url:
        ticket_proofs[interaction.channel.id] = img_url

    topic = interaction.channel.topic
    gw = None
    if topic and topic.isdigit():
        gw = giveaways.get(int(topic))
    view = GwCloseTicketView() if gw else GenericCloseButton()
    
    try:
        await interaction.followup.send(content=f"**Proof successfully uploaded to cloud storage:**\n{img_url}\n\n*Would you like to close the ticket?*", view=view)
    except Exception as e:
        print(f"Failed to send proof confirmation: {e}")

# -------------------------------------------------------------------
class GwCloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="gw_close_ticket_persistent", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.id not in ticket_proofs:
            await interaction.response.send_message("❌ You must upload a proof via the `/proof` command before closing this ticket!", ephemeral=True)
            return
            
        if interaction.channel.id in closing_tickets:
            try:
                await interaction.response.send_message("Ticket is already closing...", ephemeral=True)
            except:
                pass
            return
        closing_tickets.add(interaction.channel.id)

        await interaction.response.defer(ephemeral=True)
        try:
            channel = interaction.channel
            topic = channel.topic
            if not topic or not topic.isdigit():
                await interaction.followup.send("Cannot identify the giveaway.", ephemeral=True)
                return
            msg_id = int(topic)
            gw = giveaways.get(msg_id)
            if not gw:
                await interaction.followup.send("Giveaway data not found.", ephemeral=True)
                return

            allowed_ids = set(gw.get('winners_list', set()))
            allowed_ids.add(gw['host_id'])
            if not (interaction.user.guild_permissions.administrator or interaction.user.id in allowed_ids):
                await interaction.followup.send("Only the winner or host can close this ticket.", ephemeral=True)
                return

            await create_and_send_transcript(interaction, gw)

            try:
                await channel.delete()
            except discord.Forbidden:
                pass
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"GwCloseTicketView error: {e}")

# -------------------------------------------------------------------
class GiveawayIGNModal(discord.ui.Modal, title="Claim Prize"):
    ign = discord.ui.TextInput(
        label="In-Game Name (IGN)",
        style=discord.TextStyle.short,
        placeholder="Your Minecraft username",
        required=True
    )

    def __init__(self, message_id: int, winner_id: int, button: discord.ui.Button, original_message: discord.Message):
        super().__init__()
        self.message_id = message_id
        self.winner_id = winner_id
        self.button = button
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            gw = giveaways.get(self.message_id)
            if not gw: return

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
            if len(channel_name) > 100: channel_name = channel_name[:100].rstrip('-')

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                winner: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
            if host: overwrites[host] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            try:
                ticket_channel = await guild.create_text_channel(
                    channel_name, category=category, overwrites=overwrites,
                    reason=f"Giveaway ticket for {gw['prize']}", topic=str(self.message_id)
                )

                pings = f"{winner.mention} {host_mention}"
                embed = discord.Embed(
                    title="Giveaway Claim Ticket",
                    description="Welcome! Thank you for reaching out to claim your prize.\nThe host will be with you shortly to hand over your reward!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Host", value=f"<@{host_id}>", inline=True)
                embed.add_field(name="Winner", value=f"<@{self.winner_id}>", inline=True)
                embed.add_field(name="Prize", value=str(gw['prize']), inline=True)
                embed.add_field(name="In-Game Name", value=self.ign.value, inline=False)
                
                claim_duration = int(time.time() - gw.get('end_time', time.time()))
                minutes, seconds = divmod(claim_duration, 60)
                hours, minutes = divmod(minutes, 60)
                time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
                embed.add_field(name="Claim Time", value=f"Claimed after {time_str}", inline=False)
            
                view = GwCloseTicketView()
                await ticket_channel.send(content=f"{pings} Welcome to your claim ticket!", embed=embed, view=view)
                bot.add_view(view)

            except discord.Forbidden:
                await interaction.followup.send("I don't have permission to create a ticket channel.", ephemeral=True)
                return

            gw.setdefault('claimed', set()).add(self.winner_id)
            save_giveaways()

            self.button.disabled = True
            self.button.label = f"Claimed by {winner.display_name}"
            self.button.style = discord.ButtonStyle.secondary
            try:
                await self.original_message.edit(view=self.button.view)
            except Exception as e:
                print(f"Failed to edit original message: {e}")
                
            await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)
        except Exception as e:
            print(f"GiveawayIGNModal error: {e}")

class ClaimPrizeButton(discord.ui.Button):
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

        await interaction.response.send_modal(GiveawayIGNModal(self.message_id, self.winner_id, self, interaction.message))

class ClaimView(discord.ui.View):
    def __init__(self, message_id: int, winners: Set[int]):
        super().__init__(timeout=None)
        for winner_id in winners:
            self.add_item(ClaimPrizeButton(message_id, winner_id))

# -------------------------------------------------------------------
class RerollButton(discord.ui.Button):
    def __init__(self, message_id: int):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Reroll",
            emoji="🔄",
            custom_id=f"reroll_unclaimed_{message_id}"
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            gw = giveaways.get(self.message_id)
            if not gw or not gw.get('ended'):
                await interaction.followup.send("Giveaway not found or not ended.", ephemeral=True)
                return

            if interaction.user.id != gw['host_id'] and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Only the giveaway host can reroll.", ephemeral=True)
                return

            await perform_reroll(interaction, self.message_id, gw)
        except Exception as e:
            print(f"RerollButton error: {e}")

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
    except Exception as e:
        print(f"Error fetching message {msg_id}: {e}")
        return

    guild = bot.get_guild(gw['guild_id'])
    if not guild:
        return

    participant_ids = list(gw['entries'])
    total_entries = len(participant_ids)
    winners_count = min(gw['winners'], total_entries)
    winner_ids = set(random.sample(participant_ids, winners_count)) if winners_count > 0 else set()
    gw['all_time_winners'] = gw.get('all_time_winners', set()) | winner_ids

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

    claim_view = ClaimView(msg_id, winner_ids) if winner_ids else None

    try:
        await message.edit(embed=embed, view=claim_view)
        if claim_view:
            bot.add_view(claim_view)
    except discord.HTTPException as e:
        print(f"Failed to edit giveaway message {msg_id}: {e}")

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

        try:
            try:
                ping_msg = await channel.send(f"Congratulations {winner_mentions}! You won **{gw['prize']}**!")
                await asyncio.sleep(2)
                await ping_msg.delete()
            except Exception:
                pass
            await channel.send(embed=announce_embed)
            
            # DM the winners
            for uid in winner_ids:
                try:
                    user = await bot.fetch_user(uid)
                    if user:
                        await user.send(f"🎉 **Congratulations!** You won **{gw['prize']}** in a giveaway! Please go to the server to claim your prize.")
                except Exception as e:
                    print(f"Failed to DM winner {uid}: {e}")
                    
        except Exception as e:
            print(f"Failed to send winner announcement: {e}")

# -------------------------------------------------------------------
async def check_claim_expiry():
    now = time.time()
    for msg_id, gw in list(giveaways.items()):
        try:
            if not gw.get('ended'):
                continue
            if not gw.get('claim_time'):
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
            message = await channel.fetch_message(msg_id)
            view = discord.ui.View(timeout=None)
            for wid in gw['winners_list']:
                btn = ClaimPrizeButton(msg_id, wid)
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
        except Exception as e:
            print(f"Error in check_claim_expiry for {msg_id}: {e}")

async def main_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = time.time()
            for msg_id, gw in list(giveaways.items()):
                if not gw.get('ended') and now >= gw['end_time']:
                    await end_giveaway(msg_id)
            await check_claim_expiry()
        except Exception as e:
            print(f"Error in main_loop: {e}")
            traceback.print_exc()
        await asyncio.sleep(5)

# -------------------------------------------------------------------
# TICKET PANEL IMPLEMENTATION
# -------------------------------------------------------------------

class TicketPanelGiveawayDisclaimerModal(discord.ui.Modal, title='Giveaway Claim Disclaimer'):
    info = discord.ui.TextInput(
        label='Please read carefully:',
        style=discord.TextStyle.paragraph,
        default="If you would like to claim a giveaway you won, open a ticket from the giveaway you won. If it doesn't work open a support ticket.",
        required=False
    )
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Please open a support ticket if the giveaway's ticket system did not work.", ephemeral=True)

async def create_ticket_channel_util(interaction: discord.Interaction, ticket_type: str, quantity: str = None, total_cost: str = None, ign: str = None):
    if ticket_type == "support":
        category_id = SUPPORT_CATEGORY_ID
    elif ticket_type == "giveaway":
        category_id = GIVEAWAY_CATEGORY_ID
    elif ticket_type.startswith("buy_") or ticket_type.startswith("sell_"):
        category_id = SPAWNER_CATEGORY_ID if SPAWNER_CATEGORY_ID and SPAWNER_CATEGORY_ID != 'your_spawner_category_id_here' else SUPPORT_CATEGORY_ID
    else:
        category_id = PARTNERSHIP_CATEGORY_ID

    ticket_role_id = TICKET_ROLE_ID
    high_perms_role_id = HIGH_PERMS_ROLE_ID

    if not category_id or not ticket_role_id or not high_perms_role_id or str(category_id).startswith('your_'):
        await interaction.response.send_message('The ticket system is not configured correctly.', ephemeral=True)
        return False
        
    if ticket_type.startswith("buy_") or ticket_type.startswith("sell_"):
        parts = ticket_type.split('_', 1)
        action = parts[0]
        spawner = parts[1] if len(parts) > 1 else "unknown"
        q = quantity if quantity else "unknown"
        ticket_name = f"{action}-{spawner}-{q}-{interaction.user.name.lower()}"
    else:
        ticket_name = f"{ticket_type}-{interaction.user.name.lower()}"

    existing_channel = discord.utils.get(interaction.guild.channels, name=ticket_name)
    
    if existing_channel:
        await interaction.response.send_message(f"You already have a {ticket_type} ticket open: {existing_channel.mention}", ephemeral=True)
        return False

    category = interaction.guild.get_channel(int(category_id))
    ticket_role = interaction.guild.get_role(int(ticket_role_id))
    high_perms_role = interaction.guild.get_role(int(high_perms_role_id))

    if not category:
        await interaction.response.send_message("Configured category not found.", ephemeral=True)
        return False

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
    }
    
    if ticket_role:
        overwrites[ticket_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
    if high_perms_role:
        overwrites[high_perms_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

    try:
        topic = None
        if ticket_type.startswith("buy_") or ticket_type.startswith("sell_"):
            topic = f"{interaction.user.id}:spawner"
        elif ticket_type in ("support", "partnership"):
            topic = f"{interaction.user.id}:{ticket_type}"
            
        ticket_channel = await interaction.guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=topic
        )
        
        if ticket_type == "support":
            title_text = "Support Ticket"
            desc_text = "Staff will be with you shortly.\nTo close this ticket, click the button below."
        elif ticket_type == "giveaway":
            title_text = "Giveaway Claim"
            desc_text = "**Disclaimer:** If you would like to claim a giveaway you won, open a ticket from the giveaway you won. If it doesn't work open a support ticket.\n\nStaff will be with you shortly.\nTo close this ticket, click the button below."
        elif ticket_type.startswith("buy_") or ticket_type.startswith("sell_"):
            parts = ticket_type.split('_', 1)
            action = parts[0]
            item = parts[1] if len(parts) > 1 else ""
            title_text = f"{action.capitalize()} {item.capitalize()} Ticket"
            qty_text = f"**Quantity:** {quantity}\n" if quantity else ""
            cost_text = f"**Total Amount:** {total_cost}\n\n" if total_cost else "\n"
            desc_text = f"{qty_text}{cost_text}Staff will be with you shortly to assist with your {action} request.\nTo close this ticket, click the button below."
        else:
            title_text = "Partnership Ticket"
            desc_text = "Staff will be with you shortly.\nTo close this ticket, click the button below."

        embed = discord.Embed(
            title=f"{title_text}: {interaction.user.name}",
            description=desc_text,
            color=discord.Color.green()
        )
        embed.add_field(name="Opened by", value=interaction.user.mention, inline=False)
        if ign:
            embed.add_field(name="In-Game Name", value=ign, inline=False)

        mentions = [interaction.user.mention]
            
        ping_staff = os.getenv('PING_STAFF', 'true').lower() == 'true'
        if ping_staff:
            if ticket_role: mentions.append(ticket_role.mention)

        if ticket_type == "giveaway":
            close_view = GwCloseTicketView()
        elif ticket_type.startswith("buy_") or ticket_type.startswith("sell_"):
            close_view = SpawnerControlView()
        else:
            close_view = GenericCloseButton()
            
        await ticket_channel.send(" | ".join(mentions), embed=embed, view=close_view)
        await interaction.response.send_message(f"Your {ticket_type} ticket has been created: {ticket_channel.mention}", ephemeral=True)
        return True
    except Exception as e:
        print(f"Error creating ticket channel: {e}")
        await interaction.response.send_message("There was an error creating your ticket.", ephemeral=True)
        return False

import asyncio

async def generate_partnership_requirements(guild: discord.Guild = None, override_member_count: int = None) -> str:
    """Return partnership requirement description.
    If ENABLE_AI is True, the AI logic would be used (placeholder for future).
    If ENABLE_AI is False, we either use custom thresholds from the env or fall back to a static message.
    """
    # Determine member count
    if override_member_count is not None:
        member_count = override_member_count
    elif guild is not None:
        member_count = sum(1 for m in guild.members if not m.bot)
    else:
        return "**Partnership requirements unavailable:** member count not provided."

    if not ENABLE_AI:
        # Try to parse custom ranges from env variable
        if PARTNERSHIP_RANGES:
            try:
                import json
                ranges = json.loads(PARTNERSHIP_RANGES)
                lines = [f"**Server size:** {member_count} members\n"]
                for r in ranges:
                    we_ping = r.get("we", "")
                    you_ping = r.get("you", "")
                    lines.append(f"• {r.get('label', '')} ➤ We ping {we_ping}, you ping {you_ping or 'nothing'}")
                return "\n".join(lines)
            except Exception as e:
                print(f"Error parsing PARTNERSHIP_RANGES: {e}")
        # Default when AI disabled and no custom ranges
        return "**AI partnership generation is disabled.** Set ENABLE_AI=1 or provide PARTNERSHIP_RANGES in .env."

    # AI enabled – deterministic example logic (previous implementation)
    if member_count < 75:
        range_label = "0–75"
        we_ping = "Nothing"
        you_ping = "@everyone"
    elif member_count < 300:
        range_label = "75–300"
        we_ping = "Nothing"
        you_ping = "@Member"
    elif member_count < 600:
        range_label = "300–600"
        we_ping = "@partner"
        you_ping = "@Member"
    elif member_count < 700:
        range_label = "600–700"
        we_ping = "@here + @partner"
        you_ping = "@Member"
    elif member_count < 750:
        range_label = "700–750"
        we_ping = "@Member"
        you_ping = "@Member"
    elif member_count < 850:
        range_label = "750–850"
        we_ping = "@Member"
        you_ping = "@here + @partner"
    else:
        range_label = ">=850"
        we_ping = "your requirements"
        you_ping = ""

    lines = [
        f"**Server size:** {member_count} members",
        f"• {range_label} ➤ We ping {we_ping}, you ping {you_ping or 'nothing'}"
    ]
    return "\n".join(lines)

class PartnershipModal(discord.ui.Modal, title="Partnership Request"):
    members = discord.ui.TextInput(label="Number of members", placeholder="e.g., 150", required=True)
    invite = discord.ui.TextInput(label="Invite link", placeholder="Discord invite URL", style=discord.TextStyle.short, required=True)

    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        # Use the members count as quantity and invite as IGN for ticket creation
        await create_ticket_channel_util(self.interaction, "partnership", quantity=self.members.value, ign=self.invite.value)
        await interaction.response.send_message("✅ Partnership ticket created!", ephemeral=True)

class PartnershipTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.success, custom_id="create_ticket_partnership_panel", emoji="🤝")
    async def create_partnership(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PartnershipModal(interaction))

class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, custom_id="create_ticket_support", emoji="🛠️")
    async def create_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket_channel_util(interaction, "support")

    @discord.ui.button(label="Technical Support", style=discord.ButtonStyle.success, custom_id="create_ticket_partnership", emoji="🤝")
    async def create_partnership(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket_channel_util(interaction, "partnership")

    @discord.ui.button(label="Giveaway Claim", style=discord.ButtonStyle.secondary, custom_id="create_ticket_giveaway", emoji="🎉")
    async def create_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketPanelGiveawayDisclaimerModal())

class VouchModal(discord.ui.Modal, title="Leave a Vouch"):
    comments = discord.ui.TextInput(
        label="Comments",
        style=discord.TextStyle.paragraph,
        placeholder="How was your experience?",
        required=True,
        max_length=1000
    )
    def __init__(self, is_scam: bool, ticket_type: str, target_user: int = None, view_to_disable: discord.ui.View = None, message: discord.Message = None, extra_info: str = None):
        super().__init__()
        self.is_scam = is_scam
        self.ticket_type = ticket_type
        self.target_user = target_user
        self.view_to_disable = view_to_disable
        self.message = message
        self.extra_info = extra_info
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Thank you for your feedback!", ephemeral=True)
        if VOUCH_CHANNEL_ID and str(VOUCH_CHANNEL_ID) != 'your_vouch_channel_id_here':
            channel = interaction.client.get_channel(int(VOUCH_CHANNEL_ID))
            if channel:
                title = "❌ Scam Vouch" if self.is_scam else "✅ Vouch"
                color = discord.Color.red() if self.is_scam else discord.Color.green()
                embed = discord.Embed(title=title, description=self.comments.value, color=color)
                embed.add_field(name="User", value=interaction.user.mention, inline=True)
                embed.add_field(name="Vouch Type", value=self.ticket_type.replace('_', '-').capitalize(), inline=True)
                if self.target_user:
                    embed.add_field(name="Vouched For", value=f"<@{self.target_user}>", inline=True)
                if self.extra_info:
                    if self.ticket_type == "giveaway":
                        embed.add_field(name="Prize", value=self.extra_info, inline=False)
                    elif self.ticket_type.startswith("spawner"):
                        embed.add_field(name="Spawners", value=self.extra_info, inline=False)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await channel.send(embed=embed)
                
        vouch_cooldowns[interaction.user.id] = time.time()
            
        if self.message and self.view_to_disable:
            try:
                for item in self.view_to_disable.children:
                    item.disabled = True
                await self.message.edit(view=self.view_to_disable)
            except:
                pass
                
        # Save to vouch_data
        if self.target_user:
            user_id_str = str(self.target_user)
            if user_id_str not in vouch_data:
                vouch_data[user_id_str] = {"vouches": 0, "scam_vouches": 0}
                
            if self.is_scam:
                vouch_data[user_id_str]["scam_vouches"] += 1
            else:
                vouch_data[user_id_str]["vouches"] += 1
                
            save_vouch_data()

class VouchView(discord.ui.View):
    def __init__(self, ticket_type: str, target_user: int = None, extra_info: str = None):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        self.target_user = target_user
        self.extra_info = extra_info
        
    @discord.ui.button(label="Vouch", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_vouch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VouchModal(is_scam=False, ticket_type=self.ticket_type, target_user=self.target_user, view_to_disable=self, message=interaction.message, extra_info=self.extra_info))
        
    @discord.ui.button(label="Scam Vouch", style=discord.ButtonStyle.danger, emoji="❌")
    async def btn_scam(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VouchModal(is_scam=True, ticket_type=self.ticket_type, target_user=self.target_user, view_to_disable=self, message=interaction.message, extra_info=self.extra_info))

closing_tickets = set()

async def create_and_send_transcript(interaction: discord.Interaction, gw: dict = None, spawner_completed: bool = False):
    channel = interaction.channel
    explicit_proof = ticket_proofs.pop(channel.id, None)
    proof_url = explicit_proof

    extra_info = None
    if gw:
        extra_info = gw['prize']

    transcript_content = f"Transcript for {channel.name}\n"
    transcript_content += f"Generated at {datetime.now(discord.utils.utcnow().tzinfo).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"

    messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
    for msg in messages:
        if not extra_info and msg.embeds:
            for em in msg.embeds:
                if em.description and "**Quantity:** " in em.description:
                    try:
                        qty = em.description.split("**Quantity:** ")[1].split("\n")[0]
                        spawner_name = channel.name.split('-')[1] if len(channel.name.split('-')) > 1 else ""
                        extra_info = f"{qty} {spawner_name.capitalize()} Spawners"
                        break
                    except Exception:
                        pass
            if extra_info:
                    break
                    
        if not msg.clean_content and not msg.attachments:
            continue
        time_str = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        content_str = msg.clean_content if msg.clean_content else "*[attachment]*"
        transcript_content += f"[{time_str}] {msg.author.name}: {content_str}\n"
        
        if msg.attachments:
            for attachment in msg.attachments:
                try:
                    file_data = await attachment.read()
                    file_url = None
                    if attachment.content_type and attachment.content_type.startswith('image/') and IMGBB_API_KEY and IMGBB_API_KEY != 'your_imgbb_api_key_here':
                        b64_image = base64.b64encode(file_data).decode('utf-8')
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}",
                                data={"image": b64_image}
                            ) as resp:
                                if resp.status == 200:
                                    json_resp = await resp.json()
                                    file_url = json_resp['data']['url']
                                    transcript_content += f"    [Image Uploaded to ImgBB: {file_url}]\n"
                    else:
                        data = aiohttp.FormData()
                        data.add_field('reqtype', 'fileupload')
                        data.add_field('fileToUpload', file_data, filename=attachment.filename)
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.post("https://catbox.moe/user/api.php", data=data) as resp:
                                if resp.status == 200:
                                    file_url = await resp.text()
                                    transcript_content += f"    [File Uploaded to Catbox: {file_url}]\n"
                                    
                    if file_url:
                        if not explicit_proof:
                            proof_url = file_url
                    else:
                        transcript_content += f"    [Attachment: {attachment.url}]\n"
                        if not explicit_proof:
                            proof_url = attachment.url
                except Exception:
                    transcript_content += f"    [Attachment: {attachment.url}]\n"
                    if not explicit_proof:
                        proof_url = attachment.url

    if proof_url:
        transcript_content = f"=== TICKET PROOF ===\nProof Image: {proof_url}\n====================\n\n" + transcript_content

    embed = discord.Embed(
        title=f"Ticket Closed: {channel.name}",
        color=discord.Color.red()
    )
    
    opener_id = None
    if gw:
        winners = gw.get('winners_list', set())
        if winners:
            opener_id = list(winners)[0]
    elif channel.topic:
        if ":spawner" in channel.topic:
            opener_id = channel.topic.split(":")[0]
        elif ":support" in channel.topic:
            opener_id = channel.topic.split(":")[0]
        elif ":partnership" in channel.topic:
            opener_id = channel.topic.split(":")[0]
            
    opener_mention = f"<@{opener_id}>" if opener_id else "Unknown"
    closer_mention = interaction.user.mention
    
    if gw:
        embed.description = f"**Giveaway Prize:** {gw['prize']}\n**Opened By:** {opener_mention}\n**Closed by:** {closer_mention}\n**Host:** <@{gw['host_id']}>"
    else:
        embed.description = f"**Opened By:** {opener_mention}\n**Closed by:** {closer_mention}"

    if proof_url:
        embed.add_field(name="Proof", value=f"**[Proof of payment]({proof_url})**", inline=False)
        embed.set_image(url=proof_url)

    transcript_bytes = transcript_content.encode('utf-8')

    if TRANSCRIPT_CHANNEL_ID and str(TRANSCRIPT_CHANNEL_ID) != 'your_transcript_channel_id_here':
        transcript_channel = interaction.guild.get_channel(int(TRANSCRIPT_CHANNEL_ID))
        if transcript_channel:
            try:
                await transcript_channel.send(embed=embed, file=discord.File(io.BytesIO(transcript_bytes), filename=f"{channel.name}-transcript.txt"))
            except Exception as e:
                print(f"Failed to send to transcript channel: {e}")

    # Removed host/closer transcript delivery to prevent unwanted DMs

    # Forward giveaway proof
    if gw and proof_url and GIVEAWAY_PROOF_CHANNEL_ID and str(GIVEAWAY_PROOF_CHANNEL_ID) != 'your_giveaway_proof_channel_id_here':
        proof_channel = interaction.client.get_channel(int(GIVEAWAY_PROOF_CHANNEL_ID))
        if not proof_channel:
            try: proof_channel = await interaction.guild.fetch_channel(int(GIVEAWAY_PROOF_CHANNEL_ID))
            except: pass
        if proof_channel:
            try:
                proof_embed = discord.Embed(title=f"Giveaway Proof: {gw['prize']}", color=discord.Color.gold())
                proof_embed.set_image(url=proof_url)
                await proof_channel.send(embed=proof_embed)
            except Exception as e:
                print(f"Failed to forward giveaway proof: {e}")
                
    # Send Vouch Prompts
    target_users = []
    ticket_type = "unknown"
    target_vouch_user = None
    spawner_claimer = None
    uid = None

    if gw:
        ticket_type = "giveaway"
        target_vouch_user = gw['host_id']
        for uid in gw.get('winners_list', set()):
            try:
                winner = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
                if winner: target_users.append(winner)
            except Exception:
                pass
    elif channel.topic and (channel.topic.endswith(":spawner") or ":spawner:" in channel.topic):
        if channel.name.startswith("buy-"):
            ticket_type = "spawner_buy"
        else:
            ticket_type = "spawner_sell"
        try:
            parts = channel.topic.split(":")
            uid = int(parts[0])
            if len(parts) >= 3:
                target_vouch_user = int(parts[2])
                try:
                    spawner_claimer = interaction.guild.get_member(target_vouch_user) or await interaction.guild.fetch_member(target_vouch_user)
                except Exception:
                    pass
            opener = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
            if opener: target_users.append(opener)
        except Exception:
            pass
    elif channel.topic and (":support" in channel.topic or ":partnership" in channel.topic):
        try:
            parts = channel.topic.split(":")
            uid = int(parts[0])
            ticket_type = parts[1]
            target_vouch_user = interaction.user.id
            opener = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
            if opener: target_users.append(opener)
        except Exception:
            pass
    for u in target_users:
        if u.id == bot.user.id:
            continue
            
        is_staff_member = False
        if hasattr(u, 'guild_permissions') and u.guild_permissions.administrator:
            is_staff_member = True
        elif hasattr(u, 'roles'):
            if TICKET_ROLE_ID and any(str(r.id) == str(TICKET_ROLE_ID) for r in u.roles):
                is_staff_member = True
            elif HIGH_PERMS_ROLE_ID and any(str(r.id) == str(HIGH_PERMS_ROLE_ID) for r in u.roles):
                is_staff_member = True
                
        if is_staff_member:
            continue

        try:
            vouch_embed = discord.Embed(
                title=f"Feedback Request: {channel.name}",
                description="Would you like to leave a vouch or a scam vouch for your recent ticket?",
                color=discord.Color.blue()
            )
            if target_vouch_user:
                vouch_embed.add_field(name="User", value=f"<@{target_vouch_user}>", inline=True)
            if extra_info:
                if ticket_type == "giveaway":
                    vouch_embed.add_field(name="Prize", value=extra_info, inline=True)
                elif ticket_type.startswith("spawner"):
                    vouch_embed.add_field(name="Spawners", value=extra_info, inline=True)
            if ticket_type == "giveaway":
                transcript_file = discord.File(io.BytesIO(transcript_bytes), filename=f"{channel.name}-transcript.txt")
                await u.send(embeds=[embed, vouch_embed], view=VouchView(ticket_type, target_vouch_user, extra_info), file=transcript_file)
            elif ticket_type.startswith("spawner"):
                transcript_file = discord.File(io.BytesIO(transcript_bytes), filename=f"{channel.name}-transcript.txt")
                if spawner_completed:
                    await u.send(embeds=[embed, vouch_embed], view=VouchView(ticket_type, target_vouch_user, extra_info), file=transcript_file)
                else:
                    await u.send(embed=embed, file=transcript_file)
            else:
                transcript_file = discord.File(io.BytesIO(transcript_bytes), filename=f"{channel.name}-transcript.txt")
                await u.send(embeds=[embed, vouch_embed], view=VouchView(ticket_type, target_vouch_user, extra_info), file=transcript_file)
        except discord.Forbidden:
            pass

    if ticket_type.startswith("spawner") and spawner_completed and spawner_claimer and uid:
        if spawner_claimer.id != bot.user.id:
            try:
                vouch_embed = discord.Embed(
                    title=f"Feedback Request: {channel.name}",
                    description="Would you like to leave a vouch or a scam vouch for the user you just helped?",
                    color=discord.Color.blue()
                )
                vouch_embed.add_field(name="User", value=f"<@{uid}>", inline=True)
                if extra_info:
                    vouch_embed.add_field(name="Spawners", value=extra_info, inline=True)
                await spawner_claimer.send(embed=vouch_embed, view=VouchView(ticket_type, uid, extra_info))
            except discord.Forbidden:
                pass

class GenericCloseButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="generic_close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.id in closing_tickets:
            try:
                await interaction.response.send_message("Ticket is already closing...", ephemeral=True)
            except:
                pass
            return
        closing_tickets.add(interaction.channel.id)

        await interaction.response.send_message(embed=discord.Embed(description="Ticket is being closed. Generating transcript...", color=discord.Color.red()))
        await create_and_send_transcript(interaction)
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete()
        except:
            pass

class SpawnerTransactionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Completed (Yes)", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_completed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.id in closing_tickets:
            return
        closing_tickets.add(interaction.channel.id)
        
        await interaction.response.send_message(embed=discord.Embed(description="Ticket is being closed. Generating transcript...", color=discord.Color.red()))
        await create_and_send_transcript(interaction, spawner_completed=True)
        await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

    @discord.ui.button(label="Cancelled (No)", style=discord.ButtonStyle.danger, emoji="❌")
    async def btn_cancelled(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.id in closing_tickets:
            return
        closing_tickets.add(interaction.channel.id)
        
        await interaction.response.send_message(embed=discord.Embed(description="Ticket is being closed. Generating transcript...", color=discord.Color.red()))
        await create_and_send_transcript(interaction, spawner_completed=False)
        await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class SpawnerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, custom_id="spawner_claim_ticket", emoji="🙋")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_high_staff(interaction) and not await is_spawner_staff(interaction):
            await interaction.response.send_message("❌ Only staff can claim tickets.", ephemeral=True)
            return
            
        topic = interaction.channel.topic
        if topic and (topic.endswith(":spawner") or ":spawner:" in topic):
            new_topic = f"{topic}:{interaction.user.id}" if ":spawner:" not in topic else topic
            try:
                await interaction.channel.edit(topic=new_topic)
            except:
                pass
            
            button.disabled = True
            button.label = f"Claimed by {interaction.user.display_name}"
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
            await interaction.channel.send(f"Ticket has been claimed by {interaction.user.mention}.")
        else:
            await interaction.response.send_message("Ticket already claimed or invalid.", ephemeral=True)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="spawner_close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Was the transaction completed successfully? (Did you buy/sell?)",
            view=SpawnerTransactionView(),
            ephemeral=True
        )

# ── Unified /setup command with dropdown select ────────────────────────────────

class SetupChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup_type: str):
        super().__init__(channel_types=[discord.ChannelType.text], placeholder="Select a text channel...")
        self.setup_type = setup_type

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        if guild_id not in server_config:
            server_config[guild_id] = {}
            
        channel = self.values[0]
        if self.setup_type == "welcome":
            server_config[guild_id]["welcome_channel"] = channel.id
            save_server_config()
            await interaction.response.edit_message(content=f"✅ Welcome messages will be sent to {channel.mention}", view=None)
        elif self.setup_type == "levelup":
            server_config[guild_id]["levelup_channel"] = channel.id
            save_server_config()
            await interaction.response.edit_message(content=f"✅ Level up images will be sent to {channel.mention} every 5 levels.", view=None)
        elif self.setup_type == "apps_channel":
            server_config[guild_id]["staff_apps_channel"] = channel.id
            save_server_config()
            await interaction.response.edit_message(content=f"📋 Staff applications will be sent to {channel.mention} for review.", view=None)

class SetupChannelView(discord.ui.View):
    def __init__(self, setup_type: str):
        super().__init__(timeout=180)
        self.add_item(SetupChannelSelect(setup_type))

class VouchUserSelectView(discord.ui.View):
    def __init__(self, is_scam: bool):
        super().__init__(timeout=180)
        self.is_scam = is_scam

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select the user...")
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        uid = interaction.user.id
        import time
        now = time.time()
        if uid in vouch_cooldowns:
            if now - vouch_cooldowns[uid] < 600:
                remaining = int(600 - (now - vouch_cooldowns[uid]))
                minutes, seconds = divmod(remaining, 60)
                await interaction.response.send_message(f"⏳ You can use this command again in {minutes}m {seconds}s.", ephemeral=True)
                return
        
        target_user = select.values[0]
        await interaction.response.send_modal(VouchModal(
            is_scam=self.is_scam, 
            ticket_type="custom", 
            target_user=target_user.id, 
            view_to_disable=None, 
            message=None, 
            extra_info=None
        ))

class VouchPanelButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Leave a Vouch", style=discord.ButtonStyle.success, custom_id="panel_vouch_add", emoji="👍")
    async def btn_vouch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Please select the user you want to vouch for:",
            view=VouchUserSelectView(is_scam=False),
            ephemeral=True
        )

    @discord.ui.button(label="Leave a Scam Vouch", style=discord.ButtonStyle.danger, custom_id="panel_vouch_scam", emoji="👎")
    async def btn_scam(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Please select the user you want to report as a scammer:",
            view=VouchUserSelectView(is_scam=True),
            ephemeral=True
        )

class SetupSelectView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.original_interaction = interaction

    @discord.ui.select(
        placeholder="Choose a module to setup...",
        options=[
            discord.SelectOption(label="🎫 Ticket Panel",              value="ticket",           description="Spawn the support ticket panel"),
            discord.SelectOption(label="🐣 Spawner Panel",             value="spawners",          description="Spawn the spawner trading panel"),
            discord.SelectOption(label="🤝 Partnership Panel",         value="partnership",       description="Spawn the partnership requirements panel"),
            discord.SelectOption(label="🚫 Ban Appeal Panel",            value="ban_appeal",        description="Spawn the ban appeal panel for banned members"),
            discord.SelectOption(label="🏠 Schematic Service Panel",    value="schematic",         description="Spawn the schematic editing service panel"),
            discord.SelectOption(label="📋 Staff Applications",        value="staff_apps",        description="Spawn the staff application panel"),
            discord.SelectOption(label="🌟 Vouches Panel",             value="vouches",           description="Spawn the vouches menu panel"),
            discord.SelectOption(label="👋 Welcome Channel",           value="welcome",           description="Set the channel for welcome messages"),
            discord.SelectOption(label="📋 Apps Channel",              value="apps_channel",      description="Set the channel for staff application reviews"),
            discord.SelectOption(label="📈 Server Stats",              value="serverstats",       description="Create server stats voice channels"),
            discord.SelectOption(label="⭐ Level Roles",               value="level_roles",       description="Create Level 5-50 roles automatically"),
            discord.SelectOption(label="🏆 Levelup Channel",           value="levelup",           description="Set the channel to post milestone rank cards"),
            discord.SelectOption(label="🔄 Reload All Panels",         value="reload_all",        description="Reload all persistent panels"),
        ]
    )
    async def panel_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        value = select.values[0]

        if value == "ticket":
            embed = discord.Embed(
                title=TICKET_PANEL_TITLE,
                description=TICKET_PANEL_TEXT,
                color=discord.Color.yellow()
            )
            embed.set_footer(text="Urge Support · false / troll tickets may result in a blacklist")
            msg = await self.original_interaction.channel.send(embed=embed, view=TicketButton())
            
            guild_id = str(self.original_interaction.guild_id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            server_config[guild_id]["ticket_panel_channel"] = msg.channel.id
            server_config[guild_id]["ticket_panel_message"] = msg.id
            save_server_config()

            await interaction.response.edit_message(content="✅ Ticket panel spawned!", view=None)

        elif value == "spawners":
            spawner_prices["_metadata"] = {
                "channel_id": self.original_interaction.channel.id,
                "message_id": None
            }
            save_spawner_prices()
            await update_spawner_panel(interaction.client)
            await interaction.response.edit_message(content="✅ Spawner panel spawned!", view=None)

        elif value == "partnership":
            await interaction.response.edit_message(content="⏳ Generating partnership panel...", view=None)
            new_desc = await generate_partnership_requirements(self.original_interaction.guild)
            embed = discord.Embed(
                title="🤝 Partnership Requirements",
                description=new_desc,
                color=discord.Color.yellow()
            )
            embed.set_footer(text="Click the button below to apply for a partnership")
            msg = await self.original_interaction.channel.send(embed=embed, view=PartnershipTicketButton())
            guild_id = str(self.original_interaction.guild_id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            server_config[guild_id]["partnership_panel_channel"] = msg.channel.id
            server_config[guild_id]["partnership_panel_message"] = msg.id
            save_server_config()
            await interaction.edit_original_response(content="✅ Partnership panel spawned!")

        elif value == "ban_appeal":
            if not BAN_APPEAL_CHANNEL_ID:
                await interaction.response.edit_message(content="❌ `BAN_APPEAL_CHANNEL_ID` is not set in `.env`.", view=None)
                return
            target_channel = self.original_interaction.guild.get_channel(int(BAN_APPEAL_CHANNEL_ID))
            if target_channel is None:
                await interaction.response.edit_message(content="❌ Ban appeal channel not found.", view=None)
                return
            embed = discord.Embed(
                title="🚫 Ban Appeal",
                description="If you believe your ban was unjust, click the button below to open a ban appeal ticket.\nBe honest and detailed in your explanation — staff will review your case.",
                color=discord.Color.red()
            )
            embed.set_footer(text="False appeals may result in a permanent ban")
            msg = await target_channel.send(embed=embed, view=BanAppealTicketButton())
            
            guild_id = str(self.original_interaction.guild_id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            server_config[guild_id]["ban_appeal_panel_channel"] = msg.channel.id
            server_config[guild_id]["ban_appeal_panel_message"] = msg.id
            save_server_config()

            await interaction.response.edit_message(content="✅ Ban appeal panel spawned!", view=None)

        elif value == "schematic":
            embed = discord.Embed(
                title="Schematic Editing Service  🏠",
                description="**Price:** 25–200m *(Depending on Size)*\n**Done in:** 1–2 hours\n**Anything can be edited**\n\nIf you want to order this service, open a ticket below.",
                color=discord.Color.yellow()
            )
            msg = await self.original_interaction.channel.send(embed=embed, view=SchematicTicketButton())
            
            guild_id = str(self.original_interaction.guild_id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            server_config[guild_id]["schematic_panel_channel"] = msg.channel.id
            server_config[guild_id]["schematic_panel_message"] = msg.id
            save_server_config()

            await interaction.response.edit_message(content="✅ Schematic service panel spawned!", view=None)

        elif value == "staff_apps":
            embed = discord.Embed(
                title="📋 Staff Applications",
                description="Click the button below to apply for an open staff position.\nMake sure to answer the questions honestly and completely.",
                color=discord.Color.blue()
            )
            msg = await self.original_interaction.channel.send(embed=embed, view=StaffApplicationButton())
            
            guild_id = str(self.original_interaction.guild_id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            server_config[guild_id]["staff_apps_panel_channel"] = msg.channel.id
            server_config[guild_id]["staff_apps_panel_message"] = msg.id
            save_server_config()

            await interaction.response.edit_message(content="✅ Staff Applications panel spawned!", view=None)

        elif value == "vouches":
            embed = discord.Embed(
                title="🌟 Vouches",
                description="Click the buttons below to interact with the vouching system.",
                color=discord.Color.gold()
            )
            await self.original_interaction.channel.send(embed=embed, view=VouchPanelButton())
            await interaction.response.edit_message(content="✅ Vouches panel spawned!", view=None)

        elif value == "welcome":
            await interaction.response.edit_message(content="Please select the channel for Welcome Messages:", view=SetupChannelView("welcome"))
            
        elif value == "levelup":
            await interaction.response.edit_message(content="Please select the channel for Level Up Milestone Images:", view=SetupChannelView("levelup"))
            
        elif value == "level_roles":
            await interaction.response.edit_message(content="⏳ Creating level roles...", view=None)
            guild = interaction.guild
            created = 0
            for level in range(5, 55, 5):
                role_name = f"Level {level}"
                if not discord.utils.get(guild.roles, name=role_name):
                    try:
                        await guild.create_role(name=role_name, color=discord.Color.teal(), hoist=True)
                        created += 1
                    except discord.Forbidden:
                        await interaction.edit_original_response(content="❌ I don't have permission to create roles.")
                        return
            await interaction.edit_original_response(content=f"✅ Setup complete! Created {created} level roles.")

        elif value == "serverstats":
            await interaction.response.edit_message(content="⏳ Creating server stats channels...", view=None)
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="📊 Server Stats")
            if not category:
                category = await guild.create_category("📊 Server Stats", position=0)
                
            all_members = guild.member_count
            bots = sum(1 for m in guild.members if m.bot)
            members = all_members - bots
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False)
            }
            
            ch_all = await guild.create_voice_channel(f"All Members: {all_members}", category=category, overwrites=overwrites)
            ch_mem = await guild.create_voice_channel(f"Members: {members}", category=category, overwrites=overwrites)
            ch_bot = await guild.create_voice_channel(f"Bots: {bots}", category=category, overwrites=overwrites)
            
            guild_id = str(guild.id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            
            server_config[guild_id]["stats_category"] = category.id
            server_config[guild_id]["stats_all"] = ch_all.id
            server_config[guild_id]["stats_members"] = ch_mem.id
            server_config[guild_id]["stats_bots"] = ch_bot.id
            save_server_config()
            
            await interaction.edit_original_response(content="✅ Server stats channels have been created!")

        elif value == "reload_all":
            await interaction.response.edit_message(content="⏳ Reloading all panels...", view=None)
            results = []

            # 1. Reload partnership panel
            guild_id = str(self.original_interaction.guild_id)
            if guild_id in server_config and "partnership_panel_message" in server_config[guild_id]:
                channel_id = server_config[guild_id]["partnership_panel_channel"]
                message_id = server_config[guild_id]["partnership_panel_message"]
                channel = bot.get_channel(channel_id)
                if channel:
                    try:
                        msg = await channel.fetch_message(message_id)
                        new_desc = await generate_partnership_requirements(self.original_interaction.guild)
                        embed = discord.Embed(
                            title="🤝 Partnership Requirements",
                            description=new_desc,
                            color=discord.Color.yellow()
                        )
                        embed.set_footer(text="Updated manually via /setup")
                        await msg.edit(embed=embed)
                        results.append("✅ Partnership panel reloaded")
                    except Exception as e:
                        results.append(f"⚠️ Partnership panel: {e}")
                else:
                    results.append("⚠️ Partnership panel channel not found")
            else:
                results.append("ℹ️ No partnership panel stored for this server")

            # 2. Refresh spawner panel
            try:
                await update_spawner_panel(interaction.client)
                results.append("✅ Spawner panel refreshed")
            except Exception as e:
                results.append(f"⚠️ Spawner panel: {e}")

            # 3. Reload Ticket Panel
            if guild_id in server_config and "ticket_panel_message" in server_config[guild_id]:
                channel = bot.get_channel(server_config[guild_id]["ticket_panel_channel"])
                if channel:
                    try:
                        msg = await channel.fetch_message(server_config[guild_id]["ticket_panel_message"])
                        embed = discord.Embed(
                            title=TICKET_PANEL_TITLE,
                            description=TICKET_PANEL_TEXT,
                            color=discord.Color.yellow()
                        )
                        embed.set_footer(text="Urge Support · false / troll tickets may result in a blacklist")
                        await msg.edit(embed=embed, view=TicketButton())
                        results.append("✅ Ticket panel reloaded")
                    except Exception as e:
                        results.append(f"⚠️ Ticket panel: {e}")

            # 4. Reload Ban Appeal Panel
            if guild_id in server_config and "ban_appeal_panel_message" in server_config[guild_id]:
                channel = bot.get_channel(server_config[guild_id]["ban_appeal_panel_channel"])
                if channel:
                    try:
                        msg = await channel.fetch_message(server_config[guild_id]["ban_appeal_panel_message"])
                        embed = discord.Embed(
                            title="🚫 Ban Appeal",
                description="If you believe your ban was unjust, click the button below to open a ban appeal ticket.\nBe honest and detailed in your explanation — staff will review your case.",
                            color=discord.Color.red()
                        )
                        embed.set_footer(text="False appeals may result in a permanent ban")
                        await msg.edit(embed=embed, view=BanAppealTicketButton())
                        results.append("✅ Ban appeal panel reloaded")
                    except Exception as e:
                        results.append(f"⚠️ Ban appeal panel: {e}")

            # 5. Reload Schematic Panel
            if guild_id in server_config and "schematic_panel_message" in server_config[guild_id]:
                channel = bot.get_channel(server_config[guild_id]["schematic_panel_channel"])
                if channel:
                    try:
                        msg = await channel.fetch_message(server_config[guild_id]["schematic_panel_message"])
                        embed = discord.Embed(
                            title="Schematic Editing Service  🏠",
                            description="**Price:** 25-200m *(Depending on Size)*\n**Done in:** 1-2 hours\n**Anything can be edited**\n\nIf you want to order this service, open a ticket below.",
                            color=discord.Color.yellow()
                        )
                        await msg.edit(embed=embed, view=SchematicTicketButton())
                        results.append("✅ Schematic panel reloaded")
                    except Exception as e:
                        results.append(f"⚠️ Schematic panel: {e}")

            # 6. Reload Staff Applications Panel
            if guild_id in server_config and "staff_apps_panel_message" in server_config[guild_id]:
                channel = bot.get_channel(server_config[guild_id]["staff_apps_panel_channel"])
                if channel:
                    try:
                        msg = await channel.fetch_message(server_config[guild_id]["staff_apps_panel_message"])
                        embed = discord.Embed(
                            title="📋 Staff Applications",
                description="Click the button below to apply for an open staff position.\nMake sure to answer the questions honestly and completely.",
                            color=discord.Color.blue()
                        )
                        await msg.edit(embed=embed, view=StaffApplicationButton())
                        results.append("✅ Staff Applications panel reloaded")
                    except Exception as e:
                        results.append(f"⚠️ Staff Applications panel: {e}")

            await interaction.edit_original_response(content="\n".join(results))


@tree.command(name="setup", description="Spawn panels or configure server settings")
@app_commands.default_permissions(administrator=True)
async def setup_cmd(interaction: discord.Interaction):
    if not await is_high_staff(interaction):
        await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
        return
    await interaction.response.send_message(
        "Select a module to setup:",
        view=SetupSelectView(interaction),
        ephemeral=True
    )


# ── Schematic Editing Service ──────────────────────────────────────────────────

class SchematicTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Order Service", style=discord.ButtonStyle.primary, custom_id="create_schematic_ticket", emoji="🏠")
    async def order_schematic(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user  = interaction.user
        ticket_name = f"schematic-{user.name.lower()}"

        existing = discord.utils.get(guild.channels, name=ticket_name)
        if existing:
            await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return

        category_id        = BUILDER_CATEGORY_ID or SUPPORT_CATEGORY_ID
        ticket_role_id     = TICKET_ROLE_ID
        high_perms_role_id = HIGH_PERMS_ROLE_ID

        if not category_id or not ticket_role_id or not high_perms_role_id:
            await interaction.response.send_message("Ticket system is not fully configured.", ephemeral=True)
            return

        category        = guild.get_channel(int(category_id))
        ticket_role     = guild.get_role(int(ticket_role_id))
        high_perms_role = guild.get_role(int(high_perms_role_id))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
        }
        if ticket_role:     overwrites[ticket_role]     = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
        if high_perms_role: overwrites[high_perms_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=f"{user.id}:schematic"
            )
            embed = discord.Embed(
                title="🏠 Schematic Editing Service",
                description="**Price:** 25-200m *(Depending on Size)*\n**Done in:** 1-2 hours\n**Anything can be edited**\n\nIf you want to order this service, open a ticket below.",
            )
            mentions = [user.mention]
            if ticket_role: mentions.append(ticket_role.mention)
            await ticket_channel.send(" | ".join(mentions), embed=embed, view=GenericCloseButton())
            await interaction.response.send_message(f"✅ Your schematic ticket has been opened: {ticket_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create ticket: {e}", ephemeral=True)

# ── TikTok Live Tracking ───────────────────────────────────────────────────────

@tree.command(name="live", description="Track a TikTok account for live streams")
@app_commands.default_permissions(administrator=True)
async def live_cmd(interaction: discord.Interaction, tiktok_username: str, channel: discord.TextChannel):
    if not await is_high_staff(interaction):
        await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
        return
        
    guild_id = str(interaction.guild_id)
    if guild_id not in tiktok_data:
        tiktok_data[guild_id] = {}
        
    username = tiktok_username.strip().lstrip("@")
    
    trackers = tiktok_data[guild_id]
    trackers[username] = {
        "channel_id": channel.id,
        "is_live": False # Store initial state
    }
    save_tiktok_data()
    
    await interaction.response.send_message(f"✅ Now tracking **@{username}** for live streams in {channel.mention}.", ephemeral=True)

@tree.command(name="unlive", description="Stop tracking a TikTok account")
@app_commands.default_permissions(administrator=True)
async def unlive_cmd(interaction: discord.Interaction, tiktok_username: str):
    if not await is_high_staff(interaction):
        await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
        return
        
    guild_id = str(interaction.guild_id)
    username = tiktok_username.strip().lstrip("@")
    
    if guild_id in tiktok_data and username in tiktok_data[guild_id]:
        del tiktok_data[guild_id][username]
        save_tiktok_data()
        await interaction.response.send_message(f"✅ Stopped tracking **@{username}**.", ephemeral=True)
        return
            
    await interaction.response.send_message(f"❌ Could not find **@{username}** in the tracking list.", ephemeral=True)

# ── Unified /spawner command with dropdown select ─────────────────────────────

class SpawnerAddModal(discord.ui.Modal, title="Add / Update Spawner Type"):
    name   = discord.ui.TextInput(label="Spawner name", placeholder="e.g. skeleton, creeper", required=True)
    we_sell = discord.ui.TextInput(label="We Sell price", placeholder="e.g. 100k", required=True)
    we_buy  = discord.ui.TextInput(label="We Buy price",  placeholder="e.g. 50k",  required=True)
    emoji   = discord.ui.TextInput(label="Emoji",         placeholder="📦",         required=False, default="📦", max_length=8)

    async def on_submit(self, interaction: discord.Interaction):
        n = self.name.value.lower()
        spawner_prices[n] = {
            "buy": self.we_sell.value,
            "sell": self.we_buy.value,
            "emoji": self.emoji.value or "📦",
            "buy_bulk": None,
            "sell_bulk": None,
            "bulk_threshold": 256
        }
        save_spawner_prices()
        await update_spawner_panel(interaction.client)
        await interaction.response.send_message(f"✅ Spawner **{n}** added/updated!", ephemeral=True)

class SpawnerEditModal(discord.ui.Modal, title="Edit Spawner Type"):
    name    = discord.ui.TextInput(label="Spawner name (exact)", placeholder="e.g. skeleton", required=True)
    we_sell = discord.ui.TextInput(label="New We Sell price (leave blank to keep)", required=False)
    we_buy  = discord.ui.TextInput(label="New We Buy price (leave blank to keep)",  required=False)
    emoji   = discord.ui.TextInput(label="New Emoji (leave blank to keep)",          required=False, max_length=8)

    async def on_submit(self, interaction: discord.Interaction):
        n = self.name.value.lower()
        if n not in spawner_prices or n == "_metadata":
            await interaction.response.send_message(f"❌ Spawner **{n}** not found.", ephemeral=True)
            return
        data = spawner_prices[n]
        if self.we_sell.value: data["buy"] = self.we_sell.value
        if self.we_buy.value:  data["sell"] = self.we_buy.value
        if self.emoji.value:   data["emoji"] = self.emoji.value
        save_spawner_prices()
        await update_spawner_panel(interaction.client)
        await interaction.response.send_message(f"✅ Spawner **{n}** updated!", ephemeral=True)

class SpawnerRemoveModal(discord.ui.Modal, title="Remove Spawner Type"):
    name = discord.ui.TextInput(label="Spawner name (exact)", placeholder="e.g. skeleton", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        n = self.name.value.lower()
        if n in spawner_prices and n != "_metadata":
            del spawner_prices[n]
            save_spawner_prices()
            await update_spawner_panel(interaction.client)
            await interaction.response.send_message(f"✅ Spawner **{n}** removed!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Spawner **{n}** not found.", ephemeral=True)

class SpawnerActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="Choose an action...",
        options=[
            discord.SelectOption(label="📋 List Spawners",          value="list",   description="Show all current spawner types and prices"),
            discord.SelectOption(label="➕ Add / Update Spawner",   value="add",    description="Add a new spawner type or update an existing one"),
            discord.SelectOption(label="✏️ Edit Spawner",           value="edit",   description="Edit prices or emoji of an existing spawner"),
            discord.SelectOption(label="🗑️ Remove Spawner",         value="remove", description="Delete a spawner type from the panel"),
        ]
    )
    async def spawner_action_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        value = select.values[0]
        if value == "list":
            items = [n for n in spawner_prices if n != "_metadata"]
            if not items:
                await interaction.response.send_message("No spawner types configured yet.", ephemeral=True)
                return
            lines = []
            for n in items:
                data = spawner_prices[n]
                emoji = data.get('emoji', '📦')
                sell = data.get('buy', '?')
                buy  = data.get('sell', '?')
                lines.append(f"{emoji} **{n.capitalize()}** — We Sell: `{sell}` | We Buy: `{buy}`")
            embed = discord.Embed(title="📋 Spawner Types", description="\n".join(lines), color=discord.Color.yellow())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif value == "add":
            await interaction.response.send_modal(SpawnerAddModal())
        elif value == "edit":
            await interaction.response.send_modal(SpawnerEditModal())
        elif value == "remove":
            await interaction.response.send_modal(SpawnerRemoveModal())

async def spawner_name_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    choices = []
    for name in spawner_prices:
        if name == "_metadata": continue
        if current.lower() in name.lower():
            choices.append(app_commands.Choice(name=name.capitalize(), value=name))
    return choices[:25]

@tree.command(name="spawner", description="Manage spawner types and prices")
async def spawner_cmd(interaction: discord.Interaction):
    if not await is_spawner_staff(interaction):
        await interaction.response.send_message("You do not have permission to manage spawners.", ephemeral=True)
        return
    await interaction.response.send_message(
        "Select a spawner action:",
        view=SpawnerActionView(),
        ephemeral=True
    )

# ── Ban Appeal ─────────────────────────────────────────────────────────────────

class BanAppealUnbanView(discord.ui.View):
    """Shown to high staff after they press Close on a ban appeal ticket."""
    def __init__(self, appealer_id: int):
        super().__init__(timeout=120)
        self.appealer_id = appealer_id

    @discord.ui.button(label="✅ Unban Member", style=discord.ButtonStyle.success, custom_id="ban_appeal_unban_yes")
    async def unban_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild  = interaction.guild
        member = guild.get_member(self.appealer_id)

        if member:
            banned_role = guild.get_role(int(BANNED_ROLE_ID)) if BANNED_ROLE_ID else None

            # Remove banned role
            if banned_role and banned_role in member.roles:
                try:
                    await member.remove_roles(banned_role, reason=f"Unbanned via ban appeal by {interaction.user}")
                except discord.Forbidden:
                    pass

            # Restore saved roles
            guild_id = str(guild.id)
            saved_ids = server_config.get(guild_id, {}).get("banned_member_roles", {}).get(str(self.appealer_id), [])
            roles_to_add = []
            for rid in saved_ids:
                role = guild.get_role(rid)
                if role and role not in member.roles:
                    roles_to_add.append(role)
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add, reason="Roles restored after unban")
                except discord.Forbidden:
                    pass

            # Clean up stored roles
            if guild_id in server_config and "banned_member_roles" in server_config[guild_id]:
                server_config[guild_id]["banned_member_roles"].pop(str(self.appealer_id), None)
                save_server_config()

            # DM the member
            try:
                await member.send(embed=discord.Embed(
                    title="✅ Ban Appeal Accepted",
                    description=f"Your ban appeal in **{guild.name}** has been accepted. Your access and roles have been restored.",
                    color=discord.Color.green()
                ))
            except Exception:
                pass

        await interaction.response.edit_message(
            content=f"✅ {member.mention if member else f'<@{self.appealer_id}>'} has been unbanned. Closing ticket...",
            view=None
        )
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="🚫 Keep Banned", style=discord.ButtonStyle.danger, custom_id="ban_appeal_unban_no")
    async def unban_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.appealer_id)
        # DM the member about rejection
        if member:
            try:
                await member.send(embed=discord.Embed(
                    title="🚫 Ban Appeal Rejected",
                    description=f"Your ban appeal in **{interaction.guild.name}** has been reviewed and rejected. You remain banned.",
                    color=discord.Color.red()
                ))
            except Exception:
                pass

        await interaction.response.edit_message(content="🚫 Appeal rejected. Member remains banned. Closing ticket...", view=None)
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class BanAppealCloseView(discord.ui.View):
    """Close button for ban appeal tickets — high staff only."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ban_appeal_close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only high staff can close
        if not await is_high_staff(interaction):
            await interaction.response.send_message("❌ Only high staff can close ban appeal tickets.", ephemeral=True)
            return

        # Parse the appealer's user ID from channel topic
        topic = interaction.channel.topic or ""
        appealer_id = None
        if ":" in topic:
            try:
                appealer_id = int(topic.split(":")[0])
            except ValueError:
                pass

        if not appealer_id:
            await interaction.response.send_message("⚠️ Could not determine who opened this appeal. Closing anyway...", ephemeral=True)
            await asyncio.sleep(2)
            try:
                await interaction.channel.delete()
            except Exception:
                pass
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚖️ Ban Appeal Decision",
                description=f"Do you want to **unban** <@{appealer_id}>?\n\nChoose below:",
                color=discord.Color.orange()
            ),
            view=BanAppealUnbanView(appealer_id),
            ephemeral=True
        )


class BanAppealTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Appeal Ban", style=discord.ButtonStyle.danger, custom_id="create_ban_appeal_ticket", emoji="🚫")
    async def appeal_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        import time
        guild = interaction.guild
        user  = interaction.user
        ticket_name = f"ban-appeal-{user.name.lower()}"

        # ── 24h cooldown check ──────────────────────────────────────────────
        COOLDOWN_SECONDS = 86400  # 24 hours
        guild_id = str(guild.id)
        cooldowns = server_config.get(guild_id, {}).get("ban_appeal_cooldowns", {})
        last_opened = cooldowns.get(str(user.id))
        if last_opened:
            elapsed = time.time() - last_opened
            if elapsed < COOLDOWN_SECONDS:
                remaining = COOLDOWN_SECONDS - elapsed
                hours   = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                seconds = int(remaining % 60)
                parts = []
                if hours:   parts.append(f"{hours}h")
                if minutes: parts.append(f"{minutes}m")
                if seconds: parts.append(f"{seconds}s")
                await interaction.response.send_message(
                    f"⏳ You are on cooldown. You can open a new ban appeal in **{' '.join(parts)}**.",
                    ephemeral=True
                )
                return
        # ───────────────────────────────────────────────────────────────────

        existing = discord.utils.get(guild.channels, name=ticket_name)
        if existing:
            await interaction.response.send_message(f"You already have an open appeal: {existing.mention}", ephemeral=True)
            return

        category_id        = SUPPORT_CATEGORY_ID
        ticket_role_id     = TICKET_ROLE_ID
        high_perms_role_id = HIGH_PERMS_ROLE_ID

        if not category_id or not ticket_role_id or not high_perms_role_id:
            await interaction.response.send_message("Ticket system is not fully configured.", ephemeral=True)
            return

        category        = guild.get_channel(int(category_id))
        ticket_role     = guild.get_role(int(ticket_role_id))
        high_perms_role = guild.get_role(int(high_perms_role_id))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
        }
        if ticket_role:     overwrites[ticket_role]     = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
        if high_perms_role: overwrites[high_perms_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=f"{user.id}:ban_appeal"
            )
            embed = discord.Embed(
                title=f"🚫 Ban Appeal: {user.name}",
                description="Please explain why you believe your ban should be lifted.\n\nStaff will review your appeal and respond as soon as possible.\n\n⚠️ **Only staff can close this ticket.**",
                color=discord.Color.red()
            )
            embed.add_field(name="Opened by", value=user.mention, inline=False)
            mentions = [user.mention]
            if ticket_role: mentions.append(ticket_role.mention)
            await ticket_channel.send(" | ".join(mentions), embed=embed, view=BanAppealCloseView())

            # Save cooldown timestamp
            if guild_id not in server_config:
                server_config[guild_id] = {}
            if "ban_appeal_cooldowns" not in server_config[guild_id]:
                server_config[guild_id]["ban_appeal_cooldowns"] = {}
            server_config[guild_id]["ban_appeal_cooldowns"][str(user.id)] = time.time()
            save_server_config()

            await interaction.response.send_message(f"✅ Your ban appeal has been opened: {ticket_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create appeal ticket: {e}", ephemeral=True)



@tree.command(name="ban", description="Ban a member — strips roles and assigns the Banned role")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(member="Member to ban", reason="Reason for the ban")
async def ban_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not await is_high_staff(interaction):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    guild = interaction.guild

    if not BAN_APPEAL_CHANNEL_ID:
        await interaction.response.send_message("❌ `BAN_APPEAL_CHANNEL_ID` is not set in `.env`.", ephemeral=True)
        return
    if not BANNED_ROLE_ID:
        await interaction.response.send_message("❌ `BANNED_ROLE_ID` is not set in `.env`.", ephemeral=True)
        return

    appeal_channel = guild.get_channel(int(BAN_APPEAL_CHANNEL_ID))
    banned_role    = guild.get_role(int(BANNED_ROLE_ID))

    if appeal_channel is None:
        await interaction.response.send_message("❌ Ban appeal channel not found. Check `BAN_APPEAL_CHANNEL_ID` in `.env`.", ephemeral=True)
        return
    if banned_role is None:
        await interaction.response.send_message("❌ Banned role not found. Check `BANNED_ROLE_ID` in `.env`.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    # Save the member's current roles before stripping (for restoration on unban)
    guild_id = str(guild.id)
    if guild_id not in server_config:
        server_config[guild_id] = {}
    if "banned_member_roles" not in server_config[guild_id]:
        server_config[guild_id]["banned_member_roles"] = {}
    roles_to_save = [r.id for r in member.roles if r != guild.default_role and r.id != int(BANNED_ROLE_ID)]
    server_config[guild_id]["banned_member_roles"][str(member.id)] = roles_to_save
    save_server_config()

    # Strip all existing roles
    try:
        roles_to_remove = [r for r in member.roles if r != guild.default_role]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Banned by {interaction.user}: {reason}")
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Could not remove member roles (missing permissions).")
        return

    # Assign the Banned role
    try:
        await member.add_roles(banned_role, reason=f"Banned by {interaction.user}: {reason}")
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Could not assign the Banned role (missing permissions).")
        return

    # Make sure the appeal channel allows the Banned role to read (view-only)
    try:
        await appeal_channel.set_permissions(banned_role, read_messages=True, send_messages=False, read_message_history=True)
    except discord.Forbidden:
        pass

    # DM the member
    try:
        await member.send(embed=discord.Embed(
            title="🚫 You have been banned",
            description=f"You have been banned from **{guild.name}**.\n\n**Reason:** {reason}\n\nYou can appeal your ban using the button in {appeal_channel.mention}.",
            color=discord.Color.red()
        ))
    except Exception:
        pass

    confirm = discord.Embed(
        title="🚫 Member Banned",
        description=f"{member.mention} has been given the **{banned_role.name}** role and can only access {appeal_channel.mention} to appeal.\n\n**Reason:** {reason}",
        color=discord.Color.red()
    )
    confirm.set_footer(text=f"Banned by {interaction.user}")
    await interaction.followup.send(embed=confirm)


@tree.command(name="unban", description="Unban a member — removes the Banned role")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(member="Member to unban")
async def unban_cmd(interaction: discord.Interaction, member: discord.Member):
    if not await is_high_staff(interaction):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if not BANNED_ROLE_ID:
        await interaction.response.send_message("❌ `BANNED_ROLE_ID` is not set in `.env`.", ephemeral=True)
        return

    banned_role = interaction.guild.get_role(int(BANNED_ROLE_ID))
    if banned_role is None:
        await interaction.response.send_message("❌ Banned role not found.", ephemeral=True)
        return

    if banned_role not in member.roles:
        await interaction.response.send_message(f"⚠️ {member.mention} does not have the Banned role.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        await member.remove_roles(banned_role, reason=f"Unbanned by {interaction.user}")
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Could not remove the Banned role (missing permissions).")
        return

    guild_id = str(interaction.guild_id)
    saved_ids = server_config.get(guild_id, {}).get("banned_member_roles", {}).get(str(member.id), [])
    roles_to_add = []
    for rid in saved_ids:
        role = interaction.guild.get_role(rid)
        if role and role not in member.roles:
            roles_to_add.append(role)
    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add, reason="Roles restored after unban")
        except discord.Forbidden:
            pass
    # Clean up stored roles
    if guild_id in server_config and "banned_member_roles" in server_config[guild_id]:
        server_config[guild_id]["banned_member_roles"].pop(str(member.id), None)
        save_server_config()

    # DM the member
    try:
        await member.send(embed=discord.Embed(
            title="✅ You have been unbanned",
            description=f"Your ban in **{interaction.guild.name}** has been lifted. Welcome back!",
            color=discord.Color.green()
        ))
    except Exception:
        pass

    await interaction.followup.send(embed=discord.Embed(
        title="✅ Member Unbanned",
        description=f"{member.mention} has had the **{banned_role.name}** role removed.",
        color=discord.Color.green()
    ).set_footer(text=f"Unbanned by {interaction.user}"))


class QuantityModal(discord.ui.Modal, title='Enter Quantity & IGN'):

    quantity = discord.ui.TextInput(
        label='Quantity (Numbers only)',
        style=discord.TextStyle.short,
        placeholder='e.g. 1, 5, 10',
        required=True
    )
    ign = discord.ui.TextInput(
        label='In-Game Name (IGN)',
        style=discord.TextStyle.short,
        placeholder='Your Minecraft username',
        required=True
    )
    
    def __init__(self, ticket_type: str, price_str: str, bulk_price_str: str = None, bulk_threshold: int = 256, action_msg: discord.Message = None):
        super().__init__()
        self.ticket_type = ticket_type
        self.price_str = price_str
        self.bulk_price_str = bulk_price_str
        self.bulk_threshold = bulk_threshold
        self.action_msg = action_msg
        
    async def on_submit(self, interaction: discord.Interaction):
        q_val = self.quantity.value.strip()
        if not q_val.isdigit():
            await interaction.response.send_message("❌ Error: Quantity must be a valid number.", ephemeral=True)
            return
            
        q_num = int(q_val)
        
        if self.bulk_price_str and q_num >= self.bulk_threshold:
            unit_price = parse_price(self.bulk_price_str)
        else:
            unit_price = parse_price(self.price_str)
            
        total_price = format_price(unit_price * q_num)
        
        parts = self.ticket_type.split('_', 1)
        action = parts[0]
        spawner_name = parts[1] if len(parts) > 1 else "unknown"
        log_spawner_transaction(interaction.user, action, spawner_name, q_num, total_price)
        
        if interaction.message:
            try: await interaction.message.delete()
            except: pass
        if self.action_msg:
            try: await self.action_msg.delete()
            except: pass
            
        await create_ticket_channel_util(interaction, self.ticket_type, q_val, total_price, self.ign.value)

class BuySpawnerSelect(discord.ui.Select):
    def __init__(self, action_msg: discord.Message = None):
        self.action_msg = action_msg
        options = []
        for name, data in spawner_prices.items():
            if name == "_metadata": continue
            desc = f"Price: {data.get('buy', 'N/A')}"
            thresh = data.get('bulk_threshold', 256)
            if data.get('buy_bulk'):
                desc += f" (if {thresh}+: {data['buy_bulk']})"
            options.append(discord.SelectOption(label=f"Buy {name.capitalize()}", value=f"buy_{name}", description=desc, emoji=data.get('emoji', '📦')))
        if not options:
            options.append(discord.SelectOption(label="No spawners available", value="none"))
        super().__init__(placeholder="Select a spawner to BUY...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("No spawners configured.", ephemeral=True)
            return
        item_name = val.split('_', 1)[1]
        price_str = spawner_prices.get(item_name, {}).get("buy", "0")
        bulk_price_str = spawner_prices.get(item_name, {}).get("buy_bulk")
        bulk_threshold = spawner_prices.get(item_name, {}).get("bulk_threshold", 256)
        await interaction.response.send_modal(QuantityModal(val, price_str, bulk_price_str, bulk_threshold, self.action_msg))

class SellSpawnerSelect(discord.ui.Select):
    def __init__(self, action_msg: discord.Message = None):
        self.action_msg = action_msg
        options = []
        for name, data in spawner_prices.items():
            if name == "_metadata": continue
            desc = f"Price: {data.get('sell', 'N/A')}"
            thresh = data.get('bulk_threshold', 256)
            if data.get('sell_bulk'):
                desc += f" (if {thresh}+: {data['sell_bulk']})"
            options.append(discord.SelectOption(label=f"Sell {name.capitalize()}", value=f"sell_{name}", description=desc, emoji=data.get('emoji', '📦')))
        if not options:
            options.append(discord.SelectOption(label="No spawners available", value="none"))
        super().__init__(placeholder="Select a spawner to SELL...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("No spawners configured.", ephemeral=True)
            return
        item_name = val.split('_', 1)[1]
        price_str = spawner_prices.get(item_name, {}).get("sell", "0")
        bulk_price_str = spawner_prices.get(item_name, {}).get("sell_bulk")
        bulk_threshold = spawner_prices.get(item_name, {}).get("bulk_threshold", 256)
        await interaction.response.send_modal(QuantityModal(val, price_str, bulk_price_str, bulk_threshold, self.action_msg))

class EphemeralBuyView(discord.ui.View):
    def __init__(self, action_msg: discord.Message = None):
        super().__init__(timeout=300)
        self.add_item(BuySpawnerSelect(action_msg))

class EphemeralSellView(discord.ui.View):
    def __init__(self, action_msg: discord.Message = None):
        super().__init__(timeout=300)
        self.add_item(SellSpawnerSelect(action_msg))

class ActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Buy Spawner", value="buy", description="Buy spawners from the server", emoji="🛒"),
            discord.SelectOption(label="Sell Spawner", value="sell", description="Sell your spawners to the server", emoji="💰")
        ]
        super().__init__(placeholder="What would you like to do?", min_values=1, max_values=1, options=options)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "buy":
            await interaction.response.send_message(content="Please select which spawner you would like to buy:", view=EphemeralBuyView(interaction.message), ephemeral=True)
        else:
            await interaction.response.send_message(content="Please select which spawner you would like to sell:", view=EphemeralSellView(interaction.message), ephemeral=True)

class EphemeralActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ActionSelect())

class SpawnerTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Open a ticket", style=discord.ButtonStyle.success, custom_id="spawner_btn_open", emoji="🎫")
    async def btn_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Select an action:", view=EphemeralActionView(), ephemeral=True)

async def update_spawner_panel(bot: discord.Client):
    meta = spawner_prices.get("_metadata")
    if not meta: return
    channel_id = meta.get("channel_id")
    msg_id = meta.get("message_id")
    if not channel_id: return
    
    channel = bot.get_channel(channel_id)
    if not channel: return
    
    if msg_id:
        try:
            old_msg = await channel.fetch_message(msg_id)
            await old_msg.delete()
        except discord.NotFound:
            pass
            
    desc = "Open a ticket to buy or sell spawners with our staff!\n\n"
    for name, data in spawner_prices.items():
        if name == "_metadata": continue
        emoji = data.get('emoji', '📦')
        thresh = data.get('bulk_threshold', 256)
        
        buy_text = data.get('sell', 'N/A')
        if data.get('sell_bulk'):
            buy_text += f" *(if {thresh}+: {data['sell_bulk']})*"
            
        sell_text = data.get('buy', 'N/A')
        if data.get('buy_bulk'):
            sell_text += f" *(if {thresh}+: {data['buy_bulk']})*"

        desc += f"**{emoji} {name.capitalize()} Spawners**\n"
        desc += f"We Buy: **{buy_text}**\n"
        desc += f"We Sell: **{sell_text}**\n\n"
    
    if len([k for k in spawner_prices if k != "_metadata"]) == 0:
        desc += "*No spawners currently configured.*\n\n"
        
    desc += "> Use the dropdown menus below to open a ticket."

    embed = discord.Embed(
        title="Spawner Trading Station",
        description=desc,
        color=discord.Color.yellow()
    )
    new_msg = await channel.send(embed=embed, view=SpawnerTicketView())
    spawner_prices["_metadata"]["message_id"] = new_msg.id
    save_spawner_prices()




vouch_cooldowns = {}

class VouchLeaderboardView(discord.ui.View):
    def __init__(self, sorted_users):
        super().__init__(timeout=120)
        self.sorted_users = sorted_users
        self.current_page = 0
        self.per_page = 10
        self.max_pages = max(1, (len(self.sorted_users) + self.per_page - 1) // self.per_page)
        self.update_buttons()
        
    def update_buttons(self):
        self.btn_prev.disabled = self.current_page == 0
        self.btn_next.disabled = self.current_page >= self.max_pages - 1

    def generate_embed(self):
        embed = discord.Embed(title="🏆 Server Vouch Leaderboard", description="Top members by vouches!", color=discord.Color.gold())
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_users = self.sorted_users[start_idx:end_idx]
        
        desc = ""
        for i, (uid, data) in enumerate(page_users):
            vouches = data.get("vouches", 0)
            scams = data.get("scam_vouches", 0)
            if vouches > 0 or scams > 0:
                desc += f"**{start_idx + i + 1}.** <@{uid}> - **{vouches}** ✅ | **{scams}** ❌\n"
                
        if not desc:
            desc = "No vouches have been recorded yet."
        embed.description = desc
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
        return embed
        
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        
    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

vouch_group = app_commands.Group(name="vouch", description="Vouch stats and commands")

@vouch_group.command(name="user", description="View vouch stats for a specific member")
@app_commands.describe(user="The user to check stats for")
async def vouchstats_user(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    uid = str(user.id)
    data = vouch_data.get(uid, {"vouches": 0, "scam_vouches": 0})
    embed = discord.Embed(title=f"Vouch Stats for {user.name}", color=discord.Color.blue())
    embed.add_field(name="✅ Positive Vouches", value=str(data["vouches"]), inline=True)
    embed.add_field(name="❌ Scam Vouches", value=str(data["scam_vouches"]), inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.followup.send(embed=embed)

@vouch_group.command(name="stats", description="View the server vouch leaderboard")
async def vouchstats_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    sorted_users = sorted(vouch_data.items(), key=lambda x: x[1].get("vouches", 0), reverse=True)
    sorted_users = [x for x in sorted_users if x[1].get("vouches", 0) > 0 or x[1].get("scam_vouches", 0) > 0]
    
    view = VouchLeaderboardView(sorted_users)
    await interaction.followup.send(embed=view.generate_embed(), view=view)

@vouch_group.command(name="add", description="Submit a custom vouch")
@app_commands.describe(target="The user you are vouching for (optional)")
async def vouch_add_cmd(interaction: discord.Interaction, target: discord.Member = None):
    uid = interaction.user.id
    now = time.time()
    if uid in vouch_cooldowns:
        if now - vouch_cooldowns[uid] < 600:
            remaining = int(600 - (now - vouch_cooldowns[uid]))
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(f"❌ You can use this command again in {minutes}m {seconds}s.", ephemeral=True)
            return
            
    target_id = target.id if target else None
    await interaction.response.send_message(
        "Would you like to leave a positive vouch or a scam vouch?",
        view=VouchView(ticket_type="custom", target_user=target_id),
        ephemeral=True
    )




class GStatsLeaderboardView(discord.ui.View):
    def __init__(self, sorted_wins, sorted_hosts):
        super().__init__(timeout=120)
        self.sorted_wins = sorted_wins
        self.sorted_hosts = sorted_hosts
        self.current_page = 0
        self.per_page = 10
        self.max_pages = max(1, (max(len(self.sorted_wins), len(self.sorted_hosts)) + self.per_page - 1) // self.per_page)
        self.update_buttons()
        
    def update_buttons(self):
        self.btn_prev.disabled = self.current_page == 0
        self.btn_next.disabled = self.current_page >= self.max_pages - 1

    def generate_embed(self):
        embed = discord.Embed(title="🏆 Server Giveaway Leaderboards", color=discord.Color.magenta())
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        
        page_wins = self.sorted_wins[start_idx:end_idx]
        win_desc = ""
        for i, (uid, data) in enumerate(page_wins):
            wins = data["wins"]
            if wins > 0: win_desc += f"**{start_idx + i + 1}.** <@{uid}> - **{wins}** 🎉\n"
        if not win_desc: win_desc = "No winners yet."
        embed.add_field(name="Top Winners", value=win_desc, inline=True)
        
        page_hosts = self.sorted_hosts[start_idx:end_idx]
        host_desc = ""
        for i, (uid, data) in enumerate(page_hosts):
            hosts = data["hosts"]
            if hosts > 0: host_desc += f"**{start_idx + i + 1}.** <@{uid}> - **{hosts}** 👑\n"
        if not host_desc: host_desc = "No hosts yet."
        embed.add_field(name="Top Hosts", value=host_desc, inline=True)
        
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
        return embed
        
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        
    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

gstats_group = app_commands.Group(name="gstats", description="Giveaway stats system")

@gstats_group.command(name="user", description="View giveaway stats for a specific member")
@app_commands.describe(user="The user to check stats for")
async def gstats_user_cmd(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    
    g_stats = {}
    for gw in giveaways.values():
        if gw.get("ended"):
            host = str(gw.get("host_id"))
            if host != "None":
                if host not in g_stats: g_stats[host] = {"wins": 0, "hosts": 0}
                g_stats[host]["hosts"] += 1
            for winner in gw.get("winners_list", []):
                w_id = str(winner)
                if w_id not in g_stats: g_stats[w_id] = {"wins": 0, "hosts": 0}
                g_stats[w_id]["wins"] += 1

    uid = str(user.id)
    data = g_stats.get(uid, {"wins": 0, "hosts": 0})
    embed = discord.Embed(title=f"Giveaway Stats for {user.name}", color=discord.Color.purple())
    embed.add_field(name="🎉 Giveaways Won", value=str(data["wins"]), inline=True)
    embed.add_field(name="👑 Giveaways Hosted", value=str(data["hosts"]), inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.followup.send(embed=embed)

@gstats_group.command(name="stats", description="View the server giveaway leaderboards")
async def gstats_stats_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    
    g_stats = {}
    for gw in giveaways.values():
        if gw.get("ended"):
            host = str(gw.get("host_id"))
            if host != "None":
                if host not in g_stats: g_stats[host] = {"wins": 0, "hosts": 0}
                g_stats[host]["hosts"] += 1
            for winner in gw.get("winners_list", []):
                w_id = str(winner)
                if w_id not in g_stats: g_stats[w_id] = {"wins": 0, "hosts": 0}
                g_stats[w_id]["wins"] += 1

    sorted_by_wins = sorted([x for x in g_stats.items() if x[1]["wins"] > 0], key=lambda x: x[1]["wins"], reverse=True)
    sorted_by_hosts = sorted([x for x in g_stats.items() if x[1]["hosts"] > 0], key=lambda x: x[1]["hosts"], reverse=True)
    
    view = GStatsLeaderboardView(sorted_by_wins, sorted_by_hosts)
    await interaction.followup.send(embed=view.generate_embed(), view=view)



def create_rank_card(username, avatar_bytes, current_xp, next_xp, level, rank):
    width = 900
    height = 250
    img = Image.new("RGBA", (width, height), (35, 39, 42, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.rounded_rectangle([0, 0, width, height], radius=20, fill=(35, 39, 42, 255))
    
    if avatar_bytes:
        try:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((150, 150))
            
            mask = Image.new("L", (150, 150), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, 150, 150), fill=255)
            
            img.paste(avatar, (50, 50), mask)
            
            draw.ellipse((46, 46, 204, 204), outline="white", width=4)
        except Exception:
            pass

    draw.text((230, 60), str(username), font=font, fill="white")
    
    bar_x = 230
    bar_y = 160
    bar_width = 600
    bar_height = 30
    
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], radius=15, fill=(72, 75, 78, 255))
    
    progress = 0
    if next_xp > 0:
        progress = min(current_xp / next_xp, 1.0)
    
    fill_width = int(bar_width * progress)
    if fill_width > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_width, bar_y + bar_height], radius=15, fill="#ffcc00")
        
    draw.text((230, 120), f"Level {level} | Rank #{rank}", font=font_small, fill="white")
    
    xp_text = f"{current_xp} / {next_xp} XP"
    try:
        bbox = draw.textbbox((0,0), xp_text, font=font_small)
        text_w = bbox[2] - bbox[0]
    except:
        text_w = len(xp_text) * 12
    draw.text((bar_x + bar_width - text_w, 120), xp_text, font=font_small, fill="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

@tree.command(name="levels", description="Check your or another member's rank")

async def rank_view_cmd(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    member = member or interaction.user
    guild_id = str(interaction.guild_id)
    user_id = str(member.id)
    
    if guild_id not in levels_data or user_id not in levels_data[guild_id]:
        await interaction.followup.send(f"📉 {member.mention} hasn't earned any XP yet.")
        return
        
    user_data = levels_data[guild_id][user_id]
    current_xp = user_data["xp"]
    level = user_data["level"]
    next_xp = xp_for_level(level)
    
    all_users = sorted(levels_data[guild_id].items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    rank = 1
    for uid, data in all_users:
        if uid == user_id:
            break
        rank += 1
        
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()
            
    loop = asyncio.get_running_loop()
    buffer = await loop.run_in_executor(None, create_rank_card, member.name, avatar_bytes, current_xp, next_xp, level, rank)
    
    file = discord.File(fp=buffer, filename="rank.png")
    await interaction.followup.send(file=file)

    
@tree.command(name="rank", description="View the leveling leaderboard")
async def levels_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = str(interaction.guild_id)
    if guild_id not in levels_data or not levels_data[guild_id]:
        await interaction.followup.send("📉 No XP data found for this server.")
        return
        
    all_users = sorted(levels_data[guild_id].items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    
    embed = discord.Embed(
        title="🏆 Leveling Leaderboard",
        color=discord.Color.teal(),
        timestamp=discord.utils.utcnow()
    )
    
    desc = ""
    for i, (uid, data) in enumerate(all_users[:10]):
        user = interaction.guild.get_member(int(uid))
        user_name = user.mention if user else f"<@{uid}>"
        
        medal = ""
        if i == 0: medal = "🥇 "
        elif i == 1: medal = "🥈 "
        elif i == 2: medal = "🥉 "
        
        desc += f"**{i+1}.** {medal}{user_name} - **Lvl {data['level']}** ({data['xp']} XP)\n"
        
    embed.description = desc
    await interaction.followup.send(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
        
    if await process_word_filter(message):
        return
        
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    
    if guild_id not in levels_data:
        levels_data[guild_id] = {}
        
    user_data = levels_data[guild_id].get(user_id, {"xp": 0, "level": 1, "last_message": 0})
    
    now = time.time()
    if now - user_data["last_message"] >= 60:
        user_data["xp"] += random.randint(15, 25)
        user_data["last_message"] = now
        
        req_xp = xp_for_level(user_data["level"])
        leveled_up = False
        
        while user_data["xp"] >= req_xp:
            user_data["xp"] -= req_xp
            user_data["level"] += 1
            leveled_up = True
            req_xp = xp_for_level(user_data["level"])
            
        if leveled_up:
            level_role_name = f"Level {user_data['level']}"
            role = discord.utils.get(message.guild.roles, name=level_role_name)
            if role:
                try:
                    await message.author.add_roles(role)
                except Exception:
                    pass
            
            lvl = user_data["level"]
            ch_id = server_config.get(guild_id, {}).get("levelup_channel")
            ch = message.guild.get_channel(int(ch_id)) if ch_id else None
            
            if lvl % 5 == 0 and ch:
                try:
                    avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
                    async with aiohttp.ClientSession() as session:
                        async with session.get(avatar_url) as resp:
                            avatar_bytes = await resp.read()
                    
                    next_xp = xp_for_level(lvl)
                    all_users = sorted(levels_data[guild_id].items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
                    rank = 1
                    for uid, data in all_users:
                        if uid == user_id: break
                        rank += 1
                        
                    loop = asyncio.get_running_loop()
                    buffer = await loop.run_in_executor(None, create_rank_card, message.author.name, avatar_bytes, 0, next_xp, lvl, rank)
                    file = discord.File(fp=buffer, filename="levelup.png")
                    await ch.send(f"🎉 Huge congratulations to {message.author.mention} for hitting **Level {lvl}**!", file=file)
                except Exception as e:
                    print(f"Failed to send level up image: {e}")
            else:
                try:
                    await message.channel.send(f"🎉 Congratulations {message.author.mention}, you advanced to **Level {user_data['level']}**!")
                except discord.Forbidden:
                    pass
                
    levels_data[guild_id][user_id] = user_data
    save_levels_data()

# ── Moderation System ─────────────────────────────────────────────────────────

slowmode_group = app_commands.Group(name="slowmode", description="Slowmode commands")
tree.add_command(slowmode_group)

@slowmode_group.command(name="set", description="Set a slowmode delay in the current channel")
@app_commands.describe(seconds="The slowmode delay in seconds (0 to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slowmode_set_cmd(interaction: discord.Interaction, seconds: int):
    if seconds < 0 or seconds > 21600:
        await interaction.response.send_message("❌ Slowmode must be between 0 and 21600 seconds (6 hours).", ephemeral=True)
        return
        
    try:
        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message("✅ Slowmode has been disabled.")
        else:
            await interaction.response.send_message(f"✅ Slowmode set to **{seconds} seconds**.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I do not have permission to manage this channel.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

@slowmode_group.command(name="remove", description="Remove slowmode from the current channel")
@app_commands.default_permissions(manage_channels=True)
async def slowmode_remove_cmd(interaction: discord.Interaction):
    try:
        await interaction.channel.edit(slowmode_delay=0)
        await interaction.response.send_message("✅ Slowmode has been removed.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I do not have permission to manage this channel.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

import json
import os
BANNED_WORDS_FILE = "data/banned_words.json"
def load_banned_words():
    if os.path.exists(BANNED_WORDS_FILE):
        try:
            with open(BANNED_WORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

banned_word_patterns = load_banned_words()

async def process_word_filter(message: discord.Message):
    if message.author.bot:
        return False
        
    content_lower = message.content.lower()
    content_nospaces = content_lower.replace(" ", "")
    
    for pattern in banned_word_patterns:
        try:
            if re.search(pattern, content_lower) or re.search(pattern, content_nospaces):
                await message.delete()
                
                try:
                    duration = datetime.timedelta(hours=1)
                    await message.author.timeout(duration, reason="Automod: Banned word detected")
                    await message.channel.send(f"⚠️ {message.author.mention} has been timed out for 1 hour for using a banned word.")
                    
                    try:
                        await message.author.send(f"You were timed out in **{message.guild.name}** for 1 hour for using a banned word. \nYour message: ||{message.content}||")
                    except:
                        pass
                except discord.Forbidden:
                    await message.channel.send(f"⚠️ Detected a banned word from {message.author.mention} but I don't have permission to time them out!")
                    
                return True
        except Exception as e:
            print(f"Regex error with pattern {pattern}: {e}")
            
    return False

# -------------------------------------------------------------------

@bot.event
async def on_ready():
    tree.add_command(vouch_group)
    tree.add_command(application_group)
    tree.add_command(filter_group)
    tree.add_command(gstats_group)
    print(f"Logged in as {bot.user}")
    load_giveaways()
    load_spawner_prices()
    load_server_config()
    load_vouch_data()
    load_tiktok_data()
    load_applications_data()
    load_levels_data()
    print(f"Loaded {len(giveaways)} giveaway(s).")
    
    if not update_stats_task.is_running():
        update_stats_task.start()
    if not update_partnership_panels.is_running():
        update_partnership_panels.start()
    if not check_tiktok_live.is_running():
        check_tiktok_live.start()

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="Doing bot stuff")
    )

    # Add TicketPanel views globally
    bot.add_view(TicketButton())
    bot.add_view(PartnershipTicketButton())
    bot.add_view(BanAppealTicketButton())
    bot.add_view(BanAppealCloseView())
    bot.add_view(SchematicTicketButton())
    bot.add_view(GenericCloseButton())
    bot.add_view(SpawnerControlView())
    bot.add_view(SpawnerTicketView())
    bot.add_view(GwCloseTicketView())
    bot.add_view(ApplicationReviewView())
    bot.add_view(StaffApplicationButton())

    for msg_id, gw in giveaways.items():
        if not gw.get('ended'):
            view = GiveawayView(msg_id)
            bot.add_view(view)
        else:
            winners = gw.get('winners_list', set())
            if not winners:
                continue
            if gw.get('reroll_performed') or not gw.get('reroll_button_added'):
                view = ClaimView(msg_id, winners)
                for child in view.children:
                    if hasattr(child, 'winner_id') and child.winner_id in gw.get('claimed', set()):
                        child.disabled = True
                        child.label = "Claimed"
                        child.style = discord.ButtonStyle.secondary
            else:
                view = discord.ui.View(timeout=None)
                for wid in winners:
                    btn = ClaimPrizeButton(msg_id, wid)
                    if wid in gw.get('claimed', set()):
                        btn.disabled = True
                        btn.label = "Claimed"
                        btn.style = discord.ButtonStyle.secondary
                    view.add_item(btn)
                view.add_item(RerollButton(msg_id))
            bot.add_view(view)

    bot.loop.create_task(main_loop())

    try:
        await tree.sync()
        print("Slash commands synced globally.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")



async def generate_welcome_image(member: discord.Member, count: int) -> discord.File:
    width, height = 800, 250
    
    # 1. Fetch Avatar First
    avatar_url = member.display_avatar.with_size(128).url
    av_img = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    av_bytes = await resp.read()
                    av_img = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
    except Exception as e:
        print(f"Failed to fetch avatar: {e}")

    # 2. Determine Background Color
    bg_color = (255, 215, 0, 255) # Fallback Yellow
    if av_img:
        try:
            # Resize to 1x1 to get average color
            avg_color = av_img.resize((1, 1)).getpixel((0, 0))
            bg_color = avg_color
        except:
            pass

    # 3. Create Base Image
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 4. Draw Rounded Background
    draw.rounded_rectangle([10, 10, width-10, height-10], radius=15, fill=bg_color, outline=(255, 255, 255), width=5)
    
    # 5. Draw Avatar
    if av_img:
        av_img = av_img.resize((150, 150))
        # Make avatar circular
        mask = Image.new("L", (150, 150), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 150, 150), fill=255)
        av_img.putalpha(mask)
        img.alpha_composite(av_img, (50, 50))

    # 6. Text Rendering
    try:
        font_large = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 36)
        font_small = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 28)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    text_color = (255, 255, 255)
    shadow_color = (0, 0, 0)
    
    # Text strings
    t1 = f"Welcome {member.name}"
    suffix = 'st' if str(count).endswith('1') and not str(count).endswith('11') else 'nd' if str(count).endswith('2') and not str(count).endswith('12') else 'rd' if str(count).endswith('3') and not str(count).endswith('13') else 'th'
    t2 = f"to {member.guild.name} you are the {count}{suffix} member!"
    
    # Draw text with outline (stroke)
    draw.text((250, 80), t1, font=font_large, fill=text_color, stroke_width=2, stroke_fill=shadow_color)
    draw.text((250, 130), t2, font=font_small, fill=text_color, stroke_width=2, stroke_fill=shadow_color)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="welcome.png")

async def update_server_stats(guild: discord.Guild):
    guild_id = str(guild.id)
    if guild_id not in server_config: return
    cfg = server_config[guild_id]
    
    all_members = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    members = all_members - bots
    
    try:
        if "stats_all" in cfg:
            c = guild.get_channel(cfg["stats_all"])
            if c: await c.edit(name=f"All Members: {all_members}")
        if "stats_members" in cfg:
            c = guild.get_channel(cfg["stats_members"])
            if c: await c.edit(name=f"Members: {members}")
        if "stats_bots" in cfg:
            c = guild.get_channel(cfg["stats_bots"])
            if c: await c.edit(name=f"Bots: {bots}")
    except Exception as e:
        print(f"Error updating stats channels: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    guild_id = str(member.guild.id)
    if guild_id in server_config and "welcome_channel" in server_config[guild_id]:
        channel = member.guild.get_channel(server_config[guild_id]["welcome_channel"])
        if channel:
            try:
                count = member.guild.member_count
                suffix = 'st' if str(count).endswith('1') and not str(count).endswith('11') else 'nd' if str(count).endswith('2') and not str(count).endswith('12') else 'rd' if str(count).endswith('3') and not str(count).endswith('13') else 'th'
                file = await generate_welcome_image(member, count)
                
                msg_content = f"Welcome {member.mention} to **{member.guild.name}**! You are the {count}{suffix} member!"
                embed = discord.Embed(color=0x2b2d31)
                embed.set_image(url="attachment://welcome.png")
                
                await channel.send(content=msg_content, embed=embed, file=file)
                
                # Send DM
                try:
                    await member.send(f"Welcome {member.mention} to **{member.guild.name}**! You are the {count}{suffix} member!")
                except discord.Forbidden:
                    pass
            except Exception as e:
                print(f"Error sending welcome message: {e}")

@bot.event
async def on_member_remove(member: discord.Member):
    pass

@tasks.loop(hours=24)
async def update_partnership_panels():
    for guild_id_str, config in server_config.items():
        panel_ch = config.get("partnership_panel_channel")
        panel_msg = config.get("partnership_panel_message")
        if panel_ch and panel_msg:
            try:
                guild = bot.get_guild(int(guild_id_str))
                if not guild: continue
                channel = guild.get_channel(int(panel_ch))
                if not channel: continue
                message = await channel.fetch_message(int(panel_msg))
                
                new_desc = await generate_partnership_requirements(guild)
                embed = discord.Embed(
                    title="🤝 Partnership Requirements",
                    description=new_desc,
                    color=discord.Color.brand_green()
                )
                embed.set_footer(text="Updated automatically by AI every 24 hours")
                await message.edit(embed=embed)
            except Exception as e:
                print(f"Error updating partnership panel for guild {guild_id_str}: {e}")

@update_partnership_panels.before_loop
async def before_update_partnership_panels():
    await bot.wait_until_ready()

# ── Staff Applications ────────────────────────────────────────────────────────

application_group = app_commands.Group(name="application", description="Manage staff applications", default_permissions=discord.Permissions(administrator=True))

filter_group = app_commands.Group(name="filter", description="Manage the banned words filter", default_permissions=discord.Permissions(administrator=True))

@filter_group.command(name="list", description="List all banned word patterns")
async def filter_list_cmd(interaction: discord.Interaction):
    global banned_word_patterns
    if not banned_word_patterns:
        await interaction.response.send_message("There are currently no banned words.", ephemeral=True)
        return
        
    embed = discord.Embed(title="Banned Word Patterns", color=discord.Color.red())
    
    chunks = []
    current_chunk = ""
    for i, pattern in enumerate(banned_word_patterns):
        line = f"`{i}`: {pattern}\n"
        if len(current_chunk) + len(line) > 1000:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += line
    if current_chunk:
        chunks.append(current_chunk)
        
    for i, chunk in enumerate(chunks):
        embed.add_field(name=f"Patterns (Part {i+1})", value=chunk, inline=False)
        
    await interaction.response.send_message(embed=embed, ephemeral=True)

@filter_group.command(name="add", description="Add a new banned word pattern")
@app_commands.describe(word="The word to ban (will be automatically formatted to catch bypasses)")
async def filter_add_cmd(interaction: discord.Interaction, word: str):
    global banned_word_patterns
    import json
    if word.isalnum():
        pattern = r"\s*".join(list(word.lower()))
    else:
        pattern = word.lower()
        
    if pattern in banned_word_patterns:
        await interaction.response.send_message(f"❌ Pattern `{pattern}` is already banned.", ephemeral=True)
        return
        
    banned_word_patterns.append(pattern)
    
    try:
        with open(BANNED_WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(banned_word_patterns, f, indent=2)
        await interaction.response.send_message(f"✅ Successfully added banned pattern: `{pattern}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to save to file: {e}", ephemeral=True)

@filter_group.command(name="remove", description="Remove a banned word pattern by index")
@app_commands.describe(index="The index number from /filter list")
async def filter_remove_cmd(interaction: discord.Interaction, index: int):
    global banned_word_patterns
    import json
    if index < 0 or index >= len(banned_word_patterns):
        await interaction.response.send_message(f"❌ Invalid index. Use `/filter list` to see valid indices.", ephemeral=True)
        return
        
    removed = banned_word_patterns.pop(index)
    
    try:
        with open(BANNED_WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(banned_word_patterns, f, indent=2)
        await interaction.response.send_message(f"✅ Successfully removed banned pattern: `{removed}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to save to file: {e}", ephemeral=True)


class ApplicationConfigModal(discord.ui.Modal):
    def __init__(self, position_name: str, role_id: int):
        super().__init__(title=f"Questions for {position_name[:30]}")
        self.position_name = position_name
        self.role_id = role_id
        
        self.q1 = discord.ui.TextInput(label="Question 1", required=True)
        self.q2 = discord.ui.TextInput(label="Question 2", required=False)
        self.q3 = discord.ui.TextInput(label="Question 3", required=False)
        self.q4 = discord.ui.TextInput(label="Question 4", required=False)
        self.q5 = discord.ui.TextInput(label="Question 5", required=False)
        
        for q in [self.q1, self.q2, self.q3, self.q4, self.q5]:
            self.add_item(q)

    async def on_submit(self, interaction: discord.Interaction):
        questions = [q.value.strip() for q in [self.q1, self.q2, self.q3, self.q4, self.q5] if q.value.strip()]
        
        guild_id = str(interaction.guild_id)
        if guild_id not in applications_data:
            applications_data[guild_id] = {}
            
        applications_data[guild_id][self.position_name] = {
            "role_id": self.role_id,
            "questions": questions
        }
        save_applications_data()
        await interaction.response.send_message(f"✅ Application for **{self.position_name}** has been saved with {len(questions)} questions.", ephemeral=True)

@application_group.command(name="add", description="Add a new staff application position")
async def app_add(interaction: discord.Interaction, position_name: str, role: discord.Role):
    await interaction.response.send_modal(ApplicationConfigModal(position_name, role.id))

@application_group.command(name="remove", description="Remove a staff application position")
async def app_remove(interaction: discord.Interaction, position_name: str):
    guild_id = str(interaction.guild_id)
    if guild_id in applications_data and position_name in applications_data[guild_id]:
        del applications_data[guild_id][position_name]
        save_applications_data()
        await interaction.response.send_message(f"✅ Removed position **{position_name}**.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Position not found.", ephemeral=True)

@application_group.command(name="list", description="List all staff application positions")
async def app_list(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    if guild_id not in applications_data or not applications_data[guild_id]:
        await interaction.response.send_message("No positions available.", ephemeral=True)
        return
        
    desc = ""
    for pos, data in applications_data[guild_id].items():
        desc += f"**{pos}** - <@&{data['role_id']}> ({len(data['questions'])} questions)\n"
    await interaction.response.send_message(embed=discord.Embed(title="Staff Positions", description=desc, color=discord.Color.blue()), ephemeral=True)


class ApplicationReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="app_approve", emoji="✅")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You do not have permission to review applications.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text
        try:
            uid = int(footer.split("User ID: ")[1])
        except (IndexError, ValueError):
            await interaction.response.send_message("❌ Could not parse User ID from footer.", ephemeral=True)
            return

        member = interaction.guild.get_member(uid)
        
        pos_name = embed.title.replace("New Application: ", "")
        guild_id = str(interaction.guild_id)
        role_id = None
        if guild_id in applications_data and pos_name in applications_data[guild_id]:
            role_id = applications_data[guild_id][pos_name].get("role_id")

        if member and role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except Exception as e:
                    print(f"Failed to add role: {e}")

        if member:
            try:
                succ_embed = discord.Embed(title="✅ Application Approved", description=f"Congratulations! Your application for **{pos_name}** has been approved.", color=discord.Color.green())
                await member.send(embed=succ_embed)
            except Exception:
                pass

        embed.color = discord.Color.green()
        embed.title = f"✅ APPROVED: {pos_name}"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="app_deny", emoji="❌")
    async def deny_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You do not have permission to review applications.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        footer = embed.footer.text
        try:
            uid = int(footer.split("User ID: ")[1])
        except (IndexError, ValueError):
            await interaction.response.send_message("❌ Could not parse User ID from footer.", ephemeral=True)
            return

        member = interaction.guild.get_member(uid)
        pos_name = embed.title.replace("New Application: ", "")

        if member:
            try:
                err_embed = discord.Embed(title="❌ Application Denied", description=f"Unfortunately, your application for **{pos_name}** has been denied.", color=discord.Color.red())
                await member.send(embed=err_embed)
            except Exception:
                pass

        embed.color = discord.Color.red()
        embed.title = f"❌ DENIED: {pos_name}"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

class StaffApplicationButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Apply for Staff", style=discord.ButtonStyle.primary, custom_id="staff_app_button", emoji="📋")
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild_id)
        if guild_id not in applications_data or not applications_data[guild_id]:
            await interaction.response.send_message("There are no open staff positions at the moment.", ephemeral=True)
            return
            
        options = []
        for pos in applications_data[guild_id].keys():
            options.append(discord.SelectOption(label=pos, value=pos))
            
        select = discord.ui.Select(placeholder="Choose a position to apply for...", options=options)
        
        async def select_callback(inter: discord.Interaction):
            pos_name = select.values[0]
            data = applications_data[guild_id][pos_name]
            questions = data["questions"]
            
            await inter.response.send_message(f"✅ I have sent you a DM to start your application for **{pos_name}**!", ephemeral=True)
            
            try:
                dm_channel = await inter.user.create_dm()
                start_embed = discord.Embed(title=f"📋 Application: {pos_name}", description=f"There are {len(questions)} questions. Type your answer to each and send it.\n*(Type `cancel` at any time to abort)*", color=discord.Color.blue())
                await dm_channel.send(embed=start_embed)
            except discord.Forbidden:
                await inter.followup.send("❌ I could not DM you! Please enable DMs from server members.", ephemeral=True)
                return

            answers = []
            def check(m):
                return m.author.id == inter.user.id and m.channel.id == dm_channel.id

            for i, q in enumerate(questions):
                q_embed = discord.Embed(title=f"Question {i+1}/{len(questions)}", description=q, color=discord.Color.gold())
                await dm_channel.send(embed=q_embed)
                try:
                    import asyncio
                    msg = await bot.wait_for('message', check=check, timeout=3600.0)
                except asyncio.TimeoutError:
                    err_embed = discord.Embed(title="⏱️ Timeout", description="Application timed out after 1 hour. Please try again later.", color=discord.Color.red())
                    await dm_channel.send(embed=err_embed)
                    return
                
                if msg.content.lower() == 'cancel':
                    cancel_embed = discord.Embed(title="🛑 Cancelled", description="Application has been cancelled.", color=discord.Color.red())
                    await dm_channel.send(embed=cancel_embed)
                    return
                    
                answers.append(msg.content)
                
            ch_id = server_config.get(guild_id, {}).get("staff_apps_channel")
            if not ch_id and APPLICATION_REVIEW_CHANNEL_ID:
                ch_id = APPLICATION_REVIEW_CHANNEL_ID
                
            if not ch_id:
                err_embed = discord.Embed(title="❌ Error", description="The server's staff application review channel is not set. Your application could not be submitted.", color=discord.Color.red())
                await dm_channel.send(embed=err_embed)
                return
                
            review_channel = inter.guild.get_channel(int(ch_id))
            if not review_channel:
                err_embed = discord.Embed(title="❌ Error", description="The server's staff application review channel was not found.", color=discord.Color.red())
                await dm_channel.send(embed=err_embed)
                return
                
            embed = discord.Embed(title=f"New Application: {pos_name}", color=discord.Color.gold())
            embed.set_author(name=inter.user.name, icon_url=inter.user.avatar.url if inter.user.avatar else inter.user.default_avatar.url)
            
            for i, q in enumerate(questions):
                embed.add_field(name=q, value=answers[i], inline=False)
                
            embed.set_footer(text=f"User ID: {inter.user.id}")
            
            await review_channel.send(embed=embed, view=ApplicationReviewView())
            succ_embed = discord.Embed(title="✅ Submitted", description="Your application has been successfully submitted! The staff team will review it shortly.", color=discord.Color.green())
            await dm_channel.send(embed=succ_embed)
            
        select.callback = select_callback
        view = discord.ui.View(timeout=120)
        view.add_item(select)
        await interaction.response.send_message("Select the position you want to apply for:", view=view, ephemeral=True)

@tasks.loop(minutes=1.0)
async def check_tiktok_live():
    for guild_id_str, trackers in tiktok_data.items():
        for username, tracker_info in trackers.items():
            channel_id = tracker_info["channel_id"]
    save_tiktok_data()

@check_tiktok_live.before_loop
async def before_check_tiktok_live():
    await bot.wait_until_ready()

# -------------------------------------------------------------------
@tasks.loop(minutes=5.5)
async def update_stats_task():
    for guild_id_str in server_config.keys():
        try:
            guild = bot.get_guild(int(guild_id_str))
            if guild:
                await update_server_stats(guild)
        except Exception as e:
            print(f"Error in update_stats_task for guild {guild_id_str}: {e}")

@update_stats_task.before_loop
async def before_update_stats_task():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if TOKEN is None:
        raise ValueError("No DISCORD_TOKEN found in .env")
    bot.run(TOKEN)
