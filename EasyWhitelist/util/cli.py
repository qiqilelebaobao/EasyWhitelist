
_RST = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_CYAN = "\033[36m"

COLS = {
    "idx": 5,
    "region": 20,
    "id": 30,
    "ctime": 30,
    "addrs": 60,
    "name": 30,
}
HEADER_WIDTH = sum(COLS.values())


def echo_ok(msg: str) -> None:
    """Print a success line: green ✔  message."""
    print(f"  {_GREEN}\u2714{_RST}  {msg}")


def echo_err(msg: str) -> None:
    """Print an error line:   red  ✘  message."""
    print(f"  {_RED}\u2718{_RST}  {msg}")


def echo_info(msg: str) -> None:
    """Print an info line:   cyan ›  message."""
    print(f"  {_CYAN}\u203a{_RST}  {msg}")


def print_header(title: str) -> None:
    header = (f"{_BOLD}"
              f"{'#':<{COLS['idx']}}"
              f"{'Region':<{COLS['region']}}"
              f"{'Template ID':<{COLS['id']}}"
              f"{'CreatedTime':<{COLS['ctime']}}"
              f"{'Addresses':<{COLS['addrs']}}"
              f"{'AddressTemplateName':<{COLS['name']}}"
              f"{_RST}")

    print(f"\n{_BOLD}{_CYAN}{title:^{HEADER_WIDTH}}{_RST}")
    print("\u2500" * HEADER_WIDTH)
    print(header)
    print("\u2500" * HEADER_WIDTH)


def print_separator() -> None:
    print("\u2504" * HEADER_WIDTH)


def print_tail() -> None:
    print("\u2500" * HEADER_WIDTH + "\n")
