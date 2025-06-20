# Work System Module
from .work_cog import Work

async def setup(bot):
    bot.add_cog(Work(bot))
