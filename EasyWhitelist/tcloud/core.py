import logging
from typing import Optional

from . import client
from .template import set_template, create_template_and_associate, loop_list


def t_main(action: str, target: str, target_id: Optional[str], region: Optional[str], proxy: Optional[int] = None, app_dir: Optional[str] = None) -> int:
    if target == "template":
        regions = client.obtain_region_set(app_dir=app_dir)
        if regions is None or len(regions) == 0:
            logging.error("[tencentcloud] No regions available to proceed with template action")
            return 1
        common_client = client.get_common_client(regions[0].get("RegionId"), proxy)

        ACTION_MAP = {
            "list": lambda: loop_list(common_client, proxy),
            "set": lambda: set_template(common_client, target_id, proxy),
            "init": lambda: create_template_and_associate(common_client, target_id, proxy),
        }

        if action in ACTION_MAP:
            ACTION_MAP[action]()
        else:
            logging.error("[tencentcloud] Unsupported action: %s", action)
    else:
        logging.error("[tencentcloud] Unsupported target: %s", target)
        return 1
    return 0
