import json
import logging
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List, Optional

from tqdm import tqdm

from alibabacloud_ecs20140526 import models as ecs_20140526_models
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client

from ..util.defaults import RESOURCE_NAME_PREFIX, DEFAULT_CONCURRENT_WORKERS
from ..util.cli import echo_start, echo_progress, echo_success, echo_fail, echo_hint
from ..util.cli import print_header, print_row, print_separator, print_tail
from ..detector.detectors import retrieve_unique_ip_addresses

from .defaults import DEFAULT_MAX_ENTRIES, _runtime, _ecs_api_call
from .region import Regions
from .client import ClientFactory
from ..util.db import upsert_ip_address
from .sg import SecurityGroup
from ..config import settings


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
        self._prefix_list: Optional[List[PrefixList]] = None
        self.current_prefix_list = None

    @property
    def prefix_list(self) -> List[PrefixList]:
        """Lazily discover prefix lists across all regions on first access."""
        if self._prefix_list is None:
            self._prefix_list = self._discover_prefix_list()
            logging.info("[prefix] Using prefix lists: %s",
                         [pl.__dict__ for pl in self._prefix_list] if self._prefix_list else None)
        return self._prefix_list

    def init_whitelist(self, sg_id: Optional[str]) -> int:
        """Initialize whitelist by associating a prefix list with a security group.

        Args:
            sg_id: Security group ID to associate the prefix list with.

        Returns:
            0 on success, non-zero error code on failure:
            1 - sg_id not provided
            2 - failed to look up security group
            3 - security group not found
            4 - failed to get/create/update prefix list
            5 - failed to create security group rule
        """
        if not sg_id:
            logging.error("Security group ID is required for initialization")
            return 1

        # 1. Look up the security group; return on failure
        try:
            sg = SecurityGroup(sg_id, self.regions)
            logging.info("[prefix] Security group lookup result: sg_id=%s, region_id=%s, sg_name=%s",
                         sg.sg_id, sg.region_id, sg.sg_name)
        except Exception:
            logging.error("Failed to look up security group %s", sg_id)
            return 2

        if not sg.region_id:
            logging.error("Security group %s not found in any region", sg_id)
            return 3

        # 2. Get or create the prefix list and update it with the current client IP.
        # `init_prefix` returns a non-zero value on failure. The second condition
        # acts as a safety check for the unlikely case where `init_prefix` returns
        # 0 but `prefix_list_id` remains unset.

        ip_list = self.init_prefix(sg.region_id)
        if not ip_list or not self.current_prefix_list:
            logging.error("Failed to create prefix list, cannot proceed with whitelist initialization")
            return 4
        logging.info("[prefix] Prefix list initialized: %s", self.current_prefix_list.__dict__ if self.current_prefix_list else None)

        if not sg.add_prefix_list_rule(self.current_prefix_list.prefix_list_id):
            logging.error("Failed to create security group rule with prefix list")
            return 5
        logging.info("[prefix] Security group rule with prefix list %s applied to %s", self.current_prefix_list.prefix_list_id, sg.sg_id)

        echo_success(f"前缀列表 {self.current_prefix_list.prefix_list_id} 已关联到安全组 {sg_id}")

        return 0

    def init_prefix(self, region_id: str) -> list:
        """Find or create a prefix list in the given region and populate it with the current client IP.

        Args:
            region_id: Target Alibaba Cloud region, e.g. 'cn-hangzhou'.

        Returns:
            A list of updated IPs on success; empty list if prerequisites are missing or the API call fails.
        """
        self.current_prefix_list = self._ensure_prefix_list(region_id)
        if not self.current_prefix_list:
            return []
        return self._update_prefix_list()

    def update_prefix(self) -> int:
        """Update the existing prefix list with the current client IP.

        The prefix list must already have been created via init_prefix; if not found, the user is prompted to run init first.

        Returns:
            0 on success; 1 if the prefix list does not exist or the update fails.
        """
        if not self.prefix_list:
            logging.error('No prefix list with name prefix "%s" found in any region — run init first', RESOURCE_NAME_PREFIX)
            return 1

        client_ip_list = retrieve_unique_ip_addresses()
        client_ip_list = self._normalize_ip_list(client_ip_list)
        echo_hint("已规范化 IP 列表并记录到数据库")

        failed = 0
        for pl in self.prefix_list:
            ok = self._modify_one_prefix_list(pl.region_id, pl.prefix_list_id, client_ip_list)
            if ok:
                echo_success(f"前缀列表 {pl.prefix_list_id} ({pl.region_id}) 已更新 -> {client_ip_list}")
            else:
                failed += 1
                echo_fail(f"前缀列表 {pl.prefix_list_id} ({pl.region_id}) 更新失败（请检查网络或前缀列表状态）")
                logging.warning("[prefix] Failed to update prefix list: %s in %s", pl.prefix_list_id, pl.region_id)

        return 0 if failed == 0 else 1

    def _display_prefix_list(self) -> List[str]:
        """Fetch and display prefix lists as a table, returning prefix list IDs."""
        logging.info("[prefix] Printing prefix list.")
        if not self.prefix_list:
            return []

        logging.info("[prefix] Fetching prefix list details with up to %d concurrent workers...", min(DEFAULT_CONCURRENT_WORKERS, len(self.prefix_list) or 1))

        with ThreadPoolExecutor(max_workers=min(DEFAULT_CONCURRENT_WORKERS, len(self.prefix_list) or 1)) as executor:
            results: List[Optional[tuple[PrefixList, Optional[List[Dict[str, Any]]]]]] = [None] * len(self.prefix_list)

            def fetch_entries(prefix: PrefixList, index: int):
                return index, prefix, self._get_prefix_detail_by_id(prefix.region_id, prefix.prefix_list_id)

            futures = {executor.submit(fetch_entries, prefix, i): i for i, prefix in enumerate(self.prefix_list)}

            with tqdm(
                total=len(futures),
                desc='\U0001f504 [\u8fdb\u884c\u4e2d]  Fetching prefix list details',
                unit='task',
                ncols=84,
                mininterval=0.3,
                maxinterval=1.0,
                ascii=True,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            ) as pbar:
                for future in as_completed(futures):
                    try:
                        idx, prefix, entries = future.result()
                        results[idx] = (prefix, entries)
                    except Exception:
                        logging.exception("[prefix] Error searching prefix list in region %s", futures[future])
                    finally:
                        pbar.update(1)

        print_header('Alibaba Cloud Prefix List')
        self._print_prefix_list_results(results)
        print_tail()
        logging.info("[prefix] Prefix list IDs: %s", [pl.prefix_list_id for pl in self.prefix_list])

        return [pl.prefix_list_id for pl in self.prefix_list]

    def process_prefix_list_input(self) -> int:
        """Display prefix lists and accept interactive input to update them.

        Returns:
            0 always (exits on user request or error); 1 if no prefix lists found.
        """
        prefix_list_ids = self._display_prefix_list()
        if not prefix_list_ids:
            return 1

        last_input = None
        input_prompt = "Please choose # prefix list to update (or [L]ist, [S]et all, [Q]uit, [\u21b5\u00d72] to exit): "

        while True:
            try:
                user_input = input(input_prompt).strip().lower()

                if last_input == "" and user_input == "":
                    break
                last_input = user_input

                if user_input.isdigit():
                    index = int(user_input)
                    if 1 <= index <= len(prefix_list_ids):
                        pl = self.prefix_list[index - 1]
                        client_ip_list = retrieve_unique_ip_addresses()
                        client_ip_list = self._normalize_ip_list(client_ip_list)
                        if self._modify_one_prefix_list(pl.region_id, pl.prefix_list_id, client_ip_list):
                            echo_success(f"\u524d\u7f00\u5217\u8868 {pl.prefix_list_id} ({pl.region_id}) \u5df2\u66f4\u65b0 -> {client_ip_list}")
                            echo_hint("\u5df2\u89c4\u8303\u5316 IP \u5217\u8868\u5e76\u8bb0\u5f55\u5230\u6570\u636e\u5e93")
                        else:
                            msg = (
                                f"前缀列表 {pl.prefix_list_id} ({pl.region_id}) 更新失败"
                                "（请检查网络或前缀列表状态）"
                            )
                            echo_fail(msg)
                    else:
                        logging.warning("[prefix] Selection out of range (available: 1~%d)", len(prefix_list_ids))
                elif user_input == "l":
                    self._prefix_list = None  # force refresh
                    prefix_list_ids = self._display_prefix_list()
                elif user_input == "s":
                    self.update_prefix()
                elif user_input == "q":
                    break
                elif user_input != "":
                    logging.warning("[prefix] Invalid command: %s (hint: l/s/q)", user_input)

            except KeyboardInterrupt:
                logging.warning("[prefix] Operation cancelled by user")
                break
            except ValueError as e:
                logging.warning("[prefix] Input failed: value error: %s", e)
            except ConnectionError as e:
                logging.error("[prefix] Connection failed: %s", e)
                break
            except Exception as e:
                logging.error("[prefix] Request failed: %s", e)
                break

        return 0

    def _print_prefix_list_results(self, results: List[Optional[tuple[PrefixList, Optional[List[Dict[str, Any]]]]]]) -> bool:
        """Render prefix list query results in table form and return any-error flag."""
        any_error = False

        items = [item for item in results if item is not None]
        for idx, item in enumerate(items, start=1):
            prefix, entries = item
            if entries is None:
                any_error = True
                entries = []
            cidrs = [e['Cidr'] for e in entries]
            first = cidrs[0] if cidrs else ""
            suffix = f" (+{len(cidrs) - 1})" if len(cidrs) > 1 else ""
            print_row(idx=idx,
                      region=prefix.region_id,
                      id=prefix.prefix_list_id,
                      ctime=prefix.creation_time,
                      addrs=f"{first}{suffix}",
                      name=prefix.prefix_list_name)
            for extra in cidrs[1:]:
                print_row(addrs=extra)
            if idx != len(items):
                print_separator()

        return any_error

    def _ensure_prefix_list(self, region_id: str) -> Optional[PrefixList]:
        """高效查找或创建指定 region 的 prefix list，仅查目标 region，避免全局遍历。"""
        # 优先用缓存
        if self._prefix_list is not None:
            for pl in self._prefix_list:
                if pl.region_id == region_id:
                    self.current_prefix_list = pl
                    logging.info("[prefix] Reusing prefix list %s in %s", pl.prefix_list_id, region_id)
                    echo_progress(f"已有前缀列表 {pl.prefix_list_id}，直接更新本地公网IP")
                    return pl

        # 只查目标 region
        found = []
        for entry in self._fetch_prefix_lists(region_id):
            if entry['PrefixListName'].startswith(RESOURCE_NAME_PREFIX):
                found.append(PrefixList(entry['PrefixListId'], region_id, entry.get('CreationTime'), entry.get('PrefixListName')))
        if found:
            # 更新缓存
            if self._prefix_list is None:
                self._prefix_list = []
            self._prefix_list.extend([pl for pl in found if pl not in self._prefix_list])
            self.current_prefix_list = found[0]
            logging.info("[prefix] Reusing prefix list %s in %s", found[0].prefix_list_id, region_id)
            echo_progress(f"已有前缀列表 {found[0].prefix_list_id}，直接更新本地公网IP")
            return found[0]

        # 没有则创建
        self.current_prefix_list = self._create_prefix_list(region_id)
        if self.current_prefix_list:
            if self._prefix_list is None:
                self._prefix_list = []
            self._prefix_list.append(self.current_prefix_list)
            logging.info("[prefix] Created prefix list %s in %s", self.current_prefix_list.prefix_list_id, region_id)
            return self.current_prefix_list

        logging.error('Failed to find or create a prefix list with name prefix "%s" in %s', RESOURCE_NAME_PREFIX, region_id)
        return None

    def _create_prefix_list(self, region_id: str, prefix_name: str = RESOURCE_NAME_PREFIX) -> Optional[PrefixList]:
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
        echo_start(f"创建前缀列表, 名字为：{prefix_list_name}")
        client: Ecs20140526Client = ClientFactory.create_client(region_id)
        create_prefix_list_request = ecs_20140526_models.CreatePrefixListRequest(
            region_id=region_id,
            prefix_list_name=prefix_list_name,
            description=description,
            max_entries=DEFAULT_MAX_ENTRIES,
            address_family='IPv4'
        )
        runtime = _runtime(settings.proxy_port is not None)
        resp = _ecs_api_call(
            lambda: client.create_prefix_list_with_options(create_prefix_list_request, runtime),
            "creating prefix list",
        )
        if resp is None:
            return None
        ret_data = resp.body.to_map()
        logging.debug(json.dumps(ret_data))
        if "PrefixListId" in ret_data:
            echo_progress(f"前缀列表 {ret_data['PrefixListId']} 已创建")
            return PrefixList(ret_data["PrefixListId"], region_id)
        return None

    def _update_prefix_list(self) -> List[str]:
        """Retrieve the current client IP list, validate and deduplicate the entries, then append them to the prefix list.

        Returns:
            A list of updated IPs on success; empty list if prerequisites are missing or the API call fails.
        """
        if not self.current_prefix_list:
            logging.error("[prefix] Prefix list ID or region ID is not initialized")
            return []

        client_ip_list = retrieve_unique_ip_addresses()
        client_ip_list = self._normalize_ip_list(client_ip_list)

        if self._modify_one_prefix_list(self.current_prefix_list.region_id, self.current_prefix_list.prefix_list_id, client_ip_list):
            logging.info("[prefix] Prefix list %s updated successfully with %d IP(s)", self.current_prefix_list.prefix_list_id, len(client_ip_list))
            echo_success(f"前缀列表 {self.current_prefix_list.prefix_list_id} 已更新 -> {client_ip_list}")
            return client_ip_list

        logging.error("[prefix] Failed to update prefix list %s with client IPs", self.current_prefix_list.prefix_list_id)
        echo_fail(f"前缀列表 {self.current_prefix_list.prefix_list_id} 更新失败（请检查网络或前缀列表状态）")
        return []

    def _modify_one_prefix_list(self, region_id: str, prefix_list_id: str, ip_list: List[str]) -> bool:
        """Send a ModifyPrefixList request for a single prefix list.

        Returns:
            True on success; False on failure.
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id)
        request = ecs_20140526_models.ModifyPrefixListRequest(
            region_id=region_id,
            prefix_list_id=prefix_list_id,
            add_entry=[ecs_20140526_models.ModifyPrefixListRequestAddEntry(
                cidr=ip,
                description=f"EasyWhitelist@{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ) for ip in ip_list]
        )
        runtime = _runtime(settings.proxy_port is not None)
        resp = _ecs_api_call(
            lambda: client.modify_prefix_list_with_options(request, runtime),
            "modifying prefix list",
        )
        if resp is not None:
            logging.debug(json.dumps(resp.body.to_map()))
            return True
        return False

    def _print_prefix_operation(self, title: str, rows: List[Dict[str, str]]) -> None:
        """Print a compact table for prefix operation results."""
        print_header(title)
        for i, row in enumerate(rows, start=1):
            print_row(
                idx=i,
                region=row.get("region", ""),
                id=row.get("id", ""),
                ctime=row.get("status", ""),
                addrs=row.get("info", ""),
                name=row.get("name", ""),
            )
        print_tail()

    def _fetch_prefix_lists(self, region_id: str) -> List[Dict[str, Any]]:
        """Call the ECS DescribePrefixLists API to list all prefix lists in the given region.
        Iterates all pages via NextToken / MaxResults and returns a flat list.

        Args:
            region_id: The Alibaba Cloud region to query.

        Returns:
            A list of prefix list dicts; empty list on network or API error.
        """
        client: Ecs20140526Client = ClientFactory.create_client(region_id)
        logging.debug("[prefix] Retrieving prefix lists in region %s...", region_id)
        runtime = _runtime(settings.proxy_port is not None)
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
                logging.debug("[prefix] API response, detail=%s", json.dumps(body_map))
                page_entries = (body_map.get("PrefixLists") or {}).get("PrefixList") or []
                all_entries.extend(page_entries)
                next_token = body_map.get("NextToken") or None
                if not next_token:
                    break
            logging.debug("[prefix] Retrieved  prefix list(s) in region %s: %s", region_id, all_entries)
            return all_entries
        except Exception as err:
            logging.error("[prefix] Failed to describe prefix lists in region %s, err=%s", region_id, err)
            return []

    def _discover_prefix_list(self, prefix_name: str = RESOURCE_NAME_PREFIX) -> List[PrefixList]:
        """Iterate over all regions in self.regions to find a prefix list whose name starts with prefix_name.

        Args:
            prefix_name: Name prefix to match against prefix list names; defaults to RESOURCE_NAME_PREFIX.

        Returns:
            A list of PrefixList objects if found; empty list if not found.
        """
        logging.info("[prefix] Searching for a prefix list across all regions, prefix_name=%s", prefix_name)
        prefix_list: List[PrefixList] = []

        def _search_region(region_id: str) -> List[PrefixList]:
            logging.debug("[prefix] Searching in region %s", region_id)
            found: List[PrefixList] = []
            for entry in self._fetch_prefix_lists(region_id):
                logging.debug(entry)
                if entry['PrefixListName'].startswith(prefix_name):
                    logging.info("[prefix] Found prefix list: name=%s, id=%s", entry['PrefixListName'], entry['PrefixListId'])
                    found.append(PrefixList(entry['PrefixListId'], region_id, entry['CreationTime'], entry['PrefixListName']))
            return found

        def _search_region_safe(region_id: str) -> List[PrefixList]:
            try:
                return _search_region(region_id)
            except Exception as err:
                logging.error("[prefix] Error searching prefix list in region %s, err=%s", region_id, err)
                return []

        with ThreadPoolExecutor(max_workers=min(DEFAULT_CONCURRENT_WORKERS, len(self.regions.regions_list) or 1)) as executor:
            logging.info("[prefix] Submitting search tasks for (%d), total %d regions ...",
                         min(DEFAULT_CONCURRENT_WORKERS, len(self.regions.regions_list) or 1), len(self.regions.regions_list))
            futures = {executor.submit(_search_region_safe, e['RegionId']): e['RegionId'] for e in self.regions.regions_list}
            with tqdm(
                total=len(futures),
                desc="\U0001f504 [\u8fdb\u884c\u4e2d]  Searching prefix lists",
                unit='region',
                ncols=84,
                mininterval=0.3,
                maxinterval=1.0,
                ascii=True,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            ) as pbar:
                for future in as_completed(futures):
                    region_id = futures[future]
                    try:
                        result = future.result()
                        logging.debug("[prefix] Completed search in region %s, found %d matching prefix list(s)", region_id, len(result))
                        prefix_list.extend(result)
                    except Exception:
                        logging.exception("[prefix] Error searching prefix list in region %s", region_id)
                    finally:
                        pbar.update(1)

        logging.info(
            "[prefix] Completed searching for prefix lists. Found %d matching prefix list(s) across %d regions.",
            len(prefix_list), len(self.regions.regions_list))
        return prefix_list

    def _normalize_ip_list(self, ip_list: List[str]) -> List[str]:
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
                logging.warning("[prefix] Invalid IP/CIDR skipped: %s", s)
                continue
            if cidr in seen:
                continue
            seen.add(cidr)
            normalized.append(cidr)

            # 记录到 SQLite，用于后续分析
            if self.regions.conn:
                try:
                    upsert_ip_address(self.regions.conn, s, cidr, "aliyun")
                except Exception as e:
                    logging.warning("[db] Failed to record normalized IP %s: %s", cidr, e)

            if len(normalized) >= DEFAULT_MAX_ENTRIES:
                logging.warning("[prefix] Truncating IP list to %d entries (DEFAULT_MAX_ENTRIES)", DEFAULT_MAX_ENTRIES)
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
        client: Ecs20140526Client = ClientFactory.create_client(region_id)
        logging.info("[prefix] Fetching prefix list details for prefix_list_id=%s in region %s", prefix_list_id, region_id)
        runtime = _runtime(settings.proxy_port is not None)
        try:
            describe_req = ecs_20140526_models.DescribePrefixListAttributesRequest(
                region_id=region_id,
                prefix_list_id=prefix_list_id,
            )
            describe_resp = client.describe_prefix_list_attributes_with_options(describe_req, runtime)  # type: ignore
            current_entries = describe_resp.body.to_map().get('Entries', {}).get('Entry', []) or []
            logging.debug("[prefix] Prefix list entries: %s", current_entries)
        except Exception:
            logging.exception("[prefix] Failed to describe prefix list attributes for %s", prefix_list_id)
            return None
        return current_entries

    # def _auto_search_prefix_by_name(self, prefix_name: str = RESOURCE_NAME_PREFIX) -> Optional[str]:
    #     '''Search for a prefix list by name prefix. Returns the prefix list ID if found, or None if not found.'''
    #     logging.info("[prefix] Search prefix list, region=%s, prefix_name=%s ", self.region, prefix_name)
    #     prefix_lists = self.get_prefix_list(self.client)
    #     logging.debug(prefix_lists)
    #     if prefix_lists and 'PrefixLists' in prefix_lists and 'PrefixList' in prefix_lists['PrefixLists']:
    #         for prefix in prefix_lists['PrefixLists']['PrefixList']:  # type: ignore
    #             logging.debug(prefix)
    #             if prefix['PrefixListName'].startswith(prefix_name):
    #                 logging.info("[prefix] Found prefix list, name=%s id=%s", prefix['PrefixListName'], prefix['PrefixListId'])
    #                 return prefix["PrefixListId"]
    #     return None
