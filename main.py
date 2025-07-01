import os
from threading import Thread
from urllib.parse import urlencode
from flask import Flask, session, redirect, url_for, request, render_template_string, abort
import requests
import discord
from discord.ext import commands
from google.cloud import firestore

# ─── CONFIG ─────────────────────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
CLIENT_ID          = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET      = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI       = os.getenv("REDIRECT_URI")
OAUTH_SCOPES       = ["identify", "guilds"]
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", "CHANGE_ME")
BOT_PERMISSIONS    = os.getenv("BOT_PERMISSIONS", "8")

# ─── FIRESTORE ─────────────────────────────────────────────────────────
db       = firestore.Client()
settings = db.collection("guild_settings")

# ─── DISCORD BOT ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True  # if you later use member lookups
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ─── SLASH: /admin → give panel link for this guild ─────────────────────
@tree.command(name="admin", description="Open this server’s dashboard")
async def admin_cmd(interaction: discord.Interaction):
    # build an OAuth link that redirects into /admin/<guild_id>
    state_path = f"/admin/{interaction.guild.id}"
    state      = OAUTH_STATE_SECRET + "|" + state_path
    params     = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         " identify guilds".strip(),
        "state":         state,
    }
    oauth_url = "https://discord.com/oauth2/authorize?" + urlencode(params)
    await interaction.response.send_message(
        f"🔒 Manage **{interaction.guild.name}** here:\n{oauth_url}", ephemeral=True
    )

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ─── FLASK APP ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Invite-bot link (server selection UI)
invite_url = (
    "https://discord.com/oauth2/authorize?"
    + urlencode(
        {
            "client_id":   CLIENT_ID,
            "scope":       "bot applications.commands",
            "permissions": BOT_PERMISSIONS,
        }
    )
)

@app.route("/")
def index():
    return render_template_string(
        """
        <h1>Discord Admin Panel</h1>
        <p><a href="{{ invite_url }}">🔗 Invite Bot to Your Server</a></p>
        <p><a href="{{ oauth_url }}">🔒 Login with Discord</a></p>
        """,
        invite_url=invite_url,
        oauth_url=make_oauth_url("/admin"),
    )

def make_oauth_url(next_path="/admin"):
    state = OAUTH_STATE_SECRET + "|" + next_path
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "identify guilds",
        "state":         state,
    }
    return "https://discord.com/oauth2/authorize?" + urlencode(params)

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    state = request.args.get("state", "")
    try:
        secret, nxt = state.split("|", 1)
    except ValueError:
        abort(400, "Bad state")
    if secret != OAUTH_STATE_SECRET:
        abort(403, "Invalid state")

    # Exchange code for token
    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
            "scope":         "identify guilds",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    # Fetch user + guilds
    hdr    = {"Authorization": f"Bearer {access_token}"}
    user   = requests.get("https://discord.com/api/users/@me", headers=hdr).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=hdr).json()

    session["user"]   = user
    session["guilds"] = guilds
    return redirect(nxt or url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if "user" not in session:
        return redirect(url_for("index"))
    # ... your logic to list allowed guilds ...
    return "Full server list here"

@app.route("/admin/<guild_id>")
def configure_guild(guild_id):
    if "user" not in session:
        return redirect(url_for("index"))
    # ... your per-guild settings page ...
    return f"Settings for {guild_id}"

# ─── RUN BOTH ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) start your Flask panel on port 8080 in a background thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080), daemon=True).start()
    # 2) then start your Discord bot (blocks here, connects Gateway)
    bot.run(DISCORD_TOKEN)
