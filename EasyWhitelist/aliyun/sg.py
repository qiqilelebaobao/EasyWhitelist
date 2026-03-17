import json
import logging
from typing import Dict, Any, Optional, Tuple

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.cli import echo_ok, echo_err

from .defaults import DEFAULT_REGION, DEFAULT_VPC_ID, _runtime
from .region import Regions
from .client import ClientFactory


class SecurityGroup:
    def __init__(self, sg_id: str, regions: Regions, proxy_port: Optional[int] = None, sg_name: str = ''):
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

    def _find_in_region(self, region_id):
        # Retrieve all security groups in the region to find the target one
        security_groups = self._fetch_security_groups(region_id)
        if security_groups and "SecurityGroups" in security_groups and "SecurityGroup" in security_groups["SecurityGroups"]:
            for sg in security_groups["SecurityGroups"]["SecurityGroup"]:
                if sg["SecurityGroupId"] == self.sg_id:
                    echo_ok(f"Found security group {self.sg_id} in {region_id}")
                    return sg
        logging.info("[aliyun] Security group with ID %s not found in region %s", self.sg_id, region_id)
        return None

    def _find_security_group(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        for region_id in self.regions.region_ids:
            sg = self._find_in_region(region_id)
            if sg:
                return sg, region_id

        return None, None

    # Alibaba Cloud silently ignores this call if the rule already exists; otherwise it creates the rule immediately.
    def add_prefix_list_rule(self, prefix_list_id: str):
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
        # Set runtime options
        runtime = _runtime(self.proxy_port is not None)
        try:
            # Call the AuthorizeSecurityGroup API
            security_group_authorization_response = self.client.authorize_security_group_with_options(create_sg_rule_with_prefix_request, runtime)
            logging.info(json.dumps(security_group_authorization_response.body.to_map()))
            echo_ok(f"Security group rule with prefix list {prefix_list_id} applied to {self.sg_id}")
            return True
        except UnretryableException:
            logging.exception("Network error when creating security group rule")
            return False
        except TeaException:
            logging.exception("Tea API error when creating security group rule")
            return False
        except Exception:
            logging.exception("Unexpected error when creating security group rule")
            return False

    def create_security_group(self, name: str = 'test_sg',
                              description: str = 'test_sg_desc',
                              region_id: str = DEFAULT_REGION,
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
        # Set runtime options
        runtime = _runtime(self.proxy_port is not None)
        try:
            # Call the CreateSecurityGroup API
            create_sg_response = client.create_security_group_with_options(create_sg_request, runtime)
            logging.info(json.dumps(create_sg_response.body.to_map()))
            return create_sg_response.body.to_map()
        except UnretryableException:
            logging.exception("Network error when creating security group")
            return None
        except TeaException:
            logging.exception("Tea API error when creating security group")
            return None
        except Exception:
            logging.exception("Unexpected error when creating security group")
            return None

    def _fetch_security_groups(self, region_id: str = DEFAULT_REGION) -> Optional[Dict[str, Any]]:
        """Retrieve ALL security groups in the given region using page-based pagination.

        DescribeSecurityGroups returns at most 100 entries per page; this method iterates
        all pages and returns a merged result in the same shape as a single-page response.

        Args:
            region_id: Region ID; defaults to DEFAULT_REGION.

        Returns:
            Merged response dict on success (all pages combined); None on failure (logged).
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
                # Stop when we have received all entries or the page was empty
                if not page_sgs or len(all_sgs) >= (body.get("TotalCount") or 0):
                    break
                page_number += 1
            return {"SecurityGroups": {"SecurityGroup": all_sgs}}
        except UnretryableException:
            logging.exception("Network error when describing security groups")
            return None
        except TeaException:
            logging.exception("Tea API error when describing security groups")
            return None
        except Exception:
            logging.exception("Unexpected error when describing security groups")
            return None
