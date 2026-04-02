import sys
import logging

from .util.app import generate_app_directory
from .util.db import init_db
from .config import arg
from .config.log import set_log
from .tcloud.core import t_main
from .aliyun.core import aliyun_main


def init_app_and_db():
    """Initialize the application, including creating necessary directories and setting up logging."""
    app_dir = generate_app_directory()
    if app_dir is None:
        logging.error("[core] Failed to create application directory.")
        return None

    conn = init_db(app_dir)
    if not conn:
        logging.error("[core] Failed to initialize database.")
        return None
    return conn


def main() -> None:

    args = arg.init_arg()

    set_log(args.verbose)
    logging.info("[core] Parsed arguments: %s", args)

    conn = init_app_and_db()
    logging.info("[core] Initialization complete: conn=%s", conn)

    cloud_provider = args.cloud
    logging.info("[core] Cloud provider selected: %s", cloud_provider.upper())

    if cloud_provider == "tencent":
        sys.exit(t_main(args.action, args.target_id, args.proxy, conn=conn))
    elif cloud_provider == "alibaba":
        sys.exit(aliyun_main(args.action, args.target_id, args.proxy, conn=conn))
    else:
        logging.error("[core] Unsupported cloud provider: %s", cloud_provider)
        sys.exit(1)
