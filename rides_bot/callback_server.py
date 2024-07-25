import re
from flask import Flask, Response, request

from utils.config import Config
from .app import run_bot, CONFIG_FILE_PATH

config = Config().load(CONFIG_FILE_PATH)


class RuntimeArgs(object):

    def __init__(self, arg_dict):
        for arg, val in arg_dict.items():
            self.__setattr__(arg, val)


# Handle the groupme callback
app = Flask(__name__)


@app.post("/update/prod", endpoint="prod")
@app.post("/update/dev", endpoint="dev")
@app.post("/update/a910", endpoint="a910")
@app.post("/update/north", endpoint="north")
def groupme():
    data = request.get_json()
    args = RuntimeArgs(config.gunicorn.rides_bot_args)

    # Quick and dirty handling of where the bot posts
    args.gm_debug = False
    args.groupme = False
    args.groupme910 = False
    if request.endpoint == "dev":
        args.gm_debug = True
        args.debug = True
    elif request.endpoint == "prod":
        args.groupme = True
    elif request.endpoint == "a910":
        args.groupme910 = True
    elif request.endpoint == "north":
        args.groupme_north = True

    date_pattern = r"analyze ((0[0-9]{1}|1[0-2]{1})\/([0-2]{1}[0-9]{1}|3[0-1]{1})\/20[1-3]{1}[0-9]{1})"
    message = data.__getitem__("text").lower().strip()

    if message == "refresh":
        run_bot(args)
        return Response(status=200)

    elif re.match(date_pattern, message):
        args.date = re.search(date_pattern, message).group(1)
        run_bot(args)
        return Response(status=200)
    else:
        return Response(status=204)
