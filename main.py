import os
from threading import Thread
from urllib.parse import urlencode
import sys
import requests
from flask import Flask, session, redirect, url_for, request, render_template_string, abort
import discord
from discord.ext import commands
from google.cloud import firestore

# ─── CONFIG ─────────────────────────────────────────────────────────────
DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN")
CLIENT_ID           = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET       = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI        = os.getenv("REDIRECT_URI")  # e.g. https://panel.senticord.org/callback
OAUTH_SCOPES        = ["identify", "guilds"]
OAUTH_STATE_SECRET  = os.getenv("OAUTH_STATE_SECRET", "CHANGE_ME")
BOT_PERMISSIONS     = os.getenv("BOT_PERMISSIONS", "8")  # Administrator perms

# Debug prints for environment
def debug_env():
    print(f"[DEBUG] DISCORD_TOKEN length: {len(DISCORD_TOKEN) if DISCORD_TOKEN else 'None'}", file=sys.stderr)
    print(f"[DEBUG] CLIENT_ID: {CLIENT_ID}", file=sys.stderr)
    print(f"[DEBUG] REDIRECT_URI: {REDIRECT_URI}", file=sys.stderr)
    print(f"[DEBUG] OAUTH_STATE_SECRET: {'SET' if OAUTH_STATE_SECRET!='CHANGE_ME' else 'DEFAULT'}", file=sys.stderr)

# ─── FIRESTORE ─────────────────────────────────────────────────────────
db       = firestore.Client()
settings = db.collection("guild_settings")

# ─── DISCORD BOT ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ─── BOT EVENTS & TEST COMMAND ──────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ [Discord] Logged in as {bot.user} (ID: {bot.user.id})", file=sys.stderr)

# Simple ping command to test responsiveness\@tree.command(name="ping", description="Ping the bot to test responsiveness")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓")
    print(f"[Slash] /ping invoked by {interaction.user}", file=sys.stderr)

@tree.command(name="admin", description="Open this server’s dashboard")
async def admin_cmd(interaction: discord.Interaction):
    path = f"/admin/{interaction.guild.id}"
    state = f"{OAUTH_STATE_SECRET}|{path}"
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "identify guilds",
        "state":         state,
    }
    oauth_url = "https://discord.com/oauth2/authorize?" + urlencode(params)
    await interaction.response.send_message(
        f"🔒 Open dashboard for **{interaction.guild.name}**:\n{oauth_url}",
        ephemeral=True
    )
    print(f"[Slash] /admin invoked by {interaction.user} in {interaction.guild}", file=sys.stderr)

# ─── FLASK APP ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route("/")
def index():
    return render_template_string(
        """
        <!doctype html><html lang="en"><head><meta charset="utf-8"><title>Discord Panel</title></head>
        <body>
          <h1>Discord Admin Panel</h1>
          <p><a href="{{ invite_url }}">🔗 Invite Bot to Your Server</a></p>
          <p><a href="{{ oauth_url }}">🔒 Login with Discord</a></p>
        </body></html>
        """,
        invite_url=invite_url,
        oauth_url=make_oauth_url("/admin")
    )

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    state = request.args.get("state", "")
    try:
        secret, path = state.split("|", 1)
    except ValueError:
        abort(400, "Invalid state format")
    if secret != OAUTH_STATE_SECRET:
        abort(403, "Invalid state secret")

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
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    token_res.raise_for_status()
    access_token = token_res.json().get("access_token")

    hdr    = {"Authorization": f"Bearer {access_token}"}
    user   = requests.get("https://discord.com/api/users/@me", headers=hdr).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=hdr).json()

    session["user"]   = user
    session["guilds"] = guilds
    return redirect(path or url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if "user" not in session:
        return redirect(url_for("index"))
    user   = session["user"]
    guilds = session.get("guilds", [])
    allowed = []
    for g in guilds:
        gid = g["id"]
        m = requests.get(
            f"https://discord.com/api/guilds/{gid}/members/{user['id']}",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
        )
        if m.status_code != 200:
            continue
        member = m.json()
        cfg    = settings.document(gid).get().to_dict() or {}
        admin_role = cfg.get("admin_role")
        if g.get("owner") or (admin_role and str(admin_role) in member.get("roles", [])):
            allowed.append(g)

    return render_template_string(
        """
        <!doctype html><html lang="en"><head><meta charset="utf-8"><title>Admin Panel</title></head><body>
          <h1>Welcome {{ user.username }}#{{ user.discriminator }}</h1>
          <h2>Your Servers</h2>
          {% if allowed %}<ul>{% for g in allowed %}
            <li><a href="/admin/{{ g.id }}">{{ g.name }}</a></li>
          {% endfor %}</ul>{% else %}
            <p>No servers available.</p>
          {% endif %}
          <p><a href="{{ invite_url }}">🔗 Invite Bot to Another Server</a></p>
        </body></html>
        """,
        user=user, allowed=allowed, invite_url=invite_url
    )

@app.route("/admin/<guild_id>", methods=["GET", "POST"])
def configure_guild(guild_id):
    if "user" not in session:
        return redirect(url_for("index"))
    user = session["user"]
    m = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/members/{user['id']}",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
    )
    if m.status_code != 200:
        abort(403)
    if request.method == "POST":
        settings.document(guild_id).set({"admin_role": request.form.get("admin_role")}, merge=True)

    roles = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/roles",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
    ).json()
    cfg   = settings.document(guild_id).get().to_dict() or {}
    ginfo = requests.get(f"https://discord.com/api/guilds/{guild_id}", headers={"Authorization": f"Bot {DISCORD_TOKEN}"})
    guild = ginfo.json() if ginfo.status_code == 200 else {"id": guild_id, "name": "Unknown"}

    return render_template_string(
        """
        <!doctype html><html lang="en"><head><meta charset="utf-8"><title>Configure {{ guild.name }}</title></head><body>
          <h1>Settings for {{ guild.name }}</h1>
          <form method="post">
            <label>Admin Role:</label>
            <select name="admin_role">
              <option value="">-- none --</option>
              {% for r in roles %}
                <option value="{{ r.id }}" {% if cfg.get('admin_role') == r.id|string %}selected{% endif %}>{{ r.name }}</option>
              {% endfor %}
            </select>
            <button type="submit">Save</button>
          </form>
          <p><a href="/admin">← Back</a></p>
        </body></html>
        """,
        guild=guild, roles=roles, cfg=cfg
    )

# ─── RUN FLASK + DISCORD BOT ─────────────────────────────────────────────
if __name__ == "__main__":
    debug_env()
    # start Flask in a non-daemon thread so errors are visible
    flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=8080))
    flask_thread.start()
    print("▶ Flask panel should be up on port 8080", file=sys.stderr)
    # start Discord bot (blocks here)
    print("▶ Connecting Discord bot to Gateway…", file=sys.stderr)
    bot.run(DISCORD_TOKEN)
