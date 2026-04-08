import atexit
import sys
import logging

from .util.app import generate_app_directory
from .util.db import init_db
from .config import arg
from .config import settings
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

    settings.ctx.proxy_port = args.proxy
    set_log(args.verbose)
    logging.info("[core] Parsed arguments: %s", args)

    db_conn = init_app_and_db()
    settings.ctx.db_conn = db_conn
    if db_conn is not None:
        atexit.register(db_conn.close)
    logging.info("[core] Initialization complete: conn=%s", db_conn)

    cloud_provider = args.cloud
    logging.info("[core] Cloud provider selected: %s", cloud_provider.upper())

    if cloud_provider == "tencent":
        sys.exit(t_main(args.action, args.target_id))
    elif cloud_provider == "alibaba":
        sys.exit(aliyun_main(args.action, args.target_id))
    else:
        logging.error("[core] Unsupported cloud provider: %s", cloud_provider)
        sys.exit(1)
