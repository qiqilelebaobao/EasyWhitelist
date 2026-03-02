import json

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .client import ClientFactory


class SecurityGroup:
    def __init__(self):
        pass

    @staticmethod
    def create_security_group(description='test_sg_desc'):
        client = ClientFactory.create_client()
        # 构造请求对象
        create_sg_request = ecs_20140526_models.CreateSecurityGroupRequest(
            region_id='cn-hangzhou', security_group_name=description, description=description, vpc_id='vpc-bp1okdh0otxlepq71u9x4'
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 CreateSecurityGroup 接口
            create_sg_response = client.create_security_group_with_options(create_sg_request, runtime)
            print(json.dumps(create_sg_response.body.to_map()))

            # json.dumps(describe_instances_response.body)
        except UnretryableException as e:
            # 网络异常，此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常
            print(e)
        except TeaException as e:
            # 业务异常，此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常
            print(e)
        except Exception as e:
            # 其他异常，此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常
            print(e)

    @staticmethod
    def describe_security_groups():
        client = ClientFactory.create_client()
        # 构造请求对象
        describe_sg_request = ecs_20140526_models.DescribeSecurityGroupsRequest(
            region_id='cn-hangzhou'
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribeSecurityGroups 接口
            describe_sg_response = client.describe_security_groups_with_options(describe_sg_request, runtime)
            print(json.dumps(describe_sg_response.body.to_map()))

            # json.dumps(describe_instances_response.body)
        except UnretryableException as e:
            # 网络异常，此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常
            print(e)
        except TeaException as e:
            # 业务异常，此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常
            print(e)
        except Exception as e:
            # 其他异常，此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常
            print(e)
