import json
import logging
import re
import ipaddress
from typing import List

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .defaults import DEFAULT_MAX_ENTRIES, DEFAULT_REGION
from .client import ClientFactory
from ..util.nm import TEMPLATE_PREFIX
from ..ip_detector.detectors import get_iplist


class Prefix:
    def __init__(self, region: str | None = None, proxy: str | None = None) -> None:
        """Initialize Prefix helper.

        Args:
            region: Alibaba Cloud region, defaults to DEFAULT_REGION when not provided.
            proxy: Optional proxy configuration (currently stored but not used).
        """
        self.region = region if region else DEFAULT_REGION
        self.proxy = proxy
        logging.info("[config] region set to %s", self.region)

    def create_prefix_list(self, prefix_list_name: str = f'{TEMPLATE_PREFIX}0', description: str = f'{TEMPLATE_PREFIX}0_desc') -> dict | None:
        """Create a prefix list in the configured region.

        Returns the SDK response as a dict on success, or None on failure.
        """
        client = ClientFactory.create_client()
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

            # json.dumps(describe_instances_response.body)
        except UnretryableException:
            logging.exception("Network error when creating prefix list")
            return None
        except TeaException:
            logging.exception("Tea API error when creating prefix list")
            return None
        except Exception:
            logging.exception("Unexpected error when creating prefix list")
            return None

    def _associate_prefix_list_with_id(self, prefix_list_id: str) -> dict | None:
        """Associate normalized client IPs with the given prefix list id.

        Returns SDK response dict on success or None on failure.
        """
        client = ClientFactory.create_client()
        client_ip_list = get_iplist(self.proxy)

        # 校验、去重并限制数量
        client_ip_list = self._normalize_ip_list(client_ip_list)

        logging.warning("[aliyun] Associating prefix list %s in region %s with client IPs: %s", prefix_list_id, self.region, client_ip_list)

        # 构造请求对象
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=self.region,
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

    def list_prefix_list(self) -> dict | None:
        """List prefix lists in the configured region. Returns response dict or None."""
        logging.info("List prefix list of region: %s...", self.region)
        client = ClientFactory.create_client()
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

    def _search_prefix_by_name(self, prefix_list_name):
        logging.info("Search prefix list by name: %s in region: %s...", prefix_list_name, self.region)
        prefix_lists = self.list_prefix_list()
        logging.debug(prefix_lists)
        if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
            for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
                logging.debug(prefix)
                if re.search(re.escape(prefix_list_name), prefix['PrefixListName']):
                    logging.info("Found prefix list with name: %s, id: %s", prefix_list_name, prefix['PrefixListId'])
                    return prefix["PrefixListId"]

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
