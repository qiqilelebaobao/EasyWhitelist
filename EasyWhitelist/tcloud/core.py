import logging
import sqlite3
from typing import Optional

from . import client
from .template import update_template, initialize_and_bind_template, loop_list
from .sg import discover_regions_from_api_with_cache


def t_main(action: str,
           security_rule_id: Optional[str],
           proxy_port: Optional[int] = None,
           conn: Optional[sqlite3.Connection] = None) -> int:

    regions = client.obtain_region_set(conn=conn, proxy_port=proxy_port)
    if regions is None or len(regions) == 0:
        logging.error("[tencentcloud] No regions available to proceed with template action")
        return 1

    logging.info("[tencentcloud] Using region '%s' for template operations", regions[0].get("RegionId"))
    if action == 'init' and security_rule_id:
        logging.info("[tencentcloud] Target security rule ID: %s", security_rule_id)
        region_id = discover_regions_from_api_with_cache(conn, regions, security_rule_id)  # Discover the region of the security group via API (if not cached), so subsequent operations can accurately target it
        if not region_id:
            logging.warning("[tencentcloud] Failed to discover region for security group '%s'; defaulting to first region in list", security_rule_id)
            return 2
        common_client = client.get_common_client(region_id, proxy_port=proxy_port)
    else:
        common_client = client.get_common_client(regions[0].get("RegionId"), proxy_port=proxy_port)

    ACTION_MAP = {
        "init": lambda: initialize_and_bind_template(common_client, security_rule_id, proxy_port),
        "list": lambda: loop_list(common_client, proxy_port),
        "set": lambda: update_template(common_client, security_rule_id, proxy_port),
    }

    if action in ACTION_MAP:
        return ACTION_MAP[action]()
    else:
        logging.error("[tencentcloud] Unsupported action: %s", action)
        return 3

    return 0
