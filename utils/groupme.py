import json, requests

import cmdline
from config import Config, debug as conf_debug


class GroupMe:

    def __init__(self, gmconf: Config, debug: bool = False, dev_bot: bool = False):
        self._gmconf = gmconf
        self._debug = debug
        self._dev_bot = dev_bot

    def post(self, message) -> bool:
        msg_data = {
            'bot_id': (
                self._gmconf.bot_id if not self._dev_bot else self._gmconf.dev_bot_id
            ),
            'text': message,
        }

        resp = requests.post(
            'https://api.groupme.com/v3/bots/post', json.dumps(msg_data)
        )
        if self._debug:
            cmdline.logger(
                f'GroupMe response: [Status {resp.status_code} {resp.reason}]',
                level='debug',
            )
        return True if resp.status_code == 200 else False


# Debug when run from command line
if __name__ == '__main__':
    config = conf_debug()
    gm = GroupMe(config.groupme)
    cmdline.logger(gm.__dict__, level='debug')
