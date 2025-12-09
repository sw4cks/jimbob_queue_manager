import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
from threading import Thread

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

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
        await message.channel.send(f'{message.author.mention} has added the show {text_before} to the queue!')
    elif '(movie)' in content:
        text_before = message.content[:message.content.lower().index('(movie)')].strip()
        await message.channel.send(f'{message.author.mention} has added the movie {text_before} to the queue!')
    elif '(anime)' in content:
        text_before = message.content[:message.content.lower().index('(anime)')].strip()
        await message.channel.send(f'{message.author.mention} has added the anime {text_before} to the queue!')
    await bot.process_commands(message)

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

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