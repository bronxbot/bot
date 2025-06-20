import nextcord
import random
import json
from nextcord.ext import commands
import logging
import asyncio
import string
import time
import aiohttp
import sys
import os

# Add the project root to Python path to fix imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

class Fun(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        # Cache for active games to prevent spam
        self.active_games = set()
        self.logger = CogLogger(self.__class__.__name__)

    def get_command_help(self) -> list[nextcord.Embed]:
        """Get paginated help embeds for this cog"""
        pages = []
        
        # Game Commands Page
        games_embed = nextcord.Embed(
            title="🎲 Fun Commands - Games",
            color=nextcord.Color.blue()
        )
        game_commands = ['guess', 'typingtest']
        for cmd_name in game_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                games_embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        pages.append(games_embed)

        # Utility Fun Commands Page
        util_embed = nextcord.Embed(
            title="🎲 Fun Commands - Utilities",
            color=nextcord.Color.blue()
        )
        util_commands = ['pick', 'ball8', 'flip', 'roll']
        for cmd_name in util_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                util_embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        pages.append(util_embed)

        # ASCII & Visual Commands Page
        visual_embed = nextcord.Embed(
            title="🎲 Fun Commands - Visual",
            color=nextcord.Color.blue()
        )
        visual_commands = ['ascii', 'fireworks', 'tableflip']
        for cmd_name in visual_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                visual_embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        pages.append(visual_embed)

        return pages

    @commands.command(aliases=['choose', 'random'])
    async def pick(self, ctx, *options):
        """pick a random option from your list
        
        Usage: pick [option1] [option2] ... [optionN]
        """
        if not options:
            return await ctx.reply("```provide some options to choose from```")
        if len(options) > 50:
            return await ctx.reply("```too many options (max 50)```")
        
        chosen = random.choice(options)
        await ctx.reply(f"🎲 ```i choose: {chosen}```")


    # Magic 8-ball with more responses
    @commands.command(aliases=['8ball', 'magic8ball'])
    async def ball8(self, ctx, *, question: str):
        """ask the magic 8-ball a question"""
        if len(question) > 200:
            return await ctx.reply("```question too long```")
            
        responses = [
            "it is certain", "without a doubt", "yes definitely", "you may rely on it",
            "as i see it, yes", "most likely", "outlook good", "yes",
            "signs point to yes", "reply hazy, try again", "ask again later",
            "better not tell you now", "cannot predict now", "concentrate and ask again",
            "don't count on it", "my reply is no", "my sources say no",
            "outlook not so good", "very doubtful", "absolutely not"
        ]
        
        response = random.choice(responses)
        await ctx.reply(f"🎱 ```{response}```")

    @commands.command(aliases=['dice', 'di'])
    async def roll(self, ctx, dice: str = "1d6"):
        """roll dice (format: 2d20, 1d6, etc.)"""
        try:
            if 'd' not in dice.lower():
                return await ctx.reply("```format: XdY (like 2d6 or 1d20)```")
            
            num_dice, sides = map(int, dice.lower().split('d'))
            
            if num_dice > 20 or sides > 1000 or num_dice < 1 or sides < 2:
                return await ctx.reply("```reasonable limits: 1-20 dice, 2-1000 sides```")
            
            rolls = [random.randint(1, sides) for _ in range(num_dice)]
            total = sum(rolls)
            
            if num_dice == 1:
                await ctx.reply(f"🎲 ```rolled {sides}-sided die: {total}```")
            else:
                rolls_str = ", ".join(map(str, rolls))
                await ctx.reply(f"🎲 ```rolled {num_dice}d{sides}: [{rolls_str}] = {total}```")
                
        except ValueError:
            await ctx.reply("```format: XdY (like 2d6 or 1d20)```")

    # Interactive games
    @commands.command(aliases=['guessnumber'])
    async def guess(self, ctx, max_num: int = 100):
        """start a number guessing game"""
        if max_num > 10000 or max_num < 10:
            return await ctx.reply("```number range: 10-10000```")
        
        if ctx.author.id in self.active_games:
            return await ctx.reply("```finish your current game first!```")
        
        self.active_games.add(ctx.author.id)
        
        try:
            num = random.randint(1, max_num)
            await ctx.reply(f"🎯 ```guess a number between 1-{max_num}\ntype 'quit' to give up```")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            tries = 0
            start_time = time.time()
            
            while tries < 10:  # Max 10 tries
                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=45.0)
                    
                    if msg.content.lower() in ['quit', 'stop', 'exit']:
                        return await ctx.reply(f"```game over! the number was {num}```")
                    
                    try:
                        guess = int(msg.content)
                    except ValueError:
                        await ctx.reply("```please enter a valid number```")
                        continue
                    
                    if guess < 1 or guess > max_num:
                        await ctx.reply(f"```number must be between 1-{max_num}```")
                        continue
                    
                    tries += 1
                    
                    if guess == num:
                        elapsed = time.time() - start_time
                        await ctx.reply(f"🎉 ```correct! the number was {num}\ntries: {tries}\ntime: {elapsed:.1f}s```")
                        return
                    
                    hint = "too high" if guess > num else "too low"
                    remaining = 10 - tries
                    await ctx.reply(f"```{hint}! tries left: {remaining}```")
                    
                except asyncio.TimeoutError:
                    return await ctx.reply(f"```timeout! the number was {num}```")
            
            await ctx.reply(f"```out of tries! the number was {num}```")
            
        finally:
            self.active_games.discard(ctx.author.id)

    @commands.command(aliases=['tt', 'typerace'])
    async def typingtest(self, ctx, difficulty: str = "easy"):
        """test your typing speed
    
        Difficulties: easy, medium, hard
        """
        if ctx.author.id in self.active_games:
            return await ctx.reply("```finish your current game first!```")
        
        sentences = {
            "easy": [
                "the quick brown fox jumps over the lazy dog",
                "hello world this is a simple test",
                "discord bots are pretty cool",
                "python is a great programming language",
                "i love learning new things every day",
                "practice makes perfect in everything you do",
                "coding can be fun and rewarding",
                "stay positive and keep moving forward"
            ],
            "medium": [
                "tsukami has a lot of melanin on his bones",
                "south bronx is a pretty cool server despite the vanity",
                "there is no such thing as a free lunch in this world",
                "programming requires patience and logical thinking skills",
                "sometimes mistakes are the best teachers in life",
                "never underestimate the power of a kind word",
                "consistency is the key to achieving your goals",
                "every challenge is an opportunity to grow"
            ],
            "hard": [
                "you are what you eat unless you eat yourself, then you are what you are",
                "a man is not complete until he is married, then he is finished",
                "the complexity of modern software systems requires careful architectural planning",
                "asynchronous programming paradigms enable efficient resource utilization",
                "perseverance in the face of adversity often leads to unexpected success",
                "the intersection of creativity and logic defines the art of programming",
                "understanding recursion requires first understanding recursion itself",
                "effective communication is essential for collaborative problem solving"
            ]
        }
        
        if difficulty not in sentences:
            return await ctx.reply("```difficulties: easy, medium, hard```")
        
        self.active_games.add(ctx.author.id)
        
        try:
            sentence = random.choice(sentences[difficulty])
            # Add invisible characters to prevent copy-paste
            import secrets
            def add_invisible(text):
                # Add a zero-width space after each word
                zwsp = '\u200b'
                return zwsp.join(list(text))
            disguised_sentence = add_invisible(sentence)

            start = time.time()
            
            embed = nextcord.Embed(
                description=f"⌨️ Type this exactly:\n```{disguised_sentence}```\n`{difficulty.title()} | 60s limit`\n*Copy-paste won't work!*",
                color=nextcord.Color.blue()
            )
            await ctx.reply(embed=embed)
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                elapsed = time.time() - start

                # Remove invisible chars from the original for checking
                def strip_invisible(text):
                    return text.replace('\u200b', '')

                # Calculate stats
                words = len(sentence.split())
                wpm = words / (elapsed / 60)
                
                # Calculate accuracy
                correct_chars = sum(a == b for a, b in zip(msg.content, sentence))
                accuracy = (correct_chars / len(sentence)) * 100

                # If the user's message matches the disguised sentence (with invisible chars), it's likely a paste
                if msg.content == disguised_sentence:
                    await ctx.reply("```No copy-pasting! Try typing it out yourself.```")
                    return

                # If the user's message matches the original sentence, but is too fast (<1.5s), it's suspicious
                if msg.content == sentence and elapsed < 1.5:
                    await ctx.reply("```That was too fast! No copy-pasting allowed.```")
                    return

                # --- Grading system ---
                # Accuracy out of 50
                accuracy_score = min(max(accuracy, 0), 100) / 2  # 0-50

                # WPM out of 50 (scale: 60+ WPM = 50, 0 WPM = 0, linear in between)
                wpm_score = min(max(wpm, 0), 60) / 60 * 50  # 0-50

                grade_percent = accuracy_score + wpm_score

                if grade_percent >= 95:
                    grade = "Perfect! 🏆"
                elif grade_percent >= 85:
                    grade = "Excellent! ⭐"
                elif grade_percent >= 70:
                    grade = "Good! 👍"
                elif grade_percent >= 50:
                    grade = "Not bad! 👌"
                else:
                    grade = "Keep practicing! 💪"
                
                # Results embed
                embed = nextcord.Embed(
                    description=f"📊 **Results**\n\n"
                                f"Time: `{elapsed:.2f}s`\n"
                                f"Speed: `{wpm:.1f}` WPM\n"
                                f"Accuracy: `{accuracy:.1f}%`\n"
                                f"Grade: `{grade_percent:.1f}%` - {grade}",
                    color=nextcord.Color.green()
                )
                await ctx.reply(embed=embed)
                
            except asyncio.TimeoutError:
                await ctx.reply("```time's up! try again when you're ready```")
    
        finally:
            self.active_games.discard(ctx.author.id)

    # Fun interaction commands
    @commands.command(aliases=['ship'])
    async def lovecalc(self, ctx, user1: nextcord.Member, user2: nextcord.Member = None):
        """calculate love compatibility percentage"""
        user2 = user2 or ctx.author
        
        if user1 == user2:
            return await ctx.reply("```you can't ship someone with themselves! (or can you? 🤔)```")
        
        # Consistent score based on user IDs
        score = (user1.id + user2.id) % 101
        
        if score < 20:
            emoji = "💔"
            comment = "not compatible at all!"
        elif score < 40:
            emoji = "😐"
            comment = "just friends maybe?"
        elif score < 60:
            emoji = "😊"
            comment = "decent compatibility!"
        elif score < 80:
            emoji = "❤️"
            comment = "great match!"
        else:
            emoji = "💞"
            comment = "soulmates! 💕"
        
        await ctx.reply(f"💘 ```{user1.display_name} {emoji} {user2.display_name}\ncompatibility: {score}%\n{comment}```")

    @commands.command()
    async def hack(self, ctx, user: nextcord.Member):
        """totally real hacking simulator (joke command)"""
        if user == ctx.author:
            return await ctx.reply("```you can't hack yourself... or can you? 🤔```")
        
        if user.bot:
            return await ctx.reply("```bots have advanced firewalls! (they're unhackable)```")
        
        steps = [
            f"```initializing hack on {user.display_name}...```",
            "```bypassing discord security... 23%```",
            "```cracking password... 56%```",
            "```accessing mainframe... 78%```",
            "```downloading data... 94%```",
            f"```hack complete! discovered: {random.choice([
                'their browser history is 99% memes',
                'they have 847 unread discord notifications',
                'their password is literally \"password123\"',
                'they\'ve been typing for 5 minutes without sending',
                'they have 23 servers muted',
                'they use light mode (shocking!)',
                'they have nitro but no good emotes'
            ])}```"
        ]
        
        msg = await ctx.reply(steps[0])
        for step in steps[1:]:
            await asyncio.sleep(random.uniform(1.2, 2.0))
            await msg.edit(content=step)

    # ASCII Art and visuals
    @commands.command(aliases=['textart'])
    async def ascii(self, ctx, *, name: str):
        """get cool ASCII art
        
        Available: cat, dog, heart, star, shrug, tableflip
        """
        arts = {
            "cat": "```\n /\\_/\\  \n( o.o ) \n > ^ < \n```",
            "dog": "```\n  / \\__\n (    @\\___\n /         O\n /   (_____/\n /_____/   \n```",
            "heart": "```\n  ♥♥♥    ♥♥♥\n ♥♥♥♥♥  ♥♥♥♥♥\n ♥♥♥♥♥♥♥♥♥♥♥\n  ♥♥♥♥♥♥♥♥♥\n   ♥♥♥♥♥♥♥\n    ♥♥♥♥♥\n     ♥♥♥\n      ♥\n```",
            "star": "```\n    ★\n   ★★★\n  ★★★★★\n ★★★★★★★\n★★★★★★★★★\n ★★★★★★★\n  ★★★★★\n   ★★★\n    ★\n```",
            "shrug": "```¯\\_(ツ)_/¯```",
            "tableflip": "```(╯°□°）╯︵ ┻━┻```"
        }
        
        name = name.lower().strip()
        if name not in arts:
            available = ", ".join(arts.keys())
            return await ctx.reply(f"```available arts: {available}```")
        
        await ctx.reply(arts[name])

    @commands.command()
    async def fireworks(self, ctx):
        """celebrate with animated fireworks! 🎆"""
        fireworks = ["🎇", "🎆", "✨", "💥", "🌟"]
        
        msg = await ctx.reply("```preparing fireworks...```")
        await asyncio.sleep(1)
        
        for i in range(3, 0, -1):
            await msg.edit(content=f"```{i}...```")
            await asyncio.sleep(1)
        
        # Multiple firework bursts
        for _ in range(3):
            burst = "".join(random.choices(fireworks, k=random.randint(8, 15)))
            await msg.edit(content=burst)
            await asyncio.sleep(0.8)
        
        await msg.edit(content="🎉 ```celebration complete! 🎉```")

    @commands.command(aliases=['password', 'pwd'])
    async def genpass(self, ctx, length: int = 12):
        """generate a random secure password"""
        if length < 6 or length > 50:
            return await ctx.reply("```password length: 6-50 characters```")
        
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choices(chars, k=length))
        
        try:
            await ctx.author.send(f"🔐 Your generated password: ```{password}```")
            await ctx.reply("```password sent to your DMs for security!```")
        except nextcord.Forbidden:
            await ctx.reply("```couldn't DM you! enable DMs from server members```")

    @commands.command()
    async def cooldown(self, ctx):
        """check command cooldowns"""
        embed = nextcord.Embed(
            title="⏰ Active Games",
            description="Games you're currently playing:",
            color=nextcord.Color.blue()
        )
        
        if ctx.author.id in self.active_games:
            embed.add_field(
                name="Status", 
                value="You have an active game running!\nFinish it before starting another.", 
                inline=False
            )
        else:
            embed.add_field(
                name="Status", 
                value="No active games - you're free to play!", 
                inline=False
            )
        
        await ctx.reply(embed=embed)

    @ball8.error
    async def text_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("```please provide some text to predict```")

    @lovecalc.error
    @hack.error
    async def user_command_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.reply("```user not found in this server```")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("```please mention a user```")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if ctx.command and ctx.command.cog_name == self.__class__.__name__:
            await self.handle_error(ctx, error)


async def setup(bot):
    try:
        logger = CogLogger("Fun")
        bot.add_cog(Fun(bot))
    except Exception as e:
        logger.error(f"Failed to load Fun cog: {e}")
        raise e