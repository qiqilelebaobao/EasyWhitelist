import argparse


def _port(txt: str) -> int:
    """argparse type checker: 1-65535"""
    n = int(txt)
    if not 0 < n < 65536:
        raise argparse.ArgumentTypeError(f"Port must be 1-65535, got {n}")
    return n


def init_arg():
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

    # 位置参数
    parser.add_argument("-r", "--region", help="region or rule")

    parser.add_argument("target", help="template or rule",
                        choices=["template", "rule"])

    parser.add_argument("action", help="action to perform", choices=[
                        "list", "set", "create"])

    parser.add_argument("target_id", help="template id or rule id", nargs="?")

    args = parser.parse_args()

    return args
