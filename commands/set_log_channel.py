import discord
from discord import app_commands
from discord.ext import commands
from utils import set_settings

class LogChannelCog(commands.Cog):
    @app_commands.command(
        name="set_log_channel",
        description="Set mod-log channel"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_settings(str(interaction.guild.id), log_channel=str(channel.id))
        await interaction.response.send_message(f"📑 Log channel set to {channel.mention}")

async def setup(bot):
    await bot.add_cog(LogChannelCog(bot))
