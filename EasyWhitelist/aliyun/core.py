import logging
from typing import Optional

from .client import ClientFactory
# from .sg import SecurityGroup
from .prefix import Prefix


def aliyun_main(action: str, target: str, target_id: Optional[str], region: Optional[str], proxy: Optional[int] = None) -> None:
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

    aliyun_client = ClientFactory.create_client(region, proxy)

    prefix = Prefix(aliyun_client, region=region, proxy=proxy)

    if target == "template":
        ACTION_MAP = {
            "create": lambda: prefix.create_prefix_list(),
            "list": lambda: prefix.print_prefix_list(),
            "set": lambda: prefix.set_prefix(),
        }
        if action in ACTION_MAP:
            ACTION_MAP[action]()
        else:
            logging.error("[cli] unsupported operation, reason=unknown action, detail=%s", action)
    else:
        logging.error("[cli] unsupported target, reason=not implemented, detail=%s", target)
