import discord
from discord.ext import commands
global muted
my_file = open("muted.txt", "r")
muted = my_file.readlines()
my_file.close()
print(muted)
intents = discord.Intents.default()
intents.members = True

#Moderation Cog
class Moderation(commands.Cog):
    def _init_(self, client):
        self.client = client
    async def cog_check(self, ctx):
        #Check if user has admin role
        return ctx.author.guild_permissions.manage_messages
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        global muted
        joineduser = str(member)
        for user in muted:
            if user == joineduser:
                role = discord.utils.get(member.guild.roles, name='Muted')
                await member.add_roles(role)

    @commands.command()
    @commands.has_role("Operations Command")
    async def clean(self, ctx, amount=5):
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send("Messages have been removed!", delete_after=5)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, member : discord.Member, *, reason=None):
        await member.ban(reason=reason)
        await ctx.send(f'Banned {member.mention}')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unban(self, ctx, *, member):
        banned_users = await ctx.guild.bans()
        member_name, member_discriminator = member.split('#')

        for ban_entry in banned_users:
            user = ban_entry.user
        
            if (user.name, user.discriminator) == (member_name, member_discriminator):
                await ctx.guild.unban(user)
                await ctx.send(f'Unbanned {user.name}#{user.discriminator}')
                return
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def mute(self, ctx, *, member : discord.Member):
        global muted
        print(muted)
        guild = ctx.guild
        role = discord.utils.get(ctx.guild.roles, name='Muted')
        user = member
        await user.add_roles(role)
        user = str(user)
        print(user)
        muted.append(user)
        with open("muted.txt", "w") as f:
            for element in muted:
                f.write(element)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unmute(self, ctx, *, member : discord.Member):
        global muted
        guild = ctx.guild
        role = discord.utils.get(ctx.guild.roles, name='Muted')
        user = member
        await user.remove_roles(role)
        user = str(user)
        print(user)
        print(f'before removal: {muted}')
        muted.remove(user)
        print(f'post removal: {muted}')
        with open("muted.txt", "w") as f:
            for element in muted:
                f.write(element)

def setup(client):
    client.add_cog(Moderation(client))