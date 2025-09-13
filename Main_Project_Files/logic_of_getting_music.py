import os
import asyncio
import tempfile
import discord
import yt_dlp as youtube_dl

# YTDL config
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
