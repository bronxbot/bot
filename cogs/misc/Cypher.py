import random
import string
import asyncio
import nextcord
from nextcord.ext import commands
from nextcord import DMChannel, TextChannel
from cogs.logging.logger import CogLogger

class Cypher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
    
    def extract_from_codeblock(self, text):
        """Extract content from codeblocks if present"""
        if isinstance(text, str) and text.startswith('```') and text.endswith('```'):
            text = text[3:-3].strip()
            # Remove potential language specifier
            if '\n' in text:
                first_line, rest = text.split('\n', 1)
                if first_line.strip() and not any(c in first_line for c in ' \t\n'):
                    text = rest
        return text
    
    def wrap_in_codeblock(self, text):
        """Wrap text in codeblocks if it contains newlines or is long"""
        if isinstance(text, bool):  # Handle boolean values
            text = str(text)
        if '\n' in text or len(text) > 50 or any(c in text for c in '+=<>/\\|`~"\''):
            return f"```\n{text}\n```"
        return f"**__{text}__**"
    
    def generate_cipher_mapping(self, key):
        """Generate a cipher mapping based on the key"""
        # Extract key from codeblock if present
        key = self.extract_from_codeblock(key)
        
        # Use key as seed for reproducible randomization
        random.seed(key)
        
        # Characters to encrypt/decrypt
        chars = string.ascii_letters + string.digits + ' .,!?;:-_()[]{}@#$%^&*+=<>/\\|`~"\'`'
        
        # Create shuffled version for mapping
        shuffled_chars = list(chars)
        random.shuffle(shuffled_chars)
        
        # Create mapping dictionaries
        encrypt_map = str.maketrans(chars, ''.join(shuffled_chars))
        decrypt_map = str.maketrans(''.join(shuffled_chars), chars)
        
        return encrypt_map, decrypt_map
    
    async def process_input(self, ctx, input_type="encrypt"):
        """Handle interactive input collection"""
        await ctx.reply("```Please check your DMs!```")
        
        try:
            action = "encrypt" if input_type == "encrypt" else "decrypt"
            await ctx.author.send(f"""```What do you want to {action}?
Usage: {input_type} [key] [message]
Example: {input_type} mykey123 hello world

You can use a colon to separate the key and message:
mykey123:hello world (sending key and message at the same time)
mykey123 (sending just key, I will ask for message after)

this command also supports DMs & codeblocks
mykey123:```hello world```

If you want to cancel, type "cancel"
Please send your KEY now (or in format key:message):```""")
            
            def dm_check(m):
                return m.author == ctx.author and isinstance(m.channel, DMChannel)
            
            # wait for key in DMs
            key_msg = await self.bot.wait_for('message', check=dm_check, timeout=120)
            
            if key_msg.content.lower() == 'cancel':
                return await ctx.author.send("```❌ Operation cancelled```"), None
            
            if ':' in key_msg.content:
                key, text = key_msg.content.split(':', 1)
                key = self.extract_from_codeblock(key.strip())
                text = self.extract_from_codeblock(text.strip())
            else:
                key = self.extract_from_codeblock(key_msg.content.strip())
                await ctx.author.send(f"```Now please send your message to {action}:```")
                text_msg = await self.bot.wait_for('message', check=dm_check, timeout=120)
                text = self.extract_from_codeblock(text_msg.content.strip())
            
            return key, text
            
        except asyncio.TimeoutError:
            await ctx.author.send("```⌛ Operation timed out```")
            return None, None
        except Exception as e:
            await ctx.author.send(f"```❌ Error: {str(e)}```")
            return None, None
    
    @commands.command(aliases=['secret', 'encrypt'])
    async def cypher(self, ctx, key: str = None, *, text: str = None):
        """Send encrypted messages using a key-based cipher"""
        # case where no arguments provided
        if not text and not key:
            key, text = await self.process_input(ctx, "encrypt")
            if not key:
                return
        
        elif not key:
            return await ctx.reply("```Please provide a key```", delete_after=10)
        
        elif not text:
            return await ctx.reply("```Please provide the text to encrypt```", delete_after=10)
        
        # get that boy from codeblocks if present
        key = self.extract_from_codeblock(key)
        text = self.extract_from_codeblock(text)
        
        # check it
        if len(text) > 1900:
            return await ctx.reply("```Text too long (max 1900 chars)```", delete_after=10)
        
        if len(key) > 50:
            return await ctx.reply("```Key too long (max 50 chars)```", delete_after=10)
        
        if len(key) < 3:
            return await ctx.reply("```Key too short (min 3 chars)```", delete_after=10)
        
        # cipher mapping and encrypt
        try:
            encrypt_map, _ = self.generate_cipher_mapping(key)
            encrypted_text = text.translate(encrypt_map)
            
            embed = nextcord.Embed(color=0x2b2d31) 
            embed.add_field(name="Key", value=f"`{key[:50]}`", inline=False)
            embed.add_field(name="Original", value=self.wrap_in_codeblock(text[:1900]), inline=False)
            embed.add_field(name="Encrypted", value=self.wrap_in_codeblock(encrypted_text), inline=False)
            
            await ctx.author.send(embed=embed)
            if isinstance(ctx.channel, TextChannel):
                await ctx.reply("✅ Encryption complete - check your DMs", mention_author=False)
        
        except Exception as e:
            await ctx.reply(f"```Encryption failed: {str(e)}```")

    @commands.command(aliases=['decrypt'])
    async def decypher(self, ctx, key: str = None, *, text: str = None):
        """Decrypt encrypted messages using the same key"""
        # missing arguments
        if not key or not text:
            key, text = await self.process_input(ctx, "decrypt")
            if not key:
                return
        
        # from codeblocks if present
        key = self.extract_from_codeblock(key)
        text = self.extract_from_codeblock(text)
        
        # check that boy
        if len(text) > 2000:
            return await ctx.reply("```Text too long (max 2000 chars)```")
        
        if len(key) > 50:
            return await ctx.reply("```Key too long (max 50 chars)```")
        
        if len(key) < 3:
            return await ctx.reply("```Key too short (min 3 chars)```")
        
        # cipher mapping and decrypt
        try:
            _, decrypt_map = self.generate_cipher_mapping(key)
            decrypted_text = text.translate(decrypt_map)
            
            embed = nextcord.Embed(color=0x2b2d31)
            embed.add_field(name="Key", value=f"`{key[:50]}`", inline=False)
            embed.add_field(name="Encrypted", value=self.wrap_in_codeblock(text[:1900]), inline=False)
            embed.add_field(name="Decrypted", value=self.wrap_in_codeblock(decrypted_text), inline=False)
            
            await ctx.author.send(embed=embed)
            if isinstance(ctx.channel, TextChannel):
                await ctx.reply("✅ Decryption complete - check your DMs", mention_author=False)
        
        except Exception as e:
            await ctx.reply(f"```Decryption failed: {str(e)} (wrong key?)```")

    @commands.command(aliases=['testcipher'])
    async def cipher_test(self, ctx, key: str = None, *, text: str = None):
        """Test the cipher system interactively"""
        # no arguments provided, start wizard
        if not key:
            key, text = await self.process_input(ctx, "test")
            if not key:
                return
        
        await self.process_cipher_test(ctx, key, text or "Hello World! This is a test message 123.")

    async def process_cipher_test(self, ctx, key, text, user=None):
        """Process cipher test with embeds"""
        target = user or ctx.author
        
        try:
            key = self.extract_from_codeblock(key)
            text = self.extract_from_codeblock(text)
            
            # cipher mappings
            encrypt_map, decrypt_map = self.generate_cipher_mapping(key)
            
            # if text appears encrypted
            likely_encrypted = self.is_likely_encrypted(text)
            
            # base embed
            embed = nextcord.Embed(color=0x2b2d31)
            embed.add_field(name="Key", value=f"`{key}`", inline=False)
            
            if likely_encrypted:
                # double decrypt if input appears encrypted
                decrypted_once = text.translate(decrypt_map)
                decrypted_twice = decrypted_once.translate(decrypt_map)
                encrypted_version = decrypted_once.translate(encrypt_map)
                
                embed.add_field(name="Original", value=self.wrap_in_codeblock(text), inline=False)
                embed.add_field(name="First Decryption", value=self.wrap_in_codeblock(decrypted_once), inline=False)
                embed.add_field(name="Second Decryption", value=self.wrap_in_codeblock(decrypted_twice), inline=False)
                embed.add_field(name="Success", value=("✅ Round-trip successful" if encrypted_version == text else "❌ Round-trip failed"), inline=False)
                embed.set_footer(text="Input appeared encrypted - showing decryption results")
            else:
                # encryption/decryption flow
                encrypted = text.translate(encrypt_map)
                decrypted = encrypted.translate(decrypt_map)
                success = (decrypted == text)
                
                embed.add_field(name="Original", value=self.wrap_in_codeblock(text), inline=False)
                embed.add_field(name="Encrypted", value=self.wrap_in_codeblock(encrypted), inline=False)
                embed.add_field(name="Decrypted", value=self.wrap_in_codeblock(decrypted), inline=False)
                embed.add_field(name="Result", value="✅ Round-trip successful" if success else "❌ Round-trip failed", inline=False)
            
            await target.send(embed=embed)
            if isinstance(ctx.channel, TextChannel):
                reply_msg = "🔍 Test complete (encrypted input detected)" if likely_encrypted else "✅ Test complete"
                await ctx.reply(f"{reply_msg} - check your DMs", mention_author=False)
                
        except Exception as e:
            error_embed = nextcord.Embed(
                description=f"```❌ Cipher Test Failed\nError: {str(e)}```",
                color=0xe74c3c
            )
            await target.send(embed=error_embed)
            if isinstance(ctx.channel, TextChannel):
                await ctx.reply("❌ Test failed - check your DMs", mention_author=False)

    def is_likely_encrypted(self, text):
        """Heuristic to detect if text is likely encrypted"""
        # high percentage of non-alphanumeric characters
        non_alpha = sum(1 for c in text if not c.isalnum() and not c.isspace())
        ratio = non_alpha / len(text) if text else 0
        
        # unusual character distribution
        common_chars = sum(1 for c in text.lower() if c in 'etaoin shrdlu')
        uncommon_ratio = 1 - (common_chars / len(text)) if text else 0
        
        # encrypted* if:
        # 1. High non-alphanumeric ratio (>40%), or
        # 2. Very uncommon character distribution (>80% uncommon)
        return ratio > 0.4 or uncommon_ratio > 0.8

async def setup(bot):
    bot.add_cog(Cypher(bot))