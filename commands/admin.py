import discord
from discord import app_commands
from discord.ext import commands

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin", description="Open the management panel")
    async def admin(self, interaction: discord.Interaction):
        url = f"https://panel.senticord.org/guilds/{interaction.guild.id}"
        embed = discord.Embed(
            title="Guild Management Panel",
            description=f"[Open Panel]({url})",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
