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

# Store queue message reference
queue_message = None
queue_channel = None

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    global queue_message, queue_channel
    print(f'Logged in as {bot.user.name}... Press ENTER to exit.')
    
    if queue_channel_id:
        queue_channel = bot.get_channel(int(queue_channel_id))
        if queue_channel and queue_message_id:
            try:
                queue_message = await queue_channel.fetch_message(int(queue_message_id))
            except:
                queue_message = None

async def update_queue_embed():
    """Update the persistent queue embed"""
    global queue_message
    
    if not queue_channel or not queue_message_id:
        return
    
    items = db.get_queue()
    
    embed = discord.Embed(title="📺 Queue", color=discord.Color.blue())
    
    if not items:
        embed.description = "The queue is empty!"
    else:
        shows = [item for item in items if item[2] == 'show']
        movies = [item for item in items if item[2] == 'movie']
        anime = [item for item in items if item[2] == 'anime']
        
        if shows:
            shows_text = '\n'.join([f"#{item[0]} - **{item[1]}**" for item in shows])
            embed.add_field(name="📺 Shows", value=shows_text, inline=False)
        
        if movies:
            movies_text = '\n'.join([f"#{item[0]} - **{item[1]}**" for item in movies])
            embed.add_field(name="🎬 Movies", value=movies_text, inline=False)
        
        if anime:
            anime_text = '\n'.join([f"#{item[0]} - **{item[1]}**" for item in anime])
            embed.add_field(name="🎌 Anime", value=anime_text, inline=False)
    
    stats = db.get_queue_stats()
    embed.set_footer(text=f"Total: {stats.get('pending', 0)} pending | {stats.get('completed', 0)} completed")
    
    try:
        if queue_message:
            await queue_message.edit(embed=embed)
    except:
        pass

@bot.event
async def on_message(message):
    global queue_message
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
        await update_queue_embed()
    elif '(movie)' in content:
        text_before = message.content[:message.content.lower().index('(movie)')].strip()
        item_id = db.add_to_queue(text_before, 'movie', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the movie **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
        await update_queue_embed()
    elif '(anime)' in content:
        text_before = message.content[:message.content.lower().index('(anime)')].strip()
        item_id = db.add_to_queue(text_before, 'anime', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the anime **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
        await update_queue_embed()
    await bot.process_commands(message)

@bot.command()
async def undo(ctx):
    """Undo your last queue entry"""
    result = db.undo_last_entry(str(ctx.author.id))
    
    if result:
        item_id, title, category = result
        await ctx.send(f'✅ Undone! Removed **{title}** ({category}) from the queue.')
        await update_queue_embed()
    else:
        await ctx.send(f"❌ Nothing to undo! You haven't added anything to the queue yet.")

@bot.command()
async def stats(ctx):
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
@commands.is_owner()
async def setup_queue(ctx):
    """Setup the persistent queue embed (owner only)"""
    global queue_message, queue_channel
    
    queue_channel = ctx.channel
    
    embed = discord.Embed(title="📺 Queue", color=discord.Color.blue())
    embed.description = "The queue is empty!"
    embed.set_footer(text="Total: 0 pending | 0 completed")
    
    queue_message = await ctx.send(embed=embed)
    
    # Save the message ID to .env
    with open('.env', 'a') as f:
        f.write(f'\nQUEUE_CHANNEL_ID={ctx.channel.id}\n')
        f.write(f'QUEUE_MESSAGE_ID={queue_message.id}\n')
    
    await ctx.send(f"✅ Queue embed created! Message ID: {queue_message.id}")

@bot.command()
@commands.is_owner()
async def set_requests_channel(ctx):
    """Set the channel where queue requests are accepted (owner only)"""
    with open('.env', 'a') as f:
        f.write(f'\nREQUESTS_CHANNEL_ID={ctx.channel.id}\n')
    
    await ctx.send(f"✅ Requests channel set to {ctx.channel.mention}!\nOnly messages in this channel will be processed for queue requests.")

@bot.command()
@commands.is_owner()
async def reset_queue(ctx):
    """Reset the queue embed (owner only)"""
    global queue_message, queue_channel
    
    queue_message = None
    queue_channel = None
    
    # Remove old queue settings from .env
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        with open('.env', 'w') as f:
            for line in lines:
                if not line.startswith('QUEUE_CHANNEL_ID') and not line.startswith('QUEUE_MESSAGE_ID'):
                    f.write(line)
    except:
        pass
    
    await ctx.send("✅ Queue embed reset! You can now run `!setup_queue` in a new channel to create a fresh queue embed.")


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