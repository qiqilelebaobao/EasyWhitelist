import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import client
from ..config import settings
from ..util.db import upsert_security_group
from ..util.defaults import DEFAULT_CONCURRENT_WORKERS


def _discover_regions_from_cache(sg_id: str) -> list:
    conn = settings.ctx.db_conn
    if conn is None:
        logging.info("[tencentcloud] No DB connection available; cannot check cache for security group '%s'", sg_id)
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT region_id FROM security_groups WHERE sg_id = ? and cloud_provider = 'tencentcloud'
            """,
            (sg_id,)
        )
        result = cursor.fetchone()
        return [result[0]] if result else []
    except Exception as e:
        logging.error("[db] Failed to discover regions from sg_id: %s", e)
        return []


def _query_region(region, sg_id: str):
    """Query a single region for the given security group ID.

    Returns (region_id, sg_dict) if found; (region_id, None) otherwise.
    """
    region_id = region.get("RegionId") or region.get("Region", "")
    logging.debug("[tencentcloud] Attempting to discover region for security group '%s' by querying region '%s'", sg_id, region_id)
    try:
        common_client = client.get_common_client(region_id, module="vpc", endpoint="vpc.tencentcloudapi.com")
        response = common_client.call_json("DescribeSecurityGroups", {"SecurityGroupIds": [sg_id]})
        security_groups = response.get("Response", {}).get("SecurityGroupSet", [])
        for sg in security_groups:
            if sg.get("SecurityGroupId") == sg_id:
                return region_id, sg
    except Exception as e:
        logging.info("[tencentcloud] Failed to query region '%s': %s", region_id, e)
    return region_id, None


def _discover_regions_from_api(regions, sg_id: str) -> str:
    max_workers = min(DEFAULT_CONCURRENT_WORKERS, len(regions))
    executor = ThreadPoolExecutor(max_workers=max_workers)
    found_region = ''
    try:
        future_to_region = {
            executor.submit(_query_region, region, sg_id): region
            for region in regions
        }
        for future in as_completed(future_to_region):
            try:
                region_id, sg = future.result()
            except Exception as e:
                logging.info("[tencentcloud] Unexpected error during region discovery: %s", e)
                continue
            if sg is not None:
                logging.info("[tencentcloud] Discovered region '%s' for security group '%s'", region_id, sg_id)
                conn = settings.ctx.db_conn
                if conn is not None:
                    upsert_security_group(
                        conn,
                        sg_id=sg_id,
                        cloud_provider='tencentcloud',
                        region_id=region_id,
                        sg_name=sg.get('SecurityGroupName', ''),
                        description=sg.get('SecurityGroupDesc', ''),
                    )
                found_region = region_id
                # Cancel pending (not yet started) futures to avoid unnecessary API calls
                for f in future_to_region:
                    f.cancel()
                break
    finally:
        executor.shutdown(wait=False)
    return found_region


def discover_regions_from_api_with_cache(regions, sg_id: str) -> str:
    """Discover the region for a given security group ID, using cache if available."""

    cached_regions = _discover_regions_from_cache(sg_id)
    if cached_regions:
        logging.info("[tencentcloud] Found cached region '%s' for security group '%s'", cached_regions[0], sg_id)
        return cached_regions[0]

    # Cache miss or no DB connection; fall back to API discovery
    return _discover_regions_from_api(regions, sg_id)
