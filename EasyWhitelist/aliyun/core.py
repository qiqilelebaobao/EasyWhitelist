import logging
from typing import Optional

from .client import ClientFactory
from .prefix import Prefix
from .sg import SecurityGroup
from .defaults import DEFAULT_REGION
from .region import Regions


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
        2 - error searching for security group
        3 - security group not found
        4 - failed to get/create/update prefix list
        5 - failed to create security group rule
    """
    if not sg_id:
        print("\033[1;91m[aliyun] Security group ID is required for initialization\033[0m")
        return 1

    # 1. 查找安全组，如果失败返回
    try:
        sg = SecurityGroup(sg_id, regions, proxy=proxy_port)
        sg_obj, region_id = sg.search_sg()
    except Exception:
        logging.exception("[aliyun] failed to search security group, sg_id=%s", sg_id)
        print(f"\033[1;91m[aliyun] failed to search security group, sg_id={sg_id}\033[0m")
        return 2

    if not sg_obj or not region_id:
        print(f"\033[1;91m[aliyun] Security group with ID {sg_id} not found in any region\033[0m")
        return 3

    # 2. 获取或创建前缀列表并更新 IP
    # init_prefix 返回非零值表示失败；后半段作为双重保险防止返回 0 但 prefix_list_id 仍为空
    if prefix.init_prefix(region_id) or prefix.prefix_list_id is None:
        print("\033[1;91m[aliyun] Failed to create prefix list, cannot proceed with whitelist initialization\033[0m")
        return 4

    if not sg.create_sg_rule_with_prefix(prefix.prefix_list_id):
        print("\033[1;91m[aliyun] Failed to create security group rule with prefix list, cannot proceed with whitelist initialization\033[0m")
        return 5

    return 0


def aliyun_main(action: str, target: str, target_id: Optional[str], proxy_port: Optional[int] = None) -> int:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: 操作，例如 'list'/'create'/'set'.
        target: 目标对象，例如 'template'.
        target_id: 目标对象的 ID（可选）。
        proxy_port: 代理端口（1–65535），不使用代理则为 None。
    """
    logging.info("[aliyun] enter aliyun (action: %s) (target: %s) (target_id: %s) (proxy: %s)",
                 action, target, target_id, proxy_port)

    regions = Regions(ClientFactory.create_client(DEFAULT_REGION, proxy_port))

    if target == "template":
        prefix = Prefix(regions)

        action_map = {
            "init": lambda: init_whitelist(prefix, regions, proxy_port, target_id),
            "list": lambda: prefix.print_prefix_list(),
            "set": lambda: prefix.set_prefix(),
        }
        if action in action_map:
            return action_map[action]()

        logging.error("[aliyun] unsupported operation, reason=unknown action, detail=%s", action)
        print(f"\033[1;91m[aliyun] Unsupported action: '{action}'. Valid actions are: {list(action_map.keys())}\033[0m")
        return 1

    logging.error("[aliyun] unsupported target, reason=not implemented, detail=%s", target)
    print(f"\033[1;91m[aliyun] Unsupported target: '{target}'. Currently supported: 'template'\033[0m")
    return 1
