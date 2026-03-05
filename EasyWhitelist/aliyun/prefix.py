import json
import logging
import re
import ipaddress
from typing import List, Optional

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .defaults import DEFAULT_MAX_ENTRIES, DEFAULT_REGION
from .client import ClientFactory
from ..util.nm import TEMPLATE_PREFIX
from ..ip_detector.detectors import get_iplist


HEADER_WIDTH = 150
COLS = {
    "idx": 10,
    "id": 30,
    "ctime": 30,
    "addrs": 60,
    "name": 30,
}


class Prefix:
    def __init__(self, region: Optional[str] = None, proxy: Optional[str] = None) -> None:
        """Initialize Prefix helper.

        Args:
            region: Alibaba Cloud region, defaults to DEFAULT_REGION when not provided.
            proxy: Optional proxy configuration (currently stored but not used).
        """
        self.region = region if region else DEFAULT_REGION
        self.proxy = proxy
        logging.info("[config] region set to %s", self.region)

    def create_prefix_list(self, prefix_list_name: str = f'{TEMPLATE_PREFIX}0', description: str = f'{TEMPLATE_PREFIX}0_desc') -> Optional[dict]:
        """Create a prefix list in the configured region.

        Returns the SDK response as a dict on success, or None on failure.
        """
        client = ClientFactory.create_client(self.region)
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

    def _associate_prefix_list_with_id(self, prefix_list_id: str) -> Optional[dict]:
        """Replace all entries in the prefix list with current client IPs.

        先查询旧条目并全部移除，再写入最新 IP，避免历史条目堆积。
        Returns SDK response dict on success or None on failure.
        """
        client = ClientFactory.create_client(self.region)
        client_ip_list = get_iplist()

        # 校验、去重并限制数量
        client_ip_list = self._normalize_ip_list(client_ip_list)

        logging.warning("[aliyun] Replacing prefix list %s in region %s with client IPs: %s", prefix_list_id, self.region, client_ip_list)

        # 查询当前条目，以便全量替换
        runtime = util_models.RuntimeOptions()
        try:
            describe_req = ecs_20140526_models.DescribePrefixListAttributesRequest(
                region_id=self.region,
                prefix_list_id=prefix_list_id,
            )
            describe_resp = client.describe_prefix_list_attributes_with_options(describe_req, runtime)
            current_entries = describe_resp.body.to_map().get('Entries', {}).get('Entry', []) or []
        except Exception:
            logging.exception("[aliyun] Failed to describe prefix list attributes for %s; will append only", prefix_list_id)
            current_entries = []

        remove_entries = [
            ecs_20140526_models.ModifyPrefixListRequestRemoveEntry(cidr=entry['Cidr'])
            for entry in current_entries
            if entry.get('Cidr')
        ]

        # 构造请求对象
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=self.region,
            prefix_list_id=prefix_list_id,
            remove_entry=remove_entries if remove_entries else None,
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

        except UnretryableException:
            logging.exception("Network error when modifying prefix list")
            return None
        except TeaException:
            logging.exception("Tea API error when modifying prefix list")
            return None
        except Exception:
            logging.exception("Unexpected error when modifying prefix list")
            return None

    def list_prefix_list(self) -> Optional[dict]:
        """List prefix lists in the configured region. Returns response dict or None."""
        logging.info("[prefix] list prefix list of region: %s...", self.region)
        client = ClientFactory.create_client(self.region)
        # 构造请求对象
        describe_prefix_lists_request = ecs_20140526_models.DescribePrefixListsRequest(
            region_id=self.region,
            # prefix_list_name=f'{TEMPLATE_PREFIX}'
        )
        # 设置运行时参数
        runtime = util_models.RuntimeOptions()
        try:
            # 调用 DescribePrefixLists 接口
            describe_prefix_lists_response = client.describe_prefix_lists_with_options(describe_prefix_lists_request, runtime)
            logging.info("[prefix] API response, detail=%s", json.dumps(describe_prefix_lists_response.body.to_map()))
            return describe_prefix_lists_response.body.to_map()
        except UnretryableException:
            logging.exception("Network error when describing prefix lists")
            return None
        except TeaException:
            logging.exception("Tea API error when describing prefix lists")
            return None
        except Exception:
            logging.exception("Unexpected error when describing prefix lists")
            return None

    def _search_prefix_by_name(self, prefix_list_name):
        logging.info("[prefix] search prefix list, name=%s region=%s", prefix_list_name, self.region)
        prefix_lists = self.list_prefix_list()
        logging.debug(prefix_lists)
        if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
            for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
                logging.debug(prefix)
                if re.match(re.escape(prefix_list_name), prefix['PrefixListName']):
                    logging.info("[prefix] found prefix list, name=%s id=%s", prefix_list_name, prefix['PrefixListId'])
                    return prefix["PrefixListId"]

    def print_prefix_list(self) -> Optional[List[str]]:
        """Print prefix list information in a human-readable format."""
        prefix_lists = self.list_prefix_list()
        if not prefix_lists or 'PrefixLists' not in prefix_lists or 'PrefixList' not in prefix_lists['PrefixLists']:
            logging.info("No prefix list information to display.")
            return

        # 表头
        header = (f"{'#':<{COLS['idx']}}"
                  f"{'Template ID':<{COLS['id']}}"
                  f"{'CreatedTime':<{COLS['ctime']}}"
                  f"{'Addresses':<{COLS['addrs']}}"
                  f"{'AddressTemplateName':<{COLS['name']}}")

        print(f"{'Alibaba Cloud Prefix List':=^{HEADER_WIDTH}}")
        print(header)
        print("-" * HEADER_WIDTH)

        template_ids = []

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
        print("-" * HEADER_WIDTH)

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

    def set_prefix(self):
        prefix_id = self._search_prefix_by_name(TEMPLATE_PREFIX)
        if not prefix_id:
            logging.warning("Prefix with template %s not found in region %s", TEMPLATE_PREFIX, self.region)
            return None
        return self._associate_prefix_list_with_id(prefix_id)
