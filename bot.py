# bot.py
import os
import discord
from discord.ext import commands
from google.cloud import firestore

# ── CONFIG ─────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ── FIRESTORE ───────────────────────────────
db = firestore.Client()
settings = db.collection("guild_settings")

# ── DISCORD BOT SETUP ───────────────────────
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user} (ID: {bot.user.id})")

@tree.command(name="ping", description="Test if bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓")

# ... other bot commands, events, captcha logic, etc. ...

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
