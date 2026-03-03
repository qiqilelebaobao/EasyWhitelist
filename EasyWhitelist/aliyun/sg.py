import json
import logging

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .client import ClientFactory
from .defaults import DEFAULT_REGION, DEFAULT_VPC_ID


class SecurityGroup:
    def __init__(self):
        pass

    @staticmethod
    def create_security_group(description='test_sg_desc', region_id=DEFAULT_REGION, vpc_id=DEFAULT_VPC_ID):
        client = ClientFactory.create_client()
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

            # json.dumps(describe_instances_response.body)
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
    def describe_security_groups():
        client = ClientFactory.create_client()
        # 构造请求对象
        describe_sg_request = ecs_20140526_models.DescribeSecurityGroupsRequest(
            region_id=DEFAULT_REGION
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribeSecurityGroups 接口
            describe_sg_response = client.describe_security_groups_with_options(describe_sg_request, runtime)
            logging.info(json.dumps(describe_sg_response.body.to_map()))
            return describe_sg_response.body.to_map()

            # json.dumps(describe_instances_response.body)
        except UnretryableException:
            logging.exception("Network error when describing security groups")
            return None
        except TeaException:
            logging.exception("Tea API error when describing security groups")
            return None
        except Exception:
            logging.exception("Unexpected error when describing security groups")
            return None
