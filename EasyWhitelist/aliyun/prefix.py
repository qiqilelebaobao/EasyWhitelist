import json
import logging
import ipaddress
from datetime import datetime
from typing import List, Optional

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .defaults import DEFAULT_MAX_ENTRIES, DEFAULT_REGION
from ..util.nm import TEMPLATE_NAME_PREFIX
from ..ip_detector.detectors import get_iplist
from ..util.cli import print_header, print_tail, COLS
from .client import ClientFactory


class Prefix:
    def __init__(self, region: str, proxy: Optional[int] = None) -> None:
        """Initialize Prefix helper.

        Args:
            region: Alibaba Cloud region, defaults to DEFAULT_REGION when not provided.
            proxy: Optional proxy configuration (currently stored but not used).
        """
        self.client = ClientFactory.create_client(region, proxy)
        self.region = region if region else DEFAULT_REGION
        self.proxy = proxy
        self.prefix_list_id = self._get_or_create_prefix_list()

        if self.prefix_list_id:
            self._update_prefix_list_by_id(self.prefix_list_id)

        logging.info("[config] region set to %s", self.region)

    def _create_prefix_list(self, prefix_list_name: str = f'{TEMPLATE_NAME_PREFIX}0', description: str = f'{TEMPLATE_NAME_PREFIX}0_desc') -> str:
        """Create a prefix list in the configured region.

        Returns the SDK response as a dict on success, or None on failure.
        """
        # 构造请求对象
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=self.region,
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

    def _get_prefix_detail_by_id(self, prefix_list_id: str):
        runtime = util_models.RuntimeOptions()
        try:
            describe_req = ecs_20140526_models.DescribePrefixListAttributesRequest(
                region_id=self.region,
                prefix_list_id=prefix_list_id,
            )
            describe_resp = self.client.describe_prefix_list_attributes_with_options(describe_req, runtime)  # type: ignore
            current_entries = describe_resp.body.to_map().get('Entries', {}).get('Entry', []) or []
            logging.info(current_entries)
        except Exception:
            logging.exception("[aliyun] Failed to describe prefix list attributes for %s; will append only", prefix_list_id)
            current_entries = []
        return current_entries

    def _update_prefix_list_by_id(self, prefix_list_id: str) -> None:

        client_ip_list = get_iplist(self.proxy)
        # 校验、去重并限制数量
        client_ip_list = self._normalize_ip_list(client_ip_list)
        print(f"\033[1;95m[aliyun] Updating prefix list {prefix_list_id} in region \"{self.region}\" with client IPs: {client_ip_list}\033[0m")

        # 构造请求对象
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=self.region,
            prefix_list_id=prefix_list_id,
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
            return

        except UnretryableException:
            logging.exception("Network error when modifying prefix list")
            return
        except TeaException:
            logging.exception("Tea API error when modifying prefix list")
            return
        except Exception:
            logging.exception("Unexpected error when modifying prefix list")
            return

    def _get_or_create_prefix_list(self, sg_id: Optional[str] = ''):

        # 1. 查找前缀列表，如果存在则复用，否则新建
        prefix_list_id = self._auto_search_prefix_by_name()
        if prefix_list_id:
            print(f"\033[1;95m[aliyun] Prefix list with prefix \"{TEMPLATE_NAME_PREFIX}\" already exists in region \"{self.region}\", id=\"{prefix_list_id}\"\033[0m")
        # 2. 否则新建
        else:
            prefix_list_id = self._create_prefix_list()
            print(f"\033[1;95m[aliyun] Created prefix list with prefix \"{TEMPLATE_NAME_PREFIX}\" in region \"{self.region}\", id=\"{prefix_list_id}\"\033[0m")

        if not prefix_list_id:
            print(f"\033[1;91m[aliyun] Failed to find or create prefix list with template "
                  f"\"{TEMPLATE_NAME_PREFIX}\" in region \"{self.region}\". "
                  f"Please check the logs for details.\033[0m")
            logging.error("Failed to find or create prefix list with template %s in region %s", TEMPLATE_NAME_PREFIX, self.region)
            return None

        return prefix_list_id

    def get_prefix_list(self) -> Optional[dict]:
        """List prefix lists in the configured region. Returns response dict or None."""
        logging.info("[prefix] get prefix list of region: %s", self.region)
        # 构造请求对象
        describe_prefix_lists_request = ecs_20140526_models.DescribePrefixListsRequest(region_id=self.region)

        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribePrefixLists 接口
            describe_prefix_lists_response = self.client.describe_prefix_lists_with_options(describe_prefix_lists_request, runtime)  # type: ignore
            body_map = describe_prefix_lists_response.body.to_map()
            logging.info("[prefix] API response, detail=%s", json.dumps(body_map))
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

    def _auto_search_prefix_by_name(self, prefix_name: str = TEMPLATE_NAME_PREFIX) -> Optional[str]:
        '''Search for a prefix list by name prefix. Returns the prefix list ID if found, or None if not found.'''
        logging.info("[prefix] search prefix list, region=%s, prefix_name=%s ", self.region, prefix_name)
        prefix_lists = self.get_prefix_list()
        logging.debug(prefix_lists)
        if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
            for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
                logging.debug(prefix)
                if prefix['PrefixListName'].startswith(prefix_name):
                    logging.info("[prefix] found prefix list, name=%s id=%s", prefix['PrefixListName'], prefix['PrefixListId'])
                    return prefix["PrefixListId"]

    def print_prefix_list(self) -> Optional[List[str]]:
        """Print prefix list information in a human-readable format."""
        prefix_lists = self.get_prefix_list()
        if not prefix_lists or 'PrefixLists' not in prefix_lists or 'PrefixList' not in prefix_lists['PrefixLists']:
            logging.error("No prefix list information to display.")
            return

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

        print_tail()

        return template_ids

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

    def set_prefix(self) -> Optional[dict]:
        prefix_id = self._auto_search_prefix_by_name()
        if not prefix_id:
            print(f"\033[1;91m[aliyun] Prefix list with template \"{TEMPLATE_NAME_PREFIX}\" not found in region \"{self.region}\". "
                  f"Please run the init action first to create it.\033[0m")
            return
        self._update_prefix_list_by_id(prefix_id)
