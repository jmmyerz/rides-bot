import datetime, json


class NestedJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict
        elif isinstance(obj, datetime.time):
            return obj.strftime('%H:%M')
        else:
            return json.JSONEncoder.default(self, obj)
