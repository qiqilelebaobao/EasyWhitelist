import argparse


def _port(txt: str) -> int:
    """argparse type checker: 1-65535"""
    try:
        n = int(txt)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Port must be an integer, got {txt!r}")
    if not 0 < n < 65536:
        raise argparse.ArgumentTypeError(f"Port must be 1-65535, got {n}")
    return n


def init_arg() -> argparse.Namespace:
    """Parse CLI for ew (cloud ACL auto-whitelist)."""

    parser = argparse.ArgumentParser(
        prog="ew",
        description="This is a cloud acl auto whitelist tool.",
        epilog="Enjoy the tool. :) ")

    # 云厂商互斥组
    cloud_grp = parser.add_mutually_exclusive_group(required=False)

    cloud_grp.add_argument(
        "-t", "--tencent", action="store_const", const="tencent", dest="cloud",
        help="use Tencent Cloud (default)"
    )
    cloud_grp.add_argument(
        "-a", "--alibaba", action="store_const", const="alibaba", dest="cloud",
        help="use Alibaba Cloud"
    )
    parser.set_defaults(cloud="tencent")  # 显式给默认值

    # 可选参数
    parser.add_argument("-p", "--proxy", type=_port,
                        metavar="port", help="local HTTP proxy port")

    parser.add_argument("-v", "--verbose", action="count", default=0)

    subparsers = parser.add_subparsers(dest="action", metavar="action", required=True)

    sub_init = subparsers.add_parser("init", help="init with a template or prefix id")
    sub_init.add_argument("target_id", help="template id or prefix id (e.g. sg-xxxxxxxx)")

    subparsers.add_parser("list", help="list current rules")
    subparsers.add_parser("set", help="set whitelist rules")

    return parser.parse_args()
