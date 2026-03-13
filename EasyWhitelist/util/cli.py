
HEADER_WIDTH = 175
COLS = {
    "idx": 5,
    "region": 20,
    "id": 30,
    "ctime": 30,
    "addrs": 60,
    "name": 30,
}


def print_header(title: str) -> None:
    header = (f"{'#':<{COLS['idx']}}"
              f"{'Region':<{COLS['region']}}"
              f"{'Template ID':<{COLS['id']}}"
              f"{'CreatedTime':<{COLS['ctime']}}"
              f"{'Addresses':<{COLS['addrs']}}"
              f"{'AddressTemplateName':<{COLS['name']}}")

    print(f"{title:=^{HEADER_WIDTH}}")
    print(header)
    print("-" * HEADER_WIDTH)


def print_tail():
    print("-" * HEADER_WIDTH)
