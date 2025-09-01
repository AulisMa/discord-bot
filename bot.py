import discord
from discord.ext import commands
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Channel IDs
COUNTING_CHANNEL_ID = # discord channel id here
ANIMAL_GAME_CHANNEL_ID = # discord channel id here
COMPOUND_GAME_CHANNEL_ID = # discord channel id here

# State
last_number = 0
last_user_id = None
last_animal_user_id = None
last_compound_user_id = None

used_animals = set()
user_animals = {}

used_compounds = set()
user_compounds = {}

# Whitelist and admin
WHITELISTED_USER_IDS = {placeholder} # <- user id here
ADMIN_ROLE_ID = user id here


def is_admin(ctx):
    return any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await detect_latest_count()
    await detect_used_animals()
    await detect_used_compounds()


# ------------------ Counting Game ------------------

async def detect_latest_count():
    global last_number, last_user_id
    channel = bot.get_channel(COUNTING_CHANNEL_ID)
    if not channel:
        print("❌ Counting channel not found.")
        return

    async for message in channel.history(limit=25, oldest_first=False):
        if message.author.bot:
            continue
        content = message.content.strip()
        if content.isdigit():
            last_number = int(content)
            last_user_id = message.author.id
            print(f"🔍 Starting count from {last_number} by {message.author}")
            return
    print("ℹ️ No valid numbers found.")


# ------------------ Word Games: Animal & Compound ------------------

async def detect_used_animals():
    channel = bot.get_channel(ANIMAL_GAME_CHANNEL_ID)
    if not channel:
        print("❌ Animal game channel not found.")
        return

    async for message in channel.history(limit=100, oldest_first=True):
        if message.author.bot:
            continue
        content = message.content.strip().lower()
        if content and message.author.id not in user_animals and content not in used_animals:
            user_animals[message.author.id] = content
            used_animals.add(content)
    print(f"🦁 Animal game initialized with {len(used_animals)} animals.")


async def detect_used_compounds():
    channel = bot.get_channel(COMPOUND_GAME_CHANNEL_ID)
    if not channel:
        print("❌ Compound game channel not found.")
        return

    async for message in channel.history(limit=100, oldest_first=True):
        if message.author.bot:
            continue
        content = message.content.strip().lower()
        if content and message.author.id not in user_compounds and content not in used_compounds:
            user_compounds[message.author.id] = content
            used_compounds.add(content)
    print(f"🧩 Compound game initialized with {len(used_compounds)} words.")


# ------------------ Message Handlers ------------------

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    global last_number, last_user_id, last_animal_user_id, last_compound_user_id

    if message.author.bot:
        return
    content = message.content.strip().lower()
    user_id = message.author.id

    # 🐾 Animal Game
    if message.channel.id == ANIMAL_GAME_CHANNEL_ID:
        if content in used_animals:
            await message.delete()
            return

        if user_id == last_animal_user_id:
            recent_users = list(user_animals.keys())
            if len(recent_users) >= 1 and recent_users[-1] == user_id:
                await message.delete()
                return

        user_animals[user_id] = content
        used_animals.add(content)
        last_animal_user_id = user_id
        return

    # 🧩 Compound Word Game
    if message.channel.id == COMPOUND_GAME_CHANNEL_ID:
        if content in used_compounds:
            await message.delete()
            return

        if user_id == last_compound_user_id:
            recent_users = list(user_compounds.keys())
            if len(recent_users) >= 1 and recent_users[-1] == user_id:
                await message.delete()
                return

        user_compounds[user_id] = content
        used_compounds.add(content)
        last_compound_user_id = user_id
        return

    # 🔢 Counting Game
    if message.channel.id == COUNTING_CHANNEL_ID:
        if message.author.id in WHITELISTED_USER_IDS and not content.isdigit():
            return
        if not content.isdigit():
            await message.delete()
            return

        number = int(content)
        if message.author.id == last_user_id or number != last_number + 1:
            await message.delete()
            return

        last_number = number
        last_user_id = message.author.id


@bot.event
async def on_message_delete(message):
    global last_animal_user_id, last_compound_user_id
    if message.author.bot:
        return
    content = message.content.strip().lower()
    user_id = message.author.id

    if message.channel.id == ANIMAL_GAME_CHANNEL_ID:
        if user_animals.get(user_id) == content:
            used_animals.discard(content)
            del user_animals[user_id]
            if last_animal_user_id == user_id:
                last_animal_user_id = None
            print(f"❌ Animal deleted: {content} by {user_id}")

    if message.channel.id == COMPOUND_GAME_CHANNEL_ID:
        if user_compounds.get(user_id) == content:
            used_compounds.discard(content)
            del user_compounds[user_id]
            if last_compound_user_id == user_id:
                last_compound_user_id = None
            print(f"❌ Compound deleted: {content} by {user_id}")


# ------------------ Admin Commands ------------------

@bot.command(name="reset")
@commands.has_role(ADMIN_ROLE_ID)
async def reset_count(ctx, number: int):
    global last_number, last_user_id
    last_number = number
    last_user_id = None
    await ctx.send(f"🔄 Count reset to {number}")


@bot.command(name="whitelist")
@commands.has_role(ADMIN_ROLE_ID)
async def show_whitelist(ctx):
    if not WHITELISTED_USER_IDS:
        await ctx.send("⚠️ Whitelist is currently empty.")
        return
    members = []
    for uid in WHITELISTED_USER_IDS:
        member = ctx.guild.get_member(uid)
        members.append(member.name if member else f"User ID: {uid}")
    await ctx.send("✅ Whitelisted users:\n" + "\n".join(members))


@bot.command(name="setwhitelist")
@commands.has_role(ADMIN_ROLE_ID)
async def modify_whitelist(ctx, action: str, user_id: int):
    action = action.lower()
    if action == "add":
        WHITELISTED_USER_IDS.add(user_id)
        await ctx.send(f"✅ Added user ID `{user_id}` to whitelist.")
    elif action == "remove":
        WHITELISTED_USER_IDS.discard(user_id)
        await ctx.send(f"✅ Removed user ID `{user_id}` from whitelist.")
    else:
        await ctx.send("⚠️ Use `add` or `remove`.")


# ------------------ Keep-Alive Server ------------------

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running!')


def run_dummy_server():
    server = HTTPServer(('0.0.0.0', 8080), KeepAliveHandler)
    server.serve_forever()


threading.Thread(target=run_dummy_server).start()

# ------------------ Run Bot ------------------

bot.run(os.getenv("TOKEN"))