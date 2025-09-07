import os
import discord
from discord.ext import commands
from discord.utils import get
from datetime import datetime
import json
from dotenv import load_dotenv
from discord import app_commands

# --- Load .env ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

# --- Role & Channel IDs ---
UNVERIFIED_ROLE_ID = 816809420222234624
VERIFIED_ROLE_ID = 801939332004839424
AUTOROLE_ID = 1405803005235953704
TRUSTED_ROLE_ID = 811019152533356574
LOG_CHANNEL_ID = 1414135252380553357

# Staff Roles
STAFF_ROLE_IDS = {
    "trial_mod": 1413202670033965097,
    "staff": 802672046659993670,
    "manager": 802671985796710460,
    "ex_chairman": 968604883668312095,
    "head_manager": 1412887734976254032,
    "chairman": 802671745332412456,
    "founder": 1402031729820172400
}
TRIAL_MOD_BAN_EXCLUDED = STAFF_ROLE_IDS["trial_mod"]

# Club/League roles for auto-naming
ROLE_NAME_MAP = {
    1414131263987646464: "Ligue 1",
    1414131190335803463: "Serie A",
    1414130964912930857: "Bundesliga",
    1414131059397890110: "La Liga",
    1414130805621522472: "PL",
    802687773672472656: "Manc",
    812773738696278047: "Everton",
    805526606004486144: "Neutral",
    805526893524418601: "Londoner",
    804336116760707072: "Other Club"
}

# --- Bot Setup ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)


# --- Logging Helper ---
async def log_action(member, action, details, color=discord.Color.blue()):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title=action, description=details, color=color, timestamp=datetime.utcnow())
        embed.set_author(name=str(member), icon_url=getattr(member.display_avatar, "url", ""))
        await log_channel.send(embed=embed)

# --- Check Staff Permissions ---
def is_staff(ctx):
    return any(role.id in STAFF_ROLE_IDS.values() for role in ctx.author.roles)

def can_ban(ctx):
    return any(role.id in STAFF_ROLE_IDS.values() and role.id != TRIAL_MOD_BAN_EXCLUDED for role in ctx.author.roles)

# --- Message Count Tracking for Trusted Role ---
MESSAGE_COUNT_FILE = "message_counts.json"
if os.path.exists(MESSAGE_COUNT_FILE):
    with open(MESSAGE_COUNT_FILE, "r") as f:
        message_counts = json.load(f)
else:
    message_counts = {}

# --- Events ---
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="Protecting the BETTER LFC Discord Server"))


@bot.event
async def on_member_join(member):
    guild = member.guild
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    autorole = guild.get_role(AUTOROLE_ID)

    if unverified_role:
        await member.add_roles(unverified_role)
    if autorole:
        await member.add_roles(autorole)

    await log_action(member, "New Member Joined",
                     f"{member.mention} joined the server.\nUnverified + Season role applied.",
                     color=discord.Color.yellow())

@bot.event
async def on_member_update(before, after):
    guild = after.guild
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    verified_role = guild.get_role(VERIFIED_ROLE_ID)

    new_roles = [role for role in after.roles if role not in before.roles]
    for role in new_roles:
        if role.id in ROLE_NAME_MAP:
            account_age_days = (datetime.utcnow() - after.created_at.replace(tzinfo=None)).days
            if account_age_days < 30:
                await log_action(after, "Verification Skipped",
                                 f"{after.mention} received {role.name} role but account is only {account_age_days} days old.",
                                 color=discord.Color.orange())
                return

            if unverified_role in after.roles:
                await after.remove_roles(unverified_role)
            if verified_role not in after.roles:
                await after.add_roles(verified_role)

            new_nick = f"{after.name} | {ROLE_NAME_MAP[role.id]}"
            try:
                await after.edit(nick=new_nick)
            except discord.Forbidden:
                await log_action(after, "Nickname Change Failed",
                                 f"Could not rename {after.mention} to '{new_nick}'.",
                                 color=discord.Color.red())

            await log_action(after, "Member Verified",
                             f"{after.mention} verified automatically.\n"
                             f"Account created: {after.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')} ({account_age_days} days old).\n"
                             f"Role assigned: {role.name}\nNickname set: {new_nick}",
                             color=discord.Color.green())

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Increment message count
    user_id = str(message.author.id)
    message_counts[user_id] = message_counts.get(user_id, 0) + 1
    with open(MESSAGE_COUNT_FILE, "w") as f:
        json.dump(message_counts, f)

    # Assign Trusted Role at 5000 messages
    if message_counts[user_id] >= 5000:
        trusted_role = message.guild.get_role(TRUSTED_ROLE_ID)
        if trusted_role and trusted_role not in message.author.roles:
            await message.author.add_roles(trusted_role)
            await log_action(message.author, "Trusted Role Granted",
                             f"{message.author.mention} has been granted the Trusted role for sending {message_counts[user_id]} messages!",
                             color=discord.Color.green())

    await bot.process_commands(message)

# --- Moderation Commands ---
@bot.command()
@commands.check(is_staff)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await log_action(member, "Kick", f"{ctx.author.mention} kicked {member.mention}\nReason: {reason}", color=discord.Color.orange())
    await ctx.send(f"{member.mention} has been kicked.")

@bot.command()
@commands.check(can_ban)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await log_action(member, "Ban", f"{ctx.author.mention} banned {member.mention}\nReason: {reason}", color=discord.Color.red())
    await ctx.send(f"{member.mention} has been banned.")

@bot.command()
@commands.check(is_staff)
async def timeout(ctx, member: discord.Member, duration: int, *, reason=None):
    await member.timeout(duration=duration, reason=reason)
    await log_action(member, "Timeout", f"{ctx.author.mention} timed out {member.mention} for {duration}s\nReason: {reason}")
    await ctx.send(f"{member.mention} has been timed out for {duration}s.")

@bot.command()
@commands.check(is_staff)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await log_action(ctx.author, "Purge", f"{ctx.author.mention} deleted {len(deleted)} messages in {ctx.channel.mention}")
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

@bot.command()
@commands.check(is_staff)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await log_action(ctx.author, "Channel Locked", f"{ctx.author.mention} locked {ctx.channel.mention}")
    await ctx.send(f"{ctx.channel.mention} is now locked.")

@bot.command()
@commands.check(is_staff)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await log_action(ctx.author, "Channel Unlocked", f"{ctx.author.mention} unlocked {ctx.channel.mention}")
    await ctx.send(f"{ctx.channel.mention} is now unlocked.")

# --- Slash Command ---
@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")
    
# --- Utility Commands ---
@bot.command()
@commands.check(is_staff)
async def say(ctx, *, message):
    await ctx.send(message)

@bot.command()
@commands.check(is_staff)
async def embed(ctx, *, content):
    try:
        title, description = map(str.strip, content.split("|", 1))
        embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        await ctx.send(embed=embed)
    except:
        await ctx.send("Usage: +embed [title] | [description]")

# --- Custom Help Command ---
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="LFC Bot Commands & Info", color=discord.Color.green())
    
    # Moderation Commands
    embed.add_field(
        name="🛡️ Moderation Commands",
        value=(
            "+kick @user [reason] — Kick a user from the server (Staff only)\n"
            "+ban @user [reason] — Ban a user (Staff only; Trial Mod cannot ban)\n"
            "+timeout @user [duration] [reason] — Timeout a user (Staff only)\n"
            "+purge [number] — Delete messages in a channel (Staff only)\n"
            "+lock — Lock the current channel (Staff only)\n"
            "+unlock — Unlock the current channel (Staff only)"
        ),
        inline=False
    )

    # Utility Commands
    embed.add_field(
        name="📝 Utility Commands",
        value=(
            "+say [message] — Make the bot say something (Staff only)\n"
            "+embed [title] | [description] — Create an embed message (Staff only)\n"
            "+help — Show this commands list"
        ),
        inline=False
    )

    # Roles & Verification Info
    embed.add_field(
        name="👑 Roles & Verification",
        value=(
            "• **Verified Role:** Automatically given to accounts older than 30 days when they choose a club/league in the prejoin menu.\n"
            "• **Unverified Role:** Removed automatically when Verified role is assigned.\n"
            "• **Auto Roles:** Everyone gets the 25/26 season role on join.\n"
            "• **Club/League Roles:** Assigned automatically from prejoin questions (e.g., PL, Ligue 1, Serie A, etc.) and auto-naming updates nickname to `Name | Club/League`.\n"
            "• **Trusted Role:** Granted after sending 5000 messages.\n"
            "• **Account Age Check:** Only accounts older than 30 days are auto-verified; younger accounts remain unverified until manually checked."
        ),
        inline=False
    )

    # Logging
    embed.add_field(
        name="📜 Logging",
        value=(
            "• Bot logs all moderation actions (kick, ban, timeout, purge, lock/unlock) to the designated log channel.\n"
            "• Also logs auto-verification, nickname changes, and role assignments.\n"
            "• Verified logs include account creation date and age for staff to manually verify."
        ),
        inline=False
    )


    await ctx.send(embed=embed)

# --- Run Bot ---
bot.run(TOKEN)
