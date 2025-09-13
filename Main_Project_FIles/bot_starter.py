import os
import discord
from discord.ext import commands
from bot_commands import setup_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("Discord_Token")
PREFIX = '.'

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f'✅ Вошёл как {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f'🔗 Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')


def main():
    setup_commands(bot)
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
