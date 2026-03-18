
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
_COL_WIDTHS = list(COLS.values())


def echo_ok(msg: str) -> None:
    """Print a success line: green ✔  message."""
    print(f"  {_GREEN}\u2714{_RST}  {msg}")


def echo_err(msg: str) -> None:
    """Print an error line:   red  ✘  message."""
    print(f"  {_RED}\u2718{_RST}  {msg}")


def echo_info(msg: str) -> None:
    """Print an info line:   cyan ›  message."""
    print(f"  {_CYAN}\u203a{_RST}  {msg}")


def _build_line(left: str, mid: str, right: str, fill: str = '\u2500') -> str:
    return left + mid.join(fill * w for w in _COL_WIDTHS) + right


def print_header(title: str) -> None:
    table_width = HEADER_WIDTH + len(COLS) + 1
    col_names = ['#', 'Region', 'Template ID', 'CreatedTime', 'Addresses', 'Name']
    cells = [f"{_BOLD}{n:<{w}}{_RST}" for n, w in zip(col_names, _COL_WIDTHS)]

    print(f"\n{_BOLD}{_CYAN}{title:^{table_width}}{_RST}")
    print(_build_line('\u250c', '\u252c', '\u2510'))
    print('\u2502' + '\u2502'.join(cells) + '\u2502')
    print(_build_line('\u251c', '\u253c', '\u2524'))


def print_row(**values) -> None:
    """Print a table row. Pass column values as keyword arguments matching COLS keys."""
    cells = [f"{str(values.get(key, '')):<{width}}" for key, width in COLS.items()]
    print('\u2502' + '\u2502'.join(cells) + '\u2502')


def print_separator() -> None:
    print(_build_line('\u251c', '\u253c', '\u2524', '\u2504'))


def print_tail() -> None:
    print(_build_line('\u2514', '\u2534', '\u2518'))
    print()
