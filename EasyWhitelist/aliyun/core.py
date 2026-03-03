import logging
# from .sg import SecurityGroup
from .prefix import Prefix
# from ..util.nm import TEMPLATE_PREFIX


def aliyun_main(action, target, target_id, region, proxy=None) -> None:
    logging.info("Enter aliyun %(action)s %(target)s %(target_id)s %(region)s..." % {"action": action, "target": target, "target_id": target_id, "region": region})

    if region is None:
        region = "cn-hangzhou"
        logging.info("[config] region not set, fallback to %s", region)

    if target == "template":

        ACTION_MAP = {
            "list": lambda: Prefix.list_prefix_list(region_id=region),
            "set": lambda: Prefix.associate_prefix_list(prefix_list_id=target_id, region_id=region),
            "create": lambda: Prefix.create_prefix_list(region_id=region),
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
    Prefix.associate_prefix_list("pl-bp1fa6b4ajysaelrsdnt", "cn-hangzhou")
