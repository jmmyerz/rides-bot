import datetime, json, regex as re
import requests, requests.cookies, requests.utils

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
        start_time: str = "",
        end_time: str = "",
        total_hours: str = "",
        description: str = "",
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
            if len(times) > 0:
                self._manager_start = times["start_time"]
                self._manager_end = times["end_time"]
            else:
                self._manager_start = self.start_time
                self._manager_end = self.end_time

    def __iter__(self):
        dict = {
            "employee": self.employee,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_hours": self.total_hours,
            "description": self.description,
            "meta": {
                "is_am_shift": self.is_am_shift,
                "is_pm_shift": self.is_pm_shift,
                "is_double_shift": self.is_double_shift,
                "is_manager_on": self.is_manager_on,
                "is_second_manager": self.is_second_manager,
                "is_north_south_coord": self.is_north_south_coord,
            },
        }
        if self.is_manager_on:
            dict["meta"] |= {"manager_on_times": self.manager_on_times}
        if self.is_north_south_coord:
            dict["meta"] |= {"coord_area": self.coord_area}

        yield from dict.items()

    def __str__(self):
        return json.dumps(self.to_dict, cls=NestedJSONEncoder)

    def __repr__(self):
        return self.__str__

    # Internal method to change W2W time to a time object
    def _to_time(self, time_str: str) -> datetime.time:
        formats = [
            "%I%p",  # e.g. 3pm
            "%I:%M%p",  # e.g. 11:30am
            "%I:%M",  # e.g. 8:00
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
            "is_manager_on": r"(?:manager taking calls|manager on)",
            "manager_on_times": r"(?:manager taking calls|manager on)(?>\s?)(?P<start_time>[0-9]{1,2}:?[0-9]{0,2})(?P<start_am_pm>am|pm|a|p?)?(?>[\s-]+)(?P<end_time>[0-9]{1,2}:?[0-9]{0,2})(?P<end_am_pm>am|pm|a|p?)?",
            "is_second_manager": r"second manager",
            "is_north_south_coord": r"^(?<!(?:shadow\s))(?P<which>north|south)(\s?(?=coord|coordinator)|$)",
        }
        _description_patterns_fuzzy = {
            "is_manager_on": f"({description_regex['is_manager_on']}){{2s+2i+2d<=3}}",
            "manager_on_times": f"({description_regex['manager_on_times']}){{1s+2i+2d<=3}}",
            "is_second_manager": f"({description_regex['is_second_manager']}){{1s+2i+2d<=3}}",
            "is_north_south_coord": f"({description_regex['is_north_south_coord']}){{1s+2i+2d<=3}}",
        }
        return _description_patterns_fuzzy[key]

    def _get_manager_times(self) -> dict:
        match = (
            re.search(
                self._description_regex("manager_on_times"),
                self.description,
                re.BESTMATCH | re.IGNORECASE,
            )
            if self.is_manager_on
            else None
        )
        start_time = match.group("start_time") if match is not None else None
        end_time = match.group("end_time") if match is not None else None

        # Create datetime.time objects from the manager on time strings
        # Strings could be formatted as 8, 8:00, 8:30, 8am, 8:30am, 8:30a, 8:30p, etc.
        # Match groups are start_time, start_am_pm, end_time, end_am_pm

        start_am_pm = match.group("start_am_pm") if match is not None else None
        end_am_pm = match.group("end_am_pm") if match is not None else None

        if start_time is not None:
            if start_am_pm is not None:
                if start_am_pm in ["a", "p"]:
                    start_am_pm = f"{start_am_pm}m"
                # Sanity check that shouldn't be necessary!
                # Start time should never be between 0-6am, so if it is, it's probably pm
                if int(start_time.split(":")[0]) < 6:
                    start_am_pm = "pm"
                start_time = f"{start_time}{start_am_pm}"
                start_time = self._to_time(start_time)
            else:
                start_time = self._to_time(start_time)

        if end_time is not None:
            if end_am_pm is not None:
                if end_am_pm in ["a", "p"]:
                    end_am_pm = f"{end_am_pm}m"
                # Sanity check that shouldn't be necessary!
                # End time should never be am, except maybe 12am or 1am on a rare occasion
                if end_am_pm == "am" and int(end_time.split(":")[0]) > 1:
                    end_am_pm = "pm"
                end_time = f"{end_time}{end_am_pm}"
                end_time = self._to_time(end_time)
            else:
                end_time = self._to_time(end_time)

        return (
            {
                "start_time": start_time,
                "end_time": end_time,
            }
            if match is not None
            else {}
        )

    @property
    def to_dict(self):
        return dict(self)

    @property
    def start_am_pm(self) -> str:
        return "am" if self.start_time.hour < 12 else "pm"

    @property
    def end_am_pm(self) -> str:
        return "am" if self.end_time.hour < 12 else "pm"

    @property
    def is_am_shift(self) -> bool:
        return True if self.start_am_pm == "am" else False

    @property
    def is_pm_shift(self) -> bool:
        return True if self.start_am_pm == "pm" or self.end_time.hour >= 17 else False

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
            self._description_regex("is_manager_on"),
            self.description,
            re.BESTMATCH | re.IGNORECASE,
        )
        return match is not None

    @property
    def manager_on_times(self) -> dict:
        if not self._manager_start or not self._manager_end:
            return self._get_manager_times()
        else:
            return {
                "start_time": self._manager_start,
                "end_time": self._manager_end,
            }

    @manager_on_times.setter
    def manager_on_times(self, set_dict) -> None:
        self._manager_start = set_dict["start_time"]
        self._manager_end = set_dict["end_time"]

    @property
    def is_second_manager(self) -> bool:
        match = re.search(
            self._description_regex("is_second_manager"),
            self.description,
            re.BESTMATCH | re.IGNORECASE,
        )
        return match is not None

    @property
    def is_north_south_coord(self) -> bool:
        match = re.search(
            self._description_regex("is_north_south_coord"),
            self.description,
            re.BESTMATCH | re.IGNORECASE,
        )
        return match is not None

    @property
    def coord_area(self) -> str | None:
        match = (
            re.search(
                self._description_regex("is_north_south_coord"),
                self.description,
                re.BESTMATCH | re.IGNORECASE,
            )
            if self.is_north_south_coord
            else None
        )
        return match.group("which").lower() if match is not None else None


class W2WSession:

    def __init__(self, config: Config, debug: bool = False):
        self._w2wconf = config
        self._debug = debug
        self._session = requests.Session()

        # Determine if we already have cookies, and either add them to the session or login
        if hasattr(self._w2wconf, "cookies") and self._w2wconf.cookies is not None:
            self._session.cookies.update(
                requests.cookies.cookiejar_from_dict(self._w2wconf.cookies)
            )
        else:
            self._login(reason="missing cookie")

        # If we haven't stored the SID or the DLL (which w2w changes, frustratingly) then login
        if not hasattr(self._w2wconf, "session_id") or self._w2wconf.session_id == None:
            self._login(reason="missing session id")
        if not hasattr(self._w2wconf, "dll") or self._w2wconf.dll == None:
            self._login(reason="missing dll")

        # Attempt to load a page with the existing SID and DLL
        # URL string is broken out to easily see the components
        url_string = (
            f"{self._w2wconf.base_url}{self._w2wconf.dll}/home?"
            f"SID={self._w2wconf.session_id}"
        )
        resp = self._session.get(url_string)

        # Handle login page (session expired), or security warnings
        if (
            re.search("Log into your WhenToWork account", resp.text, re.IGNORECASE)
            is not None
        ):
            return self._login(reason="expired")
        if (
            re.search("Your session could not be verified", resp.text, re.IGNORECASE)
            is not None
        ):
            return self._login(reason="security exception")

    # Method for logging in to W2W if we don't have a session going
    def _login(self, reason: str = "unknown") -> None:
        if self._debug:
            cmdline.logger(f"Starting login, reason: {reason}", level="debug")

        # Define some regex
        _login_regex = {
            "session_id": r"(?<=SID=)([0-9A-Za-z]+)",
            "dll": r"(?<=https:\/\/www3\.whentowork\.com\/cgi-bin\/)(.*dll)(?=\/)",
        }

        # Clear any existing cookies since we're getting a new one anyway
        self._session.cookies.clear()

        resp = self._session.post(
            self._w2wconf.login_url,
            {
                "name": "signin",
                "UserId1": self._w2wconf.username,
                "Password1": self._w2wconf.password,
                "captcha_required": "false",
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
                f"SID: {self._w2wconf.session_id} DLL: {self._w2wconf.dll}",
                level="debug",
            )

        self._w2wconf.cookies = requests.utils.dict_from_cookiejar(
            self._session.cookies
        )

    # Retrieve the schedule for a day with skill filters from the conf
    # Filter should be a tuple (label, filter id)
    def retrieve_schedule(self, filter: tuple, date="Today") -> list:
        if self._debug:
            cmdline.logger(
                f"Running filter "
                f"{cmdline.colorize(filter[0], colors=[cmdline.cmd_colors.BOLD, cmdline.cmd_colors.OKBLUE])}"
                f" ({filter[1]})",
                level="debug",
            )

        shifts = []

        # Define our regex
        _schedule_regex = {
            "swl": r"(?<=swl\()([^;]+)(?=\);)",
            "shift_data": r'"([^"]*)"|\w[^",]*',
            "shift_time": r"([0-9]{1,2}[:]?[0-9]{0,2}[a|p]m)",
            "total_hours": r"([0-9]{0,2}[\.]{1}[0-9]{0,2})\s?hour[s]?",
        }

        # Attempt to load the position view for {date} with all filters reset except skill
        # URL string is broken out to easily see the components
        url_string = (
            f"{self._w2wconf.base_url}{self._w2wconf.dll}/mgrschedule?"
            f"SID={self._w2wconf.session_id}"
            f"&lmi="
            f"&Date={date}"
            f"&View=Pos"  # Position view (we know this has swl data)
            f"&SkillFilter={filter[1]}"  # Only show our specified filter
            f"&CatFilter=-1"  # Resets any category filter
            f"&StatFilter=-1"  # Resets any stat filter
        )
        resp = self._session.get(url_string)

        # W2W returns no structure, but places all the shifts inside some javascript
        # We need to parse out the assigned shifts wrapped in the "swl();" functions
        # swl("380352058",2,"#000000","Jordan Myers","750227705","3pm - 10pm","   7.0 hours","North Coord")
        swl_data = re.findall(_schedule_regex["swl"], resp.text)

        # Pull out the relevant data
        for shift in swl_data:
            parsed = re.findall(_schedule_regex["shift_data"], shift)
            obj = Shift(
                employee=parsed[3],
                start_time=re.findall(_schedule_regex["shift_time"], parsed[5])[0],
                end_time=re.findall(_schedule_regex["shift_time"], parsed[5])[1],
                total_hours=re.findall(_schedule_regex["total_hours"], parsed[6])[0],
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


# Debuggin' time
if __name__ == "__main__":
    config = conf_debug()
    session = W2WSession(config.whentowork, debug=True)

    debug_shifts: dict = {}
    for filter in session.w2wconf.filters.items():
        shifts = session.retrieve_schedule(filter)
        debug_shifts[filter[0]] = [shift.to_dict for shift in shifts]

    print(json.dumps(debug_shifts, indent=2, default=str))
