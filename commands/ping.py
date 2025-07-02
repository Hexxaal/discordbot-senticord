import discord
from discord import app_commands
from discord.ext import commands

class PingCog(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="ping", description="Check if bot is alive")
    async def ping(self, interaction: commands.Interaction):
        await interaction.response.send_message("Pong! 🏓")

async def setup(bot):
    await bot.add_cog(PingCog(bot))