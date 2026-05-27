import atexit
import os
import sys
import logging
from urllib.parse import urlparse

from .util.app import generate_app_directory
from .util.db import init_db
from .config import arg, settings
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


def ignore_ssl_warnings_if_proxyed(is_proxy_enabled: bool):
    """Suppress SSL warnings if SSL verification is bypassed."""
    if is_proxy_enabled:
        import warnings
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def _resolve_proxy_port(cli_port: int | None) -> int | None:
    """Return the proxy port to use.

    Priority: CLI flag (-p) > HTTPS_PROXY / https_proxy env var > None.
    Only the port number is extracted from the env var; the host is ignored
    because all internal proxy references use 127.0.0.1.
    """
    if cli_port is not None:
        return cli_port
    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else "http://" + raw)
    port = parsed.port
    if port and 1 <= port <= 65535:
        return port
    return None


def main() -> None:

    args = arg.init_arg()
    args.proxy = _resolve_proxy_port(args.proxy)
    ignore_ssl_warnings_if_proxyed(args.proxy is not None)

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
        sys.exit(t_main(args.action, getattr(args, "target_id", None)))
    elif cloud_provider == "alibaba":
        sys.exit(aliyun_main(args.action, getattr(args, "target_id", None)))
    else:
        logging.error("[core] Unsupported cloud provider: %s", cloud_provider)
        sys.exit(1)
