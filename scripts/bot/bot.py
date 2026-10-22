import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import wavelink
import asyncio
import logging
from prometheus_client import start_http_server, Counter, Gauge

from checks import NotInVoiceChannel, InDifferentVoiceChannel, require_voice_channel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music Bot")

intents = discord.Intents.default()
intents.message_content = False

MESSAGES_PROCESSED = Counter('discord_messages_processed_total', 'Total messages processed by the bot')
ACTIVE_GUILDS = Gauge('discord_active_guilds', 'Current number of connected guilds')
BOT_LATENCY = Gauge('discord_bot_latency_seconds', 'Discord WebSocket heartbeat latency')

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_URI = "http://lavalink:2333"
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        start_http_server(8000)
        logger.info("Prometheus metrics server started on port 8000")
        
        self.update_metrics.start()

        logger.info("Waiting 5 seconds for Lavalink WebSocket to boot...")
        await asyncio.sleep(5)

        node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)
        await wavelink.Pool.connect(client=self, nodes=[node])
        logger.info("WebSocket Connected to Lavalink!")

        self.tree.on_error = self.on_tree_error

        await self.tree.sync()
        logger.info("Slash commands synced to Discord!")

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Catches all command errors centrally, including our custom voice checks."""
        if isinstance(error, NotInVoiceChannel):
            await interaction.response.send_message("Treci ma pe canal!", ephemeral=True)
        elif isinstance(error, InDifferentVoiceChannel):
            await interaction.response.send_message("Suntem pe canale diferite! Intra la mine sa pui muzica.", ephemeral=True)
        else:
            logger.error(f"Unhandled Command Error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("A aparut o eroare interna.", ephemeral=True)

    @tasks.loop(seconds=15)
    async def update_metrics(self):
        ACTIVE_GUILDS.set(len(self.guilds))
        BOT_LATENCY.set(self.latency)

    async def on_message(self, message):
        if not message.author.bot:
            MESSAGES_PROCESSED.inc()
        await self.process_commands(message)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        logger.info(f"Track Started: {payload.track.title}")

    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return

        reason = str(payload.reason).upper()
    
        is_stream = False
        if payload.track:
            is_stream = getattr(payload.track, 'is_stream', False) or getattr(payload.track, 'length', 0) == 0

        if is_stream and ("FINISHED" in reason or "LOAD_FAILED" in reason):
            logger.info("[Lavalink] Stream dropped! Healing connection...")
            await asyncio.sleep(0.1)
            await player.play(payload.track)
            return

        if "REPLACED" in reason:
            return

        player.queue.history.put(payload.track)

        if not player.queue.is_empty:
            next_track = player.queue.get()
            logger.info(f"Queue: Playing next song -> {next_track.title}")
            await player.play(next_track)
        else:
            logger.info("Queue is empty. Player is now idle.")
            await player.disconnect()

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        player: wavelink.Player = member.guild.voice_client
        
        if not player:
            return

        if member == self.user and before.channel and not after.channel:
            logger.info(f"Bot forcibly kicked from {before.channel.name} in {member.guild.name}. Destroying player.")
            await player.disconnect()
            return

        if player.channel:
            human_members = [m for m in player.channel.members if not m.bot]
            
            if len(human_members) == 0:
                logger.info(f"Everyone left {player.channel.name} in {member.guild.name}. Disconnecting to save resources.")
                await player.disconnect()

bot = MusicBot()

@bot.tree.command(name="play", description="Baga o piesa sau adaugo la coada")
@require_voice_channel()
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    player: wavelink.Player = interaction.guild.voice_client
    if not player:
        player = await interaction.user.voice.channel.connect(cls=wavelink.Player)

    tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
    if not tracks:
        return await interaction.followup.send("Nam gasit piesa incearca altceva")

    track = tracks[0]
    await player.queue.put_wait(track)

    if not player.playing:
        await player.play(player.queue.get())
        await interaction.followup.send(f"▶️ Acuma bagam: **{track.title}**")
    else:
        await interaction.followup.send(f"✅ Adaugat la coada: **{track.title}**")

@bot.tree.command(name="skip", description="Treci peste piesa curenta")
@require_voice_channel()
async def skip(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if not player or not player.playing:
        return await interaction.response.send_message("La momentul de fata nu se reda nimic", ephemeral=True)

    await player.skip()
    await interaction.response.send_message("⏭️ Trecut la urmatoarea dedicatie.")

@bot.tree.command(name="pause", description="Opreste melodia")
@require_voice_channel()
async def pause(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.playing:
        await player.pause(True)
        await interaction.response.send_message("⏸️ Am oprit.")
    else:
        await interaction.response.send_message("La momentul de fata nu se reda nimic.", ephemeral=True)

@bot.tree.command(name="resume", description="Continua melodia")
@require_voice_channel()
async def resume(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.paused:
        await player.pause(False)
        await interaction.response.send_message("▶️ Iam redat drumul.")
    else:
        await interaction.response.send_message("Cum vrei so redau daca nai oprito?", ephemeral=True)

@bot.tree.command(name="previous", description="Replay la ultima piesa")
@require_voice_channel()
async def previous(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    
    if not player or player.queue.history.is_empty:
        return await interaction.response.send_message("Istoricul de piese este gol.", ephemeral=True)

    if player.playing:
        player.queue.put_at(0, player.current)

    previous_track = player.queue.history.get()
    player.queue.put_at(0, previous_track)
    await player.skip()

    await interaction.response.send_message(f"⏪ Inapoi la: **{previous_track.title}**")

bot.run(DISCORD_TOKEN)