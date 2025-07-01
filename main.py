import os
from threading import Thread
from urllib.parse import urlencode
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

# ─── FIRESTORE ─────────────────────────────────────────────────────────
db       = firestore.Client()
settings = db.collection("guild_settings")

# ─── DISCORD BOT ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ─── OAUTH & INVITE URL HELPERS ─────────────────────────────────────────
def make_oauth_url(path: str = "/admin") -> str:
    # state: secret|path to redirect to after auth
    state = f"{OAUTH_STATE_SECRET}|{path}"
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(OAUTH_SCOPES),
        "state":         state,
    }
    return "https://discord.com/oauth2/authorize?" + urlencode(params)

invite_url = "https://discord.com/oauth2/authorize?" + urlencode({
    "client_id":   CLIENT_ID,
    "scope":       "bot applications.commands",
    "permissions": BOT_PERMISSIONS,
})

# ─── DISCORD EVENTS & COMMANDS ──────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="admin", description="Open this server’s dashboard")
async def admin_cmd(interaction: discord.Interaction):
    # build OAuth2 link that will redirect to /admin/<guild_id>
    path = f"/admin/{interaction.guild.id}"
    url  = make_oauth_url(path)
    await interaction.response.send_message(
        f"🔒 Open dashboard for **{interaction.guild.name}**:\n{url}",
        ephemeral=True
    )

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
    # parse state into secret and path
    try:
        secret, path = state.split("|", 1)
    except ValueError:
        abort(400, "Invalid state")
    if secret != OAUTH_STATE_SECRET:
        abort(403, "Invalid state secret")

    # Exchange code for token
    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
            "scope":         " ".join(OAUTH_SCOPES),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    token_res.raise_for_status()
    access_token = token_res.json().get("access_token")

    # Fetch user & guilds
    hdr    = {"Authorization": f"Bearer {access_token}"}
    user   = requests.get("https://discord.com/api/users/@me", headers=hdr).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=hdr).json()

    session["user"]   = user
    session["guilds"] = guilds
    # redirect to requested path or default
    return redirect(path or url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if "user" not in session:
        return redirect(url_for("index"))
    user   = session["user"]
    guilds = session.get("guilds", [])
    allowed = []
    # Filter guilds where bot is present and user is owner or has admin_role
    for g in guilds:
        gid = g["id"]
        # check bot membership via Bot token
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
    # verify membership and bot presence
    m = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/members/{user['id']}",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
    )
    if m.status_code != 200:
        abort(403)
    if request.method == "POST":
        settings.document(guild_id).set({"admin_role": request.form.get("admin_role")}, merge=True)

    # fetch guild roles
    roles = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/roles",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
    ).json()
    cfg   = settings.document(guild_id).get().to_dict() or {}
    # fetch guild name
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
    # start Flask first (non-daemon so errors are visible)
    flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=8080))
    flask_thread.start()
    # then start the Discord bot (blocks)
    bot.run(DISCORD_TOKEN)
