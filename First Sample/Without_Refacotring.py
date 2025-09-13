import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
import os
import tempfile

from Projects.Bots.GpoDIr.gpo_bot import client

TOKEN = os.getenv("Discord_Token")
PREFIX = '.'

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'extract_flat': False,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

FFMPEG_OPTIONS_STREAM = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}
FFMPEG_OPTIONS_LOCAL = {
    'options': '-vn',
}

repeat_track = False
current_player = None
queue = []

@bot.event
async def on_message(message):
    await asyncio.sleep(30)
    try:
        await message.delete()
    except:
        pass
    await bot.process_commands(message)

async def delete_after(response, delay=30):
    try:
        await asyncio.sleep(delay)
        await response.delete()
    except:
        pass

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data=None, file_path=None):
        super().__init__(source)
        self.data = data
        self.file_path = file_path

    @classmethod
    async def from_query(cls, query, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()

        # TikTok
        if "tiktok.com" in query:
            try:
                temp_dir = tempfile.mkdtemp()
                ydl_opts = ytdl_format_options.copy()
                ydl_opts["outtmpl"] = os.path.join(temp_dir, "tiktok_audio.%(ext)s")
                with youtube_dl.YoutubeDL(ydl_opts) as tiktok_dl:
                    data = await loop.run_in_executor(None, lambda: tiktok_dl.extract_info(query, download=True))
                    filename = tiktok_dl.prepare_filename(data)
                # Поиск загруженного файла
                if not os.path.isfile(filename):
                    for file in os.listdir(temp_dir):
                        if file.startswith("tiktok_audio"):
                            filename = os.path.join(temp_dir, file)
                            break
                    else:
                        print("❌ Файл не найден после загрузки TikTok.")
                        return None
                return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS_LOCAL), data=data, file_path=filename)
            except Exception as e:
                print(f"Ошибка TikTok: {e}")
                return None

        # YouTube
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=not stream)), timeout=10)
        except Exception as e:
            print(f"Ошибка: {e}")
            return None

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        options = FFMPEG_OPTIONS_STREAM if stream else FFMPEG_OPTIONS_LOCAL
        return cls(discord.FFmpegPCMAudio(filename, **options), data=data, file_path=(None if stream else filename))

@bot.event
async def on_ready():
    print(f'Вошёл как {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f'Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'Ошибка синхронизации: {e}')

def play_next_song(error):
    global repeat_track, current_player, queue
    if current_player is None or current_player.get('voice_client') is None:
        return
    voice_client = current_player['voice_client']

    if current_player['player'].file_path:
        try:
            os.remove(current_player['player'].file_path)
        except:
            pass

    if repeat_track and current_player:
        source = discord.FFmpegPCMAudio(current_player['player'].data['url'], **FFMPEG_OPTIONS_STREAM)
        player = YTDLSource(source, data=current_player['player'].data)
        current_player['player'] = player
        voice_client.play(player, after=play_next_song)
    elif queue:
        next_song = queue.pop(0)
        voice_client.play(next_song, after=play_next_song)
        current_player['player'] = next_song
    else:
        current_player = None

async def join_voice_channel(interaction):
    voice_client = interaction.guild.voice_client
    if not voice_client:
        if interaction.user.voice:
            try:
                voice_client = await interaction.user.voice.channel.connect(timeout=10)
            except Exception as e:
                msg = await interaction.response.send_message(f"Ошибка подключения: {e}", ephemeral=True)
                await delete_after(msg)
                return None
        else:
            msg = await interaction.response.send_message("Вы должны быть в голосовом канале.", ephemeral=True)
            await delete_after(msg)
            return None
    return voice_client

@bot.tree.command(name="включить", description="Воспроизвести музыку по ссылке или названию трека (TikTok/YouTube)")
@app_commands.describe(query="Ссылка на TikTok/YouTube или исполнитель и название трека")
async def music(interaction: discord.Interaction, query: str):
    global current_player, queue
    voice_client = await join_voice_channel(interaction)
    if voice_client is None:
        return
    await interaction.response.send_message(f"🔍 Поиск: {query}")
    async with interaction.channel.typing():
        player = await YTDLSource.from_query(query, stream="tiktok.com" not in query)
        if player is None:
            msg = await interaction.followup.send("❌ Не удалось воспроизвести трек.")
            await delete_after(msg)
            return
        if voice_client.is_playing() or voice_client.is_paused():
            queue.append(player)
            msg = await interaction.followup.send(f"➕ В очередь: {player.data.get('title', 'Неизвестно')}")
        else:
            voice_client.play(player, after=play_next_song)
            current_player = {'voice_client': voice_client, 'player': player}
            msg = await interaction.followup.send(f"🎶 Сейчас играет: {player.data.get('title', 'Неизвестно')}")
        await delete_after(msg)

@bot.tree.command(name="скип", description="Пропустить текущий трек")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        if queue:
            next_title = queue[0].data.get('title', 'Неизвестно')
            msg = await interaction.response.send_message(f"⏭️ Пропущено. Сейчас будет: {next_title}")
        else:
            msg = await interaction.response.send_message("⏭️ Пропущено. Очередь пуста.")
        voice_client.stop()
    else:
        msg = await interaction.response.send_message("❌ Сейчас ничего не воспроизводится.")
    await delete_after(msg)

@bot.tree.command(name="пауза", description="Поставить трек на паузу")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        msg = await interaction.response.send_message("⏸️ Пауза.")
    else:
        msg = await interaction.response.send_message("❌ Нечего ставить на паузу.")
    await delete_after(msg)

@bot.tree.command(name="возобновить", description="Возобновить воспроизведение")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        msg = await interaction.response.send_message("▶️ Возобновлено.")
    else:
        msg = await interaction.response.send_message("❌ Нечего возобновлять.")
    await delete_after(msg)

@bot.tree.command(name="очередь", description="Показать очередь треков")
async def show_queue(interaction: discord.Interaction):
    if queue:
        queue_titles = [player.data.get('title', 'Неизвестно') for player in queue]
        msg = await interaction.response.send_message(f"📃 Очередь:\n" + "\n".join(queue_titles))
    else:
        msg = await interaction.response.send_message("🈳 Очередь пуста.")
    await delete_after(msg)

@bot.tree.command(name="повтор", description="Переключить режим повтора")
async def repeat(interaction: discord.Interaction):
    global repeat_track
    repeat_track = not repeat_track
    status = "включен" if repeat_track else "выключен"
    msg = await interaction.response.send_message(f"🔁 Повтор {status}.")
    await delete_after(msg)

@bot.tree.command(name="выйти", description="Выйти из голосового канала")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        msg = await interaction.response.send_message("👋 Вышел из голосового канала.")
    else:
        msg = await interaction.response.send_message("❌ Не в голосовом канале.")
    await delete_after(msg)

client.run(TOKEN)
