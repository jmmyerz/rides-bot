import datetime, json, sys, random
from pathlib import Path

import utils
import utils.shift_logic as shift_logic
from utils.nested_json import NestedJSONEncoder
from utils.config import Config
from utils.w2w import W2WSession
from utils.groupme import GroupMe
from utils.discord import SingleMessageClient

CONFIG_FILE_PATH = (Path(__file__).parent.parent / "config.yaml").resolve()


def run_bot(args):
    config = Config().load(CONFIG_FILE_PATH)

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
    #    utils.cmdline.logger(
    #        'Shifts JSON:\n\n' + json.dumps(shifts, indent=2, cls=NestedJSONEncoder),
    #        level='debug',
    #    )

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
            for shift in shifts["coords"] + shifts["assistants"]
            if shift.is_north_south_coord and shift.coord_area == "north"
        ],
        "south_coords": [
            shift
            for shift in shifts["coords"] + shifts["assistants"]
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
                outlist.append("First shift:" if shift_id == 0 else "\nSecond shift:")
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

    shift_msg = "\n".join(build_message(operating_day_meta))

    # The discord message should remove lines beginning with "Second manager: " or "North coord: "
    discord_message = "\n".join(
        [
            line
            for line in shift_msg.split("\n")
            if not line.startswith("Second manager: ")
            and not line.startswith("North coord: ")
        ]
    )

    if hasattr(args, "return_discord_message") and args.return_discord_message:
        # print("Returning discord message")
        return discord_message

    if args.groupme or args.gm_debug:
        gm = GroupMe(config.groupme, debug=args.debug, dev_bot=args.gm_debug)
        gm.post(args.message if args.message else shift_msg)
    if args.discord or args.discord_debug:
        channel_id = (
            config.discord.test_channel_id
            if args.discord_debug
            else config.discord.main_channel_id
        )
        ds = SingleMessageClient(channel_id=channel_id, message=discord_message)
        ds.run(config.discord.bot_token)
    if args.debug:
        utils.cmdline.logger(f"Message for GroupMe:\n{shift_msg}", level="debug")
        utils.cmdline.logger(f"Message for Discord:\n{discord_message}", level="debug")


if __name__ == "__main__":
    import utils.cmdline

    run_bot(utils.cmdline.get_args())
