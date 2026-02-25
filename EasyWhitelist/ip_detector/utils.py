import re
import random

safari_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"]
chrome_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"]
edge_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"]
curl_user_agent = ["curl/8.6.0", "curl/7.29.0"]

IFCONFIG_ME_PATTERN = r"(.+)"
CIP_CC_PATTERN = r"URL\s+?:\s+?http://www.cip.cc/(.+)"
TOOL_LU_PATTERN = r"<p>你的外网IP地址是：\s*?(.+)</p>"
IP_SB_PATTERN = r"(.+)"


def parse_ip_from_response(response, patt):
    if result := re.search(patt, response):
        return result.group(1)


detect_url = [
    ["https://ifconfig.me", IFCONFIG_ME_PATTERN,
        random.choice(curl_user_agent), "enable"],
    ["http://cip.cc", CIP_CC_PATTERN,
        random.choice(chrome_user_agent), "DISABLE"],
    ["https://tool.lu/ip/", TOOL_LU_PATTERN,
        random.choice(chrome_user_agent), "enable"],
    ["http://ip.sb/", IP_SB_PATTERN, random.choice(curl_user_agent), "enable"]
]
