import sys
import logging

from .config import arg
from .config.log import set_log
from .tcloud.core import t_main
from .aliyun.core import aliyun_main


def main() -> None:

    args = arg.init_arg()

    set_log(args.verbose)
    logging.info("[cli] arg parsed, detail=%s", args)

    cloud_provider = args.cloud
    logging.info("[cli] cloud provider selected, provider=%s", cloud_provider.upper())

    if cloud_provider == "tencent":
        t_main(args.action, args.target, args.target_id, args.region, args.proxy)
    elif cloud_provider == "alibaba":
        sys.exit(aliyun_main(args.action, args.target, args.target_id, args.region, args.proxy))
    else:
        logging.error("[cli] unsupported cloud provider, reason=unknown provider, detail=%s", cloud_provider)
        sys.exit(1)
