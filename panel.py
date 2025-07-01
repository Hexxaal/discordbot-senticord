import os
from urllib.parse import urlencode
from flask import Flask, session, redirect, url_for, request, abort, render_template_string
import requests

# ─── CONFIG ───────────────────────────────────────────────────────────
CLIENT_ID        = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET    = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_TOKEN    = os.getenv("DISCORD_TOKEN")
REDIRECT_URI     = os.getenv("REDIRECT_URI")      # https://panel.senticord.org/callback
OAUTH_SCOPES     = ["identify", "guilds"]
BOT_PERMISSIONS  = os.getenv("BOT_PERMISSIONS","8")

# ─── FIRESTORE (for optional admin_role) ──────────────────────────────
from google.cloud import firestore
db       = firestore.Client()
settings = db.collection("guild_settings")

# ─── FLASK SETUP ───────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

def make_oauth_url(path="/admin"):
    # We pass the desired panel path in `state`
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
    data = {
      "client_id":     CLIENT_ID,
      "client_secret": CLIENT_SECRET,
      "grant_type":    "authorization_code",
      "code":          code,
      "redirect_uri":  REDIRECT_URI,
      "scope":         " ".join(OAUTH_SCOPES),
    }
    r = requests.post("https://discord.com/api/oauth2/token",
                      data=data,
                      headers={"Content-Type":"application/x-www-form-urlencoded"})
    r.raise_for_status()
    token = r.json()["access_token"]

    hdr = {"Authorization": f"Bearer {token}"}
    session["user"]   = requests.get("https://discord.com/api/users/@me", headers=hdr).json()
    session["guilds"] = requests.get("https://discord.com/api/users/@me/guilds", headers=hdr).json()
    # Redirect to the panel path we asked for
    return redirect(path)

@app.route("/admin")
def admin_index():
    user   = session.get("user")
    guilds = session.get("guilds", [])
    if not user:
        return redirect(url_for("index"))

    # Show only guilds where the bot is present AND you’re the owner
    allowed = [g for g in guilds if g.get("owner")]

    return render_template_string("""
      <h1>{{ user.username }}#{{ user.discriminator }}</h1>
      <h2>Your Servers (owner-only)</h2>
      {% if allowed %}
        <ul>
          {% for g in allowed %}
            <li><a href="{{ url_for('configure_guild', guild_id=g.id) }}">{{ g.name }}</a></li>
          {% endfor %}
        </ul>
      {% else %}
        <p>You don’t own any servers where the bot is installed.</p>
      {% endif %}
      <p><a href="{{ invite_url }}">🔗 Invite Bot to Another Server</a></p>
    """, user=user, allowed=allowed, invite_url=invite_url)

@app.route("/admin/<guild_id>", methods=["GET","POST"])
def configure_guild(guild_id):
    user   = session.get("user")
    guilds = session.get("guilds", [])
    if not user:
        return redirect(url_for("index"))

    # Check you actually own this guild
    me_guild = next((g for g in guilds if str(g["id"])==guild_id), None)
    if not me_guild or not me_guild.get("owner"):
        abort(403, "You must be the server owner to access this page.")

    # At this point you’re guaranteed owner, so you can POST settings
    if request.method=="POST":
        # e.g. save admin_role if you want
        settings.document(guild_id).set({
          "admin_role": request.form.get("admin_role","")
        }, merge=True)

    # Optionally fetch roles/channels and show a form
    # ...
    return render_template_string("""
      <h1>Settings for {{ me_guild.name }}</h1>
      <form method="post">
        <!-- your settings form here -->
        <button>Save</button>
      </form>
      <p><a href="{{ url_for('admin_index') }}">← Back</a></p>
    """, me_guild=me_guild)
