import discord
from discord.ext import commands
import wavelink
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music Bot")

# 1. Setup Intents
intents = discord.Intents.default()
intents.message_content = False

DISCORD_TOKEN = "MTU1NDIxODUxMjc0OTI5NzcxNA.G2F4wl.1VjNE9xu0kQ6NFMWQj5Yjep-l_6WRTQf0nSA-g"
LAVALINK_URI = "http://lavalink:2333"
LAVALINK_PASSWORD = "youshallnotpass"

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        logger.info("Waiting 5 seconds for Lavalink WebSocket to boot...")
        await asyncio.sleep(5)

        node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)
        await wavelink.Pool.connect(client=self, nodes=[node])
        logger.info("WebSocket Connected to Lavalink!")

        await self.tree.sync()
        logger.info("Slash commands synced to Discord!")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

    # Wavelink events belong INSIDE the class using 'self'
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        logger.info(f"[WS TEST] Track Started: {payload.track.title}")

    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return

        print(f"\n====== TRACK END FIRED ======", flush=True)
        print(f"Reason: {payload.reason}", flush=True)

        reason = str(payload.reason).upper()

        # --- 1. LIVESTREAM HEALER ---
        # Safely check if the track was a livestream (streams have 0 length)
        is_stream = False
        if payload.track:
            is_stream = getattr(payload.track, 'is_stream', False) or getattr(payload.track, 'length', 0) == 0

        # If a stream naturally finishes or fails, it means it crashed. Resurrect it!
        if is_stream and reason in ["FINISHED", "LOAD_FAILED"]:
            print("[Lavalink] Stream dropped! Healing connection...", flush=True)
            await asyncio.sleep(0.1)
            await player.play(payload.track)
            return

        # --- 2. QUEUE PROGRESSION (Normal songs & Skips) ---
        # If reason is REPLACED, another song was forcibly started by a command. Do nothing.
        if reason == "REPLACED":
            return

        # If the queue has songs waiting, play the next one!
        if not player.queue.is_empty:
            next_track = player.queue.get()
            print(f"Queue: Playing next song -> {next_track.title}", flush=True)
            await player.play(next_track)
        else:
            print("Queue is empty. Player is now idle.", flush=True)

# 3. Initialize the Bot
bot = MusicBot()

# 4. Music Commands (These stay outside using @bot.tree.command)
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

# 5. Run Bot
bot.run(DISCORD_TOKEN)
