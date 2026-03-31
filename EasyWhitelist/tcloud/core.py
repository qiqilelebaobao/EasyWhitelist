import logging
from typing import Optional

from . import client
from .template import set_template, create_template_and_associate, loop_list


def t_main(action: str,
           target_id: Optional[str],
           proxy: Optional[int] = None,
           app_dir: Optional[str] = None) -> int:
    regions = client.obtain_region_set(app_dir=app_dir)
    if regions is None or len(regions) == 0:
        logging.error("[tencentcloud] No regions available to proceed with template action")
        return 1

    logging.info("[tencentcloud] Using region '%s' for template operations", regions[0].get("RegionId"))
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

    return 0
