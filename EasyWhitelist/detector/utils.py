import re
import random
from typing import NamedTuple

safari_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"]
chrome_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"]
edge_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"]
curl_user_agent = ["curl/8.6.0", "curl/7.29.0", "curl/8.7.1"]

# Use a more specific IP regex to avoid matching non-IP content such as error pages
_IP = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
IFCONFIG_ME_PATTERN = rf"({_IP})"
CIP_CC_PATTERN = rf"IP\s*:\s*({_IP})"
TOOL_LU_PATTERN = rf"<p>你的外网IP地址是\s*：\s*?({_IP})</p>"
IP_SB_PATTERN = rf"({_IP})"


class DetectSource(NamedTuple):
    url: str
    pattern: str
    user_agent: str
    enabled: bool


def parse_ip_from_response(response, patt):
    if result := re.search(patt, response):
        return result.group(1)
    return None


detect_url = [
    DetectSource("https://ifconfig.me", IFCONFIG_ME_PATTERN,
                 random.choice(curl_user_agent), True),
    DetectSource("https://cip.cc", CIP_CC_PATTERN,
                 random.choice(chrome_user_agent), True),
    DetectSource("https://tool.lu/ip/", TOOL_LU_PATTERN,
                 random.choice(chrome_user_agent), True),
    DetectSource("http://ip.sb/", IP_SB_PATTERN, random.choice(curl_user_agent), True)
]
