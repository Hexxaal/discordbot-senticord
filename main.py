import os, io, random, string
from datetime import datetime, timedelta
from threading import Thread

import requests
from flask import Flask, session, redirect, url_for, request, render_template_string, abort
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
from google.cloud import firestore

# ─── CONFIG ─────────────────────────────────────────────────────────────
DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN")
CLIENT_ID           = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET       = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI        = os.getenv("REDIRECT_URI")
OAUTH_SCOPE         = "identify guilds"
TIMEOUT_MINUTES     = int(os.getenv("CAPTCHA_TIMEOUT_MIN", "20"))
MAX_ATTEMPTS        = int(os.getenv("CAPTCHA_MAX_ATTEMPTS", "2"))

# ─── FIRESTORE ─────────────────────────────────────────────────────────
db = firestore.Client()
pending = db.collection("pending_captchas")
settings = db.collection("guild_settings")

# ─── DISCORD BOT ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
TIMEOUT = timedelta(minutes=TIMEOUT_MINUTES)

# ─── UTILS ──────────────────────────────────────────────────────────────
def gen_code(n=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))

def make_captcha(text):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",36)
    img = Image.new("RGB",(200,80),(255,255,255))
    d = ImageDraw.Draw(img)
    for i,ch in enumerate(text):
        d.text((10+i*30, random.randint(5,25)), ch, font=font, fill=(0,0,0))
    for _ in range(100):
        d.point((random.randint(0,199), random.randint(0,79)), fill=(0,0,0))
    buf = io.BytesIO(); img.save(buf,"PNG"); buf.seek(0)
    return buf

async def log_action(guild_id, msg):
    cfg = settings.document(str(guild_id)).get().to_dict() or {}
    ch = cfg.get("log_channel")
    if ch:
        c = bot.get_channel(int(ch))
        if c: await c.send(msg)

# ─── BOT EVENTS ─────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    code = gen_code()
    pending.document(str(member.id)).set({
        "guild_id": member.guild.id, "code": code, "attempts":0, "created":datetime.utcnow()
    })
    await log_action(member.guild.id, f"🔔 Captcha issued for {member.mention}")
    try:
        dm = await member.create_dm()
        await dm.send(f"Solve captcha in {TIMEOUT_MINUTES}m, {MAX_ATTEMPTS} tries")
        await dm.send(file=discord.File(make_captcha(code),"captcha.png"))
    except discord.Forbidden:
        await member.kick(reason="Cannot DM captcha")

@bot.event
async def on_message(msg):
    if isinstance(msg.channel, discord.DMChannel) and not msg.author.bot:
        doc = pending.document(str(msg.author.id)).get()
        if doc.exists:
            data = doc.to_dict()
            if datetime.utcnow()-data["created"]>TIMEOUT:
                await msg.author.send("⏰ Time expired. Kicked.")
                g=bot.get_guild(data["guild_id"]); await g.kick(msg.author,reason="Timeout")
                await log_action(data["guild_id"],f"⏰ {msg.author.mention} timed out")
                doc.reference.delete(); return
            if msg.content.strip().upper()==data["code"]:
                await msg.author.send("✅ Passed captcha."); g=bot.get_guild(data["guild_id"])
                m=g.get_member(msg.author.id); r=discord.utils.get(g.roles,name="Member")
                if m and r: await m.add_roles(r)
                await log_action(data["guild_id"],f"✅ {msg.author.mention} passed")
                doc.reference.delete()
            else:
                att=data["attempts"]+1
                if att>=MAX_ATTEMPTS:
                    await msg.author.send("❌ Too many tries. Kicked.")
                    g=bot.get_guild(data["guild_id"]); await g.kick(msg.author,reason="Failed")
                    await log_action(data["guild_id"],f"❌ {msg.author.mention} failed")
                    doc.reference.delete()
                else:
                    doc.reference.update({"attempts":att})
                    await msg.author.send(f"❌ Wrong. {MAX_ATTEMPTS-att} left.")
        return
    await bot.process_commands(msg)

# ─── SLASH: set_log_channel ───────────────────────────────────────────────
@tree.command(name="set_log_channel",description="Set mod-log channel")
@app_commands.checks.has_permissions(administrator=True)
async def set_log_channel(interaction, channel: discord.TextChannel):
    settings.document(str(interaction.guild.id)).set({"log_channel":channel.id},merge=True)
    await interaction.response.send_message(f"Log channel set to {channel.mention}")

# ─── SLASH: set_admin_role ────────────────────────────────────────────────
@tree.command(name="set_admin_role",description="Set admin role for panel access")
@app_commands.checks.has_permissions(administrator=True)
async def set_admin_role(interaction, role: discord.Role):
    settings.document(str(interaction.guild.id)).set({"admin_role":role.id},merge=True)
    await interaction.response.send_message(f"Admin role set to {role.name}")

# ─── SLASH: admin (OAuth2 login) ─────────────────────────────────────────
@tree.command(name="admin",description="Open admin panel")
async def admin(interaction):
    oauth_url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={redirect_uri_encode:=requests.utils.quote(REDIRECT_URI,safe='')}"
        "&scope=identify%20guilds"
    )
    await interaction.response.send_message(f"🔒 Login: {oauth_url}",ephemeral=True)

# ─── FLASK PANEL (callback + admin list) ─────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route("/callback")
def callback():
    code=request.args.get("code")
    data={
      "client_id":CLIENT_ID,
      "client_secret":CLIENT_SECRET,
      "grant_type":"authorization_code",
      "code":code,
      "redirect_uri":REDIRECT_URI,
      "scope":OAUTH_SCOPE
    }
    r=requests.post("https://discord.com/api/oauth2/token",data=data,
                    headers={"Content-Type":"application/x-www-form-urlencoded"})
    r.raise_for_status(); tok=r.json()["access_token"]
    hdr={"Authorization":f"Bearer {tok}"}
    me=requests.get("https://discord.com/api/users/@me",headers=hdr).json()
    guilds=requests.get("https://discord.com/api/users/@me/guilds",headers=hdr).json()
    session["user"],session["guilds"]=me,guilds
    return redirect("/admin")

@app.route("/admin")
def admin_panel():
    user=session.get("user")
    gs=session.get("guilds",[])
    if not user: return redirect("/callback")
    allowed=[]
    for g in gs:
        mreq=requests.get(f"https://discord.com/api/guilds/{g['id']}/members/{user['id']}",
                          headers={"Authorization":f"Bot {DISCORD_TOKEN}"})
        if mreq.status_code!=200: continue
        m=mreq.json()
        if g.get("owner"): allowed.append(g); continue
        cfg=settings.document(str(g["id"])).get().to_dict() or {}
        if cfg.get("admin_role") and int(cfg["admin_role"]) in m["roles"]:
            allowed.append(g)
    return render_template_string("""<h1>Your Servers</h1>
<ul>{% for g in allowed %}<li><a href='/admin/{{g.id}}'>{{g.name}}</a></li>{% endfor %}</ul>""", allowed=allowed)
if __name__=="__main__":
    Thread(target=lambda:app.run(host="0.0.0.0",port=8080),daemon=True).start()
    bot.run(DISCORD_TOKEN)
