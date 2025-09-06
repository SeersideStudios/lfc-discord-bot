import os
import discord
from discord.ext import commands
from discord.ext.commands import has_permissions
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
VERIFIED_ROLE = int(os.getenv("VERIFIED_ROLE"))
TRUSTED_ROLE = int(os.getenv("TRUSTED_ROLE"))
TRUSTED_MESSAGE_COUNT = int(os.getenv("TRUSTED_MESSAGE_COUNT"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents)

# Track message counts
message_counts = {}

# Permissions mapping
STAFF_ROLES = {
    "trial_mod": 1413202670033965097,
    "staff": 802672046659993670,
    "manager": 802671985796710460,
    "ex_chairman": 968604883668312095,
    "head_manager": 1412887734976254032,
    "chairman": 802671745332412456,
    "founder": 1402031729820172400,
}

COMMAND_PERMS = {
    "purge": list(STAFF_ROLES.values()),
    "lock": list(STAFF_ROLES.values()),
    "unlock": list(STAFF_ROLES.values()),
    "say": list(STAFF_ROLES.values()),
    "kick": list(STAFF_ROLES.values()),
    "timeout": list(STAFF_ROLES.values()),
    "ban": [r for k, r in STAFF_ROLES.items() if k != "trial_mod"],  # everyone except trial_mod
}

def has_permission(member: discord.Member, command_name: str) -> bool:
    allowed_roles = COMMAND_PERMS.get(command_name, [])
    return any(r.id in allowed_roles for r in member.roles)

# ========== Events ==========

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    # Auto-verify if account older than 30 days
    if (datetime.now(timezone.utc) - member.created_at).days >= 30:
        role = member.guild.get_role(VERIFIED_ROLE)
        if role:
            await member.add_roles(role)
            print(f"Verified {member.name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Count messages for Trusted role
    count = message_counts.get(message.author.id, 0) + 1
    message_counts[message.author.id] = count
    if count >= TRUSTED_MESSAGE_COUNT:
        role = message.guild.get_role(TRUSTED_ROLE)
        if role and role not in message.author.roles:
            await message.author.add_roles(role)
            await message.channel.send(f"🎉 {message.author.mention} is now Trusted!")
    await bot.process_commands(message)

# ========== Commands ==========

@bot.command()
async def purge(ctx, amount: int):
    if not has_permission(ctx.author, "purge"):
        return await ctx.send("❌ No permission.")
    deleted = await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"🧹 Deleted {len(deleted)-1} messages.", delete_after=5)

@bot.command()
async def lock(ctx):
    if not has_permission(ctx.author, "lock"):
        return await ctx.send("❌ No permission.")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Channel locked.")

@bot.command()
async def unlock(ctx):
    if not has_permission(ctx.author, "unlock"):
        return await ctx.send("❌ No permission.")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Channel unlocked.")

@bot.command()
async def say(ctx, *, message):
    if not has_permission(ctx.author, "say"):
        return await ctx.send("❌ No permission.")
    await ctx.message.delete()
    await ctx.send(message)

@bot.command()
async def kick(ctx, member: discord.Member, *, reason=None):
    if not has_permission(ctx.author, "kick"):
        return await ctx.send("❌ No permission.")
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member.mention}")

@bot.command()
async def ban(ctx, member: discord.Member, *, reason=None):
    if not has_permission(ctx.author, "ban"):
        return await ctx.send("❌ No permission.")
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member.mention}")

@bot.command()
async def timeout(ctx, member: discord.Member, minutes: int):
    if not has_permission(ctx.author, "timeout"):
        return await ctx.send("❌ No permission.")
    until = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
    await member.edit(timeout=until)
    await ctx.send(f"⏳ {member.mention} timed out for {minutes} minutes.")

bot.run(TOKEN)
