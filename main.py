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
db = QueueDatabase()

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}... Press ENTER to exit.')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    content = message.content.lower()

    if '(show)' in content:
        text_before = message.content[:message.content.lower().index('(show)')].strip()
        item_id = db.add_to_queue(text_before, 'show', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the show **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
    elif '(movie)' in content:
        text_before = message.content[:message.content.lower().index('(movie)')].strip()
        item_id = db.add_to_queue(text_before, 'movie', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the movie **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
    elif '(anime)' in content:
        text_before = message.content[:message.content.lower().index('(anime)')].strip()
        item_id = db.add_to_queue(text_before, 'anime', str(message.author.id), message.author.name)
        await message.channel.send(f'{message.author.mention} has added the anime **{text_before}** to the queue!\nNot quite right? Type `!undo` and retry')
    await bot.process_commands(message)

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.command()
async def undo(ctx):
    """Undo your last queue entry"""
    result = db.undo_last_entry(str(ctx.author.id))
    
    if result:
        item_id, title, category = result
        await ctx.send(f'✅ Undone! Removed **{title}** ({category}) from the queue.')
    else:
        await ctx.send(f"❌ Nothing to undo! You haven't added anything to the queue yet.")

@bot.command()
async def queue(ctx, category: str = None):
    """Display the current queue"""
    items = db.get_queue(category.lower() if category else None)
    
    if not items:
        await ctx.send("The queue is empty!")
        return
    
    embed = discord.Embed(title="📺 Queue", color=discord.Color.blue())
    for item_id, title, cat, user_id, date, status in items:
        embed.add_field(name=f"#{item_id} - {title}", value=f"Category: **{cat}**\nAdded by: <@{user_id}>", inline=False)
    
    await ctx.send(embed=embed)

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
    else:
        await ctx.send(f"❌ Could not remove item #{item_id}")


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