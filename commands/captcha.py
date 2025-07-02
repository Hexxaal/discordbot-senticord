import discord
from discord.ext import commands
from datetime import datetime
from bot import gen_code, make_captcha, TIMEOUT, MAX_ATTEMPTS, log_action
from utils import get_pending, set_pending, update_attempts, delete_pending

class CaptchaCog(commands.Cog):
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        code = gen_code()
        set_pending(str(member.id), str(member.guild.id), code)
        await log_action(member.guild.id, f"🔔 Captcha issued to {member.mention}")
        try:
            dm = await member.create_dm()
            embed = discord.Embed(
                title="🔐 Verify Yourself",
                description=f"Enter **{code}** within {TIMEOUT}",
                color=discord.Color.blue()
            )
            await dm.send(embed=embed)
            await dm.send(file=discord.File(make_captcha(code), "captcha.png"))
        except discord.Forbidden:
            await member.kick(reason="Cannot DM captcha")
            await log_action(member.guild.id, f"⚠️ Kicked {member.mention}: cannot DM")

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not isinstance(msg.channel, discord.DMChannel) or msg.author.bot:
            return
        p = get_pending(str(msg.author.id))
        if not p:
            return

        # Timeout check
        if datetime.utcnow() - p["created"] > TIMEOUT:
            await msg.author.send("⏰ Time expired. You have been kicked.")
            guild = msg.author.guild
            await guild.kick(msg.author, reason="Captcha timeout")
            await log_action(p["guild_id"], f"⏰ {msg.author.mention} timed out")
            delete_pending(str(msg.author.id))
            return

        # Correct?
        if msg.content.strip().upper() == p["code"]:
            await msg.author.send("✅ Captcha passed!")
            guild = msg.author.guild
            member = guild.get_member(msg.author.id)
            role = discord.utils.get(guild.roles, name="Member")
            if member and role:
                await member.add_roles(role)
            await log_action(p["guild_id"], f"✅ {msg.author.mention} verified")
            delete_pending(str(msg.author.id))
        else:
            # Wrong attempt
            atts = p["attempts"] + 1
            update_attempts(str(msg.author.id), atts)
            if atts >= MAX_ATTEMPTS:
                await msg.author.send("❌ Too many attempts. You have been kicked.")
                guild = msg.author.guild
                await guild.kick(msg.author, reason="Failed captcha")
                await log_action(p["guild_id"], f"❌ {msg.author.mention} failed captcha")
                delete_pending(str(msg.author.id))
            else:
                left = MAX_ATTEMPTS - atts
                await msg.author.send(f"❌ Wrong code. {left} tries left.")

async def setup(bot):
    await bot.add_cog(CaptchaCog(bot))
