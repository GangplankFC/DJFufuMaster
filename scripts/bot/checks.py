import discord
from discord import app_commands


class NotInVoiceChannel(app_commands.CheckFailure):
    pass

class InDifferentVoiceChannel(app_commands.CheckFailure):
    pass

def require_voice_channel():
    """Decorator to ensure the user is in a voice channel, and in the SAME channel as the bot."""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Edge Case: Is the user in any voice channel at all?
        if not interaction.user.voice or not interaction.user.voice.channel:
            raise NotInVoiceChannel()
        
        # Edge Case: Is the bot already in a channel, and is the user in a different one?
        bot_voice = interaction.guild.voice_client
        if bot_voice and bot_voice.channel.id != interaction.user.voice.channel.id:
            raise InDifferentVoiceChannel()
            
        return True
    return app_commands.check(predicate)