import logging
from typing import Optional

# from .sg import SecurityGroup
from .prefix import Prefix
from .sg import SecurityGroup
from .defaults import DEFAULT_REGION


def init_whitelist(_prefix: Prefix, sg_id: Optional[str]) -> int:

    if not sg_id:
        print("\033[1;91m[aliyun] Security group ID is required for initialization\033[0m")
        return 1

    # 1. 查找安全组,如果失败返回
    try:
        sg = SecurityGroup(sg_id)
        sg_obj = sg.search_sg()
    except Exception:
        print("\033[1;91m[aliyun] failed to search security group, sg_id=%s\033[0m", sg_id)
        return 3

    if not sg_obj:
        print(f"\033[1;91m[aliyun] Security group with ID {sg_id} not found in any region\033[0m")
        return 2

    if not _prefix.prefix_list_id:
        print("\033[1;91m[aliyun] Failed to create prefix list, cannot proceed with whitelist initialization\033[0m")
        return 4

    if not sg.create_sg_rule_with_prefix(_prefix.prefix_list_id):
        print("\033[1;91m[aliyun] Failed to create security group rule with prefix list, cannot proceed with whitelist initialization\033[0m")
        return 5

    return 0


def aliyun_main(action: str, target: str, target_id: Optional[str], region: Optional[str], proxy: Optional[int] = None) -> int:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: 操作，例如 'list'/'create'/'set'.
        target: 目标对象，例如 'template'.
        target_id: 目标对象的 ID（可选）。
        region: 阿里云区域（可选，默认使用 Prefix 的默认 region）。
        proxy: 可选代理配置。
    """
    logging.info("[core] enter aliyun (action: %s) (target: %s) (target_id: %s) (region: %s) (proxy: %s)",
                 action, target, target_id, region, proxy)

    region = region or DEFAULT_REGION

    prefix = Prefix(region=region, proxy=proxy)

    if target == "template":
        action_map = {
            "init": lambda: init_whitelist(prefix, target_id),
            "list": lambda: prefix.print_prefix_list() or 0,
            "set": lambda: prefix.set_prefix() or 0,
        }
        if action in action_map:
            return action_map[action]()

        logging.error("[cli] unsupported operation, reason=unknown action, detail=%s", action)
        return 1

    logging.error("[cli] unsupported target, reason=not implemented, detail=%s", target)
    return 1
