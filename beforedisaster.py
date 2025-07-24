import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
import os
from collections import defaultdict
from discord.utils import get
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('discord_token')

my_guild_id = discord.Object(id=1397310189191037039)
intents = discord.Intents.default()
locks = defaultdict(asyncio.Lock)
intents.message_content = True
intents.voice_states = True
queue = defaultdict(list)
intents.guilds = True
now_playing = {}



class MyBot(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Comandos slash sincronizados en el servidor {my_guild_id.id}")
        print("Lista de comandos:")
        for cmd in self.tree.get_commands():
            print(f"- /{cmd.name}: {cmd.description}")


bot = MyBot(command_prefix='!', intents=intents)

@bot.tree.command(name='help', description='Muestra la lista de comandos disponibles')
async def help(interaction: discord.Interaction):
    help_message = """
📜 **Lista de comandos disponibles:**

🗑️ **/clear_queue** — Limpia la cola de canciones.
❓ **/help** — Muestra este mensaje de ayuda.
📞 **/join** — Conecta al bot al canal de voz.
👣 **/leave** — Desconecta al bot del canal de voz.
🎶 **/now_playing** — Muestra la canción actual.
⏸️**/pause** — Pausa la canción actual.
🎵 **/play <url>** — Reproduce una canción desde un link de YouTube.
📃 **/queue_list** — Muestra la lista de canciones en cola.
🚫 **/remove** — Elimina una cancion de la cola.
▶️ **/resume** — Reanuda la cancion pausada.
⏭️ **/skip** — Salta a la siguiente canción en la cola.
📴 **/stop** — Detiene la música y desconecta al bot.

"""
    await interaction.response.send_message(help_message)


@bot.tree.command(name='join', description='Conecta el bot al canal de voz actual')
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"Conectado a {channel}")
    else:
        await interaction.response.send_message("¡Debes estar en un canal de voz!", ephemeral=True)

@bot.tree.command(name='leave', description='Desconecta el bot  del canal de voz')
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Me desconecté del canal de voz.")
    else:
        await interaction.response.send_message("No estoy en un canal de voz.")


@bot.tree.command(name='play', description='Reproduce una canción desde una URL de YouTube')
@app_commands.describe(url='Link de la canción')

async def play(interaction: discord.Interaction, url: str):
    voice = interaction.user.voice
    if not voice:
        await interaction.response.send_message("¡Debes estar en un canal de voz!", ephemeral=True)
        return

    voice_channel = voice.channel
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not vc or not vc.is_connected():
        vc = await voice_channel.connect()
        await interaction.response.send_message(f'🔊 Conectado a {voice_channel}.') 

    if interaction.guild.id not in queue:
        queue[interaction.guild.id] = []

    queue[interaction.guild.id].append(url)
    if not vc.is_playing():
        await play_next(interaction, vc)
    else:
        await interaction.response.send_message("🎵 Canción agregada a la cola.")
   


async def play_next(interaction, vc):
    async with locks[interaction.guild.id]:
        if not queue[interaction.guild.id]:
            await vc.disconnect()
            return

        url = queue[interaction.guild.id].pop(0)
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts)

        now_playing[interaction.guild.id] = info.get('title') 

        vc.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction, vc), bot.loop)
        )

        await interaction.channel.send(f"🎶 Reproduciendo: {info.get('title')}")



@bot.tree.command(name='skip', description='Salta la canción actual')
async def skip(interaction: discord.Interaction):
    await interaction.response.defer()

    vc = get(bot.voice_clients, guild=interaction.guild)
    if vc and vc.is_playing():
        vc.stop()
        await interaction.followup.send("⏭ Canción saltada.")
    else:
        await interaction.followup.send("No hay nada sonando.")

@bot.tree.command(name='queue_list', description='Muestra las canciones en cola')
async def queue_list(interaction: discord.Interaction):
    q = queue.get(interaction.guild.id, [])
    if not q:
        await interaction.response.send_message("🎵 La cola está vacía.")
    else:
        message = "**🎶 Cola de reproducción:**\n"
        for i, url in enumerate(q, start=1):
            message += f"{i}. {url}\n"
        await interaction.response.send_message(message)

@bot.tree.command(name='stop', description='Detiene la canción actual')
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏹️ Música detenida.")

@bot.tree.command(name='clear_queue', description='Limpia la cola de reproducción')
async def clear_queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in queue:
        queue[guild_id].clear()
        await interaction.response.send_message("🎵 Cola de reproducción limpiada.")
    else:
        await interaction.response.send_message("La cola ya estaba vacía.")

@bot.tree.command(name='pause', description='Pausa la canción actual')
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸ Canción pausada.")
    else:
        await interaction.response.send_message('No hay ninguna canciín reproduciendose')

@bot.tree.command(name='resume', description='Reanuda la canción pausada')
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message('▶️ Canción reanudada')
    else:
        await interaction.response.send_message('No hay ninguna canción pausada')

@bot.tree.command(name='remove', description='Elimina una canción de la cola')
@app_commands.describe(index='Número de la canción en la cola (1, 2, 3, ...)')
async def remove(interaction: discord.Interaction, index: int):
    q = queue.get(interaction.guild.id, [])
    if 1 <= index <= len(q):
        removed = q.pop(index - 1)
        await interaction.response.send_message(f'🗑 Canción eliminada de la cola:\n{removed}')
    else:
        await interaction.response.send_message("❌ Índice inválido. Usa /queue_list para ver las posiciones.")
    
@bot.tree.command(name='now_playing', description='Muestra la canción actual')
async def now_playing_cmd(interaction: discord.Interaction):
    current = now_playing.get(interaction.guild.id)
    if current:
        await interaction.response.send_message(f'🎧 Ahora suena: {current}')
    else:
        await interaction.response.send_message('No hay ninguna canción sonando')






bot.run(TOKEN)