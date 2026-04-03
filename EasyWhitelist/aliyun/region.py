import logging
from typing import List, Dict

from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.db import is_cache_fresh, load_cached_regions, upsert_regions
from .client import ClientFactory
from .defaults import _runtime, DEFAULT_REGION_1, DEFAULT_REGION_2
from ..config import settings


class Regions:
    """Fetches and stores all available Alibaba Cloud regions for a given ECS client."""

    def __init__(self):
        """Initialize by loading regions from cache or cloud, and populating region list."""
        self.proxy_url = f"http://localhost:{settings.proxy_port}" if settings.proxy_port is not None else None
        self.conn = settings.db_conn
        self.regions_list = self._load_regions()

    def get_region_name(self, region_id: str) -> str:
        """Return LocalName/region_name for a known region_id (empty string if not found)."""
        for r in self.regions_list or []:
            if r.get('RegionId') == region_id:
                return r.get('LocalName', '') or r.get('name', '') or ''
        return ''

    def _load_regions(self) -> List[Dict]:
        """Load regions from cache when fresh, otherwise fetch from Aliyun API."""
        if not self.conn:
            logging.warning("[region] No database connection available; fetching regions from network")
            return self._fetch_regions_from_network()

        try:
            if is_cache_fresh(conn=self.conn, cloud_provider='aliyun'):
                logging.info("[region] Loaded regions from cache")
                return load_cached_regions(conn=self.conn, cloud_provider='aliyun')
            else:
                logging.info("[region] Cached regions are stale; fetching from network")
                return self._fetch_regions_from_network()
        except Exception as db_exc:
            logging.warning("[region] Cache check failed; fetching regions from network: %s", db_exc)
            return self._fetch_regions_from_network()

    def _fetch_regions_from_network(self) -> List[Dict]:
        """Fetch regions directly from Aliyun API without caching."""
        try:
            client: Ecs20140526Client = ClientFactory.create_client(DEFAULT_REGION_1)
        except Exception:
            logging.warning("[region] Failed to create client for %s, falling back to %s", DEFAULT_REGION_1, DEFAULT_REGION_2)
            client = ClientFactory.create_client(DEFAULT_REGION_2)

        describe_regions_request = ecs_20140526_models.DescribeRegionsRequest()
        runtime = _runtime(settings.proxy_port is not None)

        try:
            response = client.describe_regions_with_options(describe_regions_request, runtime)
            regions = response.body.to_map().get('Regions', {}).get('Region', [])
            logging.debug("[region] DescribeRegions response: %s", regions)
        except Exception as e:
            logging.error("[region] Failed to fetch regions from API: %s", e)
            return []

        if self.conn is not None:
            try:
                upsert_regions(self.conn, regions, cloud_provider='aliyun')
            except Exception as db_exc:
                logging.warning("[region] Failed to cache regions to db: %s", db_exc)

        return regions
