import os
import logging
import sqlite3
from typing import List, Optional, Dict

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.cli import echo_err
from .client import ClientFactory
from .defaults import _runtime, DEFAULT_REGION_1, DEFAULT_REGION_2


def cache_regions(app_dir: str, regions: List[Dict], cloud_provider: str = 'aliyun') -> None:
    """将 regions 列表缓存到数据库 regions 表中。
    Args:
        app_dir: 数据库所在目录
        regions: [{'RegionId': ..., 'LocalName': ...}, ...]
        cloud_provider: 云厂商标识，默认 'aliyun'
    """
    db_path = os.path.join(app_dir, "whitelist.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for region in regions:
        region_id = region.get('RegionId', '')
        if not region_id:
            continue
        cursor.execute(
            """
            INSERT OR IGNORE INTO regions (region_id, name, region_endpoint, cloud_provider, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (region_id, region.get('LocalName', ''), region.get('RegionEndpoint', ''), cloud_provider)
        )
    conn.commit()
    conn.close()
    logging.info(f"[db] Cached {len(regions)} regions to database.")


class Regions:
    """Fetches and stores all available Alibaba Cloud regions for a given ECS client."""

    def __init__(self, proxy_port: Optional[int] = None, app_dir: Optional[str] = None):
        """Initialize by calling DescribeRegions and populating region IDs and endpoints.

        Args:
            proxy_port: Optional proxy port (1–65535) to propagate to sub-clients.

        Raises:
            UnretryableException: If the API call cannot be retried.
            TeaException: If the API returns an error response.
            KeyError: If the expected fields are missing from the response.
        """
        self.proxy_url = f"http://localhost:{proxy_port}" if proxy_port is not None else None
        self.regions_list: List[Dict] = []

        try:
            client: Ecs20140526Client = ClientFactory.create_client(DEFAULT_REGION_1, proxy_port)
        except Exception:
            logging.warning("[aliyun] Failed to create client for %s, falling back to %s", DEFAULT_REGION_1, DEFAULT_REGION_2)
            client = ClientFactory.create_client(DEFAULT_REGION_2, proxy_port)

        describe_regions_request = ecs_20140526_models.DescribeRegionsRequest()
        runtime = _runtime(self.proxy_url is not None)
        try:
            response = client.describe_regions_with_options(describe_regions_request, runtime)
            self.regions_list: List[Dict] = response.body.to_map()['Regions']['Region']
            logging.debug("[aliyun] DescribeRegions response: %s", self.regions_list)
            # 缓存到数据库
            if app_dir:
                try:
                    cache_regions(app_dir, self.regions_list, cloud_provider='aliyun')
                except Exception as db_exc:
                    logging.warning(f"[aliyun] Failed to cache regions to db: {db_exc}")
        except (UnretryableException, TeaException, KeyError) as e:
            echo_err(f"Failed to describe regions: {e}")
            logging.error("[aliyun] Failed to describe regions")
            raise
