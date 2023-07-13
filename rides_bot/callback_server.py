from flask import Flask, Response, request

from utils.config import Config
from .rides_bot import run_bot, CONFIG_FILE_PATH

config = Config().load(CONFIG_FILE_PATH)

class UpdateArgs(object):

    def __init__(self, arg_dict):
        for arg, val in arg_dict.items():
            self.__setattr__(f'{arg}', val)


# Handle the groupme callback
app = Flask(__name__)


@app.post('/update')
def groupme():
    data = request.get_json()

    if data.__getitem__('text').lower().strip() == 'refresh':
        run_bot(UpdateArgs(config.gunicorn.rides_bot_args))
        return Response(status=200)
    else:
        return Response(status=204)
