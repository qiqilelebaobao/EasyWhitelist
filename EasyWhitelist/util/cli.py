from .defaults import _BOLD, _CYAN, _GREEN, _RED, _RST
from typing import Optional, List

COLS = {
    "idx": 5,
    "region": 16,
    "id": 25,
    "name": 30,
    "ctime": 20,
    "addrs": 35,
}

COLS_INIT = {
    "idx": 5,
    "region": 16,
    "id": 25,
    "name": 30,
    "addrs": 60,
}

HEADER_WIDTH = sum(COLS.values())
_COL_WIDTHS = list(COLS.values())
HEADER_WIDTH_INIT = sum(COLS_INIT.values())
_COL_WIDTHS_INIT = list(COLS_INIT.values())


def echo_ok(msg: str) -> None:
    """Print a success line: green ✔  message."""
    print(f"  {_GREEN}\u2714{_RST}  {msg}")


def echo_err(msg: str) -> None:
    """Print an error line:   red  ✘  message."""
    print(f"  {_RED}\u2718{_RST}  {msg}")


def echo_info(msg: str) -> None:
    """Print an info line:   cyan ›  message."""
    print(f"  {_CYAN}\u203a{_RST}  {msg}")


def echo_start(msg: str) -> None:
    """Print a start line:  🎯 [开始] message."""
    print(f"\U0001f3af [\u5f00\u59cb] {msg}")


def echo_progress(msg: str) -> None:
    """Print a progress line: 🔄 [进行中] message."""
    print(f"\U0001f504 [\u8fdb\u884c\u4e2d] {msg}")


def echo_success(msg: str) -> None:
    """Print a success line:  ✅ [成功] message."""
    print(f"\u2705 [\u6210\u529f] {msg}")


def echo_fail(msg: str) -> None:
    """Print a failure line:  ❌ [失败] message."""
    print(f"\u274c [\u5931\u8d25] {msg}")


def echo_abort(msg: str) -> None:
    """Print an abort line:   ❗ [中止] message."""
    print(f"\u2757 [\u4e2d\u6b62] {msg}")


def echo_hint(msg: str) -> None:
    """Print a hint line:     📌 [提示] message."""
    print(f"\U0001f4cc [\u63d0\u793a] {msg}")


def _build_line(left: str, mid: str, right: str, fill: str = '\u2500', widths: Optional[List[int]] = None) -> str:
    """Build a separator line using given column widths.

    If `widths` is None, use the default `_COL_WIDTHS`.
    """
    use_widths = _COL_WIDTHS if widths is None else widths
    return left + mid.join(fill * w for w in use_widths) + right


def print_header(title: str) -> None:
    table_width = HEADER_WIDTH + len(COLS) + 1
    col_names = ['#', 'Region', 'Template ID', 'Name', 'CreatedTime', 'Addresses']
    cells = [f"{_BOLD}{n:<{w}}{_RST}" for n, w in zip(col_names, _COL_WIDTHS)]

    print(f"\n{_BOLD}{_CYAN}{title:^{table_width}}{_RST}")
    print(_build_line('\u250c', '\u252c', '\u2510', widths=_COL_WIDTHS))
    print('\u2502' + '\u2502'.join(cells) + '\u2502')
    print(_build_line('\u251c', '\u253c', '\u2524', widths=_COL_WIDTHS))


def print_header_init(title: str) -> None:
    table_width = HEADER_WIDTH_INIT + len(COLS_INIT) + 1
    col_names = ['#', 'Region', 'PrefixList ID', 'Name', 'Addresses']
    cells = [f"{_BOLD}{n:<{w}}{_RST}" for n, w in zip(col_names, _COL_WIDTHS_INIT)]

    print(f"\n{_BOLD}{_CYAN}{title:^{table_width}}{_RST}")
    print(_build_line('\u250c', '\u252c', '\u2510', widths=_COL_WIDTHS_INIT))
    print('\u2502' + '\u2502'.join(cells) + '\u2502')
    print(_build_line('\u251c', '\u253c', '\u2524', widths=_COL_WIDTHS_INIT))


def print_row(**values) -> None:
    """Print a table row. Pass column values as keyword arguments matching COLS keys."""
    cells = [f"{str(values.get(key, '')):<{width}}" for key, width in COLS.items()]
    print('\u2502' + '\u2502'.join(cells) + '\u2502')


def print_row_init(**values) -> None:
    """Print a table row for initialization. Pass column values as keyword arguments matching COLS_INIT keys."""
    cells = [f"{str(values.get(key, '')):<{width}}" for key, width in COLS_INIT.items()]
    print('\u2502' + '\u2502'.join(cells) + '\u2502')


def print_separator(widths: Optional[List[int]] = None) -> None:
    """Print a row separator. By default uses main table widths; pass widths to use others."""
    print(_build_line('\u251c', '\u253c', '\u2524', '\u2504', widths=widths))


def print_tail(widths: Optional[List[int]] = None) -> None:
    """Print table tail/end line. By default uses main table widths; pass widths to use others."""
    print(_build_line('\u2514', '\u2534', '\u2518', widths=widths))
    print()


def print_tail_init() -> None:
    """Print table tail/end line for initialization. By default uses init table widths; pass widths to use others."""
    print_tail(widths=_COL_WIDTHS_INIT)


def print_update_banner(title: str) -> None:
    """Print a compact banner for update operations."""
    width = 60
    print(f"\n  {_BOLD}{_CYAN}{'\u2500' * 3} {title} {'\u2500' * (width - len(title) - 5)}{_RST}")


def print_ip_list(ip_list: list) -> None:
    """Print detected IPs in a compact list."""
    for ip in ip_list:
        print(f"    {_CYAN}\u25B8{_RST}  {ip}")


def print_region_result(region: str, prefix_id: str, success: bool) -> None:
    """Print a single region update result line."""
    mark = f"{_GREEN}\u2714{_RST}" if success else f"{_RED}\u2718{_RST}"
    status = "ok" if success else "failed"
    print(f"    {mark}  {region:<20} {prefix_id:<30} {status}")


def print_summary(total: int, failed: int) -> None:
    """Print a final summary line for update operations."""
    succeeded = total - failed
    if failed == 0:
        print(f"\n  {_GREEN}\u2714{_RST}  Done: {succeeded}/{total} prefix list(s) updated successfully\n")
    else:
        print(f"\n  {_RED}\u2718{_RST}  Done: {succeeded}/{total} succeeded, {failed} failed\n")
