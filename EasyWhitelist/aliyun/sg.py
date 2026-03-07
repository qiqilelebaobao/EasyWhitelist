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
    def __init__(self, sg_id, sg_name=''):
        self.sg_id = sg_id
        self.id_checked = False
        self.sg_name = sg_name
        self.regions = Regions()

    def _search_sg_by_region_and_id(self, region_id, sg_id):
        # 构造请求对象
        security_groups = self._describe_security_groups(region_id)
        if security_groups and "SecurityGroups" in security_groups and "SecurityGroup" in security_groups["SecurityGroups"]:
            for sg in security_groups["SecurityGroups"]["SecurityGroup"]:
                if sg["SecurityGroupId"] == sg_id:
                    print(f"\033[1;92m[aliyun] Found security group with ID {sg_id} in region {region_id}\033[0m")
                    return sg
        print(f"\033[1;91m[aliyun] Security group with ID {sg_id} not found in region {region_id}\033[0m")
        return None

    def search_sg(self):
        for region_id in self.regions.region_ids:
            sg = self._search_sg_by_region_and_id(region_id, self.sg_id)
            if sg:
                self.id_checked = True
                return sg

        return None

    @staticmethod
    def create_security_group(description: str = 'test_sg_desc', region_id: str = DEFAULT_REGION, vpc_id: str = DEFAULT_VPC_ID) -> Optional[Dict[str, Any]]:
        """Create a security group in the specified VPC and region.

        Args:
            description: 用于安全组名称与描述的字符串。
            region_id: 区域 ID。
            vpc_id: VPC ID。

        Returns:
            成功返回响应字典；失败返回 None 并记录日志。
        """
        client = ClientFactory.create_client(region_id)
        # 构造请求对象
        create_sg_request = ecs_20140526_models.CreateSecurityGroupRequest(
            region_id=region_id, security_group_name=description, description=description, vpc_id=vpc_id
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 CreateSecurityGroup 接口
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

    @staticmethod
    def _describe_security_groups(region_id: str = DEFAULT_REGION) -> Optional[Dict[str, Any]]:
        """Describe security groups in the given region.

        Args:
            region_id: 区域 ID，默认使用 DEFAULT_REGION。

        Returns:
            成功返回响应字典；失败返回 None 并记录日志。
        """
        client = ClientFactory.create_client(region_id)
        # 构造请求对象
        describe_sg_request = ecs_20140526_models.DescribeSecurityGroupsRequest(
            region_id=region_id
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribeSecurityGroups 接口
            describe_sg_response = client.describe_security_groups_with_options(describe_sg_request, runtime)
            logging.info(json.dumps(describe_sg_response.body.to_map()))
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
