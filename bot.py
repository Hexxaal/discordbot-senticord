import os, io, random, string, sqlite3, glob
from datetime import datetime, timedelta
from threading import Lock

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

# ─── SQLITE SETUP & UTILITIES ─────────────────────────────────────────
DB_PATH = os.getenv("SQLITE_DB_PATH", "senticord.db")
_conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
_lock   = Lock()
_cursor = _conn.cursor()

# (create tables here… same as before)

from utils import (
    get_pending, set_pending, update_attempts,
    delete_pending, get_settings, set_settings
)

# ─── CONFIG ──────────────────────────────────────────────────────────
DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
TIMEOUT_MINUTES = int(os.getenv("CAPTCHA_TIMEOUT_MIN", "20"))
MAX_ATTEMPTS    = int(os.getenv("CAPTCHA_MAX_ATTEMPTS", "2"))
TIMEOUT         = timedelta(minutes=TIMEOUT_MINUTES)

# ─── BOT SETUP ───────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ─── HELPERS ────────────────────────────────────────────────────────
def gen_code(n=6):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def make_captcha(text):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    img  = Image.new("RGB", (200, 80), (255,255,255))
    d    = ImageDraw.Draw(img)
    for i,ch in enumerate(text):
        d.text((10+i*30, random.randint(5,25)), ch, font=font, fill=(0,0,0))
    for _ in range(100):
        d.point((random.randint(0,199), random.randint(0,79)), fill=(0,0,0))
    buf = io.BytesIO()
    img.save(buf, "PNG"); buf.seek(0)
    return buf

async def log_action(guild_id, msg):
    cfg = get_settings(str(guild_id))
    ch  = cfg.get("log_channel")
    if ch:
        c = bot.get_channel(int(ch))
        if c: await c.send(msg)

# ─── DYNAMIC COMMAND LOADING ────────────────────────────────────────
async def load_commands():
    for file in glob.glob("./commands/*.py"):
        name = os.path.basename(file)[:-3]
        if name == "__init__": continue
        module = __import__(f"commands.{name}", fromlist=["setup"])
        if hasattr(module, "setup"):
            await module.setup(bot)

# ─── EVENTS ────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # 1) load all your commands & cogs
    await load_commands()

    # 2) then sync the tree (so slash-commands actually register)
    await tree.sync()

    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands loaded:", [c.name for c in tree.get_commands()])

@bot.event
async def on_message(msg):
    await bot.process_commands(msg)

# ─── RUN ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
