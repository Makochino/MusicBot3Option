import discord
from discord import app_commands
from music import YTDLSource, play_next_song, queue, current_player, repeat_track
from utils import delete_after, join_voice_channel

def setup_commands(bot):

    @bot.tree.command(name="включить", description="Воспроизвести музыку (TikTok/YouTube)")
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
        from music import queue
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
        from music import queue
        if queue:
            queue_titles = [player.data.get('title', 'Неизвестно') for player in queue]
            msg = await interaction.response.send_message(f"📃 Очередь:\n" + "\n".join(queue_titles))
        else:
            msg = await interaction.response.send_message("🈳 Очередь пуста.")
        await delete_after(msg)

    @bot.tree.command(name="повтор", description="Переключить режим повтора")
    async def repeat(interaction: discord.Interaction):
        from music import repeat_track
        import music
        music.repeat_track = not repeat_track
        status = "включен" if music.repeat_track else "выключен"
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
