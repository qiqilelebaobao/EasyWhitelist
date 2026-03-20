import requests
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from typing import List

from ..util.defaults import _IGNORE_SSL, DEFAULT_CONCURRENT_WORKERS
from . import utils


def get_ip_list(proxy_port=None):

    client_ip_list: List[str] = _get_local_ips(proxy_port)
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


def _get_local_ip_from_url_and_parse(u, patt, ag, if_enable, proxy_port=None):
    # 发送GET请求
    headers = {"user-agent": ag}

    if if_enable.strip().lower() != "enable":
        return None

    try:
        logging.info("[ip.detect] fetching local IP, url=%s proxy_port=%s", u, proxy_port if proxy_port else "n/a")

        if proxy_port:
            response = requests.get(u, headers=headers, timeout=(3, 5),
                                    proxies={"http": f"http://127.0.0.1:{proxy_port}", "https": f"http://127.0.0.1:{proxy_port}"},
                                    verify=not _IGNORE_SSL)
        else:
            response = requests.get(u, headers=headers, timeout=(3, 5))

        # 获取响应内容
        respon = response.text
        l_ip = utils.parse_ip_from_response(respon, patt)
        logging.info("[ip.detect] fetched local IP, url=%s ip=%s", u, l_ip)
        return l_ip

    except Exception as e:
        logging.error("[ip.detect] parse failed, reason=exception, detail=%s", e)
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


def _get_local_ips(proxy_port=None):
    ip_list = []
    with ThreadPoolExecutor(max_workers=min(DEFAULT_CONCURRENT_WORKERS, len(utils.detect_url))) as executor:
        future_to_url = {
            executor.submit(_get_local_ip_from_url_and_parse, u[0], u[1], u[2], u[3], proxy_port): u for u in utils.detect_url
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                l_ip = future.result()
                if l_ip and _validate_ip(l_ip):
                    ip_list.append(l_ip)
            except Exception as e:
                logging.error("[ip.detect] parse failed, reason=exception, url=%s detail=%s", url, e)
    logging.info("[ip.detect] detected local IP list: %s", ip_list)
    return ip_list
