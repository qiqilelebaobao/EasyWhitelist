import logging
import sqlite3
from typing import Optional
from . import client
from ..util.db import upsert_security_group


def _discover_regions_from_cache(conn: sqlite3.Connection, sg_id: str) -> list:
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


def _discover_regions_from_api(conn: Optional[sqlite3.Connection], regions, sg_id: str) -> str:
    for region in regions:
        try:
            region_id = region.get("RegionId") or region.get("Region", "")
            logging.debug("[tencentcloud] Attempting to discover region for security group '%s' by querying region '%s'", sg_id, region_id)
            common_client = client.get_common_client(region_id, module="vpc", endpoint="vpc.tencentcloudapi.com")
            response = common_client.call_json("DescribeSecurityGroups", {"SecurityGroupIds": [sg_id]})

            security_groups = response.get("Response", {}).get("SecurityGroupSet", [])
            for sg in security_groups:
                if sg.get("SecurityGroupId") == sg_id:
                    region_id = region.get("RegionId") or region.get("Region", "")
                    logging.info("[tencentcloud] Discovered region '%s' for security group '%s'", region_id, sg_id)
                    if conn is not None:
                        upsert_security_group(
                            conn,
                            sg_id=sg_id,
                            cloud_provider='tencentcloud',
                            region_id=region_id,
                            sg_name=sg.get('SecurityGroupName', ''),
                            description=sg.get('SecurityGroupDesc', ''),
                        )
                    return region_id
        except Exception as e:
            logging.error("[tencentcloud] Failed to discover regions from API: %s", e)
    return ''


def discover_regions_from_api_with_cache(conn: Optional[sqlite3.Connection], regions, sg_id: str) -> str:
    """Discover the region for a given security group ID, using cache if available."""
    if conn:
        cached_regions = _discover_regions_from_cache(conn, sg_id)
        if cached_regions:
            logging.info("[tencentcloud] Found cached region '%s' for security group '%s'", cached_regions[0], sg_id)
            return cached_regions[0]

    # Cache miss or no DB connection; fall back to API discovery
    return _discover_regions_from_api(conn, regions, sg_id)
