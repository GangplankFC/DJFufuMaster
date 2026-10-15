import os
import discord
from discord.ext import commands
from discord.ext import tasks
import wavelink
import asyncio
import logging
from prometheus_client import start_http_server, Counter, Gauge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music Bot")

# 1. Setup Intents
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
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        start_http_server(8000)
        print("Prometheus metrics server started on port 8000", flush=True)
        
        self.update_metrics.start()

        logger.info("Waiting 5 seconds for Lavalink WebSocket to boot...")
        await asyncio.sleep(5)

        node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)
        await wavelink.Pool.connect(client=self, nodes=[node])
        logger.info("WebSocket Connected to Lavalink!")

        await self.tree.sync()
        logger.info("Slash commands synced to Discord!")

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
        logger.info(f"[WS TEST] Track Started: {payload.track.title}")

    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return

        print(f"\n====== TRACK END FIRED ======", flush=True)
        print(f"Reason: {payload.reason}", flush=True)

        reason = str(payload.reason).upper()

        is_stream = False
        if payload.track:
            is_stream = getattr(payload.track, 'is_stream', False) or getattr(payload.track, 'length', 0) == 0

        if is_stream and reason in ["FINISHED", "LOAD_FAILED"]:
            print("[Lavalink] Stream dropped! Healing connection...", flush=True)
            await asyncio.sleep(0.1)
            await player.play(payload.track)
            return

        if reason == "REPLACED":
            return

        if not player.queue.is_empty:
            next_track = player.queue.get()
            print(f"Queue: Playing next song -> {next_track.title}", flush=True)
            await player.play(next_track)
        else:
            print("Queue is empty. Player is now idle.", flush=True)

bot = MusicBot()

@bot.tree.command(name="play", description="Play a song or add it to the queue")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("You must be in a voice channel!", ephemeral=True)

    await interaction.response.defer()

    player: wavelink.Player = interaction.guild.voice_client
    if not player:
        player = await interaction.user.voice.channel.connect(cls=wavelink.Player)

    tracks = await wavelink.Playable.search(query)
    if not tracks:
        return await interaction.followup.send("No songs found. Try a different search.")

    track = tracks[0]
    await player.queue.put_wait(track)

    if not player.playing:
        await player.play(player.queue.get())
        await interaction.followup.send(f"▶️ Now playing: **{track.title}**")
    else:
        await interaction.followup.send(f"✅ Added to queue: **{track.title}**")

@bot.tree.command(name="skip", description="Skip the currently playing song")
async def skip(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if not player or not player.playing:
        return await interaction.response.send_message("There is nothing to skip!", ephemeral=True)

    await player.skip()
    await interaction.response.send_message("⏭️ Skipped to the next song.")

@bot.tree.command(name="pause", description="Pause the music")
async def pause(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.playing:
        await player.pause(True)
        await interaction.response.send_message("⏸️ Music paused.")
    else:
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)

@bot.tree.command(name="resume", description="Resume the paused music")
async def resume(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.paused:
        await player.pause(False)
        await interaction.response.send_message("▶️ Music resumed.")
    else:
        await interaction.response.send_message("The music is not paused.", ephemeral=True)

@bot.tree.command(name="previous", description="Replay previously played song")
async def previous(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client
    if not player or not player.queue.history:
        return await interaction.response.send_message("No previously played song to replay.", ephemeral=True)

    last_track = player.queue.history[-1]
    await player.play(last_track)
    await interaction.response.send_message(f"🔁 Replaying: **{last_track.title}**")

bot.run(DISCORD_TOKEN)
