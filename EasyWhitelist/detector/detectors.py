import requests
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from typing import List

from ..util.defaults import DEFAULT_CONCURRENT_WORKERS
from . import utils
from ..config import settings


def retrieve_unique_ip_addresses():

    client_ip_list: List[str] = _get_local_ips()
    # 用 dict.fromkeys 去重，同时保留顺序（set() 会破坏顺序）
    client_ip_list = list(dict.fromkeys(client_ip_list))

    return client_ip_list


def print_ip_list(ip_list):
    number = 100
    print(f"{'Detected Local IP List':=^{number}}\n"
          f"{'#':<38}IP Address\n"
          f"{'-' * number}"
          )

    for i, ip in enumerate(ip_list, 1):
        print(f"{str(i):<38}{ip}")

    print("-" * number)


def _get_local_ip_from_url_and_parse(source: utils.DetectSource):
    headers = {"user-agent": source.user_agent}

    if not source.enabled:
        return None

    try:
        logging.debug("[ip.detect] Fetching local IP from %s (proxy_port=%s)", source.url, settings.ctx.proxy_port if settings.ctx.proxy_port else "n/a")

        if settings.ctx.proxy_port:
            response = requests.get(source.url, headers=headers, timeout=(3, 5),
                                    proxies={"http": f"http://127.0.0.1:{settings.ctx.proxy_port}", "https": f"http://127.0.0.1:{settings.ctx.proxy_port}"},
                                    verify=not settings.ctx.ssl_bypass)
        else:
            response = requests.get(source.url, headers=headers, timeout=(3, 5))

        ip = utils.parse_ip_from_response(response.text, source.pattern)
        logging.info("[ip.detect] Fetched local IP from %s (ip=%s)", source.url, ip)
        return ip

    except Exception as e:
        logging.error("[ip.detect] Failed to parse response, error=%s", e)
        return None


def _validate_ip(l_ip):
    if not l_ip:
        return False

    # r"(?:(?:25[0-5]|2[0-4][0-9]|[1]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[1]?[0-9][0-9]?)"  # wip
    # r"(?:\d{1,3}\.){3}\d{1,3}"    # wip
    # r"((?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}(?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])" # wip
    # r"(?<![\.\d])(?:25[0-5]\.|2[0-4]\d\.|[01]?\d\d?\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?![\.\d])" # wip
    pat = r"((?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}(?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])"
    return bool(re.fullmatch(pat, l_ip))


def _get_local_ips():
    ip_list = []
    with ThreadPoolExecutor(max_workers=min(DEFAULT_CONCURRENT_WORKERS, len(utils.detect_url))) as executor:
        future_to_url = {
            executor.submit(_get_local_ip_from_url_and_parse, u): u for u in utils.detect_url
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                l_ip = future.result()
                if l_ip and _validate_ip(l_ip):
                    ip_list.append(l_ip)
            except Exception as e:
                logging.error("[ip.detect] Failed to parse response from %s, error=%s", url, e)
    logging.info("[ip.detect] Detected local IPs: \"%s\"", ", ".join(ip_list) if ip_list else "")
    return ip_list
