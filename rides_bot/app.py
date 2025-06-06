import datetime, json, sys, random
from pathlib import Path

import utils
import utils.shift_logic as shift_logic
from utils.nested_json import NestedJSONEncoder
from utils.config import Config
from utils.w2w import W2WSession
from utils.groupme import GroupMe
from utils.discord import SingleMessageClient
from utils.telegram import TelegramBot

CONFIG_FILE_PATH = (Path(__file__).parent.parent / "config.yaml").resolve()


class NoShiftsDetectedError(Exception):
    pass


def run_bot(args):
    config = Config().load(CONFIG_FILE_PATH)
    _no_shifts_flag = False

    if args.login:
        session = W2WSession(config.whentowork, debug=args.debug)
        config.save(filename=CONFIG_FILE_PATH)
        sys.exit(0)

    shifts = {}
    w2w = W2WSession(config.whentowork, debug=args.debug)
    config.save(filename=CONFIG_FILE_PATH)

    for filter in list(config["whentowork"]["filters"].items()):
        shifts[filter[0]] = w2w.retrieve_schedule(
            filter, date=args.date if args.date else "Today"
        )
    # if args.debug:
    #     utils.cmdline.logger(
    #         "Shifts JSON:\n\n" + json.dumps(shifts, indent=2, cls=NestedJSONEncoder),
    #         level="debug",
    #     )

    filtered_shifts = {
        "managers_on": [
            shift
            for shift in shifts["managers"] + shifts["assistants"]
            if shift.is_manager_on
        ],
        "second_managers": [
            shift
            for shift in shifts["managers"] + shifts["assistants"]
            if shift.is_second_manager
        ],
        "north_coords": [
            shift
            for shift in shifts["coords"] + shifts["assistants"] + shifts["managers"]
            if shift.is_north_south_coord and shift.coord_area == "north"
        ],
        "south_coords": [
            shift
            for shift in shifts["coords"] + shifts["assistants"] + shifts["managers"]
            if shift.is_north_south_coord and shift.coord_area == "south"
        ],
    }
    if args.debug:
        utils.cmdline.logger(
            "Filtered shifts:\n"
            + json.dumps(filtered_shifts, indent=2, cls=NestedJSONEncoder),
            level="debug",
        )

    # Build the operating day meta dict
    operating_day_meta = shift_logic.build_operating_day_meta(filtered_shifts)

    # If there are 2 shifts, the end time of the first shift should be the start time of the second shift
    # TODO: make this easier to read
    if len(operating_day_meta["shifts"]) == 2:
        print(f"Operating day meta: {operating_day_meta}")
        operating_day_meta["shifts"][0]["shift_times"]["end"] = operating_day_meta[
            "shifts"
        ][1]["shift_times"]["start"]

    if args.debug:
        utils.cmdline.logger(
            "Operating day meta:\n"
            + json.dumps(operating_day_meta, indent=2, cls=NestedJSONEncoder),
            level="debug",
        )

    # Build all the shift candidates
    for meta_shift_id, meta_shift in operating_day_meta["shifts"].items():
        # Build the manager on shifts
        if args.debug:
            utils.cmdline.logger(
                f"Running {utils.cmdline.cmd_colors.OKCYAN}manager on{utils.cmdline.cmd_colors.ENDC} for meta shift {meta_shift_id}",
                level="debug",
            )
        for shift in filtered_shifts["managers_on"]:
            shift_scored = shift_logic.determine_shift(
                operating_day_meta,
                shift,
                meta_shift["shift_times"]["start"],
                meta_shift["shift_times"]["end"],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    utils.cmdline.colorize(
                        f"{shift_scored[4].employee} score: {shift_scored[3]}",
                        utils.cmdline.cmd_colors.ITALIC,
                    ),
                    level="debug",
                )
            meta_shift["managers_on"].append(
                {
                    "name": shift.employee,
                    "score": shift_scored[3],
                }
            )

        # Build the second manager shifts
        if args.debug:
            utils.cmdline.logger(
                f"Running {utils.cmdline.cmd_colors.OKCYAN}second manager{utils.cmdline.cmd_colors.ENDC} for meta shift {meta_shift_id}",
                level="debug",
            )
        for shift in filtered_shifts["second_managers"]:
            shift_scored = shift_logic.determine_shift(
                operating_day_meta,
                shift,
                meta_shift["shift_times"]["start"],
                meta_shift["shift_times"]["end"],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    utils.cmdline.colorize(
                        f"{shift_scored[4].employee} score: {shift_scored[3]}",
                        utils.cmdline.cmd_colors.ITALIC,
                    ),
                    level="debug",
                )
            if shift_scored[3] <= -1000:
                # If the score is less than -1000, it was disqualified
                continue
            meta_shift["second_managers"].append(
                {
                    "name": shift.employee,
                    "score": shift_scored[3],
                }
            )

        # Build the north coord shifts
        if args.debug:
            utils.cmdline.logger(
                f"Running {utils.cmdline.cmd_colors.OKCYAN}north coord{utils.cmdline.cmd_colors.ENDC} for meta shift {meta_shift_id}",
                level="debug",
            )
        for shift in filtered_shifts["north_coords"]:
            shift_scored = shift_logic.determine_shift(
                operating_day_meta,
                shift,
                meta_shift["shift_times"]["start"],
                meta_shift["shift_times"]["end"],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    utils.cmdline.colorize(
                        f"{shift_scored[4].employee} score: {shift_scored[3]}",
                        utils.cmdline.cmd_colors.ITALIC,
                    ),
                    level="debug",
                )
            if shift_scored[3] <= -1000:
                # If the score is less than -1000, it was disqualified
                continue
            meta_shift["north_coords"].append(
                {
                    "name": shift.employee,
                    "score": shift_scored[3],
                }
            )

        # Build the south coord shifts
        if args.debug:
            utils.cmdline.logger(
                f"Running {utils.cmdline.cmd_colors.OKCYAN}south coord{utils.cmdline.cmd_colors.ENDC} for meta shift {meta_shift_id}",
                level="debug",
            )
        for shift in filtered_shifts["south_coords"]:
            shift_scored = shift_logic.determine_shift(
                operating_day_meta,
                shift,
                meta_shift["shift_times"]["start"],
                meta_shift["shift_times"]["end"],
                match_multiple=True,
                shift_id=meta_shift_id,
            )
            if args.debug:
                utils.cmdline.logger(
                    utils.cmdline.colorize(
                        f"{shift_scored[4].employee} score: {shift_scored[3]}",
                        utils.cmdline.cmd_colors.ITALIC,
                    ),
                    level="debug",
                )
            if shift_scored[3] <= -1000:
                # If the score is less than -1000, it was disqualified
                continue
            meta_shift["south_coords"].append(
                {
                    "name": shift.employee,
                    "score": shift_scored[3],
                }
            )

    if args.debug:
        utils.cmdline.logger(
            "Operating day:\n"
            + json.dumps(operating_day_meta, indent=2, cls=NestedJSONEncoder),
            level="debug",
        )

    def build_message(shifts: dict) -> list:
        prefixes = {
            "manager_on": "Manager on: ",
            "second_manager": "Second manager: ",
            "north": "North coord: ",
            "south": "South coord: ",
        }

        if not len(shifts["shifts"]):
            # No shifts detected, no need to continue
            raise NoShiftsDetectedError

        if args.date:
            message_date = datetime.datetime.strptime(args.date, "%m/%d/%Y")
        else:
            message_date = datetime.datetime.now()

        nowtime = datetime.datetime.now().time()
        rand = random.randint(0, 25)
        match (nowtime):
            case nowtime if nowtime.hour <= 11 and rand != 13:
                friendly_time = "Good morning! 🌤️️🎢"
            case nowtime if 12 <= nowtime.hour <= 17 and rand != 13:
                friendly_time = "Good afternoon! ☀️🎢"
            case nowtime if nowtime.hour >= 18 and rand != 13:
                friendly_time = "Good evening! 🌙🎢"
            case _:
                friendly_time = "Hi there! 😀🎢"

        outlist = [
            friendly_time,
            f'Management team for {message_date.strftime("%B %d, %Y")}',
            "",
        ]

        for shift_id, shift in shifts["shifts"].items():
            if shifts["detected_shifts"] == 2:
                time_fmts = ("%-I:%M%p", "%-I%p")

                # Extract the start and end times of the shift and format them
                start_time = shift["shift_times"]["start"].strftime(
                    time_fmts[0]
                    if shift["shift_times"]["start"].minute != 0
                    else time_fmts[1]
                )
                end_time = shift["shift_times"]["end"].strftime(
                    time_fmts[0]
                    if shift["shift_times"]["end"].minute != 0
                    else time_fmts[1]
                )

                # Prefix determination
                prefix = "" if shift_id == 0 else "\n"

                outlist.append(
                    f"{prefix}From {start_time.lower()} to {end_time.lower()}:"
                )
            if "managers_on" in shift and len(shift["managers_on"]) > 0:
                outlist.append(
                    prefixes["manager_on"]
                    + max(shift["managers_on"], key=lambda s: s["score"])["name"]
                    + ("*" if "duplicate" in shift and shift["duplicate"] else "")
                )
            if "second_managers" in shift and len(shift["second_managers"]) > 0:
                outlist.append(
                    prefixes["second_manager"]
                    + max(shift["second_managers"], key=lambda s: s["score"])["name"]
                )
            if "north_coords" in shift and len(shift["north_coords"]) > 0:
                outlist.append(
                    prefixes["north"]
                    + max(shift["north_coords"], key=lambda s: s["score"])["name"]
                )
            if "south_coords" in shift and len(shift["south_coords"]) > 0:
                outlist.append(
                    prefixes["south"]
                    + max(shift["south_coords"], key=lambda s: s["score"])["name"]
                )

        if "errors" in shifts and len(shifts["errors"]) > 0:
            outlist.extend([""])
            outlist.extend([f"*{error}" for error in shifts["errors"]])

        outlist.extend(
            [
                "",
                f'Shifts updated at {nowtime.strftime("%H:%M")}',
                'Reply "refresh" to update',
            ]
        )

        return outlist

    try:
        shift_msg = "\n".join(build_message(operating_day_meta))
    except NoShiftsDetectedError:
        if args.debug:
            utils.cmdline.logger(
                "No shifts detected, exiting",
                level="debug",
            )
        _no_shifts_flag = True

    if not _no_shifts_flag:
        # The south message should remove lines beginning with "Second manager: " or "North coord: "
        south_message = "\n".join(
            [
                line
                for line in shift_msg.split("\n")
                if not line.startswith("Second manager: ")
                and not line.startswith("North coord: ")
            ]
        )

        # The north message should remove lines beginning with "Second manager: " or "South coord: "
        north_message = "\n".join(
            [
                line
                for line in shift_msg.split("\n")
                if not line.startswith("Second manager: ")
                and not line.startswith("South coord: ")
            ]
        )

        # Set both groupme_a910_message and discord_message to south_message
        groupme_a910_message = discord_message = south_message

        # Set telegram_message to north_message
        telegram_message = north_message

        if hasattr(args, "return_discord_message") and args.return_discord_message:
            # print("Returning discord message")
            return discord_message

        if hasattr(args, "return_telegram_message") and args.return_telegram_message:
            # print("Returning telegram message")
            return telegram_message

    def _send_messages(messages: dict):
        if args.groupme or args.gm_debug or args.groupme910 or args.groupme_north:
            gm = GroupMe(
                config.groupme,
                debug=args.debug,
                main_bot=args.groupme,
                dev_bot=args.gm_debug,
                a910_bot=args.groupme910,
                north_bot=args.groupme_north,
            )
            _messages = {
                "main": messages["shift_msg"],
                "a910": messages["groupme_a910_message"],
                "north": messages["north_message"],
            }
            gm.post(args.message if args.message else _messages)
        if args.discord or args.discord_debug:
            channel_id = (
                config.discord.test_channel_id
                if args.discord_debug
                else config.discord.main_channel_id
            )
            ds = SingleMessageClient(
                channel_id=channel_id, message=messages["discord_message"]
            )
            ds.run(config.discord.bot_token)
        if args.telegram12 or args.telegram_debug:
            tb = TelegramBot(config)
            tb.send(
                messages["telegram_message"],
                (
                    config.telegram.a12_chat_id
                    if args.telegram12
                    else config.telegram.test_chat_id
                ),
            )

    def _print_messages_debug():
        if args.debug:
            utils.cmdline.logger(f"Message for GroupMe:\n{shift_msg}", level="debug")
            utils.cmdline.logger(
                f"Message for Discord:\n{discord_message}", level="debug"
            )

    ####### EOS 2024 #######
    # TODO: Move this to something that pulls a special schedule from YAML and returns early
    #       instead of only executing after whentowork has been polled

    # Check if today is EOS 2024 (November 4)
    _run_against_date = datetime.datetime.now().date()
    if args.date:
        _run_against_date = datetime.datetime.strptime(args.date, "%m/%d/%Y").date()

    if _run_against_date == datetime.datetime(2024, 11, 4).date():
        message = "Thanks for a great season. See you in 2025! 🎢🎉"
        _send_messages(
            {
                "shift_msg": message,
                "groupme_a910_message": message,
                "discord_message": message,
                "north_message": message,
                "telegram_message": message,
            }
        )
        if args.debug:
            utils.cmdline.logger(f"Special message:\n{message}", level="debug")
        return

    # Check if today is after EOS 2024 (November 4)
    # TODO: See above... but this is being commented out for now so we can start running the bot for 2025
    # elif _run_against_date > datetime.datetime(2024, 11, 4).date():
    #    return

    if not _no_shifts_flag:
        _send_messages(
            {
                "shift_msg": shift_msg,
                "groupme_a910_message": groupme_a910_message,
                "discord_message": discord_message,
                "north_message": north_message,
                "telegram_message": telegram_message,
            }
        )
        _print_messages_debug()


if __name__ == "__main__":
    import utils.cmdline

    run_bot(utils.cmdline.get_args())
