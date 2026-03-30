import logging
from typing import Optional

from ..util.cli import echo_ok, echo_err, echo_info, print_header, print_row, print_tail  # noqa: F401

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
    def _print_init_summary(region: Optional[str], prefix_list_id: Optional[str], ctime: str, addrs: str, name: str) -> None:
        print_header('Alibaba Cloud Template Init')
        print_row(idx=1,
                  region=region or '',
                  id=prefix_list_id or '',
                  ctime=ctime,
                  addrs=addrs,
                  name=name)
        print_tail()

    if not sg_id:
        echo_err("Security group ID is required for initialization")
        return 1

    # 1. Look up the security group; return on failure
    try:
        sg = SecurityGroup(sg_id, regions, proxy_port=proxy_port)
    except Exception:
        logging.exception("[aliyun] Failed to look up security group, sg_id=%s", sg_id)
        echo_err(f"Failed to look up security group {sg_id}")
        return 2

    if not sg.region_id:
        echo_err(f"Security group {sg_id} not found in any region")
        return 3

    # 2. Get or create the prefix list and update it with the current client IP.
    # `init_prefix` returns a non-zero value on failure. The second condition
    # acts as a safety check for the unlikely case where `init_prefix` returns
    # 0 but `prefix_list_id` remains unset.
    if prefix.init_prefix(sg.region_id) or not prefix.current_prefix_list:
        echo_err("Failed to create prefix list, cannot proceed with whitelist initialization")
        return 4

    if not sg.add_prefix_list_rule(prefix.current_prefix_list.prefix_list_id):
        echo_err("Failed to create security group rule with prefix list")
        return 5

    echo_ok("Successfully initialized template-based whitelist")
    _print_init_summary(sg.region_id,
                        prefix.current_prefix_list.prefix_list_id,
                        prefix.current_prefix_list.creation_time if prefix.current_prefix_list.creation_time else '',
                        "n/a",
                        prefix.current_prefix_list.prefix_list_name if prefix.current_prefix_list.prefix_list_name else '')
    return 0


def aliyun_main(action: str, target: str, target_id: Optional[str], proxy_port: Optional[int] = None, app_dir: Optional[str] = None) -> int:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: Operation to perform, e.g. 'list', 'create', or 'set'.
        target: Target resource type, e.g. 'template'.
        target_id: ID of the target resource (optional).
        proxy_port: Proxy port (1–65535); None if no proxy is used.
        app_dir: Application directory (optional).
    """
    logging.info("[aliyun] Entering handler: action=%s, target=%s, target_id=%s, proxy=%s, app_dir=%s",
                 action, target, target_id, proxy_port, app_dir)

    if target == "template":
        regions = Regions(proxy_port, app_dir=app_dir)
        logging.debug("[aliyun] Regions fetched: %s", regions.regions_list)
        prefix = Prefix(regions)
        logging.info("[aliyun] Initialized Regions and Prefix instances for template operations.")

        action_map = {
            "init": lambda: init_whitelist(prefix, regions, proxy_port, target_id),
            "list": lambda: prefix.print_prefix_list(),
            "set": lambda: prefix.update_prefix(),
        }
        if action in action_map:
            return action_map[action]()

        logging.error("[aliyun] Unsupported action: %s", action)
        echo_err(f"Unsupported action: '{action}'. Valid actions: {list(action_map.keys())}")
        return 1

    logging.error("[aliyun] Unsupported target: %s", target)
    echo_err(f"Unsupported target: '{target}'. Currently supported: 'template'")
    return 1
