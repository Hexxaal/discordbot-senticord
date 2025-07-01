# panel.py
import os
from urllib.parse import urlencode
from flask import Flask, session, redirect, url_for, request, render_template_string, abort
import requests
from google.cloud import firestore

# ── CONFIG ─────────────────────────────────
CLIENT_ID          = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET      = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI       = os.getenv("REDIRECT_URI")
OAUTH_SCOPES       = ["identify", "guilds"]
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET")
BOT_PERMISSIONS    = os.getenv("BOT_PERMISSIONS", "8")

# ── FIRESTORE ───────────────────────────────
db       = firestore.Client()
settings = db.collection("guild_settings")

# ── FLASK SETUP ─────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

def make_oauth_url(path="/admin"):
    state = f"{OAUTH_STATE_SECRET}|{path}"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(OAUTH_SCOPES),
        "state": state,
    }
    return "https://discord.com/oauth2/authorize?" + urlencode(params)

invite_url = "https://discord.com/oauth2/authorize?" + urlencode({
    "client_id": CLIENT_ID,
    "scope": "bot applications.commands",
    "permissions": BOT_PERMISSIONS,
})

@app.route("/")
def index():
    return render_template_string("""
      <h1>Discord Admin Panel</h1>
      <p><a href="{{ invite_url }}">🔗 Invite Bot to Your Server</a></p>
      <p><a href="{{ oauth_url }}">🔒 Login with Discord</a></p>
    """, invite_url=invite_url, oauth_url=make_oauth_url("/admin"))

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    state = request.args.get("state","")
    try:
        secret, path = state.split("|",1)
    except ValueError:
        abort(400,"Bad state")
    if secret != OAUTH_STATE_SECRET:
        abort(403,"Invalid state")
    # exchange...
    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(OAUTH_SCOPES),
        },
        headers={"Content-Type":"application/x-www-form-urlencoded"}
    )
    token_res.raise_for_status()
    access = token_res.json()["access_token"]
    hdr = {"Authorization": f"Bearer {access}"}
    session["user"]   = requests.get("https://discord.com/api/users/@me", headers=hdr).json()
    session["guilds"] = requests.get("https://discord.com/api/users/@me/guilds", headers=hdr).json()
    return redirect(path or url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if "user" not in session:
        return redirect(url_for("index"))
    user   = session["user"]
    guilds = session["guilds"]
    # filter owner or role-based as before...
    return render_template_string("<h2>My Servers</h2>…")

# … add per-guild pages under /admin/<guild_id> …

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
@app.errorhandler(404)
def page_not_found(e):
    return render_template_string("<h1>404 Not Found</h1><p>The page you are looking for does not exist.</p>"), 404
@app.errorhandler(500)
def internal_server_error(e):
    return render_template_string("<h1>500 Internal Server Error</h1><p>Something went wrong on our end.</p>"), 500
@app.errorhandler(403)
def forbidden(e):
    return render_template_string("<h1>403 Forbidden</h1><p>You do not have permission to access this resource.</p>"), 403
