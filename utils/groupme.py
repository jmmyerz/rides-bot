import json, requests

from . import cmdline
from .config import Config, debug as conf_debug


class GroupMe:

    def __init__(
        self,
        gmconf: Config,
        debug: bool = False,
        dev_bot: bool = False,
        a910_bot: bool = False,
    ):
        self._gmconf = gmconf
        self._debug = debug
        self._dev_bot = dev_bot
        self._a910_bot = a910_bot

    def post(self, message) -> bool:
        _bot_id = None
        if self._dev_bot:
            _bot_id = self._gmconf.dev_bot_id
        elif self._a910_bot:
            _bot_id = self._gmconf.a910_bot_id
        else:
            _bot_id = self._gmconf.bot_id

        msg_data = {
            "bot_id": (_bot_id if _bot_id is not None else self._gmconf.bot_id),
            "text": message,
        }

        resp = requests.post(
            "https://api.groupme.com/v3/bots/post", json.dumps(msg_data)
        )
        if self._debug:
            cmdline.logger(
                f"GroupMe response: [Status {resp.status_code} {resp.reason}]",
                level="debug",
            )
        return True if resp.status_code == 200 else False


# Debug when run from command line
if __name__ == "__main__":
    config = conf_debug()
    gm = GroupMe(config.groupme)
    cmdline.logger(gm.__dict__, level="debug")
