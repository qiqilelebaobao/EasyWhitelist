import json
import logging
import ipaddress
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_util import models as util_models
from alibabacloud_ecs20140526 import models as ecs_20140526_models

from .defaults import DEFAULT_MAX_ENTRIES
from ..util.nm import TEMPLATE_NAME_PREFIX
from ..ip_detector.detectors import get_iplist
from ..util.cli import print_header, print_tail, COLS
from .region import Regions
from .client import ClientFactory, Ecs20140526Client


class PrefixList:
    def __init__(self, prefix_list_id: str, region_id: str):
        self.prefix_list_id = prefix_list_id
        self.region_id = region_id


class Prefix:
    def __init__(self, regions: Regions) -> None:
        """Initialize the Prefix helper.

        Args:
            regions: A Regions object containing information for all target regions.
        """
        self.regions = regions
        parsed = urlparse(regions.proxy) if regions.proxy else None
        self.proxy_port = parsed.port if parsed else None
        self.prefix_list: List[PrefixList] = self._discover_prefix_list()
        self.current_prefix_list = None
        logging.info("[prefix] using prefix list %s", [pl.__dict__ for pl in self.prefix_list] if self.prefix_list else None)

    def init_prefix(self, region_id: str) -> int:
        """Find or create a prefix list in the given region and populate it with the current client IP.

        Args:
            region_id: Target Alibaba Cloud region, e.g. 'cn-hangzhou'.

        Returns:
            0 on success, non-zero on failure.
        """
        self.current_prefix_list = self._ensure_prefix_list(region_id)
        if not self.current_prefix_list:
            return 1
        return self._update_prefix_list()

    def update_prefix(self) -> int:
        """Update the existing prefix list with the current client IP.

        The prefix list must already have been created via init_prefix; if not found, the user is prompted to run init first.

        Returns:
            0 on success; 1 if the prefix list does not exist or the update fails.
        """
        if not self.prefix_list:
            print(f"\033[1;91m[aliyun] No prefix list with name prefix \"{TEMPLATE_NAME_PREFIX}\" was found in any region. "
                  f"Please run the init action first to create it.\033[0m")
            return 1

        client_ip_list = get_iplist(self.proxy_port)
        # Validate, deduplicate, and cap the IP list
        client_ip_list = self._normalize_ip_list(client_ip_list)
        print(f"\033[1;95m[aliyun] Updating prefix list(s) in regions {[pl.region_id for pl in self.prefix_list]} with client IPs: {client_ip_list}\033[0m")

        for prefix in self.prefix_list:
            client: Ecs20140526Client = ClientFactory.create_client(prefix.region_id, self.proxy_port)

            # Build the ModifyPrefixList request object
            modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
                region_id=prefix.region_id,
                prefix_list_id=prefix.prefix_list_id,
                add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                    cidr=ip,
                    description=f"EasyWhitelist@{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ) for ip in client_ip_list]
            )
            # Set runtime options
            runtime = util_models.RuntimeOptions()
            try:
                # Call the ModifyPrefixList API
                modify_prefix_list_response = client.modify_prefix_list_with_options(modify_prefix_list_request, runtime)  # type: ignore
                logging.info(json.dumps(modify_prefix_list_response.body.to_map()))
                return 0

            except UnretryableException:
                logging.exception("Network error when modifying prefix list")
                continue  # try the next prefix list if there's a network error
            except TeaException:
                logging.exception("Tea API error when modifying prefix list")
                continue  # try the next prefix list if there's an API error
            except Exception:
                logging.exception("Unexpected error when modifying prefix list")
                continue  # try the next prefix list if there's an unexpected error

    def print_prefix_list(self) -> int:
        """Print a tabular summary of all prefix lists in the current region.

        Returns:
            0 on success; 1 if the client or region is not initialized; 2 if no prefix list data is available.
        """

        if not self.prefix_list:
            return 1

        print_header('Alibaba Cloud Prefix List')

        template_ids = []

        for prefix in self.prefix_list:
            fetched_prefix_lists = self._fetch_prefix_lists(prefix.region_id)
            if not fetched_prefix_lists or 'PrefixLists' not in fetched_prefix_lists or 'PrefixList' not in fetched_prefix_lists['PrefixLists']:
                logging.error("No prefix list information to display.")
                return 2

            for i, prefix_entry in enumerate(fetched_prefix_lists["PrefixLists"]["PrefixList"], 1):
                template_ids.append(prefix_entry["PrefixListId"])
                # addr_set = prefix["AddressSet"]
                addreset = "placeholder for addresses"  # keep
                t_id = prefix_entry["PrefixListId"]
                t_time = prefix_entry["CreationTime"]
                t_name = prefix_entry["PrefixListName"]
                print(f"{str(i):<{COLS['idx']}}"
                      f"{prefix.region_id:<{COLS['region']}}"
                      f"{t_id:<{COLS['id']}}"
                      f"{t_time:<{COLS['ctime']}}"
                      f"{addreset:<{COLS['addrs']}}"
                      f"{t_name:{COLS['name']}}"
                      )

        logging.info("[aliyun] prefix list IDs: %s", ":".join(template_ids))
        print_tail()

        return 0

    def _ensure_prefix_list(self, region_id: str) -> Optional[PrefixList]:
        """Find an existing prefix list in the given region (name starts with TEMPLATE_NAME_PREFIX),
        or create one if none exists.

        Args:
            region_id: Target Alibaba Cloud region.

        Returns:
            Prefix list ID string; None if both lookup and creation fail.
        """
        # 1. Reuse the existing prefix list only if it was found in the same region as the security group.
        #    Prefix lists are region-scoped; reusing one from a different region would have no effect.
        if self.prefix_list and region_id in [pl.region_id for pl in self.prefix_list]:
            self.current_prefix_list = next(pl for pl in self.prefix_list if pl.region_id == region_id)
            print(f"\033[1;95m[aliyun] Reusing existing prefix list with ID {self.current_prefix_list.prefix_list_id} in region \"{region_id}\"\033[0m")

        # 2. Create a new prefix list in the target region
        else:
            self.current_prefix_list = self._create_prefix_list(region_id)
            if self.current_prefix_list:
                print(f"\033[1;95m[aliyun] Created prefix list with prefix"
                      f" \"{TEMPLATE_NAME_PREFIX}\" in region \"{region_id}\", id=\"{self.current_prefix_list.prefix_list_id}\"\033[0m")

        if not self.current_prefix_list:
            print(f"\033[1;91m[aliyun] Failed to find or create a prefix list with name prefix "
                  f"\"{TEMPLATE_NAME_PREFIX}\" in region \"{region_id}\". "
                  f"Please check the logs for details.\033[0m")
            return None

        return self.current_prefix_list

    def _create_prefix_list(self, region_id: str, prefix_list_name: str = f'{TEMPLATE_NAME_PREFIX}0', description: str = f'{TEMPLATE_NAME_PREFIX}0_desc') -> Optional[PrefixList]:
        """Create a prefix list in the given region by calling the ECS CreatePrefixList API.

        Args:
            region_id: The Alibaba Cloud region where the prefix list should be created.
            prefix_list_name: Name of the prefix list; defaults to TEMPLATE_NAME_PREFIX + '0'.
            description: Description of the prefix list; defaults to TEMPLATE_NAME_PREFIX + '0_desc'.

        Returns:
            Prefix list ID string on success; empty string on failure.

        Side effects:
            Updates self.region_id on success.
        """
        # Build the CreatePrefixList request object
        client: Ecs20140526Client = ClientFactory.create_client(region_id, self.proxy_port)
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
            # Update self.region_id only on success to keep it consistent
            self.region_id = region_id
            logging.info(json.dumps(ret_data))
            return PrefixList(ret_data["PrefixListId"], region_id) if "PrefixListId" in ret_data else None

        except UnretryableException:
            logging.exception("Network error when creating prefix list")
            return None
        except TeaException:
            logging.exception("Tea API error when creating prefix list")
            return None
        except Exception:
            logging.exception("Unexpected error when creating prefix list")
            return None

    def _update_prefix_list(self) -> int:
        """Retrieve the current client IP list, validate and deduplicate the entries, then append them to the prefix list.

        Requires self.prefix_list_id and self.region_id to be properly initialized.

        Returns:
            0 on success, 1 if prerequisites are missing or the API call fails.
        """
        if not self.current_prefix_list:
            logging.error("Prefix list ID or region ID is not initialized")
            return 1

        client: Ecs20140526Client = ClientFactory.create_client(self.current_prefix_list.region_id, self.proxy_port)

        client_ip_list = get_iplist(self.proxy_port)
        # Validate, deduplicate, and cap the IP list
        client_ip_list = self._normalize_ip_list(client_ip_list)
        print(f"\033[1;95m[aliyun] Updating prefix list {self.current_prefix_list.prefix_list_id}"
              f" in region \"{self.current_prefix_list.region_id}\" with client IPs: {client_ip_list}\033[0m")

        # Build the ModifyPrefixList request object
        modify_prefix_list_request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=self.current_prefix_list.region_id,
            prefix_list_id=self.current_prefix_list.prefix_list_id,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description=f"EasyWhitelist@{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ) for ip in client_ip_list]
        )
        # Set runtime options
        runtime = util_models.RuntimeOptions()
        try:
            # Call the ModifyPrefixList API
            modify_prefix_list_response = client.modify_prefix_list_with_options(modify_prefix_list_request, runtime)  # type: ignore
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

    def _fetch_prefix_lists(self, region_id: str) -> Optional[dict]:
        """Call the ECS DescribePrefixLists API to list all prefix lists in the given region.
        Handles token-based pagination (NextToken / MaxResults) transparently.

        Args:
            region_id: The Alibaba Cloud region to query.

        Returns:
            A dict with key 'PrefixLists' -> {'PrefixList': [...]} containing all pages;
            None on network or API error.
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id, self.proxy_port)
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

    def _discover_prefix_list(self, prefix_name: str = TEMPLATE_NAME_PREFIX) -> List[PrefixList]:
        """Iterate over all regions in self.regions to find a prefix list whose name starts with prefix_name.

        Args:
            prefix_name: Name prefix to match against prefix list names; defaults to TEMPLATE_NAME_PREFIX.

        Returns:
            A list of PrefixList objects if found; empty list if not found.
        """
        logging.info("[prefix] searching for a prefix list across all regions, prefix_name=%s", prefix_name)
        prefix_list = []
        for region_id in self.regions.region_ids:
            logging.info("[prefix] searching in region %s", region_id)
            prefix_lists = self._fetch_prefix_lists(region_id)
            logging.debug(prefix_lists)
            if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
                for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
                    logging.debug(prefix)
                    if prefix['PrefixListName'].startswith(prefix_name):
                        logging.info("[prefix] found prefix list: name=%s, id=%s", prefix['PrefixListName'], prefix['PrefixListId'])
                        prefix_list.append(PrefixList(prefix['PrefixListId'], region_id))
        return prefix_list

    @staticmethod
    def _normalize_ip_list(ip_list: List[str]) -> List[str]:
        """Validate, normalize to CIDR strings, deduplicate, and limit to DEFAULT_MAX_ENTRIES.

        - Each element may be a bare IP address or a CIDR string.
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
