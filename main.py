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
db = QueueDatabase()

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

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

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
        
        embed = discord.Embed(title=f"📺 {cat.capitalize()} Queue", color=discord.Color.blue())
        
        if not items:
            embed.description = "The queue is empty!"
        else:
            items_text = '\n'.join([f"#{item[0]} - **{item[1]}**" for item in items])
            embed.add_field(name=f"{cat.capitalize()} Requests", value=items_text, inline=False)
        
        stats = db.get_queue_stats()
        cat_count = stats.get('by_category', {}).get(cat, 0)
        embed.set_footer(text=f"Total: {cat_count} pending")
        
        try:
            if queue_messages[cat]:
                await queue_messages[cat].edit(embed=embed)
        except:
            pass

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Only process requests in the designated channel (if set)
    if requests_channel_id and message.channel.id != int(requests_channel_id):
        # Still process commands in any channel
        await bot.process_commands(message)
        return
    
    content = message.content.lower()

    if '(show)' in content:
        text_before = message.content[:message.content.lower().index('(show)')].strip()
        item_id = db.add_to_queue(text_before, 'show', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the show **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
        await update_queue_embed('show')
    elif '(movie)' in content:
        text_before = message.content[:message.content.lower().index('(movie)')].strip()
        item_id = db.add_to_queue(text_before, 'movie', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the movie **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
        await update_queue_embed('movie')
    elif '(anime)' in content:
        text_before = message.content[:message.content.lower().index('(anime)')].strip()
        item_id = db.add_to_queue(text_before, 'anime', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the anime **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
        await update_queue_embed('anime')
    await bot.process_commands(message)

@bot.command()
async def undo(ctx):
    """Undo your last queue entry"""
    result = db.undo_last_entry(str(ctx.author.id))
    
    if result:
        item_id, title, category = result
        await ctx.send(f'✅ Undone! Removed **{title}** ({category}) from the queue.')
        await update_queue_embed(category)
    else:
        await ctx.send(f"❌ Nothing to undo! You haven't added anything to the queue yet.")

@bot.command()
async def help(ctx):
    """Display available user commands"""
    embed = discord.Embed(title="📋 Queue Manager Commands", color=discord.Color.blue())
    
    embed.add_field(
        name="Add Requests",
        value="**Text (show)** - Add a show to the queue\n*Example: Breaking Bad (show)*\n\n**Text (movie)** - Add a movie to the queue\n*Example: The Matrix (movie)*\n\n**Text (anime)** - Add an anime to the queue\n*Example: Death Note (anime)*",
        inline=False
    )
    
    embed.add_field(
        name="!undo",
        value="Remove your last added request\n*Example: !undo*",
        inline=False
    )
    
    embed.add_field(
        name="!stats",
        value="View queue statistics and your contributions\n*Example: !stats*",
        inline=False
    )
    
    embed.add_field(
        name="!remove <id>",
        value="Mark an item as completed\n*Example: !remove 5*",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def helpadmin(ctx):
    """Display available admin commands"""
    embed = discord.Embed(title="🔧 Admin Commands", color=discord.Color.red())
    
    embed.add_field(
        name="!setupqueue <category>",
        value="Setup a persistent queue embed for a category\n*Categories: show, movie, anime*\n*Example: !setupqueue show*",
        inline=False
    )
    
    embed.add_field(
        name="!setrequestschannel",
        value="Set the channel where users can add requests\n*Example: !setrequestschannel*",
        inline=False
    )
    
    embed.add_field(
        name="!resetqueue <category>",
        value="Reset a queue embed for a specific category\n*Categories: show, movie, anime*\n*Example: !resetqueue show*",
        inline=False
    )
    
    embed.add_field(
        name="!resetallqueues",
        value="Reset all queue embeds at once\n*Example: !resetallqueues*",
        inline=False
    )
    
    await ctx.send(embed=embed)
    """Display queue statistics"""
    stats = db.get_queue_stats()
    user_stats = db.get_user_stats(str(ctx.author.id))
    
    embed = discord.Embed(title="📊 Queue Statistics", color=discord.Color.green())
    embed.add_field(name="Pending Items", value=stats.get('pending', 0), inline=True)
    embed.add_field(name="Completed Items", value=stats.get('completed', 0), inline=True)
    
    if stats.get('by_category'):
        categories = '\n'.join([f"**{cat}**: {count}" for cat, count in stats['by_category'].items()])
        embed.add_field(name="By Category", value=categories, inline=False)
    
    if user_stats:
        embed.add_field(name="Your Contributions", value=f"**{user_stats[1]}** items added", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def remove(ctx, item_id: int):
    """Remove an item from the queue (completed)"""
    if db.remove_from_queue(item_id):
        await ctx.send(f"✅ Item #{item_id} marked as completed!")
        await update_queue_embed()
    else:
        await ctx.send(f"❌ Could not remove item #{item_id}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setupqueue(ctx, category: str):
    """Setup the persistent queue embed for a category (show/movie/anime) (owner only)"""
    global queue_messages, queue_channels
    
    category = category.lower()
    if category not in ['show', 'movie', 'anime']:
        await ctx.send("❌ Category must be: show, movie, or anime")
        return
    
    queue_channels[category] = ctx.channel
    
    embed = discord.Embed(title=f"📺 {category.capitalize()} Queue", color=discord.Color.blue())
    embed.description = "The queue is empty!"
    embed.set_footer(text="Total: 0 pending")
    
    queue_messages[category] = await ctx.send(embed=embed)
    
    # Save the message ID to .env
    with open('.env', 'a') as f:
        f.write(f'\nQUEUE_{category.upper()}_CHANNEL_ID={ctx.channel.id}\n')
        f.write(f'QUEUE_{category.upper()}_MESSAGE_ID={queue_messages[category].id}\n')
    
    await ctx.send(f"✅ {category.capitalize()} queue embed created!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setrequestschannel(ctx):
    """Set the channel where queue requests are accepted (owner only)"""
    with open('.env', 'a') as f:
        f.write(f'\nREQUESTS_CHANNEL_ID={ctx.channel.id}\n')
    
    await ctx.send(f"✅ Requests channel set to {ctx.channel.mention}!\nOnly messages in this channel will be processed for queue requests.")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetqueue(ctx, category: str = None):
    """Reset queue embed(s) - specify show/movie/anime or leave blank to reset one (owner only)"""
    global queue_messages, queue_channels
    
    if category:
        category = category.lower()
        if category not in ['show', 'movie', 'anime']:
            await ctx.send("❌ Category must be: show, movie, or anime")
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
    else:
        await ctx.send("❌ Please specify a category: show, movie, or anime\nExample: `!resetqueue show`")

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