import discord, time

from threading import Thread

from utils.config import Config
from rides_bot.app import run_bot, CONFIG_FILE_PATH

intents = discord.Intents.default()
intents.message_content = True


class Args:
    def __init__(self):
        self.return_discord_message = True
        self.debug = False
        self.gm_debug = False
        self.login = False
        self.groupme = False
        self.discord = False
        self.discord_debug = False
        self.date = None
        self.message = ""


class DiscordListener(discord.Client):
    def __init__(self):
        self._conf = Config().load(CONFIG_FILE_PATH)
        self.token = self._conf.discord.bot_token

        super().__init__(intents=intents)

    def run(self):
        super().run(self.token)

    async def send_message(self, message, channel_id):
        channel = self.get_channel(channel_id)
        await channel.send(message)

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):

        if message.author == self.user:
            return

        if message.content == "refresh":
            if message.channel.id == self._conf.discord.test_channel_id:
                args = Args()
                args.discord_debug = True
                await self.send_message(run_bot(args), message.channel.id)

            elif message.channel.id == self._conf.discord.main_channel_id:
                args = Args()
                args.discord = True
                await self.send_message(run_bot(args), message.channel.id)

    async def close(self) -> None:
        return await super().close()


listener = DiscordListener()
listener.run()
