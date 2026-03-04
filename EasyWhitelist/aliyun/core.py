import logging
# from .sg import SecurityGroup
from .prefix import Prefix
from typing import Optional


def aliyun_main(action: str, target: str, target_id: str | None, region: Optional[str], proxy: Optional[str] = None) -> None:
    """Entry point for aliyun operations used by the CLI.

    Args:
        action: 操作，例如 'list'/'create'/'set'.
        target: 目标对象，例如 'template'.
        target_id: 目标对象的 ID（可选）。
        region: 阿里云区域（可选，默认使用 Prefix 的默认 region）。
        proxy: 可选代理配置。
    """
    logging.info("Enter aliyun %(action)s %(target)s %(target_id)s %(region)s..." % {"action": action, "target": target, "target_id": target_id, "region": region})

    prefix = Prefix(region=region, proxy=proxy)

    if target == "template":
        ACTION_MAP = {
            "create": lambda: prefix.create_prefix_list(),
            "list": lambda: prefix.list_prefix_list(),
            "set": lambda: prefix.set_prefix(),
        }
        if action in ACTION_MAP:
            ACTION_MAP[action]()
        else:
            logging.error("[cli] unsupported operation, reason=unknown action, detail=%s", action)
    else:
        logging.error("[cli] unsupported target, reason=not implemented, detail=%s", target)


if __name__ == '__main__':

    # for i in range(1, 10):
    #     Prefix.create_prefix_list(PrefixListName=f'{TEMPLATE_PREFIX}{i}', Description=f'{TEMPLATE_PREFIX}{i}_desc')
    #     # Prefix.create_prefix_list()
    pass
