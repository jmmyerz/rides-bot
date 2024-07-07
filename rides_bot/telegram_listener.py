import telegram, sys, asyncio, os
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# Find the absolute path of this script and append the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from threading import Event

from utils.config import Config
from utils.telegram import TelegramBot
from rides_bot.app import run_bot, CONFIG_FILE_PATH

config = Config().load(CONFIG_FILE_PATH)


def handle_sigterm(*args, **kwargs):
    """
    Handle SIGTERM signal, which will occur when this program runs as a systemd service.
    Raises KeyboardInterrupt to stop the program as if it was stopped by a keyboard interrupt.
    """
    raise KeyboardInterrupt


class Args:
    def __init__(self):
        self.return_discord_message = False
        self.debug = False
        self.gm_debug = False
        self.login = False
        self.groupme = False
        self.discord = False
        self.discord_debug = False
        self.date = None
        self.message = ""
        self.telegram12 = False
        self.telegram_debug = False
        self.return_telegram_message = True


class TelegramListener:
    def __init__(self):
        self.conf = config
        self.token = config.telegram.token
        self.a12_chat_id = config.telegram.a12_chat_id
        self.test_chat_id = config.telegram.test_chat_id
        self.args = Args()

        self.app = Application.builder().token(self.token).build()

    async def send_message(self, message: str, chat_id: int = None) -> bool:
        chat_id = chat_id if chat_id is not None else self.a12_chat_id
        try:
            await self.app.bot.send_message(chat_id, message)
        except Exception as e:
            print(f"Telegram error: {e}")
            return False

    async def filter_message(
        self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE
    ):
        # Get the chat id and message from the update
        chat_id = update.effective_chat.id
        message = update.message.text

        print(f"Chat ID: {chat_id}")
        print(f"Message: {message}")

        if chat_id == self.a12_chat_id:
            self.args.telegram12 = True
        elif chat_id == self.test_chat_id:
            self.args.telegram_debug = True

        if message.lower().strip() == "refresh":
            print("Refreshing...")
            await self.send_message(run_bot(self.args), chat_id)


if __name__ == "__main__":
    stop_event = Event()
    listener = TelegramListener()
    listener.app.add_handler(MessageHandler(filters.TEXT, listener.filter_message))

    while not stop_event.is_set():
        try:
            asyncio.run(
                listener.app.run_polling(allowed_updates=telegram.Update.ALL_TYPES)
            )
        except KeyboardInterrupt:
            stop_event.set()
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            stop_event.set()
            sys.exit(1)
        finally:
            stop_event.set()
            sys.exit(0)
