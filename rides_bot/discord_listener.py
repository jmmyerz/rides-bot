import discord, sys, asyncio

# Add parent directory to sys.path so we can import utils
sys.path.append("..")


from threading import Event

from utils.config import Config
from rides_bot.app import run_bot, CONFIG_FILE_PATH

intents = discord.Intents.default()
intents.message_content = True


def handle_sigterm(*args, **kwargs):
    """
    Handle SIGTERM signal, which will occur when this program runs as a systemd service.
    Raises KeyboardInterrupt to stop the program as if it was stopped by a keyboard interrupt.
    """
    raise KeyboardInterrupt


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
        self.args = Args()

        super().__init__(intents=intents)

    async def run(self):
        await super().start(self.token)

    async def send_message(self, message, channel_id):
        channel = self.get_channel(channel_id)
        await channel.send(message)

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):

        if message.author == self.user:
            return

        if message.content.lower().strip() == "refresh":
            if message.channel.id == self._conf.discord.test_channel_id:
                args = self.args
                args.discord_debug = True
                await self.send_message(run_bot(args), message.channel.id)

            elif message.channel.id == self._conf.discord.main_channel_id:
                args = self.args
                args.discord = True
                await self.send_message(run_bot(args), message.channel.id)

        if message.content.lower().strip() == "ping":
            print("Pong!")

    async def close(self) -> None:
        return await super().close()


if __name__ == "__main__":
    stop_event = Event()
    listener = DiscordListener()

    while not stop_event.is_set():
        try:
            asyncio.run(listener.run())
        except KeyboardInterrupt:
            stop_event.set()
            asyncio.run(listener.close())
        except Exception as e:
            print(f"Error: {e}")
            asyncio.run(listener.close())
