from flask import Flask, Response, request

from utils.config import Config
from .rides_bot import run_bot, CONFIG_FILE_PATH

config = Config().load(CONFIG_FILE_PATH)

class RuntimeArgs(object):

    def __init__(self, arg_dict):
        for arg, val in arg_dict.items():
            self.__setattr__(f'{arg}', val)


# Handle the groupme callback
app = Flask(__name__)


@app.post('/update/prod')
@app.post('/update/dev')
def groupme():
    data = request.get_json()
    args = RuntimeArgs(config.gunicorn.rides_bot_args)

    args.gm_debug = True if request.endpoint == 'dev' else False
    
    if data.__getitem__('text').lower().strip() == 'refresh':
        run_bot(args)
        return Response(status=200)
    else:
        return Response(status=204)
