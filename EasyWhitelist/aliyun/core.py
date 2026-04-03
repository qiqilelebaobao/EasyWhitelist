import logging
import sqlite3
from typing import Optional

from ..util.cli import echo_ok, echo_err, echo_info, print_header, print_row, print_tail  # noqa: F401

from .region import Regions
from .prefix import Prefix


def aliyun_main(action: str, target_id: Optional[str], conn: Optional[sqlite3.Connection] = None) -> int:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: Operation to perform, e.g. 'list', 'create', or 'set'.
        target: Target resource type, e.g. 'template'.
        target_id: ID of the target resource (optional).
        conn: Database connection (optional).
    """
    logging.info("[aliyun] Entering handler: action=%s, target_id=%s, conn=%s",
                 action, target_id, conn)

    regions = Regions(conn=conn)
    logging.info("[aliyun] %d Regions fetched.", len(regions.regions_list) if regions.regions_list else 0)
    prefix = Prefix(regions)
    logging.info("[aliyun] Initialized Regions and Prefix instances for template operations.")

    action_map = {
        "init": lambda: prefix.init_whitelist(target_id),
        "list": lambda: prefix.print_prefix_list(),
        "set": lambda: prefix.update_prefix(),
    }
    if action in action_map:
        return action_map[action]()

    logging.error("[aliyun] Unsupported action: %s", action)
    echo_err(f"Unsupported action: '{action}'. Valid actions: {list(action_map.keys())}")
    return 1
