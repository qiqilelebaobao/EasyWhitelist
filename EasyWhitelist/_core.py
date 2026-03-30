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
        logging.error("[core] Failed to initialize application directory.")
        return None
    logging.info(f"[core] Application directory initialized at: {app_dir}")

    if not init_db(app_dir):
        logging.error("[core] Failed to initialize database.")
        return None
    return app_dir


def main() -> None:

    args = arg.init_arg()

    set_log(args.verbose)
    logging.info("[core] Arg parsed, detail=%s", args)

    app_dir = init_app_and_db()
    logging.info("[core] Application and database initialization complete, app_dir=%s", app_dir)

    cloud_provider = args.cloud
    logging.info("[core] Cloud provider selected, provider=%s", cloud_provider.upper())

    if cloud_provider == "tencent":
        sys.exit(t_main(args.action, args.target, args.target_id, args.region, args.proxy))
    elif cloud_provider == "alibaba":
        sys.exit(aliyun_main(args.action, args.target, args.target_id, args.proxy, app_dir=app_dir))
    else:
        logging.error("[core] Unsupported cloud provider, reason=unknown provider, detail=%s", cloud_provider)
        sys.exit(1)
