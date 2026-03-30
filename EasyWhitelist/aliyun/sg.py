import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.defaults import DEFAULT_CONCURRENT_WORKERS
from ..util.db import load_cached_security_group, upsert_security_group

from .defaults import _runtime, _ecs_api_call
from .region import Regions
from .client import ClientFactory


class SecurityGroup:
    def __init__(self, sg_id: str, regions: Regions, proxy_port: Optional[int] = None, sg_name: str = ''):
        """Look up a security group by ID across all known regions.

        Args:
            sg_id: Security group ID to look up.
            regions: Regions helper with the list of regions to search.
            proxy_port: Optional proxy port for network requests.
            sg_name: Optional security group name; auto-populated from the API if empty.
        """
        self.regions = regions
        self.sg_id = sg_id
        self.proxy_port = proxy_port
        self.sg_name = sg_name
        self.conn = regions.conn

        self.client: Optional[Ecs20140526Client] = None  # may remain None if the SG is not found

        # Try cached security group first
        self.region_id = None
        cached = self._load_cached_security_group()
        if cached:
            self.region_id = cached.get('region_id')
            self.sg_name = self.sg_name or cached.get('region_name', '')
            logging.info("[db] Security group %s loaded from cache: %s/%s", self.sg_id, self.region_id, self.sg_name)

        # If not cached, do online lookup and cache result
        if not self.region_id:
            sg, self.region_id = self._find_security_group_and_cache()
            if not self.region_id or sg is None:
                logging.error("[aliyun] Security group %s not found in any region", sg_id)
                return

        self.client = ClientFactory.create_client(self.region_id, proxy_port=self.proxy_port)

    def add_prefix_list_rule(self, prefix_list_id: str) -> bool:
        """Authorize inbound traffic from a prefix list into this security group.

        Alibaba Cloud silently ignores duplicate rules.

        Args:
            prefix_list_id: The prefix list to allow.

        Returns:
            True on success; False on failure.
        """
        if not self.region_id or not self.client:
            logging.error("[aliyun] Region ID or client not set; security group not found during initialization")
            return False
        # Build the AuthorizeSecurityGroup request object
        create_sg_rule_with_prefix_request = ecs_20140526_models.AuthorizeSecurityGroupRequest(
            region_id=self.region_id,
            security_group_id=self.sg_id,
            ip_protocol='all',
            port_range='-1/-1',
            source_prefix_list_id=prefix_list_id)
        runtime = _runtime(self.proxy_port is not None)
        resp = _ecs_api_call(
            lambda: self.client.authorize_security_group_with_options(create_sg_rule_with_prefix_request, runtime),  # type: ignore[union-attr]
            "creating security group rule",
        )
        if resp is None:
            return False
        logging.debug(json.dumps(resp.body.to_map()))
        logging.info("[aliyun] Security group rule with prefix list %s applied to %s", prefix_list_id, self.sg_id)
        return True

    def _search_security_group_by_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """Search for self.sg_id in a single region.

        Args:
            region_id: The region to search in.

        Returns:
            The security group dict if found; None otherwise.
        """
        for sg in self._fetch_security_groups(region_id):
            if sg["SecurityGroupId"] == self.sg_id:
                logging.info("[aliyun] Found security group %s in %s", self.sg_id, region_id)
                return sg
        logging.info("[aliyun] Security group %s not found in region %s", self.sg_id, region_id)
        return None

    def _find_security_group(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Iterate all regions to locate self.sg_id.

        Returns:
            A (sg_dict, region_id) tuple on success; (None, None) if not found.
        """
        with ThreadPoolExecutor(max_workers=min(DEFAULT_CONCURRENT_WORKERS, len(self.regions.regions_list))) as executor:
            future_to_region = {executor.submit(self._search_security_group_by_region, e['RegionId']): e['RegionId'] for e in self.regions.regions_list}
            for future in as_completed(future_to_region):
                try:
                    sg = future.result()
                except Exception as e:
                    logging.error("[aliyun] Exception when searching security group in region %s: %s", future_to_region[future], e)
                    continue
                if sg:
                    logging.info("[aliyun] Security group %s found in region %s", self.sg_id, future_to_region[future])
                    return sg, future_to_region[future]
        return None, None

    def _find_security_group_and_cache(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Find the security group and cache it in the instance for future use."""
        sg, region_id = self._find_security_group()
        if sg and region_id:
            self.sg_name = sg.get("SecurityGroupName", "")
            self.vpc_id = sg.get("VpcId", "")
            self.sg_type = sg.get("SecurityGroupType", "")
            self.description = sg.get("Description", "")

            region_name = self.regions.get_region_name(region_id) if hasattr(self.regions, 'get_region_name') else ''
            self._cache_security_group(region_id, region_name)
        return sg, region_id

    def _load_cached_security_group(self) -> Dict[str, str]:
        """Load a cached security group from SQLite and return an empty dict if missing."""
        if not self.conn:
            return {}

        try:
            return load_cached_security_group(self.conn, self.sg_id)
        except Exception as e:
            logging.warning("[db] Failed to read cached security group %s: %s", self.sg_id, e)
            return {}

    def _cache_security_group(self, region_id: str, region_name: str = "") -> None:
        """Cache the SG id + region in SQLite for faster future lookup."""
        if not self.conn:
            return

        try:
            upsert_security_group(self.conn, self.sg_id, "aliyun", region_id, self.sg_name, self.vpc_id, self.sg_type, self.description)
            logging.info("[db] Cached security group %s => %s/%s", self.sg_id, region_id, region_name)
        except Exception as e:
            logging.warning("[db] Failed to cache security group %s: %s", self.sg_id, e)

    def _fetch_security_groups(self, region_id) -> List[Dict[str, Any]]:
        """Retrieve ALL security groups in the given region using page-based pagination.

        DescribeSecurityGroups returns at most 100 entries per page; this method iterates
        all pages and returns a flat list.

        Args:
            region_id: Region ID; defaults to DEFAULT_REGION.

        Returns:
            A list of security group dicts; empty list on failure (logged).
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id, proxy_port=self.proxy_port)
        runtime = _runtime(self.proxy_port is not None)
        all_sgs: list = []
        page_number = 1
        page_size = 100  # maximum allowed by the ECS API
        try:
            while True:
                describe_sg_request = ecs_20140526_models.DescribeSecurityGroupsRequest(
                    region_id=region_id,
                    page_number=page_number,
                    page_size=page_size,
                )
                describe_sg_response = client.describe_security_groups_with_options(describe_sg_request, runtime)
                body = describe_sg_response.body.to_map()
                logging.debug(json.dumps(body))
                page_sgs = (body.get("SecurityGroups") or {}).get("SecurityGroup") or []
                all_sgs.extend(page_sgs)
                if not page_sgs or len(all_sgs) >= (body.get("TotalCount") or 0):
                    break
                page_number += 1
            return all_sgs
        except Exception as e:
            logging.error("[aliyun] Error when describing security groups: %s", e)
            return []
