import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.defaults import DEFAULT_CONCURRENT_WORKERS
from ..util.cli import echo_ok, echo_err

from .defaults import DEFAULT_REGION_1, DEFAULT_VPC_ID, _runtime, _ecs_api_call
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
        self.client: Optional[Ecs20140526Client] = None  # may remain None if the SG is not found

        sg, self.region_id = self._find_security_group()
        if not self.region_id or sg is None:
            echo_err(f"Security group {sg_id} not found in any region")
            return
        self.client = ClientFactory.create_client(self.region_id, proxy_port=self.proxy_port)

    def _find_in_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """Search for self.sg_id in a single region.

        Args:
            region_id: The region to search in.

        Returns:
            The security group dict if found; None otherwise.
        """
        for sg in self._fetch_security_groups(region_id):
            if sg["SecurityGroupId"] == self.sg_id:
                echo_ok(f"Found security group {self.sg_id} in {region_id}")
                return sg
        logging.info("[aliyun] Security group with ID %s not found in region %s", self.sg_id, region_id)
        return None

    def _find_security_group(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Iterate all regions to locate self.sg_id.

        Returns:
            A (sg_dict, region_id) tuple on success; (None, None) if not found.
        """
        with ThreadPoolExecutor(max_workers=min(DEFAULT_CONCURRENT_WORKERS, len(self.regions.region_ids))) as executor:
            future_to_region = {executor.submit(self._find_in_region, region_id): region_id for region_id in self.regions.region_ids}
            for future in as_completed(future_to_region):
                try:
                    sg = future.result()
                except Exception as e:
                    logging.error(f"Exception when searching security group in region {future_to_region[future]}: {e}")
                    continue
                if sg:
                    logging.info(f"Security group {self.sg_id} found in region {future_to_region[future]}")
                    return sg, future_to_region[future]
        return None, None

    def add_prefix_list_rule(self, prefix_list_id: str) -> bool:
        """Authorize inbound traffic from a prefix list into this security group.

        Alibaba Cloud silently ignores duplicate rules.

        Args:
            prefix_list_id: The prefix list to allow.

        Returns:
            True on success; False on failure.
        """
        if not self.region_id or not self.client:
            logging.error("[aliyun] region_id or client is not set; SecurityGroup was not found during initialization")
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
        echo_ok(f"Security group rule with prefix list {prefix_list_id} applied to {self.sg_id}")
        return True

    def create_security_group(self, name: str = 'test_sg',
                              description: str = 'test_sg_desc',
                              region_id: str = DEFAULT_REGION_1,
                              vpc_id: str = DEFAULT_VPC_ID) -> Optional[Dict[str, Any]]:
        """Create a security group in the specified VPC and region.

        Args:
            name: Security group name.
            description: Security group description.
            region_id: Region ID.
            vpc_id: VPC ID.

        Returns:
            Response dict on success; None on failure (logged).
        """
        # Create a client scoped to the target region; the instance-level self.client is bound
        # to self.region_id and must not be reused here when region_id differs.
        client: Ecs20140526Client = ClientFactory.create_client(region_id, proxy_port=self.proxy_port)
        # Build the CreateSecurityGroup request object
        create_sg_request = ecs_20140526_models.CreateSecurityGroupRequest(
            region_id=region_id, security_group_name=name, description=description, vpc_id=vpc_id
        )
        runtime = _runtime(self.proxy_port is not None)
        resp = _ecs_api_call(
            lambda: client.create_security_group_with_options(create_sg_request, runtime),
            "creating security group",
        )
        if resp is None:
            return None
        logging.debug(json.dumps(resp.body.to_map()))
        return resp.body.to_map()

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
        except Exception:
            logging.error("[aliyun] Error when describing security groups")
            return []
