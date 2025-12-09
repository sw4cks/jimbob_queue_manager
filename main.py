import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
from threading import Thread
from database import QueueDatabase

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
queue_channel_id = os.getenv('QUEUE_CHANNEL_ID')
queue_message_id = os.getenv('QUEUE_MESSAGE_ID')
requests_channel_id = os.getenv('REQUESTS_CHANNEL_ID')
dev_channel_ids = set([cid.strip() for cid in os.getenv('DEV_CHANNEL_IDS', '').split(',') if cid.strip()])
auto_delete_channels = set([cid.strip() for cid in os.getenv('AUTO_DELETE_CHANNEL_IDS', '').split(',') if cid.strip()])
db = QueueDatabase()

# Single embed color used across all bot messages
EMBED_COLOR = discord.Color(0xffc100)

VALID_CATEGORIES = {'show', 'movie', 'anime'}
USAGE_MESSAGES = {
    'setupqueue': "Usage: !setupqueue <show|movie|anime>",
    'resetqueue': "Usage: !resetqueue <show|movie|anime>",
    'remove': "Usage: !remove <positions> <show|movie|anime> (e.g., !remove 1,2 anime)",
    'clearqueue': "Usage: !clearqueue <show|movie|anime>",
    'refresh': "Usage: !refresh [show|movie|anime]",
    'setcommandautodelete': "Usage: !setcommandautodelete <on|off>",
    'setdevchannel': "Usage: !setdevchannel [on|off]",
    'setstatus': "Usage: !setstatus <position> <show|movie|anime> <note>",
    'delstatus': "Usage: !delstatus <position> <show|movie|anime>",
    'toggledl': "Usage: !toggledl <position> <show|movie|anime>"
}

# Store queue message references for each category
queue_messages = {
    'show': None,
    'movie': None,
    'anime': None
}
queue_channels = {
    'show': None,
    'movie': None,
    'anime': None
}

def update_env_value(key: str, value: str):
    """Write or replace a single key=value pair inside .env"""
    try:
        existing_lines = []
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                existing_lines = f.readlines()
        
        with open('.env', 'w') as f:
            prefix = f"{key}="
            for line in existing_lines:
                if not line.startswith(prefix):
                    f.write(line)
            f.write(f"{key}={value}\n")
    except Exception as e:
        print(f"Error updating {key} in .env: {e}")

def serialize_id_set(values: set) -> str:
    """Serialize a set of string ids into a stable, comma-separated list"""
    return ','.join(sorted(values))

async def acknowledge_command(ctx):
    """Handle command acknowledgements, respecting auto-delete channels"""
    if str(ctx.channel.id) in auto_delete_channels:
        try:
            await ctx.message.delete()
        except Exception:
            pass
    else:
        try:
            await ctx.message.add_reaction("✅")
        except Exception:
            pass

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Disable default help so we can register our custom help command
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    global queue_messages, queue_channels
    print(f'Logged in as {bot.user.name}... Press ENTER to exit.')
    
    for category in ['show', 'movie', 'anime']:
        channel_id = os.getenv(f'QUEUE_{category.upper()}_CHANNEL_ID')
        message_id = os.getenv(f'QUEUE_{category.upper()}_MESSAGE_ID')
        
        if channel_id and message_id:
            queue_channels[category] = bot.get_channel(int(channel_id))
            if queue_channels[category]:
                try:
                    queue_messages[category] = await queue_channels[category].fetch_message(int(message_id))
                except:
                    queue_messages[category] = None

async def update_queue_embed(category: str = None):
    """Update the persistent queue embed for a specific category"""
    global queue_messages
    
    if category:
        categories = [category.lower()]
    else:
        categories = ['show', 'movie', 'anime']
    
    for cat in categories:
        if not queue_channels.get(cat):
            continue
        
        items = db.get_queue(cat)
        
        embed = discord.Embed(title=f"📺 {cat.capitalize()} Queue", color=EMBED_COLOR)
        
        if not items:
            embed.description = "The queue is empty!"
        else:
            downloading = [item for item in items if item[-1] == 1]
            pending = [item for item in items if item[-1] == 0]
            
            lines = []
            counter = 1
            
            if downloading:
                lines.append("__**Downloading...**__")
                for item in downloading:
                    title = item[1]
                    note = item[6] if item[6] else ""
                    suffix = f" - _{note}_" if note else ""
                    lines.append(f"#{counter} - **{title}**{suffix}")
                    counter += 1
            
            if pending:
                lines.append("__**Pending...**__")
                for item in pending:
                    title = item[1]
                    note = item[6] if item[6] else ""
                    suffix = f" - _{note}_" if note else ""
                    lines.append(f"#{counter} - **{title}**{suffix}")
                    counter += 1
            
            items_text = '\n'.join(lines)
            embed.description = items_text
        
        pending_count = len([item for item in items if item[-1] == 0])
        downloading_count = len([item for item in items if item[-1] == 1])
        if downloading_count > 0:
            footer_text = f"{pending_count} pending · {downloading_count} downloading"
        else:
            footer_text = f"{pending_count} pending"
        embed.set_footer(text=footer_text)
        
        try:
            if queue_messages[cat]:
                await queue_messages[cat].edit(embed=embed)
        except:
            pass

def get_category_items(category: str):
    """Return ordered active items (downloading first) for a category"""
    return db.get_queue(category)

def get_item_by_position(category: str, position: int):
    """Get queue item tuple by visible position number"""
    items = get_category_items(category)
    if position < 1 or position > len(items):
        return None, items
    return items[position - 1], items

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Only process requests in the designated channel (if set)
    allowed_channels = set(dev_channel_ids)
    if requests_channel_id:
        allowed_channels.add(str(requests_channel_id))
    if requests_channel_id and str(message.channel.id) not in allowed_channels:
        # Still process commands in any channel
        await bot.process_commands(message)
        return
    
    content = message.content.lower()

    if '(show)' in content:
        text_before = message.content[:message.content.lower().index('(show)')].strip()
        item_id = db.add_to_queue(text_before, 'show', str(message.author.id), message.author.name)
        try:
            await message.add_reaction("✅")
        except Exception:
            pass
        await update_queue_embed('show')
    elif '(movie)' in content:
        text_before = message.content[:message.content.lower().index('(movie)')].strip()
        item_id = db.add_to_queue(text_before, 'movie', str(message.author.id), message.author.name)
        try:
            await message.add_reaction("✅")
        except Exception:
            pass
        await update_queue_embed('movie')
    elif '(anime)' in content:
        text_before = message.content[:message.content.lower().index('(anime)')].strip()
        item_id = db.add_to_queue(text_before, 'anime', str(message.author.id), message.author.name)
        try:
            await message.add_reaction("✅")
        except Exception:
            pass
        await update_queue_embed('anime')
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    """Return usage hints when required parameters are missing or invalid."""
    usage = USAGE_MESSAGES.get(getattr(ctx.command, "name", ""), None)
    
    if isinstance(error, commands.MissingRequiredArgument):
        if usage:
            await ctx.send(f"❌ Incorrect usage. {usage}")
            return
    if isinstance(error, (commands.BadArgument, commands.TooManyArguments)):
        if usage:
            await ctx.send(f"❌ Incorrect usage. {usage}")
            return
    
    # Re-raise unhandled errors so they don't fail silently
    raise error

@bot.event
async def on_command_completion(ctx):
    """Clean up commands in auto-delete channels after successful execution"""
    if str(ctx.channel.id) in auto_delete_channels:
        try:
            await ctx.message.delete()
        except Exception:
            pass

@bot.command()
async def undo(ctx):
    """Undo your last queue entry"""
    result = db.undo_last_entry(str(ctx.author.id))
    
    if result:
        item_id, title, category = result
        await acknowledge_command(ctx)
        await update_queue_embed(category)
    else:
        await ctx.send(f"ƒ?O Nothing to undo! You haven't added anything to the queue yet.")

@bot.command()
async def help(ctx):
    """Display available user commands"""
    embed = discord.Embed(title="📋 Queue Manager Commands", color=EMBED_COLOR)
    
    embed.add_field(
        name="__**Add Requests**__",
        value="**Text (show)** - Add a show to the queue\n*Example: Breaking Bad (show)*\n\n**Text (movie)** - Add a movie to the queue\n*Example: The Matrix (movie)*\n\n**Text (anime)** - Add an anime to the queue\n*Example: Death Note (anime)*",
        inline=False
    )
    
    embed.add_field(
        name="__**Manage Your Requests**__",
        value="**!undo** - Remove your last added request\n*Example: !undo*\n\n**!remove <positions> <category>** - Mark one or more items as completed\n*Example: !remove 1,2,3 anime*",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def helpadmin(ctx):
    """Display available admin commands"""
    embed = discord.Embed(title="🔧 Admin Commands", color=EMBED_COLOR)
    
    embed.add_field(
        name="__**Setup & Channels**__",
        value="**!setupqueue <category>** - Create a queue embed in this channel\n**!setrequestschannel** - Set channel for user submissions\n**!setdevchannel [on|off]** - Allow/deny this channel as an extra requests channel\n**!setcommandautodelete [on|off]** - Auto-delete successful commands here",
        inline=False
    )
    
    embed.add_field(
        name="__**Queue Control**__",
        value="**!resetqueue <category>** - Reset a queue embed\n**!clearqueue <category>** - Clear all pending items\n**!resetallqueues** - Reset all queue embeds\n**!refresh [category]** - Manually refresh embeds",
        inline=False
    )

    embed.add_field(
        name="__**Statuses & Downloading**__",
        value="**!setstatus <pos> <category> <note>** - Add or overwrite a status note\n**!delstatus <pos> <category>** - Remove a status note\n**!toggledl <pos> <category>** - Move an entry between downloading/pending",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def remove(ctx, *, args: str):
    """Remove one or more items from a category queue (completed)"""
    if not args:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['remove']}")
        return
    
    parts = [part.strip() for part in args.replace(',', ' ').split() if part.strip()]
    if len(parts) < 2:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['remove']}")
        return
    
    category = parts[-1].lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['remove']}")
        return
    
    position_parts = parts[:-1]
    try:
        positions = sorted({int(p) for p in position_parts})
    except ValueError:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['remove']}")
        return
    
    items = db.get_queue(category)
    if not items:
        await ctx.send(f"❌ The {category} queue is empty.")
        return
    
    max_pos = len(items)
    invalid_positions = [p for p in positions if p < 1 or p > max_pos]
    if invalid_positions:
        await ctx.send(f"❌ Positions not found in the {category} queue: {', '.join(map(str, invalid_positions))}")
        return
    
    is_admin = ctx.author.guild_permissions.administrator
    user_id = str(ctx.author.id)
    
    # Map positions to items (1-based)
    selected_items = [(p, items[p - 1]) for p in positions]
    
    if not is_admin:
        unauthorized = [p for p, item in selected_items if item[3] != user_id]
        if unauthorized:
            await ctx.send("❌ You can't remove a request that isn't yours.")
            return
    
    removed_titles = []
    failed_positions = []
    for pos, item in selected_items:
        item_id, title = item[0], item[1]
        if db.remove_from_queue(item_id):
            removed_titles.append((pos, title))
        else:
            failed_positions.append(pos)
    
    if removed_titles:
        await acknowledge_command(ctx)
        await update_queue_embed(category)

    
    if failed_positions:
        await ctx.send(f"❌ Could not remove positions: {', '.join(map(str, failed_positions))}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setstatus(ctx, position: int = None, category: str = None, *, note: str = None):
    """Add or overwrite a status note on a queue entry"""
    if position is None or category is None or note is None:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['setstatus']}")
        return
    
    category = category.lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['setstatus']}")
        return
    
    item, items = get_item_by_position(category, position)
    if not item:
        await ctx.send(f"❌ Position not found. {USAGE_MESSAGES['setstatus']}")
        return
    
    updated = db.set_status_note(item[0], note)
    if not updated:
        await ctx.send("❌ Could not update status for that entry.")
        return
    
    await acknowledge_command(ctx)
    await update_queue_embed(category)

@bot.command()
@commands.has_permissions(administrator=True)
async def delstatus(ctx, position: int = None, category: str = None):
    """Remove a status note from a queue entry"""
    if position is None or category is None:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['delstatus']}")
        return
    
    category = category.lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['delstatus']}")
        return
    
    item, items = get_item_by_position(category, position)
    if not item:
        await ctx.send(f"❌ Position not found. {USAGE_MESSAGES['delstatus']}")
        return
    
    cleared = db.clear_status_note(item[0])
    if not cleared:
        await ctx.send("❌ Could not clear status for that entry.")
        return
    
    await acknowledge_command(ctx)
    await update_queue_embed(category)

@bot.command()
@commands.has_permissions(administrator=True)
async def toggledl(ctx, position: int = None, category: str = None):
    """Toggle a queue entry between downloading and pending"""
    if position is None or category is None:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['toggledl']}")
        return
    
    category = category.lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['toggledl']}")
        return
    
    item, items = get_item_by_position(category, position)
    if not item:
        await ctx.send(f"❌ Position not found. {USAGE_MESSAGES['toggledl']}")
        return
    
    success = db.toggle_downloading(item[0])
    if not success:
        await ctx.send("❌ Could not toggle downloading for that entry.")
        return
    
    await acknowledge_command(ctx)
    await update_queue_embed(category)

@bot.command()
@commands.has_permissions(administrator=True)
async def setupqueue(ctx, category: str):
    """Setup the persistent queue embed for a category (show/movie/anime) (owner only)"""
    global queue_messages, queue_channels
    
    category = category.lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['setupqueue']}")
        return
    
    queue_channels[category] = ctx.channel
    
    embed = discord.Embed(title=f"📺 {category.capitalize()} Queue", color=EMBED_COLOR)
    embed.description = "The queue is empty!"
    embed.set_footer(text="Total: 0 pending")
    
    queue_messages[category] = await ctx.send(embed=embed)
    
    # Save the message ID to .env
    with open('.env', 'a') as f:
        f.write(f'\nQUEUE_{category.upper()}_CHANNEL_ID={ctx.channel.id}\n')
        f.write(f'QUEUE_{category.upper()}_MESSAGE_ID={queue_messages[category].id}\n')
    
@bot.command()
@commands.has_permissions(administrator=True)
async def setrequestschannel(ctx):
    """Set the channel where queue requests are accepted (owner only)"""
    global requests_channel_id
    requests_channel_id = str(ctx.channel.id)
    
    update_env_value('REQUESTS_CHANNEL_ID', requests_channel_id)
    
    await ctx.send(f"✅ Requests channel set to {ctx.channel.mention}.\nOnly messages in this channel will be processed for queue requests.")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetqueue(ctx, category: str):
    """Reset a queue embed for a specific category (owner only)"""
    global queue_messages, queue_channels
    
    category = category.lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['resetqueue']}")
        return
    
    queue_messages[category] = None
    queue_channels[category] = None
    
    # Remove from .env
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        with open('.env', 'w') as f:
            for line in lines:
                if not line.startswith(f'QUEUE_{category.upper()}_'):
                    f.write(line)
    except:
        pass
    
    await ctx.send(f"✅ {category.capitalize()} queue embed reset! Run `!setupqueue {category}` in the new channel.")

@bot.command()
@commands.has_permissions(administrator=True)
async def clearqueue(ctx, category: str):
    """Clear all pending items in a category queue (owner only)"""
    category = category.lower()
    if category not in VALID_CATEGORIES:
        await ctx.send(f"❌ Incorrect usage. {USAGE_MESSAGES['clearqueue']}")
        return
    
    cleared = db.clear_queue(category)
    if cleared == 0:
        await ctx.send(f"ℹ️ The {category} queue is already empty.")
    else:
        await ctx.send(f"✅ Cleared {cleared} item(s) from the {category} queue.")
    await update_queue_embed(category)

@bot.command()
@commands.has_permissions(administrator=True)
async def resetallqueues(ctx):
    """Reset all queue embeds (owner only)"""
    global queue_messages, queue_channels
    
    for category in ['show', 'movie', 'anime']:
        queue_messages[category] = None
        queue_channels[category] = None
    
    # Remove all queue settings from .env
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        with open('.env', 'w') as f:
            for line in lines:
                if not line.startswith('QUEUE_'):
                    f.write(line)
    except:
        pass
    
    await ctx.send("✅ All queue embeds reset! Run `!setupqueue show`, `!setupqueue movie`, and `!setupqueue anime` in your desired channels.")



@bot.command()
@commands.has_permissions(administrator=True)
async def refresh(ctx, category: str = None):
    """Manually refresh queue embeds for all or one category (admin only)"""
    if category:
        category = category.lower()
        if category not in VALID_CATEGORIES:
            await ctx.send(f"\u274c Incorrect usage. {USAGE_MESSAGES['refresh']}")
            return
    await update_queue_embed(category)
    await acknowledge_command(ctx)

@bot.command()
@commands.has_permissions(administrator=True)
async def setdevchannel(ctx, state: str = "on"):
    """Allow or block this channel as an additional requests channel (admin only)"""
    global dev_channel_ids
    
    channel_id = str(ctx.channel.id)
    state = state.lower()
    
    if state in ['off', 'disable', 'disabled']:
        if channel_id in dev_channel_ids:
            dev_channel_ids.remove(channel_id)
            update_env_value('DEV_CHANNEL_IDS', serialize_id_set(dev_channel_ids))
            await ctx.send(f"\u2705 {ctx.channel.mention} is no longer a requests override channel.")
        else:
            await ctx.send("\u274c This channel is not currently enabled as a requests override.")
        return
    
    if state not in ['on', 'enable', 'enabled']:
        await ctx.send(f"\u274c Incorrect usage. {USAGE_MESSAGES['setdevchannel']}")
        return
    
    if channel_id in dev_channel_ids:
        await ctx.send("\u274c This channel is already enabled as a requests override.")
        return
    
    dev_channel_ids.add(channel_id)
    update_env_value('DEV_CHANNEL_IDS', serialize_id_set(dev_channel_ids))
    await ctx.send(f"\u2705 {ctx.channel.mention} can now accept queue requests alongside the main requests channel.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setcommandautodelete(ctx, state: str = "on"):
    """Toggle auto-deleting successful commands in this channel (admin only)"""
    global auto_delete_channels
    
    channel_id = str(ctx.channel.id)
    state = state.lower()
    should_cleanup = channel_id in auto_delete_channels
    
    if state in ['off', 'disable', 'disabled']:
        if channel_id in auto_delete_channels:
            auto_delete_channels.remove(channel_id)
            update_env_value('AUTO_DELETE_CHANNEL_IDS', serialize_id_set(auto_delete_channels))
            await ctx.send(f"\u2705 Auto-delete for commands disabled in {ctx.channel.mention}.")
            if should_cleanup:
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
        else:
            await ctx.send("\u274c Auto-delete is not enabled for this channel.")
        return
    
    if state not in ['on', 'enable', 'enabled']:
        await ctx.send(f"\u274c Incorrect usage. {USAGE_MESSAGES['setcommandautodelete']}")
        return
    
    if channel_id in auto_delete_channels:
        await ctx.send("\u274c Auto-delete is already enabled for this channel.")
        return
    
    auto_delete_channels.add(channel_id)
    update_env_value('AUTO_DELETE_CHANNEL_IDS', serialize_id_set(auto_delete_channels))
    await ctx.send(f"\u2705 Successful commands in {ctx.channel.mention} will now be deleted.")

async def listen_for_input():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input)
    await bot.close()

async def main():
    async with bot:
        asyncio.create_task(listen_for_input())
        await bot.start(token, reconnect=True)

if __name__ == '__main__':
    asyncio.run(main())
