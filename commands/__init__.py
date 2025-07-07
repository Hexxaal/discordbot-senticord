"""
Package for all slash-command modules.
Each module must define async `setup(bot)` to register commands or Cogs.
"""
import os, glob

async def setup(bot):
    pkg_dir = os.path.dirname(__file__)
    for filepath in glob.glob(pkg_dir + "/*.py"):
        name = os.path.basename(filepath)[:-3]
        if name == "__init__": continue
        module = __import__(f"commands.{name}", fromlist=["setup"])
        if hasattr(module, "setup"):
            await module.setup(bot)
