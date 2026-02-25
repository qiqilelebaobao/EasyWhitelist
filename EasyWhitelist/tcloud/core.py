import logging

from . import client
from .template import set_template, create_template_and_associate
from .ls_template import loop_list


def t_main(action, target, target_id, region, proxy=None) -> None:
    if target == "template":
        common_client = client.get_common_client(proxy, region)

        ACTION_MAP = {
            "list": lambda: loop_list(common_client, proxy),
            "set": lambda: set_template(common_client, target_id, proxy),
            "create": lambda: create_template_and_associate(common_client, target_id, proxy),
        }

        if action in ACTION_MAP:
            ACTION_MAP[action]()
        else:
            logging.error("[cli] unsupported operation, reason=unknown action, detail=%s", action)
    else:
        logging.error("[cli] unsupported target, reason=not implemented, detail=%s", target)
