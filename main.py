import os
from threading import Thread
from urllib.parse import urlencode
from flask import Flask, session, redirect, url_for, request, render_template_string, abort
import requests
from google.cloud import firestore

# ─── CONFIG ─────────────────────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
CLIENT_ID          = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET      = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI       = os.getenv("REDIRECT_URI")   # e.g. https://panel.senticord.org/callback
OAUTH_SCOPES       = ["identify", "guilds"]
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", "CHANGE_ME")
BOT_PERMISSIONS    = os.getenv("BOT_PERMISSIONS", "8")  # Administrator perms

# ─── FIRESTORE ─────────────────────────────────────────────────────────
db       = firestore.Client()
settings = db.collection("guild_settings")

# ─── URL HELPERS ───────────────────────────────────────────────────────
def make_oauth_url():
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(OAUTH_SCOPES),
        "state":         OAUTH_STATE_SECRET,
    }
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"

invite_url = (
    "https://discord.com/oauth2/authorize?" +
    urlencode({"client_id": CLIENT_ID, "scope": "bot applications.commands", "permissions": BOT_PERMISSIONS})
)

# ─── FLASK APP ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route("/")
def index():
    return render_template_string(
        """
        <!doctype html><html><head><meta charset='utf-8'><title>Discord Panel</title></head><body>
        <h1>Discord Admin Panel</h1>
        <p><a href='{{ oauth_url }}'>🔒 Login with Discord</a></p>
        <p><a href='{{ invite_url }}'>🔗 Invite Bot to Your Server</a></p>
        </body></html>
        """,
        oauth_url=make_oauth_url(), invite_url=invite_url
    )

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    state = request.args.get("state")
    if state != OAUTH_STATE_SECRET:
        abort(403, "Invalid state")

    # Exchange code for token
    data = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "scope":         " ".join(OAUTH_SCOPES),
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    token_res.raise_for_status()
    access_token = token_res.json()["access_token"]

    auth   = {"Authorization": f"Bearer {access_token}"}
    user   = requests.get("https://discord.com/api/users/@me", headers=auth).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=auth).json()

    session["user"]   = user
    session["guilds"] = guilds
    return redirect(url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if "user" not in session:
        return redirect(url_for("index"))

    user   = session["user"]
    guilds = session.get("guilds", [])
    allowed = []

    # filter by owner or configured admin_role
    for g in guilds:
        gid = g["id"]
        # Check membership to get roles
        m = requests.get(
            f"https://discord.com/api/guilds/{gid}/members/{user['id']}",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
        )
        if m.status_code != 200:
            continue
        member = m.json()

        cfg = settings.document(gid).get().to_dict() or {}
        admin_role = cfg.get("admin_role")

        # allow if owner or has the configured admin_role
        if g.get("owner") or (admin_role and str(admin_role) in member.get("roles", [])):
            allowed.append(g)

    return render_template_string(
        """
        <!doctype html><html><head><meta charset='utf-8'><title>Admin Panel</title></head><body>
        <h1>Welcome {{ user.username }}#{{ user.discriminator }}</h1>
        <h2>Your Servers</h2>
        {% if allowed %}<ul>
          {% for g in allowed %}<li><a href='/admin/{{ g.id }}'>{{ g.name }}</a></li>{% endfor %}
        </ul>{% else %}<p>No servers where you have admin access.</p>{% endif %}
        <p><a href='{{ invite_url }}'>🔗 Invite Bot to Another Server</a></p>
        </body></html>
        """,
        user=user, allowed=allowed, invite_url=invite_url
    )

@app.route("/admin/<guild_id>", methods=["GET", "POST"])
def configure_guild(guild_id):
    if "user" not in session:
        return redirect(url_for("index"))
    user = session["user"]

    # verify membership
    m = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/members/{user['id']}",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
    )
    if m.status_code != 200:
        abort(403)
    member_roles = m.json().get("roles", [])

    # Load or set config
    if request.method == "POST":
        settings.document(guild_id).set({
            "admin_role": request.form.get("admin_role")
        }, merge=True)

    cfg = settings.document(guild_id).get().to_dict() or {}
    # fetch guild roles
    roles = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/roles",
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
    ).json()

    return render_template_string(
        """
        <!doctype html><html><head><meta charset='utf-8'><title>Configure {{ guild.name }}</title></head><body>
        <h1>Settings for {{ guild.name }}</h1>
        <form method='post'>
          <label>Admin Role:</label>
          <select name='admin_role'>
            <option value=''>-- none --</option>
            {% for r in roles %}
              <option value='{{ r.id }}' {% if cfg.get('admin_role')==r.id|string %}selected{% endif %}>
                {{ r.name }}
              </option>
            {% endfor %}
          </select>
          <button type='submit'>Save</button>
        </form>
        <p><a href='/admin'>← Back</a></p>
        </body></html>
        """,
        guild={"id": guild_id, "name": request.args.get("guild_name", guild_id)},
        roles=roles, cfg=cfg
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
