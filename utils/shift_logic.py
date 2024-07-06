from typing import Tuple
import datetime

from .w2w import Shift


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

    def get_variance(shift_time: datetime.time, manager_time: datetime.time) -> int:
        return abs(shift_time.hour - manager_time.hour)

    score = 0
    matched = 0
    id_times = False

    if day_meta["detected_shifts"] == 1:
        return (0, m_start, m_end, 100, shift)

    if True:

        if hasattr(shift, "_manager_start"):
            score -= get_variance(shift._manager_start, m_start) * 10
        if hasattr(shift, "_manager_end"):
            score -= get_variance(shift._manager_end, m_end) * 10

        ### This set covers both correct descriptions and double shifts with a single manager on time block
        # Matches e.g. a start time of 8 and a manager time of 8-3
        if m_start.hour < 12 and matching_start(shift, m_start):
            matched += 1
            id_times = 0, m_start, m_end
            score += 200
        # Matches e.g. a start time of 15 and a manager time of 3-10
        elif m_start.hour >= 12 and matching_start(shift, m_start):
            matched += 1
            id_times = 1, m_start, m_end
            score += 200

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
            id_times = 0, m_start, m_end
            score += 200
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
            id_times = 1, m_start, m_end
            score += 200

        ### This set covers mistakes in the shift description
        # Matches e.g. a start time of 8 and a mislabeled manager time of 3-10
        if (
            not matching_start(shift, m_start)
            and shift.start_time.hour < 12
            and (
                (not match_multiple and matched < 1)
                or (match_multiple and shift_id in (0, 1))
            )
        ):
            matched += 1
            id_times = 0, shift.start_time, shift.end_time

            difference = abs(shift.start_time.hour - m_start.hour)
            score -= get_variance(shift.start_time, m_start) * 10
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
            id_times = 1, shift.start_time, shift.end_time
            difference = abs(shift.start_time.hour - m_start.hour)
            score -= get_variance(shift.start_time, m_start) * 10
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
            id_times = 0, shift.start_time, shift.end_time
            difference = abs(shift.end_time.hour - m_end.hour)
            score -= get_variance(shift.end_time, m_end) * 10
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
            id_times = 1, shift.start_time, shift.end_time
            difference = abs(shift.end_time.hour - m_end.hour)
            score -= get_variance(shift.end_time, m_end) * 10

    # Score the shift based on the variance between the shift start and manager on start times
    # score -= get_variance(shift.start_time, m_start) * 10

    # Score the shift based on the variance between the shift end and manager on end times
    # score -= get_variance(shift.end_time, m_end) * 10

    # id_times = 0, shift.start_time, shift.end_time

    if not id_times:
        return (-1, None, None, 0, shift)

    return id_times + (
        score,
        shift,
    )


def build_operating_day_meta(filtered_shifts: dict) -> dict:
    # There will probably not be a manager on double, so it's safe to assume if we only find one manager on, there's one shift
    # Build the operating day shift times based on manager on shifts

    # Check number of managers in case we have a mistake
    managers_on = len(filtered_shifts["managers_on"])
    errors = []

    if managers_on > 2:
        managers_on = 2

    operating_day_meta = {
        "detected_shifts": managers_on,
        "shifts": {i: {} for i in range(managers_on)},
        "errors": errors,
    }
    for shift in filtered_shifts["managers_on"]:
        if type(shift.manager_on_times["start_time"]) == datetime.time:
            m_start = shift.manager_on_times["start_time"]
            m_end = shift.manager_on_times["end_time"]
        else:
            # Create datetime.time objects from the manager on time strings
            m_start = datetime.datetime.strptime(
                shift.manager_on_times["start_time"], "%I:%M"
            ).time()
            m_end = datetime.datetime.strptime(
                shift.manager_on_times["end_time"], "%I:%M"
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
            "start_time": m_start,
            "end_time": m_end,
        }

        (
            shift_id,
            corrected_m_start,
            corrected_m_end,
            score,
            _meta_shift,
        ) = determine_shift(operating_day_meta, shift, m_start, m_end)

        # If the shift is already filled, mark as duplicate
        if operating_day_meta["shifts"][shift_id] != {}:
            operating_day_meta["shifts"][shift_id]["duplicate"] = True
            operating_day_meta["errors"].append(
                "Multiple managers scheduled for this shift. Result may be inaccurate."
            )
        else:
            # Add times and positions to the operating day meta
            operating_day_meta["shifts"][shift_id] = {
                "shift_times": {
                    "start": corrected_m_start,
                    "end": corrected_m_end,
                },
                "managers_on": [],
            }
        if len(filtered_shifts["second_managers"]) > 0:
            operating_day_meta["shifts"][shift_id].__setitem__("second_managers", [])
        if len(filtered_shifts["north_coords"]) > 0:
            operating_day_meta["shifts"][shift_id].__setitem__("north_coords", [])
        if len(filtered_shifts["south_coords"]) > 0:
            operating_day_meta["shifts"][shift_id].__setitem__("south_coords", [])

    return operating_day_meta
