import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
import math
import random
import os

TOKEN = os.getenv("Discord_Token")
PREFIX = '.'

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

queue = []
repeat = False
shuffle = False
players = {}

class MusicPlayer(discord.ui.View):
    def __init__(self, interaction, title=None, duration=0, vc=None):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.paused = False
        self.title = title
        self.duration = duration
        self.current_time = 0
        self.message = None
        self.update_task = None
        self.vc = vc

    async def start_updating_time(self):
        while self.current_time < self.duration:
            await asyncio.sleep(1)
            if not self.paused:
                self.current_time += 1
                await self.update_message()
        if repeat:
            await play_track(self.interaction, self.title, replay=True)
        else:
            await play_next(self.interaction)

    async def update_message(self):
        if self.message:
            await self.message.edit(content=self.generate_embed(), view=self)

    def generate_embed(self):
        if not self.title:
            return "**Ничего не играет**\n`0:00/0:00`"
        minutes = self.current_time // 60
        seconds = self.current_time % 60
        duration_min = self.duration // 60
        duration_sec = self.duration % 60
        return f"**Сейчас играет:** {self.title}\n`{minutes}:{seconds:02}/{duration_min}:{duration_sec:02}`"

    @discord.ui.button(emoji='⏮️', style=discord.ButtonStyle.blurple, row=0)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏮️ Предыдущего трека нет", ephemeral=True, delete_after=30)

    @discord.ui.button(emoji='⏯️', style=discord.ButtonStyle.blurple, row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.vc or not self.vc.is_playing():
            await interaction.response.send_message("Ничего не играет", ephemeral=True, delete_after=30)
            return
        if self.paused:
            self.vc.resume()
            self.paused = False
        else:
            self.vc.pause()
            self.paused = True
        await interaction.response.defer()

    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.blurple, row=0)
    async def repeat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        global repeat
        repeat = not repeat
        await interaction.response.send_message(f"🔁 Повтор {'включен' if repeat else 'выключен'}", ephemeral=True, delete_after=30)

    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.blurple, row=1)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        global shuffle
        shuffle = not shuffle
        await interaction.response.send_message(f"🔀 Перемешивание {'включено' if shuffle else 'выключено'}", ephemeral=True, delete_after=30)

    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.blurple, row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if queue:
            await play_next(interaction)
        else:
            await interaction.response.send_message("Очередь пуста", ephemeral=True, delete_after=30)

    @discord.ui.button(emoji='❌', style=discord.ButtonStyle.red, row=1)
    async def close_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vc:
            self.vc.stop()
            await self.vc.disconnect()
        if self.message:
            await self.message.delete()
        players.pop(interaction.guild_id, None)
        await interaction.response.defer()

@bot.tree.command(name="music", description="Добавить трек в очередь или запустить")
@app_commands.describe(query="Введите название трека или ссылку")
async def music(interaction: discord.Interaction, query: str):
    view = players.get(interaction.guild_id)
    if not view:
        view = MusicPlayer(interaction)
        players[interaction.guild_id] = view

    if not view.title:
        await interaction.response.defer()
        await play_track(interaction, query)
    else:
        queue.append(query)
        await interaction.response.send_message(f"🎵 Трек добавлен в очередь: {query}", delete_after=30)

@bot.tree.command(name="player", description="Открыть музыкальный плеер")
async def player(interaction: discord.Interaction):
    view = players.get(interaction.guild_id)
    if not view:
        view = MusicPlayer(interaction)
        players[interaction.guild_id] = view
        if interaction.user.voice:
            await play_track(interaction, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        else:
            await interaction.response.send_message("Вы должны быть в голосовом канале для запуска плеера.", ephemeral=True)
            return
    message = await interaction.response.send_message(view.generate_embed(), view=view)
    view.message = await message.original_response()

async def play_track(interaction, query, replay=False):
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
    }
    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))

    if 'entries' in data:
        data = data['entries'][0]

    url = data['url']
    title = data['title']
    duration = data['duration']

    if not interaction.user.voice:
        await interaction.followup.send("Вы должны быть в голосовом канале.", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    vc = await channel.connect()
    vc.play(discord.FFmpegPCMAudio(url, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn'))

    view = players.get(interaction.guild_id)
    if not view:
        view = MusicPlayer(interaction)
        players[interaction.guild_id] = view
    view.title = title
    view.duration = duration
    view.current_time = 0
    view.vc = vc
    if not replay:
        view.paused = False
    await view.update_message()
    asyncio.create_task(view.start_updating_time())

async def play_next(interaction):
    if shuffle:
        random.shuffle(queue)
    if queue:
        next_track = queue.pop(0)
        await play_track(interaction, next_track)
    else:
        view = players.get(interaction.guild_id)
        if view:
            view.title = None
            view.duration = 0
            view.current_time = 0
            view.vc = None
            await view.update_message()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f'Sync error: {e}')

bot.run(TOKEN)
