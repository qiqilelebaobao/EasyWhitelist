from __future__ import annotations

import logging

from ..util.cli import echo_err

from .region import Regions
from .prefix import Prefix
from ..config import settings


def aliyun_main(action: str, security_rule_id: str | None) -> int:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: Operation to perform, e.g. 'list', 'create', or 'set'.
        security_rule_id: ID of the target resource (optional).
    """
    logging.info("[aliyun] Entering handler: action=%s, security_rule_id=%s, conn=%s",
                 action, security_rule_id, settings.ctx.db_conn)

    regions = Regions()
    logging.info("[aliyun] %d Regions fetched.", len(regions.regions_list) if regions.regions_list else 0)
    prefix = Prefix(regions)
    logging.info("[aliyun] Initialized Regions and Prefix instances for template operations.")

    action_map = {
        "init": lambda: prefix.init_whitelist(security_rule_id),
        "list": lambda: prefix.process_prefix_list_input(),
        "set": lambda: prefix.update_prefix(),
    }
    if action in action_map:
        return action_map[action]()

    logging.error("[aliyun] Unsupported action: %s", action)
    echo_err(f"Unsupported action: '{action}'. Valid actions: {list(action_map.keys())}")
    return 1
