import datetime, json, re
import requests, requests.cookies, requests.utils
from typing import Tuple

from . import cmdline
from .nested_json import NestedJSONEncoder
from .config import Config, debug as conf_debug


class Employee:

    def __init__(self, name: str):
        self.name = name


class Shift:

    def __init__(
        self,
        employee: Employee,
        start_time: str = '',
        end_time: str = '',
        total_hours: str = '',
        description: str = '',
    ):
        self.employee = employee
        self._start_time_str = start_time
        self.start_time = self._to_time(start_time)
        self._end_time_str = end_time
        self.end_time = self._to_time(end_time)
        self._total_hours_str = total_hours
        self.total_hours = float(total_hours)
        self.description = description

        if self.is_manager_on:
            times = self._get_manager_times()
            self._manager_start = times['start_time']
            self._manager_end = times['end_time']

    def __iter__(self):
        dict = {
            'employee': self.employee,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_hours': self.total_hours,
            'description': self.description,
            'meta': {
                'is_am_shift': self.is_am_shift,
                'is_pm_shift': self.is_pm_shift,
                'is_double_shift': self.is_double_shift,
                'is_manager_on': self.is_manager_on,
                'is_second_manager': self.is_second_manager,
                'is_north_south_coord': self.is_north_south_coord,
            },
        }
        if self.is_manager_on:
            dict['meta'] |= {'manager_on_times': self.manager_on_times}
        if self.is_north_south_coord:
            dict['meta'] |= {'coord_area': self.coord_area}

        yield from dict.items()

    def __str__(self):
        return json.dumps(self.to_dict, cls=NestedJSONEncoder)

    def __repr__(self):
        return self.__str__

    # Internal method to change W2W time to a time object
    def _to_time(self, time_str: str) -> datetime.time:
        formats = [
            '%I%p',  # e.g. 3pm
            '%I:%M%p',  # e.g. 11:30am
        ]

        # Set the default time to midnight and try all the formats
        time_obj: datetime.time = datetime.time(0, 0)
        for format in formats:
            try:
                time_obj = datetime.datetime.strptime(time_str, format).time()
            except ValueError:
                pass

        return time_obj

    # Hold the regex for our description filters
    def _description_regex(self, key: str):
        description_regex = {
            'is_manager_on': r'(?<=manager taking calls)',
            'manager_on_times': r'(?<=manager taking calls)(?>\s?)(?P<start_time>[0-9]{1,2}:?[0-9]{0,2})(?:am|pm)?(?>[\s-]+)(?P<end_time>[0-9]{1,2}:?[0-9]{0,2})(?:am|pm)?',
            'is_second_manager': r'second manager',
            'is_north_south_coord': r'^(?<!(?:shadow\s))(?P<which>north|south)\s?(?:coord)?',
        }
        return description_regex[key]

    def _get_manager_times(self) -> dict:
        match = (
            re.search(
                self._description_regex('manager_on_times'),
                self.description,
                re.IGNORECASE,
            )
            if self.is_manager_on
            else None
        )
        return (
            {
                'start_time': match.group('start_time'),
                'end_time': match.group('end_time'),
            }
            if match is not None
            else {}
        )

    @property
    def to_dict(self):
        return dict(self)

    @property
    def start_am_pm(self) -> str:
        return 'am' if self.start_time.hour < 12 else 'pm'

    @property
    def end_am_pm(self) -> str:
        return 'am' if self.end_time.hour < 12 else 'pm'

    @property
    def is_am_shift(self) -> bool:
        return True if self.start_am_pm == 'am' else False

    @property
    def is_pm_shift(self) -> bool:
        return True if self.start_am_pm == 'pm' or self.end_time.hour >= 17 else False

    @property
    def is_double_shift(self) -> bool:
        if self.is_am_shift and self.is_pm_shift:
            return True if self.total_hours >= 10 else False
        else:
            return False

    # Properties defined by tests against description
    @property
    def is_manager_on(self) -> bool:
        match = re.search(
            self._description_regex('is_manager_on'), self.description, re.IGNORECASE
        )
        return match is not None

    @property
    def manager_on_times(self) -> dict:
        if not self._manager_start or not self._manager_end:
            return self._get_manager_times()
        else:
            return {
                'start_time': self._manager_start,
                'end_time': self._manager_end,
            }

    @manager_on_times.setter
    def manager_on_times(self, set_dict) -> None:
        self._manager_start = set_dict['start_time']
        self._manager_end = set_dict['end_time']

    @property
    def is_second_manager(self) -> bool:
        match = re.search(
            self._description_regex('is_second_manager'),
            self.description,
            re.IGNORECASE,
        )
        return match is not None

    @property
    def is_north_south_coord(self) -> bool:
        match = re.search(
            self._description_regex('is_north_south_coord'),
            self.description,
            re.IGNORECASE,
        )
        return match is not None

    @property
    def coord_area(self) -> str | None:
        match = (
            re.search(
                self._description_regex('is_north_south_coord'),
                self.description,
                re.IGNORECASE,
            )
            if self.is_north_south_coord
            else None
        )
        return match.group('which').lower() if match is not None else None


class W2WSession:

    def __init__(self, config: Config, debug: bool = False):
        self._w2wconf = config
        self._debug = debug
        self._session = requests.Session()

        # Determine if we already have cookies, and either add them to the session or login
        if hasattr(self._w2wconf, 'cookies') and self._w2wconf.cookies is not None:
            self._session.cookies.update(
                requests.cookies.cookiejar_from_dict(self._w2wconf.cookies)
            )
        else:
            self._login(reason='missing cookie')

        # If we haven't stored the SID or the DLL (which w2w changes, frustratingly) then login
        if not hasattr(self._w2wconf, 'session_id') or self._w2wconf.session_id == None:
            self._login(reason='missing session id')
        if not hasattr(self._w2wconf, 'dll') or self._w2wconf.dll == None:
            self._login(reason='missing dll')

        # Attempt to load a page with the existing SID and DLL
        # URL string is broken out to easily see the components
        url_string = (
            f'{self._w2wconf.base_url}{self._w2wconf.dll}/home?'
            f'SID={self._w2wconf.session_id}'
        )
        resp = self._session.get(url_string)

        # Handle login page (session expired), or security warnings
        if (
            re.search('Log into your WhenToWork account', resp.text, re.IGNORECASE)
            is not None
        ):
            return self._login(reason='expired')
        if (
            re.search('Your session could not be verified', resp.text, re.IGNORECASE)
            is not None
        ):
            return self._login(reason='security exception')

    # Method for logging in to W2W if we don't have a session going
    def _login(self, reason: str = 'unknown') -> None:
        if self._debug:
            cmdline.logger(f'Starting login, reason: {reason}', level='debug')

        # Define some regex
        _login_regex = {
            'session_id': r'(?<=SID=)([0-9A-Za-z]+)',
            'dll': r'(?<=https:\/\/www3\.whentowork\.com\/cgi-bin\/)(.*dll)(?=\/)',
        }

        # Clear any existing cookies since we're getting a new one anyway
        self._session.cookies.clear()

        resp = self._session.post(
            self._w2wconf.login_url,
            {
                'name': 'signin',
                'UserId1': self._w2wconf.username,
                'Password1': self._w2wconf.password,
                'captcha_required': 'false',
            },
            allow_redirects=True,
        )

        # Retrieve the SID and DLL, and store them in the config
        for key, pattern in _login_regex.items():
            match = re.search(pattern, resp.url)
            if match is not None:
                self._w2wconf.__setattr__(key, match.group(1))

        if self._debug:
            cmdline.logger(
                f'SID: {self._w2wconf.session_id} DLL: {self._w2wconf.dll}',
                level='debug',
            )

        self._w2wconf.cookies = requests.utils.dict_from_cookiejar(
            self._session.cookies
        )

    # Retrieve the schedule for a day with skill filters from the conf
    # Filter should be a tuple (label, filter id)
    def retrieve_schedule(self, filter: tuple, date='Today') -> list:
        if self._debug:
            cmdline.logger(
                f'Running filter '
                f'{cmdline.colorize(filter[0], colors=[cmdline.cmd_colors.BOLD, cmdline.cmd_colors.OKBLUE])}'
                f' ({filter[1]})',
                level='debug',
            )

        shifts = []

        # Define our regex
        _schedule_regex = {
            'swl': r'(?<=swl\()([^;]+)(?=\);)',
            'shift_data': r'"([^"]*)"|\w[^",]*',
            'shift_time': r'([0-9]{1,2}[:]?[0-9]{0,2}[a|p]m)',
            'total_hours': r'([0-9]{0,2}[\.]{1}[0-9]{0,2})\s?hour[s]?',
        }

        # Attempt to load the position view for {date} with all filters reset except skill
        # URL string is broken out to easily see the components
        url_string = (
            f'{self._w2wconf.base_url}{self._w2wconf.dll}/mgrschedule?'
            f'SID={self._w2wconf.session_id}'
            f'&lmi='
            f'&Date={date}'
            f'&View=Pos'  # Position view (we know this has swl data)
            f'&SkillFilter={filter[1]}'  # Only show our specified filter
            f'&CatFilter=-1'  # Resets any category filter
            f'&StatFilter=-1'  # Resets any stat filter
        )
        resp = self._session.get(url_string)

        # W2W returns no structure, but places all the shifts inside some javascript
        # We need to parse out the assigned shifts wrapped in the "swl();" functions
        # swl("380352058",2,"#000000","Jordan Myers","750227705","3pm - 10pm","   7.0 hours","North Coord")
        swl_data = re.findall(_schedule_regex['swl'], resp.text)

        # Pull out the relevant data
        for shift in swl_data:
            parsed = re.findall(_schedule_regex['shift_data'], shift)
            obj = Shift(
                employee=parsed[3],
                start_time=re.findall(_schedule_regex['shift_time'], parsed[5])[0],
                end_time=re.findall(_schedule_regex['shift_time'], parsed[5])[1],
                total_hours=re.findall(_schedule_regex['total_hours'], parsed[6])[0],
                description=parsed[7],
            )

            shifts.append(obj)

        return shifts

    @property
    def w2wconf(self) -> Config:
        return self._w2wconf

    @property
    def session(self) -> requests.Session:
        return self._session


# Determine if first or second shift
# Some of these are probably extraneous but should cover several edge-case mistakes
def determine_shift(
    day_meta: dict,
    shift: Shift,
    m_start: datetime.time,
    m_end: datetime.time,
    match_multiple: bool = False,
    shift_id: int = 0,
) -> Tuple[str, datetime.time, datetime.time, int, Shift]:
    def matching_start(shift: Shift, start: datetime.time, variance: int = 2) -> bool:
        return True if abs(shift.start_time.hour - start.hour) <= variance else False

    def matching_end(shift: Shift, end: datetime.time, variance: int = 2) -> bool:
        return True if abs(shift.end_time.hour - end.hour) <= variance else False

    score = 0
    matched = 0
    id_times_score = False

    if day_meta['detected_shifts'] == 1:
        return (0, m_start, m_end, 100, shift)

    ### This set covers both correct descriptions and double shifts with a single manager on time block
    # Matches e.g. a start time of 8 and a manager time of 8-3
    if m_start.hour < 12 and matching_start(shift, m_start):
        matched += 1
        id_times_score = 0, m_start, m_end
        score += 100
    # Matches e.g. a start time of 15 and a manager time of 3-10
    elif m_start.hour >= 12 and matching_start(shift, m_start):
        matched += 1
        id_times_score = 1, m_start, m_end
        score += 100
    # Matches e.g. an end time of 15 and a manager time of 8-3
    if (
        m_end.hour <= 17
        and matching_end(shift, m_end)
        and (
            (not match_multiple and matched < 1)
            or (match_multiple and shift_id in (0, 1))
        )
    ):
        matched += 1
        id_times_score = 0, m_start, m_end
        score += 100
    # Matches e.g. an end time of 22 and a manager time of 3-10
    elif (
        m_end.hour > 17
        and matching_end(shift, m_end)
        and (
            (not match_multiple and matched < 1)
            or (match_multiple and shift_id in (0, 1))
        )
    ):
        matched += 1
        id_times_score = 1, m_start, m_end
        score += 100

    ### This set covers mistakes in the shift description
    # Matches e.g. a start time of 8 amd a mislabeled manager time of 3-10
    if (
        not matching_start(shift, m_start)
        and shift.start_time.hour < 12
        and (
            (not match_multiple and matched < 1)
            or (match_multiple and shift_id in (0, 1))
        )
    ):
        matched += 1
        id_times_score = 0, shift.start_time, shift.end_time
        score -= 50
    # Matches e.g. a start time of 15 and a mislabeled manager time of 8-3
    elif (
        not matching_start(shift, m_start)
        and shift.start_time.hour >= 12
        and (
            (not match_multiple and matched < 1)
            or (match_multiple and shift_id in (0, 1))
        )
    ):
        matched += 1
        id_times_score = 1, shift.start_time, shift.end_time
        score -= 50
    # Matches e.g. an end time of 15 amd a mislabeled manager time of 3-10
    if (
        not matching_end(shift, m_end)
        and shift.end_time.hour <= 17
        and (
            (not match_multiple and matched < 1)
            or (match_multiple and shift_id in (0, 1))
        )
    ):
        matched += 1
        id_times_score = 0, shift.start_time, shift.end_time
        score -= 50
    # Matches e.g. an end time of 22 and a mislabeled manager time of 8-3
    elif (
        not matching_end(shift, m_end)
        and shift.end_time.hour > 17
        and (
            (not match_multiple and matched < 1)
            or (match_multiple and shift_id in (0, 1))
        )
    ):
        matched += 1
        id_times_score = 1, shift.start_time, shift.end_time
        score -= 50

    if not id_times_score:
        return (-1, None, None, 0, shift)

    return id_times_score + (
        score,
        shift,
    )


# Debuggin' time
if __name__ == '__main__':
    config = conf_debug()
    session = W2WSession(config.whentowork, debug=True)

    debug_shifts: dict = {}
    for filter in session.w2wconf.filters.items():
        shifts = session.retrieve_schedule(filter)
        debug_shifts[filter[0]] = [shift.to_dict for shift in shifts]

    print(json.dumps(debug_shifts, indent=2, default=str))
