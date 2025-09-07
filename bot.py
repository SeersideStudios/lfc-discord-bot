import os
import discord
from discord.ext import commands
from discord.utils import get
from datetime import datetime, timedelta, timezone
import json
from dotenv import load_dotenv
from discord import app_commands, Interaction

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
bot.launch_time = datetime.now(timezone.utc)

# --- Logging Helper ---
async def log_action(member, action, details, color=discord.Color.blue()):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title=action,
            description=details,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(member), icon_url=getattr(member.display_avatar, "url", ""))
        await log_channel.send(embed=embed)

# --- Message Count Tracking ---
MESSAGE_COUNT_FILE = "message_counts.json"
if os.path.exists(MESSAGE_COUNT_FILE):
    with open(MESSAGE_COUNT_FILE, "r") as f:
        message_counts = json.load(f)
else:
    message_counts = {}

# -----------------------------
# --- Events ---
# -----------------------------
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="Protecting the BETTER LFC Discord Server"))

@bot.event
async def on_member_join(member: discord.Member):
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
async def on_member_update(before: discord.Member, after: discord.Member):
    guild = after.guild
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    verified_role = guild.get_role(VERIFIED_ROLE_ID)

    new_roles = [role for role in after.roles if role not in before.roles]
    for role in new_roles:
        if role.id in ROLE_NAME_MAP:
            account_age_days = (datetime.now(timezone.utc) - after.created_at.replace(tzinfo=timezone.utc)).days
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
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Increment message count
    user_id = str(message.author.id)
    message_counts[user_id] = message_counts.get(user_id, 0) + 1
    with open(MESSAGE_COUNT_FILE, "w") as f:
        json.dump(message_counts, f)

    # Trusted Role at 5000 messages
    if message_counts[user_id] >= 5000:
        trusted_role = message.guild.get_role(TRUSTED_ROLE_ID)
        if trusted_role and trusted_role not in message.author.roles:
            await message.author.add_roles(trusted_role)
            await log_action(message.author, "Trusted Role Granted",
                             f"{message.author.mention} has been granted the Trusted role for sending {message_counts[user_id]} messages!",
                             color=discord.Color.green())

    await bot.process_commands(message)

# -----------------------------
# --- Helper Check for Staff ---
# -----------------------------
def is_staff(member: discord.Member):
    return any(role.id in STAFF_ROLE_IDS.values() for role in member.roles)

def can_ban(member: discord.Member):
    return is_staff(member) and TRIAL_MOD_BAN_EXCLUDED not in [role.id for role in member.roles]


# Slash Help
@bot.tree.command(name="help", description="Show all commands & info", guild=discord.Object(id=GUILD_ID))
async def help_slash(interaction: Interaction):
    embed = discord.Embed(
        title="LFC Bot Commands & Info",
        color=discord.Color.green(),
        description="Here’s a guide to all the bot commands and features!"
    )

    embed.add_field(
        name="🛡️ Moderation Commands",
        value=(
            "/kick @user [reason] — Kick a user from the server (Staff only)\n"
            "/ban @user [reason] — Ban a user (Staff only; Trial Mod cannot ban)\n"
            "/timeout @user [duration] [reason] — Timeout a user (Staff only)\n"
            "/purge [number] — Delete messages in a channel (Staff only)\n"
            "/lock — Lock the current channel (Staff only)\n"
            "/unlock — Unlock the current channel (Staff only)"
        ),
        inline=False
    )

    embed.add_field(
        name="📝 Utility Commands",
        value=(
            "/say [message] — Make the bot say something (Staff only)\n"
            "/embed [title] | [description] — Create an embed message (Staff only)\n"
            "/help — Show this commands list"
        ),
        inline=False
    )

    embed.add_field(
        name="👑 Roles & Verification",
        value=(
            "• Verified Role: Automatically given to accounts older than 30 days when they choose a club/league.\n"
            "• Unverified Role: Removed automatically when Verified role is assigned.\n"
            "• Auto Roles: Everyone gets the 25/26 season role on join.\n"
            "• Club/League Roles: Assigned automatically from prejoin questions (PL, Ligue 1, Serie A, etc.) and auto-naming updates nickname to Name | Club/League.\n"
            "• Trusted Role: Granted after sending 5000 messages.\n"
            "• Account Age Check: Only accounts older than 30 days are auto-verified; younger accounts remain unverified until manually checked."
        ),
        inline=False
    )

    embed.add_field(
        name="📜 Logging",
        value=(
            "• Bot logs all moderation actions (kick, ban, timeout, purge, lock/unlock) to the designated log channel.\n"
            "• Also logs auto-verification, nickname changes, and role assignments.\n"
            "• Verified logs include account creation date and age for staff to manually verify."
        ),
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# -----------------------------
# --- Slash Commands ---
# -----------------------------
@bot.tree.command(name="ping", description="Check bot latency & uptime", guild=discord.Object(id=GUILD_ID))
async def ping_slash(interaction: Interaction):
    latency = round(bot.latency * 1000)
    uptime = datetime.now(timezone.utc) - bot.launch_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    await interaction.response.send_message(
        f"Pong! 🏓\nLatency: `{latency}ms`\nUptime: `{days}d {hours}h {minutes}m {seconds}s`"
    )

@bot.tree.command(name="kick", description="Kick a user", guild=discord.Object(id=GUILD_ID))
async def kick_slash(interaction: Interaction, member: discord.Member, reason: str = None):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ Cannot kick someone with equal/higher role.", ephemeral=True)
        return
    await member.kick(reason=reason)
    await log_action(member, "Kick", f"{interaction.user.mention} kicked {member.mention}\nReason: {reason}", color=discord.Color.orange())
    await interaction.response.send_message(f"{member.mention} has been kicked.")

@bot.tree.command(name="ban", description="Ban a user", guild=discord.Object(id=GUILD_ID))
async def ban_slash(interaction: Interaction, member: discord.Member, reason: str = None):
    if not can_ban(interaction.user):
        await interaction.response.send_message("❌ You cannot use the ban command.", ephemeral=True)
        return
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ Cannot ban someone with equal/higher role.", ephemeral=True)
        return
    await member.ban(reason=reason)
    await log_action(member, "Ban", f"{interaction.user.mention} banned {member.mention}\nReason: {reason}", color=discord.Color.red())
    await interaction.response.send_message(f"{member.mention} has been banned.")

@bot.tree.command(name="timeout", description="Timeout a user", guild=discord.Object(id=GUILD_ID))
async def timeout_slash(interaction: Interaction, member: discord.Member, duration: str, reason: str = None):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    if interaction.user.id == member.id:
        await interaction.response.send_message("❌ You can't timeout yourself!", ephemeral=True)
        return

    unit = duration[-1].lower()
    try:
        amount = int(duration[:-1])
    except ValueError:
        await interaction.response.send_message("❌ Invalid duration format!", ephemeral=True)
        return

    delta = {"s": timedelta(seconds=amount),
             "m": timedelta(minutes=amount),
             "h": timedelta(hours=amount),
             "d": timedelta(days=amount)}.get(unit)

    if not delta:
        await interaction.response.send_message("❌ Invalid duration unit! Use s, m, h, or d.", ephemeral=True)
        return

    until_time = datetime.now(timezone.utc) + delta
    await member.edit(timed_out_until=until_time, reason=reason)
    await log_action(member, "Timeout", f"{interaction.user.mention} timed out {member.mention} for {duration}. Reason: {reason}", color=discord.Color.orange())
    await interaction.response.send_message(f"{member.mention} has been timed out for {duration}. Reason: {reason}")

@bot.tree.command(name="purge", description="Delete messages", guild=discord.Object(id=GUILD_ID))
async def purge_slash(interaction: Interaction, amount: int):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=amount)
    await log_action(interaction.user, "Purge", f"{interaction.user.mention} deleted {len(deleted)} messages in {interaction.channel.mention}")
    await interaction.response.send_message(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command(name="lock", description="Lock channel", guild=discord.Object(id=GUILD_ID))
async def lock_slash(interaction: Interaction):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await log_action(interaction.user, "Channel Locked", f"{interaction.user.mention} locked {interaction.channel.mention}")
    await interaction.response.send_message(f"{interaction.channel.mention} is now locked.")

@bot.tree.command(name="unlock", description="Unlock channel", guild=discord.Object(id=GUILD_ID))
async def unlock_slash(interaction: Interaction):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await log_action(interaction.user, "Channel Unlocked", f"{interaction.user.mention} unlocked {interaction.channel.mention}")
    await interaction.response.send_message(f"{interaction.channel.mention} is now unlocked.")

@bot.tree.command(name="say", description="Bot says a message", guild=discord.Object(id=GUILD_ID))
async def say_slash(interaction: Interaction, message: str):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    await interaction.channel.send(message)
    await log_action(interaction.user, "Say", f"{interaction.user.mention} used /say: {message}")
    await interaction.response.send_message("✅ Message sent.", ephemeral=True)

@bot.tree.command(name="embed", description="Create an embed", guild=discord.Object(id=GUILD_ID))
async def embed_slash(interaction: Interaction, title: str, description: str):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        return
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
    await interaction.channel.send(embed=embed)
    await log_action(interaction.user, "Embed", f"{interaction.user.mention} sent an embed titled '{title}'")
    await interaction.response.send_message("✅ Embed sent.", ephemeral=True)

# -----------------------------
# --- Help Commands ---
# -----------------------------
# Prefix Help
@bot.command(name="help")
async def help_prefix(ctx):
    embed = discord.Embed(
        title="LFC Bot Commands & Info",
        color=discord.Color.green(),
        description="Here’s a guide to all the bot commands and features!"
    )

    # Moderation
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

    # Utility
    embed.add_field(
        name="📝 Utility Commands",
        value=(
            "+say [message] — Make the bot say something (Staff only)\n"
            "+embed [title] | [description] — Create an embed message (Staff only)\n"
            "+help — Show this commands list"
        ),
        inline=False
    )

    # Roles & Verification
    embed.add_field(
        name="👑 Roles & Verification",
        value=(
            "• Verified Role: Automatically given to accounts older than 30 days when they choose a club/league.\n"
            "• Unverified Role: Removed automatically when Verified role is assigned.\n"
            "• Auto Roles: Everyone gets the 25/26 season role on join.\n"
            "• Club/League Roles: Assigned automatically from prejoin questions (PL, Ligue 1, Serie A, etc.) and auto-naming updates nickname to Name | Club/League.\n"
            "• Trusted Role: Granted after sending 5000 messages.\n"
            "• Account Age Check: Only accounts older than 30 days are auto-verified; younger accounts remain unverified until manually checked."
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

    embed.set_footer(text="Use slash commands with / as well!")
    await ctx.send(embed=embed)

# -----------------------------
# --- Prefix Commands ---
# -----------------------------
@bot.command(name="ping")
async def ping_prefix(ctx):
    latency = round(bot.latency * 1000)
    uptime = datetime.now(timezone.utc) - bot.launch_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    await ctx.send(f"Pong! 🏓\nLatency: `{latency}ms`\nUptime: `{days}d {hours}h {minutes}m {seconds}s`")

@bot.command(name="kick")
async def kick_prefix(ctx, member: discord.Member, *, reason: str = None):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ Cannot kick someone with equal/higher role.")
        return
    await member.kick(reason=reason)
    await log_action(member, "Kick", f"{ctx.author.mention} kicked {member.mention}\nReason: {reason}", color=discord.Color.orange())
    await ctx.send(f"{member.mention} has been kicked.")

@bot.command(name="ban")
async def ban_prefix(ctx, member: discord.Member, *, reason: str = None):
    if not can_ban(ctx.author):
        await ctx.send("❌ You cannot use the ban command.")
        return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ Cannot ban someone with equal/higher role.")
        return
    await member.ban(reason=reason)
    await log_action(member, "Ban", f"{ctx.author.mention} banned {member.mention}\nReason: {reason}", color=discord.Color.red())
    await ctx.send(f"{member.mention} has been banned.")

@bot.command(name="timeout")
async def timeout_prefix(ctx, member: discord.Member, duration: str, *, reason: str = None):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    if ctx.author.id == member.id:
        await ctx.send("❌ You can't timeout yourself!")
        return

    unit = duration[-1].lower()
    try:
        amount = int(duration[:-1])
    except ValueError:
        await ctx.send(":x: Invalid duration format! Use e.g., 30s, 5m, 2h, 7d.")
        return

    delta = {"s": timedelta(seconds=amount),
             "m": timedelta(minutes=amount),
             "h": timedelta(hours=amount),
             "d": timedelta(days=amount)}.get(unit)

    if not delta:
        await ctx.send(":x: Invalid duration unit! Use s, m, h, or d.")
        return

    until_time = datetime.now(timezone.utc) + delta
    await member.edit(timed_out_until=until_time, reason=reason)
    await log_action(member, "Timeout", f"{ctx.author.mention} timed out {member.mention} for {duration}. Reason: {reason}", color=discord.Color.orange())
    await ctx.send(f"{member.mention} has been timed out for {duration}. Reason: {reason}")

@bot.command(name="purge")
async def purge_prefix(ctx, amount: int):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    deleted = await ctx.channel.purge(limit=amount)
    await log_action(ctx.author, "Purge", f"{ctx.author.mention} deleted {len(deleted)} messages in {ctx.channel.mention}")
    await ctx.send(f"✅ Deleted {len(deleted)} messages.", delete_after=5)

@bot.command(name="lock")
async def lock_prefix(ctx):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await log_action(ctx.author, "Channel Locked", f"{ctx.author.mention} locked {ctx.channel.mention}")
    await ctx.send(f"{ctx.channel.mention} is now locked.")

@bot.command(name="unlock")
async def unlock_prefix(ctx):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await log_action(ctx.author, "Channel Unlocked", f"{ctx.author.mention} unlocked {ctx.channel.mention}")
    await ctx.send(f"{ctx.channel.mention} is now unlocked.")

@bot.command(name="say")
async def say_prefix(ctx, *, message: str):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    await ctx.send(message)
    await log_action(ctx.author, "Say", f"{ctx.author.mention} used +say: {message}")

@bot.command(name="embed")
async def embed_prefix(ctx, title: str, *, description: str):
    if not is_staff(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
    await ctx.send(embed=embed)
    await log_action(ctx.author, "Embed", f"{ctx.author.mention} sent an embed titled '{title}'")

# -----------------------------
# --- Run Bot ---
# -----------------------------
bot.run(TOKEN)
