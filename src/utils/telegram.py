from . import cmdline
from .config import Config, debug as conf_debug

import telegram, asyncio


class TelegramBot:
    def __init__(self, conf: Config, debug: bool = False):
        self.conf = conf
        self.token = conf.telegram.token
        self.a12_chat_id = conf.telegram.a12_chat_id
        self.bot = telegram.Bot(self.token)

    async def send_message(self, message: str, chat_id: int = None) -> bool:
        chat_id = chat_id if chat_id is not None else self.a12_chat_id
        try:
            bot = self.bot
            await bot.send_message(chat_id, message)
            return True
        except Exception as e:
            cmdline.logger(f"Telegram error: {e}", level="error")
            return False

    def send(self, *args, **kwargs):
        return asyncio.run(self.send_message(*args, **kwargs))
