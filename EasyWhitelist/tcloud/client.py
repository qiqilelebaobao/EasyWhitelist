import logging
import json
import os
import sqlite3

from typing import Optional, List
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.common_client import CommonClient

from ..util.db import is_cache_fresh, load_cached_regions, upsert_regions

DEFAULT_REGION = "ap-guangzhou"

# module-level cache (process-local). Prefer using DB cache via obtain_region_set().
region_list: List[dict] = []


def _fetch_regions(proxy_port: str = '') -> List[dict]:
    """Fetch regions from Tencent Cloud API and return the RegionSet list.

    Returns an empty list on error.
    """
    try:
        cred = credential.DefaultCredentialProvider().get_credential()
        http_profile = HttpProfile()
        http_profile.proxy = f"127.0.0.1:{proxy_port}" if proxy_port else None
        http_profile.endpoint = "cvm.tencentcloudapi.com"
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


def obtain_region_set(app_dir: Optional[str] = None, proxy_port: str = '') -> Optional[List]:
    """Return regions, prefer cached DB value when fresh; otherwise fetch and cache.

    If `app_dir` is provided this will open `whitelist.db` under that dir and
    use `is_cache_fresh`, `load_cached_regions`, `upsert_regions` for caching.
    """
    conn = None
    if app_dir:
        db_path = os.path.join(app_dir, "whitelist.db")
        try:
            logging.info("[tencentcloud] Attempting to open DB at %s for region caching", db_path)
            conn = sqlite3.connect(db_path)
        except Exception as e:
            logging.warning("[tencentcloud] Failed to open DB %s: %s", db_path, e)

    if conn is None:
        logging.info("[tencentcloud] No DB connection available; will fetch regions from network without caching")
        return _fetch_regions(proxy_port)

    try:
        if is_cache_fresh(conn=conn, cloud_provider='tencentcloud'):
            logging.info("[tencentcloud] Loaded regions from DB cache")
            return load_cached_regions(conn=conn)
        # stale or empty cache: fetch from network
        regions = _fetch_regions(proxy_port)
        upsert_regions(conn, regions, cloud_provider='tencentcloud')
        return regions
    except Exception as e:
        logging.warning("[tencentcloud] Cache check failed; fetching regions from network: %s", e)
        return _fetch_regions(proxy_port)


def get_region_set() -> Optional[List[dict]]:
    return region_list


def get_common_client(region, proxy_port=None) -> CommonClient:
    # cred = credential.Credential(
    #     os.environ.get("TENCENTCLOUD_SECRET_ID"),
    #     os.environ.get("TENCENTCLOUD_SECRET_KEY"))
    if region is None:
        region = DEFAULT_REGION
        logging.info("[config] Region not set; falling back to %s", region)
    try:

        cred = credential.DefaultCredentialProvider().get_credential()

        http_profile = HttpProfile()
        http_profile.endpoint = "vpc.tencentcloudapi.com"
        http_profile.proxy = f"127.0.0.1:{proxy_port}" if proxy_port is not None else None

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        # clientProfile.signMethod = "HmacSHA256"

        common_client = CommonClient(
            "vpc", "2017-03-12", cred, region, profile=client_profile)
        return common_client

    except Exception as e:
        logging.error("[tencentcloud] Failed to create Tencent Cloud client: %s", e)
        raise
