import nextcord
from nextcord.ext import commands
import datetime
from cogs.logging.logger import CogLogger

ROLE_MAPPING = {
    "south_bronx": {
        "owner": 1281553341100457995,
        "co-owner": 1262995584231669770,
        "admin": 1292612655261155428,
        "head mod": 1259718732163321906,
        "mod": 1266510089683079330,
        "trial mod": 1259718795556028446,
        "helper": 1362671155730972733,
        "staff": 1259728436377817100
    },
    "manhattan": {
        "owner": 1272930547714232320,
        "co-owner": 1284508891429736579,
        "admin": 1284509033369305169,
        "head mod": 1339105129936326676,
        "mod": 1284509125841256450,
        "trial mod": 1284509160775356476,
        "helper": 1370785143891165254,
        "staff": 1284504142580027533
    },
    "long_island": {
        "owner": 1312883774354100354,
        "co-owner": 1312883845393285181,
        "admin": 1312883891018793052,
        "head mod": "",
        "mod": 1312884008719487069,
        "trial mod": 1312884059537543259,
        "helper": 1370785036844142702,
        "staff": 1312899341068800121
    }
}

class SyncRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.staff_channel_id = 1259717946947670099
        self.logger = CogLogger(self.__class__.__name__)
        self.bot.launch_time = datetime.datetime.now()
        self.logger.info("SyncRoles cog initialized")
    
    async def get_target_servers(self, source_guild):
        """Get the other two servers based on the source server"""
        
        guilds = {
            "south_bronx": 1259717095382319215,
            "manhattan": 1142088882222022786,
            "long_island": 1299747094449623111
        }
        
        for guild in self.bot.guilds:
            if guild.id == 1259717095382319215:  # south_bronx
                guilds["south_bronx"] = guild
            elif guild.id == 1142088882222022786:  # manhattan
                guilds["manhattan"] = guild
            elif guild.id == 1299747094449623111:  # long_island
                guilds["long_island"] = guild
        
        # Determine which server we're syncing from
        if source_guild == guilds["south_bronx"]:
            targets = (guilds["manhattan"], guilds["long_island"])
        elif source_guild == guilds["manhattan"]:
            targets = (guilds["south_bronx"], guilds["long_island"])
        else:
            targets = (guilds["south_bronx"], guilds["manhattan"])
        
        return targets
    
    async def get_member_in_guild(self, member_id, guild):
        """Helper function to get member object in a specific guild"""
        try:
            return await guild.fetch_member(member_id)
        except nextcord.NotFound:
            self.logger.info(f"Member {member_id} not found in guild {guild.id}")
            return None
        except nextcord.Forbidden:
            self.logger.warning(f"Missing permissions to fetch members in guild {guild.id}")
            return None
        except nextcord.HTTPException as e:
            self.logger.error(f"Error fetching member {member_id} in guild {guild.id}: {e}")
            return None
    
    async def sync_roles(self, member, source_guild):
        """Sync roles from source server to target servers"""
        
        # Get the other two servers
        target_guild1, target_guild2 = await self.get_target_servers(source_guild)
        if not target_guild1 or not target_guild2:
            self.logger.warning("Could not find both target guilds")
            return
        
        # Get the member in the target servers
        target_member1 = await self.get_member_in_guild(member.id, target_guild1)
        target_member2 = await self.get_member_in_guild(member.id, target_guild2)
        
        # Get source server name
        source_server = None
        if source_guild.id == 1259717095382319215:  # south_bronx
            source_server = "south_bronx"
        elif source_guild.id == 1142088882222022786:  # manhattan
            source_server = "manhattan"
        elif source_guild.id == 1299747094449623111:  # long_island
            source_server = "long_island"
        
        if not source_server:
            self.logger.warning(f"Unknown source guild ID: {source_guild.id}")
            return
        
        
        # Get the roles the member has in the source server
        source_roles = {role.id for role in member.roles}
        roles_to_add = set()
        
        # Find which mapped roles the member has
        for role_name, role_id in ROLE_MAPPING[source_server].items():
            if role_id and role_id in source_roles:
                roles_to_add.add(role_name)
        
        
        # Sync to target servers
        for target_member, target_guild in [(target_member1, target_guild1), (target_member2, target_guild2)]:
            if not target_member:
                continue
            
            # Determine target server name
            target_server = None
            if target_guild.id == 1259717095382319215:  # south_bronx
                target_server = "south_bronx"
            elif target_guild.id == 1142088882222022786:  # manhattan
                target_server = "manhattan"
            elif target_guild.id == 1299747094449623111:  # long_island
                target_server = "long_island"
            
            if not target_server:
                self.logger.warning(f"Unknown target guild ID: {target_guild.id}")
                continue
            
            
            # Get current roles to avoid removing non-synced roles
            current_roles = {role.id for role in target_member.roles}
            new_roles = set(current_roles)
            changes_made = False
            
            # Process role removals first
            for role_name, role_id in ROLE_MAPPING[target_server].items():
                if not role_id:  # Skip empty role IDs
                    continue
                
                if role_name not in roles_to_add and int(role_id) in current_roles:
                    new_roles.discard(int(role_id))
                    changes_made = True
            
            # Process role additions
            for role_name in roles_to_add:
                role_id = ROLE_MAPPING[target_server].get(role_name)
                if not role_id:  # Skip if role doesn't exist in target server
                    continue
                
                if int(role_id) not in current_roles:
                    new_roles.add(int(role_id))
                    changes_made = True
            
            if not changes_made:
                continue
            
            # Convert role IDs back to role objects
            new_role_objects = []
            for role_id in new_roles:
                if role_id == target_guild.id:  # Skip @everyone role
                    continue
                role = target_guild.get_role(role_id)
                if role:
                    new_role_objects.append(role)
                else:
                    self.logger.warning(f"Role ID {role_id} not found in guild {target_guild.id}")
            
            try:
                await target_member.edit(roles=new_role_objects)
                self.logger.info(f"Successfully synced roles for {target_member} in {target_server}")
            except nextcord.Forbidden:
                self.logger.error(f"Missing permissions to edit roles in {target_server}")
            except nextcord.HTTPException as e:
                self.logger.error(f"Error syncing roles in {target_server}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Sync roles when a member joins any server"""
        await self.sync_roles(member, member.guild)
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Sync roles when a member's roles are updated"""
        if before.roles != after.roles:
            await self.sync_roles(after, after.guild)
    
    @commands.command(name="forcesync", aliases=["syncroles"])
    @commands.has_permissions(administrator=True)
    async def force_sync(self, ctx, member: nextcord.Member):
        """Force sync a member's roles across servers"""
        await self.sync_roles(member, ctx.guild)
        await ctx.send(f"Force-synced roles for {member.display_name}")

async def setup(bot):
    logger = CogLogger("SyncRoles")
    try:
        bot.add_cog(SyncRoles(bot))
    except Exception as e:
        logger.error(f"Failed to load SyncRoles cog: {e}")
        raise
