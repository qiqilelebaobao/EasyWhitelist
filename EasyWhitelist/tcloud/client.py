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
        http_profile.proxy = f"127.0.0.1:{settings.proxy_port}" if settings.proxy_port is not None else None
        if settings.proxy_port:
            http_profile.certification = False

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

        # {"Response":{"RegionSet":[{"LocationMC":null,"Region":"ap-shanghai","RegionIdMC":"4","RegionName":"华东地区(上海)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-nanjing","RegionIdMC":"33","RegionName":"华东地区(南京)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-guangzhou","RegionIdMC":"1","RegionName":"华南地区(广州)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-beijing","RegionIdMC":"8","RegionName":"华北地区(北京)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-chengdu","RegionIdMC":"16","RegionName":"西南地区(成都)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-chongqing","RegionIdMC":"19","RegionName":"西南地区(重庆)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-hongkong","RegionIdMC":"5","RegionName":"港澳台地区(中国香港)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-seoul","RegionIdMC":"18","RegionName":"亚太东北(首尔)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-tokyo","RegionIdMC":"25","RegionName":"亚太东北(东京)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-singapore","RegionIdMC":"9","RegionName":"亚太东南(新加坡)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-bangkok","RegionIdMC":"23","RegionName":"亚太东南(曼谷)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"ap-jakarta","RegionIdMC":"72","RegionName":"亚太东南(雅加达)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"na-siliconvalley","RegionIdMC":"15","RegionName":"美国西部(硅谷)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"eu-frankfurt","RegionIdMC":"17","RegionName":"欧洲地区(法兰克福)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"na-ashburn","RegionIdMC":"22","RegionName":"美国东部(弗吉尼亚)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"sa-saopaulo","RegionIdMC":"74","RegionName":"南美地区(圣保罗)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null},{"LocationMC":null,"Region":"me-saudi-arabia","RegionIdMC":"101","RegionName":"中东地区(利雅得)","RegionNameMC":null,"RegionState":"AVAILABLE","RegionTypeMC":null}],"RequestId":"f9d96f20-4183-4dab-8f73-85797e496751","TotalCount":17}}

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

    conn = settings.db_conn
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
    conn = settings.db_conn

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
