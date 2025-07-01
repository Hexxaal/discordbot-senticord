import os
from urllib.parse import urlencode
from flask import Flask, session, redirect, url_for, request, render_template_string, abort
import requests

# ─── CONFIG ─────────────────────────────────────────────────────────────
CLIENT_ID       = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET   = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI    = os.getenv("REDIRECT_URI")   # e.g. https://panel.senticord.org/callback
OAUTH_SCOPES    = ["identify", "guilds"]
OAUTH_STATE     = os.getenv("OAUTH_STATE_SECRET", "CHANGE_ME")
BOT_PERMISSIONS = os.getenv("BOT_PERMISSIONS", "8")  # Administrator perms

# ─── URL GENERATORS ────────────────────────────────────────────────────
def make_oauth_url():
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(OAUTH_SCOPES),
        "state":         OAUTH_STATE,
    }
    return "https://discord.com/oauth2/authorize?" + urlencode(params)

invite_url = "https://discord.com/oauth2/authorize?" + urlencode({
    "client_id":  CLIENT_ID,
    "scope":      "bot applications.commands",
    "permissions": BOT_PERMISSIONS,
})

# ─── FLASK APP ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route("/")
def index():
    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
        <head><meta charset="utf-8"><title>Discord Panel</title></head>
        <body>
          <h1>Discord Integration</h1>
          <p><a href="{{ oauth_url }}">🔒 Login with Discord</a></p>
          <p><a href="{{ invite_url }}">🔗 Invite Bot to Your Server</a></p>
        </body>
        </html>
        """,
        oauth_url=make_oauth_url(),
        invite_url=invite_url
    )

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    state = request.args.get("state")
    if state != OAUTH_STATE:
        abort(403, "Invalid state")

    data = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "scope":         " ".join(OAUTH_SCOPES),
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers=headers
    )
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    auth   = {"Authorization": f"Bearer {access_token}"}
    user   = requests.get("https://discord.com/api/users/@me", headers=auth).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=auth).json()

    # Keep only guilds where the user is owner
    owner_guilds = [g for g in guilds if g.get("owner")]

    session["user"]         = user
    session["owner_guilds"] = owner_guilds
    return redirect(url_for("admin"))

@app.route("/admin")
def admin():
    if "user" not in session:
        return redirect(url_for("index"))

    user   = session["user"]
    guilds = session.get("owner_guilds", [])

    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
        <head><meta charset="utf-8"><title>Admin Panel</title></head>
        <body>
          <h1>Welcome {{ user.username }}#{{ user.discriminator }}</h1>
          <h2>Your Servers (Owner)</h2>
          {% if guilds %}
            <ul>
              {% for g in guilds %}
                <li>{{ g.name }} (ID: {{ g.id }})</li>
              {% endfor %}
            </ul>
          {% else %}
            <p>No servers where you are owner.</p>
          {% endif %}
          <p><a href="{{ invite_url }}">🔗 Invite Bot to Another Server</a></p>
        </body>
        </html>
        """,
        user=user,
        guilds=guilds,
        invite_url=invite_url
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
