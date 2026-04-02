import logging
import json
import sqlite3

from typing import Optional, List
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.common_client import CommonClient

from ..util.db import is_cache_fresh, load_cached_regions, upsert_regions

# module-level cache (process-local). Prefer using DB cache via obtain_region_set().
region_list: List[dict] = []


def _fetch_regions(proxy_port: Optional[int] = None) -> List[dict]:
    """Fetch regions from Tencent Cloud API and return the RegionSet list.

    Returns an empty list on error.
    """
    try:
        cred = credential.DefaultCredentialProvider().get_credential()
        http_profile = HttpProfile()
        http_profile.proxy = f"127.0.0.1:{proxy_port}" if proxy_port else None
        http_profile.endpoint = "cvm.tencentcloudapi.com"
        if proxy_port:
            http_profile.certification = False
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        params = "{}"
        common_client = CommonClient("cvm", "2017-03-12", cred, "", profile=client_profile)
        regions = common_client.call_json("DescribeRegions", json.loads(params)).get("Response", {}).get("RegionSet", [])
        logging.info("[tencentcloud] Fetched %d regions from Tencent Cloud API", len(regions))
        return regions
    except Exception as e:
        logging.error("[tencentcloud] Failed to fetch regions: %s", e)
        return []


def obtain_region_set(conn: Optional[sqlite3.Connection] = None, proxy_port: Optional[int] = None) -> Optional[List]:
    """Return regions, prefer cached DB value when fresh; otherwise fetch and cache.

    If `conn` is provided this will use the existing database connection and
    use `is_cache_fresh`, `load_cached_regions`, `upsert_regions` for caching.
    """

    if conn is None:
        logging.info("[tencentcloud] No DB connection available; will fetch regions from network without caching")
        return _fetch_regions(proxy_port)

    try:
        if is_cache_fresh(conn=conn, cloud_provider='tencentcloud'):
            logging.info("[tencentcloud] Loaded regions from DB cache")
            return load_cached_regions(conn=conn, cloud_provider='tencentcloud')
        # stale or empty cache: fetch from network
        regions = _fetch_regions(proxy_port)
        upsert_regions(conn, regions, cloud_provider='tencentcloud')
        return regions
    except Exception as e:
        logging.warning("[tencentcloud] Cache check failed; fetching regions from network: %s", e)
        return _fetch_regions(proxy_port)


def get_region_set() -> Optional[List[dict]]:
    return region_list


def get_common_client(region: str, proxy_port: Optional[int] = None) -> CommonClient:

    try:
        cred = credential.DefaultCredentialProvider().get_credential()

        http_profile = HttpProfile()
        http_profile.endpoint = "vpc.tencentcloudapi.com"
        http_profile.proxy = f"127.0.0.1:{proxy_port}" if proxy_port is not None else None
        if proxy_port:
            http_profile.certification = False

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        # clientProfile.signMethod = "HmacSHA256"

        common_client = CommonClient("vpc", "2017-03-12", cred, region, profile=client_profile)
        return common_client

    except Exception as e:
        logging.error("[tencentcloud] Failed to create Tencent Cloud client: %s", e)
        raise
