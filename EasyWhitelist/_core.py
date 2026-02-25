import logging

from .config import arg
from .config.log import set_log
from .tcloud.core import t_main


def main() -> None:

    # tencent, alibaba, action, target, target_id, proxy, verbose = arg.init_arg()
    args = arg.init_arg()

    set_log(args.verbose)
    logging.info("[cli] arg parsed, detail=%s", args)

    cloud_provider = args.cloud
    logging.info("[cli] cloud provider selected, provider=%s", cloud_provider.upper())

    if cloud_provider == "tencent":
        t_main(args.action, args.target, args.target_id,  args.region, args.proxy)
