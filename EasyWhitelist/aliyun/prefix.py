import json
import logging
import ipaddress
from datetime import datetime
from typing import List, Optional

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .defaults import DEFAULT_MAX_ENTRIES
from ..util.nm import TEMPLATE_NAME_PREFIX
from ..ip_detector.detectors import get_iplist
from ..util.cli import print_header, print_tail, COLS
from .region import Regions
from .client import ClientFactory, Ecs20140526Client


class Prefix:
    def __init__(self, regions: Regions) -> None:
        """初始化 Prefix helper。

        Args:
            client: Alibaba Cloud ECS client。
        """
        self.regions = regions
        self.proxy = regions.proxy
        self.prefix_list_id, self.region = self._auto_get_region_by_prefix_name_from_all_regions()
        logging.info("[config] prefix_list is %s from region %s", self.prefix_list_id, self.region)
        self.client = ClientFactory.create_client(self.region, self.proxy)

    def init_prefix(self, region_id: str) -> int:
        """Find or create the prefix list and populate it with current IPs.
           Returns 0 on success, non-zero error code on failure.
        """
        self.prefix_list_id = self._get_or_create_prefix_list(region_id)
        if not self.prefix_list_id or not self.region:
            return 1
        return self._update_prefix_list_by_id()

    def _get_or_create_prefix_list(self, region_id: str) -> Optional[str]:

        # 1. 查找前缀列表，如果存在则复用，否则新建
        if self.prefix_list_id and self.region:
            print(f"\033[1;95m[aliyun] Prefix list with prefix \"{TEMPLATE_NAME_PREFIX}\" already exists in region \"{region_id}\", id=\"{self.prefix_list_id}\"\033[0m")
        # 2. 否则新建
        else:
            self.prefix_list_id = self._create_prefix_list(region_id)
            print(f"\033[1;95m[aliyun] Created prefix list with prefix \"{TEMPLATE_NAME_PREFIX}\" in region \"{region_id}\", id=\"{self.prefix_list_id}\"\033[0m")

        if not self.prefix_list_id:
            print(f"\033[1;91m[aliyun] Failed to find or create prefix list with template "
                  f"\"{TEMPLATE_NAME_PREFIX}\" in region \"{region_id}\". "
                  f"Please check the logs for details.\033[0m")
            logging.error("Failed to find or create prefix list with template %s in region %s", TEMPLATE_NAME_PREFIX, region_id)
            return None

        return self.prefix_list_id

    def _create_prefix_list(self, region_id: str, prefix_list_name: str = f'{TEMPLATE_NAME_PREFIX}0', description: str = f'{TEMPLATE_NAME_PREFIX}0_desc') -> str:
        """Create a prefix list in the configured region.
           Returns the prefix list ID string on success, or empty string on failure.
        """
        # 构造请求对象

        self.client = ClientFactory.create_client(region_id, self.proxy)
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=region_id,
            prefix_list_name=prefix_list_name,
            description=description,
            max_entries=DEFAULT_MAX_ENTRIES,
            address_family='IPv4'
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 CreatePrefixList 接口
            create_prefix_list_response = self.client.create_prefix_list_with_options(create_prefix_list_request, runtime)  # type: ignore
            ret_data = create_prefix_list_response.body.to_map()
            self.region = region_id
            logging.info(json.dumps(ret_data))
            return ret_data["PrefixListId"] if "PrefixListId" in ret_data else ''

        except UnretryableException:
            logging.exception("Network error when creating prefix list")
            return ''
        except TeaException:
            logging.exception("Tea API error when creating prefix list")
            return ''
        except Exception:
            logging.exception("Unexpected error when creating prefix list")
            return ''

    def _update_prefix_list_by_id(self) -> int:

        if not self.prefix_list_id or not self.region or not self.client:
            logging.error("Prefix list ID, region or client not properly initialized")
            return 1

        client_ip_list = get_iplist(self.proxy)
        # 校验、去重并限制数量
        client_ip_list = self._normalize_ip_list(client_ip_list)
        print(f"\033[1;95m[aliyun] Updating prefix list {self.prefix_list_id} in region \"{self.region}\" with client IPs: {client_ip_list}\033[0m")

        # 构造请求对象
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=self.region,
            prefix_list_id=self.prefix_list_id,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description=f"EasyWhitelist@{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ) for ip in client_ip_list]
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 ModifyPrefixList 接口
            modify_prefix_list_response = self.client.modify_prefix_list_with_options(modify_prefix_list_request, runtime)  # type: ignore
            logging.info(json.dumps(modify_prefix_list_response.body.to_map()))
            return 0

        except UnretryableException:
            logging.exception("Network error when modifying prefix list")
            return 1
        except TeaException:
            logging.exception("Tea API error when modifying prefix list")
            return 1
        except Exception:
            logging.exception("Unexpected error when modifying prefix list")
            return 1

    @staticmethod
    def get_prefix_list(client: Ecs20140526Client) -> Optional[dict]:
        """List prefix lists in the configured region. Returns response dict or None."""
        # 构造请求对象
        print(f"\033[1;95m[aliyun] Retrieving prefix lists in region \"{client._endpoint.split('.')[1]}\"...\033[0m", flush=True)
        describe_prefix_lists_request = ecs_20140526_models.DescribePrefixListsRequest(region_id=client._endpoint.split('.')[1])

        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribePrefixLists 接口
            describe_prefix_lists_response = client.describe_prefix_lists_with_options(describe_prefix_lists_request, runtime)  # type: ignore
            body_map = describe_prefix_lists_response.body.to_map()
            logging.debug("[prefix] API response, detail=%s", json.dumps(body_map))
            return body_map
        except UnretryableException:
            logging.exception("Network error when describing prefix lists")
            return None
        except TeaException:
            logging.exception("Tea API error when describing prefix lists")
            return None
        except Exception:
            logging.exception("Unexpected error when describing prefix lists")
            return None

    def _auto_get_region_by_prefix_name_from_all_regions(self, prefix_name: str = TEMPLATE_NAME_PREFIX) -> (Optional[str], Optional[str]):
        '''Search for a prefix list by name prefix across all regions. Returns the prefix list ID if found, or None if not found.'''
        logging.info("[prefix] search prefix list across all regions, prefix_name=%s ", prefix_name)
        for region in self.regions.region_ids:
            logging.info("[prefix] searching in region %s", region)
            client = ClientFactory.create_client(region, self.proxy)
            prefix_lists = self.get_prefix_list(client)
            logging.debug(prefix_lists)
            if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
                for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
                    logging.debug(prefix)
                    if prefix['PrefixListName'].startswith(prefix_name):
                        logging.info("[prefix] found prefix list, name=%s id=%s", prefix['PrefixListName'], prefix['PrefixListId'])
                        return prefix["PrefixListId"], region
        return None, None

    def print_prefix_list(self) -> int:
        """Print prefix list information in a human-readable format."""

        if not self.client or not self.region:
            return 1
        prefix_lists = self.get_prefix_list(self.client)
        if not prefix_lists or 'PrefixLists' not in prefix_lists or 'PrefixList' not in prefix_lists['PrefixLists']:
            logging.error("No prefix list information to display.")
            return 2

        template_ids = []

        print_header('Alibaba Cloud Prefix List')

        for i, prefix in enumerate(prefix_lists["PrefixLists"]["PrefixList"], 1):
            template_ids.append(prefix["PrefixListId"])
            # addr_set = prefix["AddressSet"]
            addreset = "placeholder for addresses"  # keep
            t_id = prefix["PrefixListId"]
            t_time = prefix["CreationTime"]
            t_name = prefix["PrefixListName"]
            print(f"{str(i):{COLS['idx']}}"
                  f"{t_id:{COLS['id']}}"
                  f"{t_time:{COLS['ctime']}}"
                  f"{addreset:<{COLS['addrs']}}"
                  f"{t_name:{COLS['name']}}"
                  )

        logging.info("[aliyun] template is %s", ":".join(template_ids))
        print_tail()

        return 0

    def _normalize_ip_list(self, ip_list: List[str]) -> List[str]:
        """Validate, normalize to CIDR strings, deduplicate and limit to DEFAULT_MAX_ENTRIES.

        - Accepts single IP or CIDR strings.
        - Normalizes to canonical network form (e.g. '1.2.3.4' -> '1.2.3.4/32').
        - Preserves order, removes duplicates, and truncates to DEFAULT_MAX_ENTRIES.
        """
        if not ip_list:
            return []

        normalized: List[str] = []
        seen = set()
        for raw in ip_list:
            if raw is None:
                continue
            s = str(raw).strip()
            if not s:
                continue
            try:
                net = ipaddress.ip_network(s, strict=False)
                cidr = str(net)
            except ValueError:
                logging.warning("Invalid IP/CIDR skipped: %s", s)
                continue
            if cidr in seen:
                continue
            seen.add(cidr)
            normalized.append(cidr)
            if len(normalized) >= DEFAULT_MAX_ENTRIES:
                logging.warning("Truncating IP list to %d entries (DEFAULT_MAX_ENTRIES)", DEFAULT_MAX_ENTRIES)
                break

        return normalized

    def set_prefix(self) -> int:
        """Update the existing prefix list with current client IPs.

        Returns 0 on success, 1 on failure (prefix list not found or update error).
        """
        # prefix_id = self._auto_search_prefix_by_name()
        if not self.prefix_list_id:
            print(f"\033[1;91m[aliyun] Prefix list with template \"{TEMPLATE_NAME_PREFIX}\" not found in all regions. "
                  f"Please run the init action first to create it.\033[0m")
            return 1
        return self._update_prefix_list_by_id()

    # def _get_prefix_detail_by_id(self, prefix_list_id: str):
    #     runtime = util_models.RuntimeOptions()
    #     try:
    #         describe_req = ecs_20140526_models.DescribePrefixListAttributesRequest(
    #             region_id=self.region,
    #             prefix_list_id=prefix_list_id,
    #         )
    #         describe_resp = self.client.describe_prefix_list_attributes_with_options(describe_req, runtime)  # type: ignore
    #         current_entries = describe_resp.body.to_map().get('Entries', {}).get('Entry', []) or []
    #         logging.info(current_entries)
    #     except Exception:
    #         logging.exception("[aliyun] Failed to describe prefix list attributes for %s; will append only", prefix_list_id)
    #         current_entries = []
    #     return current_entries

    # def _auto_search_prefix_by_name(self, prefix_name: str = TEMPLATE_NAME_PREFIX) -> Optional[str]:
    #     '''Search for a prefix list by name prefix. Returns the prefix list ID if found, or None if not found.'''
    #     logging.info("[prefix] search prefix list, region=%s, prefix_name=%s ", self.region, prefix_name)
    #     prefix_lists = self.get_prefix_list(self.client)
    #     logging.debug(prefix_lists)
    #     if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
    #         for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
    #             logging.debug(prefix)
    #             if prefix['PrefixListName'].startswith(prefix_name):
    #                 logging.info("[prefix] found prefix list, name=%s id=%s", prefix['PrefixListName'], prefix['PrefixListId'])
    #                 return prefix["PrefixListId"]
    #     return None
