from utils.db import db
from nextcord.ext import commands
from bronxbot import bot

@bot.check
async def blacklist_check(ctx):
    try:
        cmd = ctx.command.name if ctx.command else None
        if not cmd:
            return True  # fallback

        channel_id = str(ctx.channel.id)
        user_id = str(ctx.author.id)

        settings = await db.get_guild_settings(ctx.guild.id) if ctx.guild else {}
        if not settings:
            settings = {}
            
        blacklist = settings.get('command_blacklist', {})
        channel_blacklist = blacklist.get('channels', {})
        user_blacklist = blacklist.get('users', {})
        role_blacklist = blacklist.get('roles', {})

        print(f"[CHECK] Command: {cmd}")
        print(f"[CHECK] Channel ID: {channel_id}")
        print(f"[CHECK] Channel blacklist: {channel_blacklist}")        # Check channel blacklist
        channel_cmds = channel_blacklist.get(channel_id, [])
        if channel_cmds and isinstance(channel_cmds, list) and (cmd in channel_cmds or "all" in channel_cmds):
            print(f"[BLOCKED] '{cmd}' is blacklisted in channel {channel_id}")
            return False

        # Check user blacklist
        user_cmds = user_blacklist.get(user_id, [])
        if user_cmds and isinstance(user_cmds, list) and (cmd in user_cmds or "all" in user_cmds):
            print(f"[BLOCKED] '{cmd}' is blacklisted for user {user_id}")
            return False

        # Check role blacklist
        if ctx.author.roles:
            for role in ctx.author.roles:
                role_cmds = role_blacklist.get(str(role.id), [])
                if role_cmds and isinstance(role_cmds, list) and (cmd in role_cmds or "all" in role_cmds):
                    print(f"[BLOCKED] '{cmd}' is blacklisted for role {role.id}")
                    return False

        return True

    except Exception as e:
        print(f"[ERROR] blacklist_check failed: {e}")
        return True  # Allow command to proceed if check fails
