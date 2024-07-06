import argparse as ap


# Define cmdline colors
class cmd_colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"


def colorize(string: str, colors: list[str] = [cmd_colors.ENDC]) -> str:
    return "".join(colors) + string + cmd_colors.ENDC


# Define header styles
class headers:
    info = colorize("[info]", colors=[cmd_colors.BOLD, cmd_colors.OKCYAN])
    debug = colorize("[debug]", colors=[cmd_colors.BOLD, cmd_colors.WARNING])


# Define a logger
def logger(*args, level: str = "info") -> None:
    pre_msg = getattr(headers, level)
    print(pre_msg, *args)


# Define command line args
default_args = {
    "debug": {
        "flag": "d",
        "help": "Debug",
        "kwargs": {
            "action": "store_true",
        },
    },
    "gm_debug": {
        "flag": "X",
        "help": "Post to dev groupme",
        "kwargs": {
            "action": "store_true",
        },
    },
    "login": {
        "flag": "l",
        "help": "Login only (updates config)",
        "kwargs": {
            "action": "store_true",
        },
    },
    "groupme": {
        "flag": "g",
        "help": "Sends output to groupme",
        "kwargs": {
            "action": "store_true",
        },
    },
    "groupme910": {
        "flag": "9",
        "help": "Sends output to groupme910",
        "kwargs": {
            "action": "store_true",
        },
    },
    "discord": {
        "flag": "s",
        "help": "Sends output to discord",
        "kwargs": {
            "action": "store_true",
        },
    },
    "telegram12": {
        "flag": "t",
        "help": "Sends output to telegram a12",
        "kwargs": {
            "action": "store_true",
        },
    },
    "discord_debug": {
        "flag": "S",
        "help": "Sends output to discord debug channel",
        "kwargs": {
            "action": "store_true",
        },
    },
    "message": {
        "flag": "m",
        "help": "Arbitrary message for groupme",
        "kwargs": {},
    },
    "date": {
        "flag": "D",
        "help": "Retrieve date (MM/DD/YYYY)",
        "kwargs": {},
    },
}


# Figure out the command line
def get_args(args=default_args):
    parser = ap.ArgumentParser()
    for name, val in args.items():
        parser.add_argument(
            f"-{val['flag']}", f"--{name}", help=f"{val['help']}", **val["kwargs"]
        )
    return parser.parse_args()


if __name__ == "__main__":
    logger(get_args(), level="debug")
