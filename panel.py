import os
import sqlite3
from threading import Lock
from urllib.parse import urlencode
from flask import Flask, session, redirect, url_for, request, abort, render_template_string
import requests

# ─── SQLite settings store ─────────────────────────────────────────────
DB_PATH = os.getenv("SQLITE_DB_PATH", "settings.db")
_conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
_lock   = Lock()
_cursor = _conn.cursor()
_cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id    TEXT PRIMARY KEY,
  admin_role  TEXT,
  log_channel TEXT
);
""")
_conn.commit()

def get_settings(guild_id):
    _cursor.execute(
        "SELECT admin_role, log_channel FROM guild_settings WHERE guild_id=?",
        (guild_id,)
    )
    row = _cursor.fetchone()
    return {"admin_role": row[0], "log_channel": row[1]} if row else {}

def set_settings(guild_id, admin_role=None, log_channel=None):
    with _lock:
        existing = get_settings(guild_id)
        ar = admin_role  if admin_role  is not None else existing.get("admin_role")
        lc = log_channel if log_channel is not None else existing.get("log_channel")
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
CLIENT_ID       = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET   = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI    = os.getenv("REDIRECT_URI")  # e.g. https://panel.senticord.org/callback
OAUTH_SCOPES    = ["identify", "guilds"]
BOT_PERMISSIONS = os.getenv("BOT_PERMISSIONS", "8")

app = Flask(__name__)
app.secret_key = os.urandom(24)

def make_oauth_url(path="/admin"):
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(OAUTH_SCOPES),
        "state":         path,
    }
    return "https://discord.com/oauth2/authorize?" + urlencode(params)

invite_url = (
    "https://discord.com/oauth2/authorize?"
    + urlencode({
        "client_id":   CLIENT_ID,
        "scope":       "bot applications.commands",
        "permissions": BOT_PERMISSIONS,
    })
)

@app.route("/")
def index():
    return render_template_string("""
        <h1>Welcome to Senticord Admin Panel</h1>
        <p><a href="{{ invite_url }}">🔗 Invite Bot to Your Server</a></p>
        <p><a href="{{ oauth_url }}">🔒 Login with Discord</a></p>
    """, invite_url=invite_url, oauth_url=make_oauth_url("/admin"))

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    path  = request.args.get("state", "/admin")
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
    access_token = token_res.json()["access_token"]

    hdr = {"Authorization": f"Bearer {access_token}"}
    session["user"]   = requests.get("https://discord.com/api/users/@me", headers=hdr).json()
    session["guilds"] = requests.get("https://discord.com/api/users/@me/guilds", headers=hdr).json()
    return redirect(path)

@app.route("/admin")
def admin_index():
    user   = session.get("user")
    guilds = session.get("guilds", [])
    if not user:
        return redirect(url_for("index"))

    # Only show guilds where the user is owner
    allowed = [g for g in guilds if g.get("owner")]

    return render_template_string("""
        <h1>{{ user.username }}#{{ user.discriminator }}</h1>
        <h2>Your Servers (Owner Only)</h2>
        {% if allowed %}
          <ul>
            {% for g in allowed %}
              <li><a href="{{ url_for('configure_guild', guild_id=g.id) }}">{{ g.name }}</a></li>
            {% endfor %}
          </ul>
        {% else %}
          <p>You don’t own any servers with this bot installed.</p>
        {% endif %}
        <p><a href="{{ invite_url }}">🔗 Invite Bot to Another Server</a></p>
    """, user=user, allowed=allowed, invite_url=invite_url)

@app.route("/admin/<guild_id>", methods=["GET", "POST"])
def configure_guild(guild_id):
    user   = session.get("user")
    guilds = session.get("guilds", [])
    if not user:
        return redirect(url_for("index"))

    # Verify user owns this guild
    me_guild = next((g for g in guilds if str(g["id"]) == str(guild_id)), None)
    if not me_guild or not me_guild.get("owner"):
        abort(403, "You must be the server owner to access this page.")

    # Load or save settings
    if request.method == "POST":
        set_settings(
            guild_id,
            admin_role  = request.form.get("admin_role"),
            log_channel = request.form.get("log_channel")
        )

    cfg = get_settings(guild_id)

    # Optionally fetch roles/channels from Discord to populate form
    roles = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/roles",
        headers={"Authorization": f"Bot {os.getenv('DISCORD_TOKEN')}"}
    ).json()

    return render_template_string("""
        <h1>Settings for {{ me_guild.name }}</h1>
        <form method="post">
          <label>Admin Role:</label>
          <select name="admin_role">
            <option value="">-- none --</option>
            {% for r in roles %}
              <option value="{{ r.id }}" {% if cfg.get('admin_role') == r.id|string %}selected{% endif %}>
                {{ r.name }}
              </option>
            {% endfor %}
          </select>
          <br>
          <label>Log Channel:</label>
          <input type="text" name="log_channel" value="{{ cfg.get('log_channel','') }}" placeholder="Channel ID">
          <br>
          <button type="submit">Save Settings</button>
        </form>
        <p><a href="{{ url_for('admin_index') }}">← Back to Your Servers</a></p>
    """, me_guild=me_guild, roles=roles, cfg=cfg)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
