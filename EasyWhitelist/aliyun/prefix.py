import json
import logging

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .client import ClientFactory
from ..util.nm import TEMPLATE_PREFIX
from ..ip_detector.detectors import get_iplist


class Prefix:
    @staticmethod
    def create_prefix_list(RegionId='cn-hangzhou', PrefixListName=f'{TEMPLATE_PREFIX}0', Description=f'{TEMPLATE_PREFIX}0_desc'):
        client = ClientFactory.create_client()
        # 构造请求对象
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=RegionId,
            prefix_list_name=PrefixListName,
            description=Description,
            max_entries=20,
            address_family='IPv4'
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 CreatePrefixList 接口
            create_prefix_list_response = client.create_prefix_list_with_options(create_prefix_list_request, runtime)
            print(json.dumps(create_prefix_list_response.body.to_map()))

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
    def associate_prefix_list(PrefixListId, RegionId):
        client = ClientFactory.create_client()
        client_iplist = get_iplist()

        logging.warning(f"Associating prefix list {PrefixListId} in region {RegionId} with client IPs: {client_iplist}")

        # 构造请求对象
        modifiy_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=RegionId,
            prefix_list_id=PrefixListId,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description='added by EasyWhitelist'
            ) for ip in client_iplist]
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 ModifyPrefixList 接口
            modify_prefix_list_response = client.modify_prefix_list_with_options(modifiy_prefix_list_request, runtime)
            print(json.dumps(modify_prefix_list_response.body.to_map()))

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
