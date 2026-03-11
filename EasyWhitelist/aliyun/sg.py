import json
import logging
from typing import Dict, Any, Optional

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .client import ClientFactory
from .region import Regions
from .defaults import DEFAULT_REGION, DEFAULT_VPC_ID


class SecurityGroup:
    def __init__(self, sg_id: str, regions: Regions, proxy_port: Optional[int] = None, sg_name: str = ''):
        self.regions = regions
        self.sg_id = sg_id
        self.proxy_port = proxy_port
        self.sg_name = sg_name
        self.client = None  # may remain None if the SG is not found

        self.region_id: Optional[str] = self._find_security_group()[1]
        if not self.region_id:
            print(f"\033[1;91m[aliyun] Security group with ID {sg_id} not found in any region\033[0m")
            return
        self.client = ClientFactory.create_client(self.region_id, proxy_port=self.proxy_port)  # type: ignore

    def _find_in_region(self, region_id):
        # Retrieve all security groups in the region to find the target one
        security_groups = self._fetch_security_groups(region_id)
        if security_groups and "SecurityGroups" in security_groups and "SecurityGroup" in security_groups["SecurityGroups"]:
            for sg in security_groups["SecurityGroups"]["SecurityGroup"]:
                if sg["SecurityGroupId"] == self.sg_id:
                    print(f"\033[1;95m[aliyun] Found security group with ID {self.sg_id} in region {region_id}\033[0m")
                    return sg
        logging.info("[aliyun] Security group with ID %s not found in region %s", self.sg_id, region_id)
        return None

    def _find_security_group(self):
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
        runtime = util_models.RuntimeOptions()
        try:
            # Call the AuthorizeSecurityGroup API
            security_group_authorization_response = self.client.authorize_security_group_with_options(create_sg_rule_with_prefix_request, runtime)
            logging.info(json.dumps(security_group_authorization_response.body.to_map()))
            print(f"\033[1;95m[aliyun] Successfully created or reused security group rule with prefix list {prefix_list_id} for security group {self.sg_id}\033[0m")
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

    def create_security_group(self, description: str = 'test_sg_desc', region_id: str = DEFAULT_REGION, vpc_id: str = DEFAULT_VPC_ID) -> Optional[Dict[str, Any]]:
        """Create a security group in the specified VPC and region.

        Args:
            description: String used for both the security group name and description.
            region_id: Region ID.
            vpc_id: VPC ID.

        Returns:
            Response dict on success; None on failure (logged).
        """
        if not self.client:
            logging.error("[aliyun] client not initialized; security group was not found during construction")
            return None
        # Build the CreateSecurityGroup request object
        create_sg_request = ecs_20140526_models.CreateSecurityGroupRequest(
            region_id=region_id, security_group_name=description, description=description, vpc_id=vpc_id
        )
        # Set runtime options
        runtime = util_models.RuntimeOptions()
        try:
            # Call the CreateSecurityGroup API
            create_sg_response = self.client.create_security_group_with_options(create_sg_request, runtime)
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
        """Retrieve all security groups in the given region.

        Args:
            region_id: Region ID; defaults to DEFAULT_REGION.

        Returns:
            Response dict on success; None on failure (logged).
        """
        describe_sg_request = ecs_20140526_models.DescribeSecurityGroupsRequest(
            region_id=region_id
        )
        client = ClientFactory.create_client(region_id, proxy_port=self.proxy_port)
        # Set runtime options
        runtime = util_models.RuntimeOptions()
        try:
            # Call the DescribeSecurityGroups API
            describe_sg_response = client.describe_security_groups_with_options(describe_sg_request, runtime)
            logging.debug(json.dumps(describe_sg_response.body.to_map()))
            return describe_sg_response.body.to_map()
        except UnretryableException:
            logging.exception("Network error when describing security groups")
            return None
        except TeaException:
            logging.exception("Tea API error when describing security groups")
            return None
        except Exception:
            logging.exception("Unexpected error when describing security groups")
            return None
