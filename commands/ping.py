import discord
from discord import app_commands
from discord.ext import commands

class PingCog(commands.Cog):
    @app_commands.command(name="ping", description="Check latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong! 🏓")

async def setup(bot):
    await bot.add_cog(PingCog(bot))
