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
        """Initialize the Prefix helper.

        Args:
            regions: A Regions object containing information for all target regions.
        """
        self.regions = regions
        self.proxy_port = int(regions.proxy.split(':')[-1]) if regions.proxy else None
        self.prefix_list_id, self.region = self._auto_get_region_by_prefix_name_from_all_regions()
        logging.info("[config] prefix_list is %s from region %s", self.prefix_list_id, self.region)
        self.client = ClientFactory.create_client(self.region, self.proxy_port) if self.region else None

    def init_prefix(self, region_id: str) -> int:
        """Find or create a prefix list in the given region and populate it with the current client IP.

        Args:
            region_id: Target Alibaba Cloud region, e.g. 'cn-hangzhou'.

        Returns:
            0 on success, non-zero on failure.
        """
        self.prefix_list_id = self._get_or_create_prefix_list(region_id)
        if not self.prefix_list_id or not self.region or not self.client:
            return 1
        return self._update_prefix_list_by_id()

    def _get_or_create_prefix_list(self, region_id: str) -> Optional[str]:
        """Find an existing prefix list in the given region (name starts with TEMPLATE_NAME_PREFIX),
        or create one if none exists.

        Args:
            region_id: Target Alibaba Cloud region.

        Returns:
            Prefix list ID string; None if both lookup and creation fail.
        """
        # 1. Reuse the existing prefix list only if it was found in the same region as the security group.
        #    Prefix lists are region-scoped; reusing one from a different region would have no effect.
        if self.prefix_list_id and self.region == region_id:
            print(f"\033[1;95m[aliyun] Prefix list with prefix \"{TEMPLATE_NAME_PREFIX}\" already exists in region \"{region_id}\", id=\"{self.prefix_list_id}\"\033[0m")
        # 2. Create a new prefix list in the target region
        else:
            self.prefix_list_id = self._create_prefix_list(region_id)
            if self.prefix_list_id:
                print(f"\033[1;95m[aliyun] Created prefix list with prefix \"{TEMPLATE_NAME_PREFIX}\" in region \"{region_id}\", id=\"{self.prefix_list_id}\"\033[0m")

        if not self.prefix_list_id:
            print(f"\033[1;91m[aliyun] Failed to find or create prefix list with template "
                  f"\"{TEMPLATE_NAME_PREFIX}\" in region \"{region_id}\". "
                  f"Please check the logs for details.\033[0m")
            return None

        return self.prefix_list_id

    def _create_prefix_list(self, region_id: str, prefix_list_name: str = f'{TEMPLATE_NAME_PREFIX}0', description: str = f'{TEMPLATE_NAME_PREFIX}0_desc') -> str:
        """Create a prefix list in the given region by calling the ECS CreatePrefixList API.

        Args:
            region_id: The Alibaba Cloud region where the prefix list should be created.
            prefix_list_name: Name of the prefix list; defaults to TEMPLATE_NAME_PREFIX + '0'.
            description: Description of the prefix list; defaults to TEMPLATE_NAME_PREFIX + '0_desc'.

        Returns:
            Prefix list ID string on success; empty string on failure.

        Side effects:
            Updates self.client and self.region on success.
        """
        # Build the CreatePrefixList request object
        client = ClientFactory.create_client(region_id, self.proxy_port)
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=region_id,
            prefix_list_name=prefix_list_name,
            description=description,
            max_entries=DEFAULT_MAX_ENTRIES,
            address_family='IPv4'
        )
        # Set runtime options
        runtime = util_models.RuntimeOptions()
        try:
            # Call the CreatePrefixList API
            create_prefix_list_response = client.create_prefix_list_with_options(create_prefix_list_request, runtime)  # type: ignore
            ret_data = create_prefix_list_response.body.to_map()
            # Update self.client and self.region only on success to keep them consistent
            self.client = client
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
        """Retrieve the current client IP, validate and deduplicate it, then append it to the prefix list.

        Requires self.prefix_list_id, self.region, and self.client to be properly initialized.

        Returns:
            0 on success, 1 if prerequisites are missing or the API call fails.
        """
        if not self.prefix_list_id or not self.region or not self.client:
            logging.error("Prefix list ID, region, or client is not initialized")
            return 1

        client_ip_list = get_iplist(self.proxy_port)
        # Validate, deduplicate, and cap the IP list
        client_ip_list = self._normalize_ip_list(client_ip_list)
        print(f"\033[1;95m[aliyun] Updating prefix list {self.prefix_list_id} in region \"{self.region}\" with client IPs: {client_ip_list}\033[0m")

        # Build the ModifyPrefixList request object
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=self.region,
            prefix_list_id=self.prefix_list_id,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description=f"EasyWhitelist@{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ) for ip in client_ip_list]
        )
        # Set runtime options
        runtime = util_models.RuntimeOptions()
        try:
            # Call the ModifyPrefixList API
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
    def get_prefix_list(client: Ecs20140526Client, region_id: str) -> Optional[dict]:
        """Call the ECS DescribePrefixLists API to list all prefix lists in the given region.

        Args:
            client: An initialized ECS client.
            region_id: The Alibaba Cloud region to query.

        Returns:
            API response body dict (contains the PrefixLists key); None on network or API error.
        """
        # Build the DescribePrefixLists request object
        logging.info("[aliyun] Retrieving prefix lists in region %s...", region_id)
        describe_prefix_lists_request = ecs_20140526_models.DescribePrefixListsRequest(region_id=region_id)

        # Set runtime options
        runtime = util_models.RuntimeOptions()
        try:
            # Call the DescribePrefixLists API
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

    def _auto_get_region_by_prefix_name_from_all_regions(self, prefix_name: str = TEMPLATE_NAME_PREFIX) -> tuple[Optional[str], Optional[str]]:
        """Iterate over all regions in self.regions to find a prefix list whose name starts with prefix_name.

        Args:
            prefix_name: Name prefix to match against prefix list names; defaults to TEMPLATE_NAME_PREFIX.

        Returns:
            A (prefix_list_id, region_id) tuple; (None, None) if not found.
        """
        logging.info("[prefix] searching for prefix list across all regions, prefix_name=%s", prefix_name)
        for region_id in self.regions.region_ids:
            logging.info("[prefix] searching in region %s", region_id)
            client = ClientFactory.create_client(region_id, self.proxy_port)
            prefix_lists = self.get_prefix_list(client, region_id)
            logging.debug(prefix_lists)
            if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
                for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
                    logging.debug(prefix)
                    if prefix['PrefixListName'].startswith(prefix_name):
                        logging.info("[prefix] found prefix list, name=%s id=%s", prefix['PrefixListName'], prefix['PrefixListId'])
                        return prefix["PrefixListId"], region_id
        return None, None

    def print_prefix_list(self) -> int:
        """Print a tabular summary of all prefix lists in the current region.

        Returns:
            0 on success; 1 if the client or region is not initialized; 2 if no prefix list data is available.
        """

        if not self.client or not self.region:
            return 1
        prefix_lists = self.get_prefix_list(self.client, self.region)
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

    @staticmethod
    def _normalize_ip_list(ip_list: List[str]) -> List[str]:
        """Validate, normalize to CIDR strings, deduplicate, and limit to DEFAULT_MAX_ENTRIES.

        - Accepts a single IP address or CIDR string.
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
        """Update the existing prefix list with the current client IP.

        The prefix list must already have been created via init_prefix; if not found, the user is prompted to run init first.

        Returns:
            0 on success; 1 if the prefix list does not exist or the update fails.
        """
        if not self.prefix_list_id or not self.region or not self.client:
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
