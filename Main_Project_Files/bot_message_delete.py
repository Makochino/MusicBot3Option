import asyncio

async def delete_after(response, delay=30):
    try:
        await asyncio.sleep(delay)
        await response.delete()
    except:
        pass


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
