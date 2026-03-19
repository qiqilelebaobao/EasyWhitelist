import logging
from typing import Optional

from ..util.cli import echo_ok, echo_err, echo_info  # noqa: F401 (echo_ok/info available for future use)

from .region import Regions
from .prefix import Prefix
from .sg import SecurityGroup


def init_whitelist(prefix: Prefix, regions: Regions, proxy_port: Optional[int], sg_id: Optional[str]) -> int:
    """Initialize whitelist by associating a prefix list with a security group.

    Args:
        prefix: Prefix list helper instance.
        regions: Regions helper instance.
        proxy_port: Optional proxy port for network requests.
        sg_id: Security group ID to associate the prefix list with.

    Returns:
        0 on success, non-zero error code on failure:
        1 - sg_id not provided
        2 - failed to look up security group
        3 - security group not found
        4 - failed to get/create/update prefix list
        5 - failed to create security group rule
    """
    if not sg_id:
        echo_err("Security group ID is required for initialization")
        return 1

    # 1. Look up the security group; return on failure
    try:
        sg = SecurityGroup(sg_id, regions, proxy_port=proxy_port)
    except Exception:
        logging.exception("[aliyun] failed to look up security group, sg_id=%s", sg_id)
        echo_err(f"Failed to look up security group {sg_id}")
        return 2

    if not sg.region_id:
        return 3

    # 2. Get or create the prefix list and update it with the current client IP
    # init_prefix returns non-zero on failure; the second condition is a safety net for
    # the unlikely case where it returns 0 but prefix_list_id is still unset
    if prefix.init_prefix(sg.region_id) or not prefix.current_prefix_list:
        echo_err("Failed to create prefix list, cannot proceed with whitelist initialization")
        return 4

    if not sg.add_prefix_list_rule(prefix.current_prefix_list.prefix_list_id):
        echo_err("Failed to create security group rule with prefix list")
        return 5

    return 0


def aliyun_main(action: str, target: str, target_id: Optional[str], proxy_port: Optional[int] = None) -> int:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: Operation to perform, e.g. 'list', 'create', or 'set'.
        target: Target resource type, e.g. 'template'.
        target_id: ID of the target resource (optional).
        proxy_port: Proxy port (1–65535); None if no proxy is used.
    """
    logging.info("[aliyun] entering aliyun handler (action=%s, target=%s, target_id=%s, proxy=%s)",
                 action, target, target_id, proxy_port)

    if target == "template":
        regions = Regions(proxy_port)
        prefix = Prefix(regions)

        logging.info("[aliyun] initialized Regions and Prefix instances for template operations")

        action_map = {
            "init": lambda: init_whitelist(prefix, regions, proxy_port, target_id),
            "list": lambda: prefix.print_prefix_list(),
            "set": lambda: prefix.update_prefix(),
        }
        if action in action_map:
            return action_map[action]()

        logging.error("[aliyun] unsupported operation, reason=unknown action, detail=%s", action)
        echo_err(f"Unsupported action: '{action}'. Valid actions: {list(action_map.keys())}")
        return 1

    logging.error("[aliyun] unsupported target, reason=not implemented, detail=%s", target)
    echo_err(f"Unsupported target: '{target}'. Currently supported: 'template'")
    return 1
