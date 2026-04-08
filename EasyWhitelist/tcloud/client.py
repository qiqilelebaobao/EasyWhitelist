import logging
from typing import Optional, List

from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.common_client import CommonClient

from ..util.db import is_cache_fresh, load_cached_regions, upsert_regions
from ..config import settings


def get_common_client(region: str, module: str, endpoint: str) -> CommonClient:

    try:
        cred = credential.DefaultCredentialProvider().get_credential()

        http_profile = HttpProfile()
        http_profile.endpoint = endpoint
        http_profile.proxy = f"127.0.0.1:{settings.ctx.proxy_port}" if settings.ctx.proxy_port is not None else None
        if settings.ctx.proxy_port:
            http_profile.certification = not settings.ctx.IGNORE_SSL

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        # clientProfile.signMethod = "HmacSHA256"

        common_client = CommonClient(module, "2017-03-12", cred, region, profile=client_profile)
        return common_client

    except Exception as e:
        logging.error("[tencentcloud] Failed to create Tencent Cloud client: %s", e)
        raise


def _fetch_regions() -> List[dict]:
    """Fetch regions from Tencent Cloud API and return the RegionSet list.

    Returns an empty list on error.
    """
    bootstrap_region = ""
    try:
        common_client = get_common_client(region=bootstrap_region, module="cvm", endpoint="cvm.tencentcloudapi.com")
        raw_regions = common_client.call_json("DescribeRegions", {}).get("Response", {}).get("RegionSet", [])
        # Normalize to RegionId key so callers see a consistent format
        # regardless of whether data comes from the API or from DB cache.

        for r in raw_regions:
            if "RegionId" not in r and "Region" in r:
                r["RegionId"] = r["Region"]
        logging.info("[tencentcloud] Fetched %d regions from Tencent Cloud API", len(raw_regions))
        return raw_regions
    except Exception as e:
        logging.error("[tencentcloud] Failed to fetch regions: %s", e)
        return []


def _fetch_and_cache_regions() -> List[dict]:
    """Fetch regions from Tencent Cloud API and cache them in the database.

    Returns the list of regions, or an empty list on error.
    """
    regions = _fetch_regions()
    if not regions:
        return []

    conn = settings.ctx.db_conn
    if conn is None:
        logging.warning("[tencentcloud] No DB connection available; skipping cache update")
        return regions

    try:
        upsert_regions(conn, regions, cloud_provider='tencentcloud')
    except Exception as e:
        logging.warning("[tencentcloud] Failed to cache regions to DB: %s", e)
    return regions


def load_regions_prefer_cache() -> Optional[List]:
    """Return regions, prefer cached DB value when fresh; otherwise fetch and cache.

    Uses `settings.db_conn` for caching when a database connection is available.
    """
    conn = settings.ctx.db_conn

    if conn is None:
        logging.info("[tencentcloud] No DB connection available; will fetch regions from network without caching")
        return _fetch_regions()

    try:
        if is_cache_fresh(conn=conn, cloud_provider='tencentcloud'):
            logging.info("[tencentcloud] Loaded regions from DB cache")
            return load_cached_regions(conn=conn, cloud_provider='tencentcloud')
        # stale or empty cache: fetch from network
        return _fetch_and_cache_regions()
    except Exception as e:
        logging.warning("[tencentcloud] Cache check failed; fetching regions from network: %s", e)
        return _fetch_and_cache_regions()
