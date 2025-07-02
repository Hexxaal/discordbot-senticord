import discord
from discord import app_commands
from discord.ext import commands
from utils import set_settings

class AdminRoleCog(commands.Cog):
    @app_commands.command(name="set_admin_role", description="Set admin role for panel access")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_admin_role(self, interaction, role: discord.Role):
        set_settings(str(interaction.guild.id), admin_role=str(role.id))
        await interaction.response.send_message(f"🛡️ Admin role set to {role.name}")

async def setup(bot):
    await bot.add_cog(AdminRoleCog(bot))
