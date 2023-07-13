from . import path_setup

import datetime, json, sys, random, os
from pathlib import Path

from utils.nested_json import NestedJSONEncoder
from utils.config import Config
from utils.w2w import Employee, Shift, W2WSession
from utils.groupme import GroupMe

CONFIG_FILE_PATH = (Path(__file__).parent.parent / 'config.yaml').resolve()

def run_bot(args):
    config = Config().load(CONFIG_FILE_PATH)

    if args.login:
        session = W2WSession(config.whentowork, debug=args.debug)
        config.save(filename=CONFIG_FILE_PATH)
        sys.exit(0)

    shifts = {}
    w2w = W2WSession(config.whentowork, debug=args.debug)
    for filter in list(config['whentowork']['filters'].items()):
        shifts[filter[0]] = w2w.retrieve_schedule(
            filter, date=args.date if args.date else 'Today'
        )
    if args.debug:
        utils.cmdline.logger(
            'Shifts JSON:\n\n' + json.dumps(shifts, indent=2, cls=NestedJSONEncoder),
            level='debug',
        )

    useful_data = {}
    for shift in shifts['managers'] + shifts['assistants']:
        # Get manager on (manager taking calls)
        calls = shift.is_manager_on
        if calls:
            if 7 <= shift.start_time.hour <= 11:
                useful_data.__setitem__(
                    f'manager_on{"_am" if not shift.is_double_shift else ""}',
                    shift,
                )
            elif 12 <= shift.start_time.hour <= 18:
                useful_data.__setitem__(f'manager_on_pm', shift)
        # Get second manager
        second = shift.is_second_manager
        if second:
            if 7 <= shift.start_time.hour <= 11:
                useful_data.__setitem__(
                    f'second_manager{"_am" if not shift.is_double_shift else ""}',
                    shift,
                )
            elif 12 <= shift.start_time.hour <= 18:
                useful_data.__setitem__(f'second_manager_pm', shift)

    for shift in shifts['coords'] + shifts['assistants']:
        calls = shift.is_north_south_coord
        if calls:
            if 7 <= shift.start_time.hour <= 11:
                useful_data.__setitem__(
                    f'{shift.which_coord}{"_am" if not shift.is_double_shift else ""}',
                    shift,
                )
            elif 12 <= shift.start_time.hour <= 18:
                useful_data.__setitem__(f'{shift.which_coord}_pm', shift)

    if args.debug:
        utils.cmdline.logger(
            'Useful data:\n' + json.dumps(useful_data, indent=2, cls=NestedJSONEncoder),
            level='debug',
        )

    def build_message(shifts: dict) -> list:
        prefixes = {
            'manager_on': 'Manager on: ',
            'second_manager': 'Second manager: ',
            'north': 'North coord: ',
            'south': 'South coord: ',
        }

        if args.date:
            message_date = datetime.datetime.strptime(args.date, '%m/%d/%Y')
        else:
            message_date = datetime.datetime.now()

        nowtime = datetime.datetime.now().time()
        rand = random.randint(0, 25)
        match (nowtime):
            case nowtime if nowtime.hour <= 11 and rand != 13:
                friendly_time = 'Good morning! 🌤️️🎢'
            case nowtime if 12 <= nowtime.hour <= 17 and rand != 13:
                friendly_time = 'Good afternoon! ☀️🎢'
            case nowtime if nowtime.hour >= 18 and rand != 13:
                friendly_time = 'Good evening! 🌙🎢'
            case _:
                friendly_time = 'Hi there! 😀🎢'

        outlist = [
            friendly_time,
            f'Management team for {message_date.strftime("%B %d, %Y")}',
            '',
        ]

        single_shift = 'manager_on_pm' not in shifts

        shift_split = ('_am', '_pm') if not single_shift else ('',)
        for xm in shift_split:
            if xm in ('_am', '_pm'):
                outlist.append('First shift:' if xm == '_am' else '\nSecond shift:')
            if f'manager_on{xm}' in shifts:
                outlist.append(
                    prefixes['manager_on'] + shifts[f'manager_on{xm}'].employee
                )
            if f'second_manager{xm}' in shifts:
                outlist.append(
                    prefixes['second_manager'] + shifts[f'second_manager{xm}'].employee
                )
            if f'north{xm}' in shifts:
                outlist.append(prefixes['north'] + shifts[f'north{xm}'].employee)
            if f'south{xm}' in shifts:
                outlist.append(prefixes['south'] + shifts[f'south{xm}'].employee)

        outlist.extend([
            '',
            f'Shifts updated at {nowtime.strftime("%H:%M")}',
            'Reply "refresh" to update',
        ])

        return outlist

    shift_msg = '\n'.join(build_message(useful_data))
    if args.groupme or args.gm_debug:
        gm = GroupMe(config.groupme, debug=args.debug, dev_bot=args.gm_debug)
        gm.post(args.message if args.message else shift_msg)
    if args.debug:
        utils.cmdline.logger(f'Message for GroupMe:\n{shift_msg}', level='debug')

    config.save(filename=CONFIG_FILE_PATH)


if __name__ == '__main__':
    import utils.cmdline
    run_bot(utils.cmdline.get_args())
