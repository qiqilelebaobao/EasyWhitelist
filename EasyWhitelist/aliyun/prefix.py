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
    def create_prefix_list(region_id='cn-hangzhou', prefix_list_name=f'{TEMPLATE_PREFIX}0', description=f'{TEMPLATE_PREFIX}0_desc'):
        client = ClientFactory.create_client()
        # 构造请求对象
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=region_id,
            prefix_list_name=prefix_list_name,
            description=description,
            max_entries=20,
            address_family='IPv4'
        )

        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 CreatePrefixList 接口
            create_prefix_list_response = client.create_prefix_list_with_options(create_prefix_list_request, runtime)
            logging.info(json.dumps(create_prefix_list_response.body.to_map()))
            return create_prefix_list_response.body.to_map()

        except UnretryableException:
            logging.exception("Network error when creating prefix list")
            return None
        except TeaException:
            logging.exception("Tea API error when creating prefix list")
            return None
        except Exception:
            logging.exception("Unexpected error when creating prefix list")
            return None

    @staticmethod
    def associate_prefix_list(prefix_list_id, region_id):
        client = ClientFactory.create_client()
        client_ip_list = get_iplist()

        logging.warning(f"Associating prefix list {prefix_list_id} in region {region_id} with client IPs: {client_ip_list}")

        # 构造请求对象
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=region_id,
            prefix_list_id=prefix_list_id,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description='added by EasyWhitelist'
            ) for ip in client_ip_list]
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 ModifyPrefixList 接口
            modify_prefix_list_response = client.modify_prefix_list_with_options(modify_prefix_list_request, runtime)
            logging.info(json.dumps(modify_prefix_list_response.body.to_map()))
            return modify_prefix_list_response.body.to_map()

            # json.dumps(describe_instances_response.body)
        except UnretryableException:
            logging.exception("Network error when modifying prefix list")
            return None
        except TeaException:
            logging.exception("Tea API error when modifying prefix list")
            return None
        except Exception:
            logging.exception("Unexpected error when modifying prefix list")
            return None

    @staticmethod
    def list_prefix_list(region_id='cn-hangzhou'):
        logging.info("List prefix list of region: %s..." % region_id)
        client = ClientFactory.create_client()
        # 构造请求对象
        describe_prefix_lists_request = ecs_20140526_models.DescribePrefixListsRequest(
            region_id=region_id,
            # prefix_list_name=f'{TEMPLATE_PREFIX}*'
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribePrefixLists 接口
            describe_prefix_lists_response = client.describe_prefix_lists_with_options(describe_prefix_lists_request, runtime)
            logging.info(json.dumps(describe_prefix_lists_response.body.to_map()))
            return describe_prefix_lists_response.body.to_map()

            # json.dumps(describe_instances_response.body)
        except UnretryableException:
            logging.exception("Network error when describing prefix lists")
            return None
        except TeaException:
            logging.exception("Tea API error when describing prefix lists")
            return None
        except Exception:
            logging.exception("Unexpected error when describing prefix lists")
            return None
