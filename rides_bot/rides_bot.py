from . import path_setup

import datetime, json, sys, random, os
from pathlib import Path
from collections import Counter

from utils.nested_json import NestedJSONEncoder
from utils.config import Config
from utils.w2w import determine_shift, Shift, W2WSession
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
    config.save(filename=CONFIG_FILE_PATH)

    for filter in list(config['whentowork']['filters'].items()):
        shifts[filter[0]] = w2w.retrieve_schedule(
            filter, date=args.date if args.date else 'Today'
        )
    # if args.debug:
    #    utils.cmdline.logger(
    #        'Shifts JSON:\n\n' + json.dumps(shifts, indent=2, cls=NestedJSONEncoder),
    #        level='debug',
    #    )

    filtered_shifts = {
        'managers_on': [
            shift
            for shift in shifts['managers'] + shifts['assistants']
            if shift.is_manager_on
        ],
        'second_managers': [
            shift
            for shift in shifts['managers'] + shifts['assistants']
            if shift.is_second_manager
        ],
        'north_coords': [
            shift
            for shift in shifts['coords'] + shifts['assistants']
            if shift.is_north_south_coord and shift.coord_area == 'north'
        ],
        'south_coords': [
            shift
            for shift in shifts['coords'] + shifts['assistants']
            if shift.is_north_south_coord and shift.coord_area == 'south'
        ],
    }
    if args.debug:
        utils.cmdline.logger(
            'Filtered shifts:\n'
            + json.dumps(filtered_shifts, indent=2, cls=NestedJSONEncoder),
            level='debug',
        )

    # There will probably not be a manager on double, so it's safe to assume if we only find one manager on, there's one shift
    # Build the operating day shift times based on manager on shifts
    operating_day_meta = {
        'detected_shifts': len(filtered_shifts['managers_on']),
        'shifts': {i: {} for i in range(len(filtered_shifts['managers_on']))},
    }
    for shift in filtered_shifts['managers_on']:
        if type(shift.manager_on_times['start_time']) == datetime.time:
            m_start = shift.manager_on_times['start_time']
            m_end = shift.manager_on_times['end_time']
        else:
            # Create datetime.time objects from the manager on time strings
            m_start = datetime.datetime.strptime(
                shift.manager_on_times['start_time'], '%I:%M'
            ).time()
            m_end = datetime.datetime.strptime(
                shift.manager_on_times['end_time'], '%I:%M'
            ).time()

            # If start hour - end hour is negative, the start and end time should probably be pm, so change to 24h time equivalent
            # Otherwise, if start hour - end hour is positive, only the end time should probably be pm, so change to 24h time equivalent
            if m_start.hour - m_end.hour < 0:
                m_start = m_start.replace(hour=m_start.hour + 12)
                m_end = m_end.replace(hour=m_end.hour + 12)
            else:
                m_end = m_end.replace(hour=m_end.hour + 12)

        # Change these hours in the shift meta
        shift.manager_on_times = {
            'start_time': m_start,
            'end_time': m_end,
        }

        (
            shift_id,
            corrected_m_start,
            corrected_m_end,
            score,
            _meta_shift,
        ) = determine_shift(operating_day_meta, shift, m_start, m_end)

        # Add times and positions to the operating day meta
        operating_day_meta['shifts'][shift_id] = {
            'shift_times': {
                'start': corrected_m_start,
                'end': corrected_m_end,
            },
            'managers_on': [],
        }
        if len(filtered_shifts['second_managers']) > 0:
            operating_day_meta['shifts'][shift_id].__setitem__('second_managers', [])
        if len(filtered_shifts['north_coords']) > 0:
            operating_day_meta['shifts'][shift_id].__setitem__('north_coords', [])
        if len(filtered_shifts['south_coords']) > 0:
            operating_day_meta['shifts'][shift_id].__setitem__('south_coords', [])

    # Build the manager on shifts
    for meta_shift_id, meta_shift in operating_day_meta['shifts'].items():
        if args.debug:
            utils.cmdline.logger(
                f'Running manager on for meta shift {meta_shift_id}', level='debug'
            )
        for shift in filtered_shifts['managers_on']:
            shift_scored = determine_shift(
                operating_day_meta,
                shift,
                meta_shift['shift_times']['start'],
                meta_shift['shift_times']['end'],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    f'>{shift_scored[4].employee} score: {shift_scored[3]}',
                    level='debug',
                )
            meta_shift['managers_on'].append({
                'name': shift.employee,
                'score': shift_scored[3],
            })

    # Build the second manager shifts
    for meta_shift_id, meta_shift in operating_day_meta['shifts'].items():
        if args.debug:
            utils.cmdline.logger(
                f'Running second manager for meta shift {meta_shift_id}', level='debug'
            )
        for shift in filtered_shifts['second_managers']:
            shift_scored = determine_shift(
                operating_day_meta,
                shift,
                meta_shift['shift_times']['start'],
                meta_shift['shift_times']['end'],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    f'>{shift_scored[4].employee} score: {shift_scored[3]}',
                    level='debug',
                )
            meta_shift['second_managers'].append({
                'name': shift.employee,
                'score': shift_scored[3],
            })

    # Build the north coord shifts
    for meta_shift_id, meta_shift in operating_day_meta['shifts'].items():
        if args.debug:
            utils.cmdline.logger(
                f'Running north coord for meta shift {meta_shift_id}', level='debug'
            )
        for shift in filtered_shifts['north_coords']:
            shift_scored = determine_shift(
                operating_day_meta,
                shift,
                meta_shift['shift_times']['start'],
                meta_shift['shift_times']['end'],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    f'>{shift_scored[4].employee} score: {shift_scored[3]}',
                    level='debug',
                )
            meta_shift['north_coords'].append({
                'name': shift.employee,
                'score': shift_scored[3],
            })
    #
    ## Build the south coord shifts
    for meta_shift_id, meta_shift in operating_day_meta['shifts'].items():
        if args.debug:
            utils.cmdline.logger(
                f'Running south coord for meta shift {meta_shift_id}', level='debug'
            )
        for shift in filtered_shifts['south_coords']:
            shift_scored = determine_shift(
                operating_day_meta,
                shift,
                meta_shift['shift_times']['start'],
                meta_shift['shift_times']['end'],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    f'>{shift_scored[4].employee} score: {shift_scored[3]}',
                    level='debug',
                )
            meta_shift['south_coords'].append({
                'name': shift.employee,
                'score': shift_scored[3],
            })

    if args.debug:
        utils.cmdline.logger(
            'Operating day:\n'
            + json.dumps(operating_day_meta, indent=2, cls=NestedJSONEncoder),
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

        for shift_id, shift in shifts['shifts'].items():
            if shifts['detected_shifts'] == 2:
                outlist.append('First shift:' if shift_id == 0 else '\nSecond shift:')
            if 'managers_on' in shift and len(shift['managers_on']) > 0:
                outlist.append(
                    prefixes['manager_on']
                    + max(shift['managers_on'], key=lambda s: s['score'])['name']
                )
            if 'second_managers' in shift and len(shift['second_managers']) > 0:
                outlist.append(
                    prefixes['second_manager']
                    + max(shift['second_managers'], key=lambda s: s['score'])['name']
                )
            if 'north_coords' in shift and len(shift['north_coords']) > 0:
                outlist.append(
                    prefixes['north']
                    + max(shift['north_coords'], key=lambda s: s['score'])['name']
                )
            if 'south_coords' in shift and len(shift['south_coords']) > 0:
                outlist.append(
                    prefixes['south']
                    + max(shift['south_coords'], key=lambda s: s['score'])['name']
                )

        outlist.extend([
            '',
            f'Shifts updated at {nowtime.strftime("%H:%M")}',
            'Reply "refresh" to update',
        ])

        return outlist

    shift_msg = '\n'.join(build_message(operating_day_meta))
    if args.groupme or args.gm_debug:
        gm = GroupMe(config.groupme, debug=args.debug, dev_bot=args.gm_debug)
        gm.post(args.message if args.message else shift_msg)
    if args.debug:
        utils.cmdline.logger(f'Message for GroupMe:\n{shift_msg}', level='debug')


if __name__ == '__main__':
    import utils.cmdline

    run_bot(utils.cmdline.get_args())
