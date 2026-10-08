import discord
from discord.ext import commands
import wavelink

# 1. Setup Intents
intents = discord.Intents.default()
intents.message_content = False

DISCORD_TOKEN = "MTU1NDIxODUxMjc0OTI5NzcxNA.G2F4wl.1VjNE9xu0kQ6NFMWQj5Yjep-l_6WRTQf0nSA-g"
LAVALINK_URI = "http://127.0.0.1:2333"
LAVALINK_PASSWORD = "youshallnotpass"

# 2. Initialize Bot
bot = commands.Bot(command_prefix="!", intents=intents)

# 3. Setup Wavelink and Sync Commands
async def setup_hook():
    node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)
    await wavelink.Pool.connect(client=bot, nodes=[node])
    print("Connected to Lavalink!")
    
    # This line was missing from your active hook!
    await bot.tree.sync()
    print("Slash commands synced to Discord!")

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# 4. Music Commands
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
        
    await player.skip(force=True)
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
