import os
import io
import random
import string
from datetime import datetime, timedelta
from threading import Lock
import sqlite3

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

# ─── SQLITE SETUP ────────────────────────────────────────────────────────
DB_PATH = os.getenv("SQLITE_DB_PATH", "senticord.db")
_conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
_lock   = Lock()
_cursor = _conn.cursor()

_cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_captchas (
  member_id TEXT PRIMARY KEY,
  guild_id  TEXT,
  code      TEXT,
  attempts  INTEGER,
  created   TEXT
);
""" )
_cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id    TEXT PRIMARY KEY,
  admin_role  TEXT,
  log_channel TEXT
);
""" )
_conn.commit()

# Utility functions: pending & settings
# ... (same as original get_pending, set_pending, etc.)
from utils import get_pending, set_pending, update_attempts, delete_pending, get_settings, set_settings

# ─── CONFIG ─────────────────────────────────────────────────────────────
DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
TIMEOUT_MINUTES = int(os.getenv("CAPTCHA_TIMEOUT_MIN", "20"))
MAX_ATTEMPTS    = int(os.getenv("CAPTCHA_MAX_ATTEMPTS", "2"))
TIMEOUT         = timedelta(minutes=TIMEOUT_MINUTES)

# ─── BOT SETUP ───────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ─── CAPTCHA HELPERS ─────────────────────────────────────────────────────
def gen_code(n=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))

def make_captcha(text):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    img  = Image.new("RGB", (200, 80), (255, 255, 255))
    d    = ImageDraw.Draw(img)
    for i, ch in enumerate(text):
        d.text((10 + i*30, random.randint(5, 25)), ch, font=font, fill=(0, 0, 0))
    for _ in range(100):
        d.point((random.randint(0, 199), random.randint(0, 79)), fill=(0,0,0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

async def log_action(guild_id, msg):
    cfg = get_settings(str(guild_id))
    ch  = cfg.get("log_channel")
    if ch:
        c = bot.get_channel(int(ch))
        if c:
            await c.send(msg)

# ─── DYNAMIC COMMAND LOADING ────────────────────────────────────────────
import glob

def load_commands():
    for file in glob.glob("./commands/*.py"):
        name = os.path.basename(file)[:-3]
        if name == "__init__": continue
        module = __import__(f"commands.{name}", fromlist=["setup"])
        bot.loop.create_task(module.setup(bot))

@bot.event
async def on_ready():
    load_commands()
    await tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# ─── DM-CAPTCHA FLOW & EVENTS in commands/captcha.py ────────────────────
# on_member_join & on_message handlers are moved into captcha.py Cog

# ─── PROCESS OTHER COMMANDS ────────────────────────────────────────────
@bot.event
async def on_message(msg):
    await bot.process_commands(msg)

# ─── RUN BOT ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)