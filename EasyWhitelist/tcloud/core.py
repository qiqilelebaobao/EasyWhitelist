import logging
from typing import Optional

from . import client
from .template import set_template, create_template_and_associate, loop_list


def t_main(action: str, target: str, target_id: Optional[str], region: Optional[str], proxy: Optional[int] = None) -> None:
    if target == "template":
        common_client = client.get_common_client(region, proxy)

        ACTION_MAP = {
            "list": lambda: loop_list(common_client, proxy),
            "set": lambda: set_template(common_client, target_id, proxy),
            "init": lambda: create_template_and_associate(common_client, target_id, proxy),
        }

        if action in ACTION_MAP:
            ACTION_MAP[action]()
        else:
            logging.error("[tcloud] Unsupported action: %s", action)
    else:
        logging.error("[tcloud] Unsupported target: %s", target)
