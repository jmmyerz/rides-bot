import json, requests

from . import cmdline
from .config import Config, debug as conf_debug


class GroupMe:

    def __init__(
        self,
        gmconf: Config,
        debug: bool = False,
        main_bot: bool = False,
        dev_bot: bool = False,
        a910_bot: bool = False,
        north_bot: bool = False,
    ):
        self._gmconf = gmconf
        self._debug = debug
        self._main_bot = main_bot
        self._dev_bot = dev_bot
        self._a910_bot = a910_bot
        self._north_bot = north_bot

    def post(self, message) -> bool:
        _bot_id = None

        def _request(data):
            resp = requests.post(
                "https://api.groupme.com/v3/bots/post", json.dumps(data)
            )
            if self._debug:
                cmdline.logger(
                    f"GroupMe response: [Status {resp.status_code} {resp.reason}]",
                    level="debug",
                )
            return True if resp.status_code == 200 else False

        if self._dev_bot:
            _bot_id = self._gmconf.dev_bot_id
            _request(
                {
                    "bot_id": _bot_id,
                    "text": message["main"],
                }
            )
        if self._a910_bot:
            _request(
                {
                    "bot_id": self._gmconf.a910_bot_id,
                    "text": message["a910"],
                }
            )

        if self._north_bot:
            _request(
                {
                    "bot_id": self._gmconf.north_bot_id,
                    "text": message["north"],
                }
            )

        if self._main_bot:
            _request(
                {
                    "bot_id": self._gmconf.bot_id,
                    "text": message["main"],
                }
            )

        return True


# Debug when run from command line
if __name__ == "__main__":
    config = conf_debug()
    gm = GroupMe(config.groupme)
    cmdline.logger(gm.__dict__, level="debug")
