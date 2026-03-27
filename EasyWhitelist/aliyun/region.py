import os
import logging
import sqlite3
from typing import List, Optional, Dict

from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.db import is_cache_fresh, load_cached_regions, upsert_regions
from .client import ClientFactory
from .defaults import _runtime, DEFAULT_REGION_1, DEFAULT_REGION_2


def _load_regions(app_dir: Optional[str], proxy_port: Optional[int]) -> List[Dict]:
    """Load regions from cache when fresh, otherwise fetch from Aliyun API."""
    conn = None
    if app_dir:
        db_path = os.path.join(app_dir, "whitelist.db")
        conn = sqlite3.connect(db_path)
        try:
            if is_cache_fresh(conn=conn):
                logging.info("[db] Loaded regions from cache")
                return load_cached_regions(app_dir, conn=conn)
        except Exception as db_exc:
            logging.warning(f"[db] Cache check failed, will fetch from network: {db_exc}")

    try:
        client: Ecs20140526Client = ClientFactory.create_client(DEFAULT_REGION_1, proxy_port)
    except Exception:
        logging.warning("[aliyun] Failed to create client for %s, falling back to %s", DEFAULT_REGION_1, DEFAULT_REGION_2)
        client = ClientFactory.create_client(DEFAULT_REGION_2, proxy_port)

    describe_regions_request = ecs_20140526_models.DescribeRegionsRequest()
    runtime = _runtime(proxy_port is not None)

    response = client.describe_regions_with_options(describe_regions_request, runtime)
    regions = response.body.to_map()['Regions']['Region']
    logging.debug("[aliyun] DescribeRegions response: %s", regions)

    if app_dir and conn is not None:
        try:
            upsert_regions(app_dir, conn, regions, cloud_provider='aliyun')
        except Exception as db_exc:
            logging.warning(f"[aliyun] Failed to cache regions to db: {db_exc}")

    if conn is not None:
        conn.close()

    return regions


class Regions:
    """Fetches and stores all available Alibaba Cloud regions for a given ECS client."""

    def __init__(self, proxy_port: Optional[int] = None, app_dir: Optional[str] = None):
        """Initialize by loading regions from cache or cloud, and populating region list."""
        self.proxy_url = f"http://localhost:{proxy_port}" if proxy_port is not None else None
        self.regions_list = _load_regions(app_dir, proxy_port)
