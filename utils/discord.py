import discord

intents = discord.Intents.default()
intents.message_content = True


class SingleMessageClient(discord.Client):
    def __init__(self, channel_id=None, message=None):
        self.channel_id = channel_id
        self.message = message

        super().__init__(intents=intents)

    async def on_ready(self):
        channel = self.get_channel(self.channel_id)
        channel.send(self.message)
        await self.close()
