"""
Safe reply utility to handle deleted messages and other Discord API errors
"""
import nextcord
import logging

logger = logging.getLogger('SafeReply')

async def safe_reply(ctx, *args, **kwargs):
    """
    Safely reply to a message with fallbacks for common errors
    
    Args:
        ctx: Command context or interaction
        *args: Arguments to pass to reply
        **kwargs: Keyword arguments to pass to reply
    
    Returns:
        nextcord.Message or None if all attempts failed
    """
    # Try normal reply first
    try:
        if hasattr(ctx, 'reply'):
            return await ctx.reply(*args, **kwargs)
        elif hasattr(ctx, 'response') and hasattr(ctx.response, 'send_message'):
            # Interaction context
            return await ctx.response.send_message(*args, **kwargs)
        else:
            # Fallback to send
            return await ctx.send(*args, **kwargs)
    except nextcord.NotFound:
        # Original message was deleted, try sending to channel
        try:
            logger.debug(f"Reply failed (message deleted), falling back to send in {ctx.channel}")
            return await ctx.send(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Send fallback failed: {e}")
            return None
    except nextcord.Forbidden:
        # No permission to send messages
        try:
            # Try DMing the user if possible
            if hasattr(ctx, 'author'):
                logger.debug(f"No permission in channel, trying DM to {ctx.author}")
                return await ctx.author.send(*args, **kwargs)
        except Exception as e:
            logger.warning(f"DM fallback failed: {e}")
            return None
    except nextcord.HTTPException as e:
        if e.status == 400:
            # Bad request, possibly message too long or invalid content
            try:
                logger.debug(f"400 error, trying simplified message: {e}")
                # Try with a simplified error message
                error_embed = nextcord.Embed(
                    title="❌ Error",
                    description="An error occurred while processing your request.",
                    color=nextcord.Color.red()
                )
                return await ctx.send(embed=error_embed)
            except Exception as fallback_e:
                logger.warning(f"Simplified message fallback failed: {fallback_e}")
                return None
        else:
            logger.warning(f"HTTP exception {e.status}: {e}")
            return None
    except Exception as e:
        logger.error(f"Unexpected error in safe_reply: {e}")
        return None

async def safe_send(channel, *args, **kwargs):
    """
    Safely send a message to a channel with error handling
    
    Args:
        channel: Discord channel object
        *args: Arguments to pass to send
        **kwargs: Keyword arguments to pass to send
    
    Returns:
        nextcord.Message or None if failed
    """
    try:
        return await channel.send(*args, **kwargs)
    except nextcord.NotFound:
        logger.debug(f"Channel {channel} not found or deleted")
        return None
    except nextcord.Forbidden:
        logger.debug(f"No permission to send to {channel}")
        return None
    except nextcord.HTTPException as e:
        if e.status == 400:
            try:
                # Try with simplified error message
                error_embed = nextcord.Embed(
                    title="❌ Error",
                    description="An error occurred.",
                    color=nextcord.Color.red()
                )
                return await channel.send(embed=error_embed)
            except Exception:
                return None
        else:
            logger.warning(f"HTTP exception {e.status}: {e}")
            return None
    except Exception as e:
        logger.error(f"Unexpected error in safe_send: {e}")
        return None

async def safe_edit(message, *args, **kwargs):
    """
    Safely edit a message with error handling
    
    Args:
        message: Discord message object
        *args: Arguments to pass to edit
        **kwargs: Keyword arguments to pass to edit
    
    Returns:
        nextcord.Message or None if failed
    """
    try:
        return await message.edit(*args, **kwargs)
    except nextcord.NotFound:
        logger.debug(f"Message {message.id} not found or deleted")
        return None
    except nextcord.Forbidden:
        logger.debug(f"No permission to edit message {message.id}")
        return None
    except nextcord.HTTPException as e:
        logger.warning(f"HTTP exception editing message: {e.status}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in safe_edit: {e}")
        return None
