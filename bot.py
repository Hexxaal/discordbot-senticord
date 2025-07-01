import os
import io
import random
import string
from datetime import datetime, timedelta
from threading import Thread, Lock
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
""")

_cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id    TEXT PRIMARY KEY,
  admin_role  TEXT,
  log_channel TEXT
);
""")
_conn.commit()

def get_pending(member_id):
    _cursor.execute(
        "SELECT guild_id,code,attempts,created FROM pending_captchas WHERE member_id=?",
        (member_id,)
    )
    row = _cursor.fetchone()
    if not row:
        return None
    guild_id, code, attempts, created = row
    return {
        "guild_id": guild_id,
        "code": code,
        "attempts": attempts,
        "created": datetime.fromisoformat(created)
    }

def set_pending(member_id, guild_id, code):
    now = datetime.utcnow().isoformat()
    with _lock:
        _cursor.execute("""
            INSERT OR REPLACE INTO pending_captchas(member_id,guild_id,code,attempts,created)
            VALUES(?,?,?,?,?)
        """, (member_id, guild_id, code, 0, now))
        _conn.commit()

def update_attempts(member_id, attempts):
    with _lock:
        _cursor.execute(
            "UPDATE pending_captchas SET attempts=? WHERE member_id=?",
            (attempts, member_id)
        )
        _conn.commit()

def delete_pending(member_id):
    with _lock:
        _cursor.execute(
            "DELETE FROM pending_captchas WHERE member_id=?",
            (member_id,)
        )
        _conn.commit()

def get_settings(guild_id):
    _cursor.execute(
        "SELECT admin_role, log_channel FROM guild_settings WHERE guild_id=?",
        (guild_id,)
    )
    row = _cursor.fetchone()
    return {"admin_role": row[0], "log_channel": row[1]} if row else {}

def set_settings(guild_id, admin_role=None, log_channel=None):
    existing = get_settings(guild_id)
    ar = admin_role  if admin_role  is not None else existing.get("admin_role")
    lc = log_channel if log_channel is not None else existing.get("log_channel")
    with _lock:
        if existing:
            _cursor.execute(
                "UPDATE guild_settings SET admin_role=?, log_channel=? WHERE guild_id=?",
                (ar, lc, guild_id)
            )
        else:
            _cursor.execute(
                "INSERT INTO guild_settings(guild_id,admin_role,log_channel) VALUES(?,?,?)",
                (guild_id, ar, lc)
            )
        _conn.commit()

# ─── CONFIG ─────────────────────────────────────────────────────────────
DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN")
TIMEOUT_MINUTES     = int(os.getenv("CAPTCHA_TIMEOUT_MIN", "20"))
MAX_ATTEMPTS        = int(os.getenv("CAPTCHA_MAX_ATTEMPTS", "2"))
TIMEOUT             = timedelta(minutes=TIMEOUT_MINUTES)

# ─── DISCORD BOT ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ─── CAPTCHA UTILS ──────────────────────────────────────────────────────
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
        d.point((random.randint(0, 199), random.randint(0, 79)), fill=(0, 0, 0))
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

# ─── BOT EVENTS ─────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_member_join(member):
    code = gen_code()
    set_pending(str(member.id), str(member.guild.id), code)
    await log_action(member.guild.id, f"🔔 Captcha issued for {member.mention}")
    try:
        dm = await member.create_dm()
        await dm.send(f"Solve captcha in {TIMEOUT_MINUTES} minutes, {MAX_ATTEMPTS} tries")
        await dm.send(file=discord.File(make_captcha(code), "captcha.png"))
    except discord.Forbidden:
        await member.kick(reason="Cannot DM captcha")

@bot.event
async def on_message(msg):
    if isinstance(msg.channel, discord.DMChannel) and not msg.author.bot:
        p = get_pending(str(msg.author.id))
        if p:
            if datetime.utcnow() - p["created"] > TIMEOUT:
                await msg.author.send("⏰ Time expired. Kicked.")
                await msg.author.guild.kick(msg.author, reason="Timeout")
                await log_action(p["guild_id"], f"⏰ {msg.author.mention} timed out")
                delete_pending(str(msg.author.id))
                return

            if msg.content.strip().upper() == p["code"]:
                await msg.author.send("✅ Passed captcha.")
                g = bot.get_guild(int(p["guild_id"]))
                m = g.get_member(msg.author.id)
                r = discord.utils.get(g.roles, name="Member")
                if m and r:
                    await m.add_roles(r)
                await log_action(p["guild_id"], f"✅ {msg.author.mention} passed")
                delete_pending(str(msg.author.id))
            else:
                att = p["attempts"] + 1
                update_attempts(str(msg.author.id), att)
                if att >= MAX_ATTEMPTS:
                    await msg.author.send("❌ Too many tries. Kicked.")
                    g = bot.get_guild(int(p["guild_id"]))
                    await g.kick(msg.author, reason="Failed captcha")
                    await log_action(p["guild_id"], f"❌ {msg.author.mention} failed")
                    delete_pending(str(msg.author.id))
                else:
                    await msg.author.send(f"❌ Wrong. {MAX_ATTEMPTS - att} tries left.")
        return

    await bot.process_commands(msg)

# ─── SLASH COMMANDS ────────────────────────────────────────────────────
@tree.command(name="set_log_channel", description="Set mod-log channel")
@app_commands.checks.has_permissions(administrator=True)
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    set_settings(str(interaction.guild.id), log_channel=str(channel.id))
    await interaction.response.send_message(f"Log channel set to {channel.mention}")

@tree.command(name="set_admin_role", description="Set admin role for panel access")
@app_commands.checks.has_permissions(administrator=True)
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    set_settings(str(interaction.guild.id), admin_role=str(role.id))
    await interaction.response.send_message(f"Admin role set to {role.name}")

@tree.command(name="ping", description="Check if bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓")

# ─── RUN BOT ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
