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
    def __init__(self, sg_id: str, regions: Regions, proxy, sg_name: str = ''):
        self.regions = regions
        self.sg_id = sg_id
        self.proxy = proxy

        self.region_id: Optional[str] = DEFAULT_REGION
        self.client = ClientFactory.create_client(self.region_id, proxy=self.proxy)  # type: ignore
        self.id_checked = False
        self.sg_name = sg_name

    def _search_sg_by_region_and_id(self, region_id, sg_id):
        # 构造请求对象
        security_groups = self._describe_security_groups(region_id)
        if security_groups and "SecurityGroups" in security_groups and "SecurityGroup" in security_groups["SecurityGroups"]:
            for sg in security_groups["SecurityGroups"]["SecurityGroup"]:
                if sg["SecurityGroupId"] == sg_id:
                    self.region_id = region_id
                    print(f"\033[1;95m[aliyun] Found security group with ID {sg_id} in region {region_id}\033[0m")
                    return sg
        logging.info("[aliyun] Security group with ID %s not found in region %s", sg_id, region_id)
        return None

    def search_sg(self):
        for region_id in self.regions.region_ids:
            sg = self._search_sg_by_region_and_id(region_id, self.sg_id)
            if sg:
                self.id_checked = True
                return sg

        return None

    '''阿里云如果安全组已经有了前缀列表，不会有异常返回，会不做修改。如果没有前缀列表，直接尝试创建安全组规则。'''

    def create_sg_rule_with_prefix(self, prefix_list_id: str):
        if not self.region_id:
            logging.error("[aliyun] region_id not set; call search_sg() before create_sg_rule_with_prefix()")
            return False
        # 构造请求对象
        create_sg_rule_with_prefix_request = ecs_20140526_models.AuthorizeSecurityGroupRequest(
            region_id=self.region_id,
            security_group_id=self.sg_id,
            ip_protocol='all',
            port_range='-1/-1',
            source_prefix_list_id=prefix_list_id)
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 AuthorizeSecurityGroup 接口
            security_group_authorization_response = self.client.authorize_security_group_with_options(create_sg_rule_with_prefix_request, runtime)
            logging.info(json.dumps(security_group_authorization_response.body.to_map()))
            print(f"\033[1;95m[aliyun] Successfully created/reused security group rule with prefix list {prefix_list_id} for security group {self.sg_id}\033[0m")
            return True
        except UnretryableException:
            logging.exception("Network error when creating security group")
            return False
        except TeaException:
            logging.exception("Tea API error when creating security group")
            return False
        except Exception:
            logging.exception("Unexpected error when creating security group")
            return False

    def create_security_group(self, description: str = 'test_sg_desc', region_id: str = DEFAULT_REGION, vpc_id: str = DEFAULT_VPC_ID) -> Optional[Dict[str, Any]]:
        """Create a security group in the specified VPC and region.

    Args:
        description: 用于安全组名称与描述的字符串。
        region_id: 区域 ID。
        vpc_id: VPC ID。

    Returns:
        成功返回响应字典；失败返回 None 并记录日志。
    """
        # 构造请求对象
        create_sg_request = ecs_20140526_models.CreateSecurityGroupRequest(
            region_id=region_id, security_group_name=description, description=description, vpc_id=vpc_id
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 CreateSecurityGroup 接口
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

    def _describe_security_groups(self, region_id: str = DEFAULT_REGION) -> Optional[Dict[str, Any]]:
        """Describe security groups in the given region.

    Args:
        region_id: 区域 ID，默认使用 DEFAULT_REGION。

    Returns:
        成功返回响应字典；失败返回 None 并记录日志。
    """
        # 构造请求对象
        describe_sg_request = ecs_20140526_models.DescribeSecurityGroupsRequest(
            region_id=region_id
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribeSecurityGroups 接口
            describe_sg_response = self.client.describe_security_groups_with_options(describe_sg_request, runtime)
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
