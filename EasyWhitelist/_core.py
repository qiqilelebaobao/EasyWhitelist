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
        logging.error("[init] Failed to initialize application directory, exiting.")
        sys.exit(1)
    logging.info(f"[init] Application directory initialized at: {app_dir}")

    if not init_db(app_dir):
        logging.error("[init] Failed to initialize database, exiting.")
        sys.exit(1)
    logging.info("[init] Database initialized successfully")


def main() -> None:

    args = arg.init_arg()

    set_log(args.verbose)
    logging.info("[cli] arg parsed, detail=%s", args)

    init_app_and_db()

    cloud_provider = args.cloud
    logging.info("[cli] cloud provider selected, provider=%s", cloud_provider.upper())

    if cloud_provider == "tencent":
        sys.exit(t_main(args.action, args.target, args.target_id, args.region, args.proxy))
    elif cloud_provider == "alibaba":
        sys.exit(aliyun_main(args.action, args.target, args.target_id, args.proxy))
    else:
        logging.error("[cli] unsupported cloud provider, reason=unknown provider, detail=%s", cloud_provider)
        sys.exit(1)
