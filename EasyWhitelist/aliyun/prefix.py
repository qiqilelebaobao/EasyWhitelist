import json
import logging
import ipaddress
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.nm import TEMPLATE_NAME_PREFIX
from ..util.cli import echo_ok, echo_err, echo_info
from ..util.cli import print_header, print_row, print_separator, print_tail
from ..util.cli import print_update_banner, print_ip_list, print_region_result, print_summary
from ..detector.detectors import get_iplist

from .defaults import DEFAULT_MAX_ENTRIES, _runtime, _ecs_api_call
from .region import Regions
from .client import ClientFactory


class PrefixList:
    """Data class representing an Alibaba Cloud ECS prefix list."""

    def __init__(self, prefix_list_id: str, region_id: str, creation_time: Optional[str] = None, prefix_list_name: Optional[str] = None):
        """Initialize a PrefixList instance.

        Args:
            prefix_list_id: The unique identifier of the prefix list.
            region_id: The Alibaba Cloud region where the prefix list resides.
            creation_time: ISO-8601 creation timestamp returned by the API.
            prefix_list_name: Human-readable name of the prefix list.
        """
        self.prefix_list_id = prefix_list_id
        self.region_id = region_id
        self.creation_time = creation_time
        self.prefix_list_name = prefix_list_name


class Prefix:
    """Manage Alibaba Cloud ECS prefix lists across multiple regions."""

    def __init__(self, regions: Regions) -> None:
        """Initialize the Prefix helper.

        Args:
            regions: A Regions object containing information for all target regions.
        """
        self.regions = regions
        parsed = urlparse(regions.proxy_url) if regions.proxy_url else None
        self.proxy_port = parsed.port if parsed else None
        self._prefix_list: Optional[List[PrefixList]] = None
        self.current_prefix_list = None

    @property
    def prefix_list(self) -> List[PrefixList]:
        """Lazily discover prefix lists across all regions on first access."""
        if self._prefix_list is None:
            self._prefix_list = self._discover_prefix_list()
            logging.info("[aliyun] using prefix list %s",
                         [pl.__dict__ for pl in self._prefix_list] if self._prefix_list else None)
        return self._prefix_list

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
            echo_err(f'No prefix list with name prefix "{TEMPLATE_NAME_PREFIX}" found in any region — run init first')
            return 1

        client_ip_list = get_iplist(self.proxy_port)
        client_ip_list = self._normalize_ip_list(client_ip_list)

        print_update_banner(f"Update {len(self.prefix_list)} Prefix List(s)")
        echo_info(f"Detected {len(client_ip_list)} IP(s):")
        print_ip_list(client_ip_list)
        echo_info(f"Target regions: {', '.join(pl.region_id for pl in self.prefix_list)}")
        print()

        failed = 0
        for pl in self.prefix_list:
            ok = self._modify_one_prefix_list(pl.region_id, pl.prefix_list_id, client_ip_list)
            print_region_result(pl.region_id, pl.prefix_list_id, ok)
            if not ok:
                failed += 1

        print_summary(len(self.prefix_list), failed)
        return 0 if failed == 0 else 1

    def print_prefix_list(self) -> int:
        """Print a tabular summary of all prefix lists in the current region.

        Returns:
            0 on success; 1 if the client or region is not initialized; 2 if no prefix list data is available.
        """

        logging.info("[aliyun] printing prefix list.")
        if not self.prefix_list:
            return 1

        print_header('Alibaba Cloud Prefix List')

        row = 0
        any_error = False

        for prefix in self.prefix_list:
            row += 1
            entries = self._get_prefix_detail_by_id(prefix.region_id, prefix.prefix_list_id)
            if entries is None:
                any_error = True
                entries = []
            cidrs = [e['Cidr'] for e in entries]
            first = cidrs[0] if cidrs else ""
            suffix = f" (+{len(cidrs) - 1})" if len(cidrs) > 1 else ""
            print_row(idx=row,
                      region=prefix.region_id,
                      id=prefix.prefix_list_id,
                      ctime=prefix.creation_time,
                      addrs=f"{first}{suffix}",
                      name=prefix.prefix_list_name)
            for extra in cidrs[1:]:
                print_row(addrs=extra)
            print_separator()

        logging.info("[aliyun] prefix list IDs: %s", [pl.prefix_list_id for pl in self.prefix_list])
        print_tail()

        return 2 if any_error else 0

    def _ensure_prefix_list(self, region_id: str) -> Optional[PrefixList]:
        """Find an existing prefix list in the given region (name starts with TEMPLATE_NAME_PREFIX),
        or create one if none exists.

        Args:
            region_id: Target Alibaba Cloud region.

        Returns:
            PrefixList object on success; None if both lookup and creation fail.
        """
        # 1. Reuse the existing prefix list only if it was found in the same region as the security group.
        #    Prefix lists are region-scoped; reusing one from a different region would have no effect.
        if self.prefix_list and region_id in [pl.region_id for pl in self.prefix_list]:
            self.current_prefix_list = next(pl for pl in self.prefix_list if pl.region_id == region_id)
            echo_ok(f"Reusing prefix list {self.current_prefix_list.prefix_list_id} in {region_id}")

        # 2. Create a new prefix list in the target region
        else:
            self.current_prefix_list = self._create_prefix_list(region_id)
            if self.current_prefix_list:
                echo_ok(f"Created prefix list {self.current_prefix_list.prefix_list_id} in {region_id}")

        if not self.current_prefix_list:
            echo_err(f'Failed to find or create a prefix list with name prefix "{TEMPLATE_NAME_PREFIX}" in {region_id}')
            return None

        return self.current_prefix_list

    def _create_prefix_list(self, region_id: str, prefix_name: str = TEMPLATE_NAME_PREFIX) -> Optional[PrefixList]:
        """Create a prefix list in the given region by calling the ECS CreatePrefixList API.

        Args:
            region_id: The Alibaba Cloud region where the prefix list should be created.
            prefix_name: Name prefix for the prefix list; a timestamp suffix is appended automatically.

        Returns:
            A PrefixList object on success; None on failure.
        """
        # Build the CreatePrefixList request object
        prefix_list_name = f"{prefix_name}{int(datetime.now().timestamp())}"
        description = f"{prefix_list_name}_desc"
        client: Ecs20140526Client = ClientFactory.create_client(region_id, self.proxy_port)
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=region_id,
            prefix_list_name=prefix_list_name,
            description=description,
            max_entries=DEFAULT_MAX_ENTRIES,
            address_family='IPv4'
        )
        runtime = _runtime(self.proxy_port is not None)
        resp = _ecs_api_call(
            lambda: client.create_prefix_list_with_options(create_prefix_list_request, runtime),
            "creating prefix list",
        )
        if resp is None:
            return None
        ret_data = resp.body.to_map()
        logging.debug(json.dumps(ret_data))
        return PrefixList(ret_data["PrefixListId"], region_id) if "PrefixListId" in ret_data else None

    def _update_prefix_list(self) -> int:
        """Retrieve the current client IP list, validate and deduplicate the entries, then append them to the prefix list.

        Returns:
            0 on success, 1 if prerequisites are missing or the API call fails.
        """
        if not self.current_prefix_list:
            logging.error("[aliyun] Prefix list ID or region ID is not initialized")
            return 1

        client_ip_list = get_iplist(self.proxy_port)
        client_ip_list = self._normalize_ip_list(client_ip_list)

        print_update_banner("Init Prefix List")
        echo_info(f"Detected {len(client_ip_list)} IP(s):")
        print_ip_list(client_ip_list)
        echo_info(f"Target: {self.current_prefix_list.prefix_list_id} in {self.current_prefix_list.region_id}")
        print()

        ok = self._modify_one_prefix_list(
            self.current_prefix_list.region_id,
            self.current_prefix_list.prefix_list_id,
            client_ip_list,
        )
        print_region_result(self.current_prefix_list.region_id, self.current_prefix_list.prefix_list_id, ok)
        print_summary(1, 0 if ok else 1)
        return 0 if ok else 1

    def _modify_one_prefix_list(self, region_id: str, prefix_list_id: str, ip_list: List[str]) -> bool:
        """Send a ModifyPrefixList request for a single prefix list.

        Returns:
            True on success; False on failure.
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id, self.proxy_port)
        request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=region_id,
            prefix_list_id=prefix_list_id,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description=f"EasyWhitelist@{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ) for ip in ip_list]
        )
        runtime = _runtime(self.proxy_port is not None)
        resp = _ecs_api_call(
            lambda: client.modify_prefix_list_with_options(request, runtime),
            "modifying prefix list",
        )
        if resp is not None:
            logging.debug(json.dumps(resp.body.to_map()))
            return True
        return False

    def _fetch_prefix_lists(self, region_id: str) -> List[Dict[str, Any]]:
        """Call the ECS DescribePrefixLists API to list all prefix lists in the given region.
        Iterates all pages via NextToken / MaxResults and returns a flat list.

        Args:
            region_id: The Alibaba Cloud region to query.

        Returns:
            A list of prefix list dicts; empty list on network or API error.
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id, self.proxy_port)
        logging.info("[aliyun] Retrieving prefix lists in region %s...", region_id)
        runtime = _runtime(self.proxy_port is not None)
        all_entries: list = []
        next_token: Optional[str] = None
        max_results = 100  # maximum allowed by the ECS API
        try:
            while True:
                req_kwargs: dict = dict(region_id=region_id, max_results=max_results)
                if next_token:
                    req_kwargs["next_token"] = next_token
                describe_prefix_lists_request = ecs_20140526_models.DescribePrefixListsRequest(**req_kwargs)
                describe_prefix_lists_response = client.describe_prefix_lists_with_options(describe_prefix_lists_request, runtime)  # type: ignore
                body_map = describe_prefix_lists_response.body.to_map()
                logging.debug("[aliyun] API response, detail=%s", json.dumps(body_map))
                page_entries = (body_map.get("PrefixLists") or {}).get("PrefixList") or []
                all_entries.extend(page_entries)
                next_token = body_map.get("NextToken") or None
                if not next_token:
                    break
            return all_entries
        except Exception:
            logging.exception("[aliyun] Error when describing prefix lists")
            return []

    def _discover_prefix_list(self, prefix_name: str = TEMPLATE_NAME_PREFIX) -> List[PrefixList]:
        """Iterate over all regions in self.regions to find a prefix list whose name starts with prefix_name.

        Args:
            prefix_name: Name prefix to match against prefix list names; defaults to TEMPLATE_NAME_PREFIX.

        Returns:
            A list of PrefixList objects if found; empty list if not found.
        """
        logging.info("[aliyun] searching for a prefix list across all regions, prefix_name=%s", prefix_name)
        prefix_list = []
        for region_id in self.regions.region_ids:
            logging.info("[aliyun] searching in region %s", region_id)
            for entry in self._fetch_prefix_lists(region_id):
                logging.debug(entry)
                if entry['PrefixListName'].startswith(prefix_name):
                    logging.info("[aliyun] found prefix list: name=%s, id=%s", entry['PrefixListName'], entry['PrefixListId'])
                    prefix_list.append(PrefixList(entry['PrefixListId'], region_id, entry['CreationTime'], entry['PrefixListName']))
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
                logging.warning("[aliyun] Invalid IP/CIDR skipped: %s", s)
                continue
            if cidr in seen:
                continue
            seen.add(cidr)
            normalized.append(cidr)
            if len(normalized) >= DEFAULT_MAX_ENTRIES:
                logging.warning("[aliyun] Truncating IP list to %d entries (DEFAULT_MAX_ENTRIES)", DEFAULT_MAX_ENTRIES)
                break

        return normalized

    def _get_prefix_detail_by_id(self, region_id: str, prefix_list_id: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch the CIDR entries of a specific prefix list.

        Args:
            region_id: The Alibaba Cloud region of the prefix list.
            prefix_list_id: The unique identifier of the prefix list.

        Returns:
            A list of entry dicts (each containing 'Cidr' and 'Description'); None on error.
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id, self.proxy_port)
        logging.info("[aliyun] fetching prefix list details for prefix_list_id=%s in region %s", prefix_list_id, region_id)
        runtime = _runtime(self.proxy_port is not None)
        try:
            describe_req = ecs_20140526_models.DescribePrefixListAttributesRequest(
                region_id=region_id,
                prefix_list_id=prefix_list_id,
            )
            describe_resp = client.describe_prefix_list_attributes_with_options(describe_req, runtime)  # type: ignore
            current_entries = describe_resp.body.to_map().get('Entries', {}).get('Entry', []) or []
            logging.debug("[aliyun] prefix list entries: %s", current_entries)
        except Exception:
            logging.exception("[aliyun] Failed to describe prefix list attributes for %s", prefix_list_id)
            return None
        return current_entries

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
