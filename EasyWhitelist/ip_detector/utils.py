import re
import random

# keep
safari_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"]
chrome_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"]
edge_user_agent = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"]
curl_user_agent = ["curl/8.6.0", "curl/7.29.0", "curl/8.7.1"]

# 使用更具体的 IP 正则，避免匹配到错误页等非 IP 内容
IFCONFIG_ME_PATTERN = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
CIP_CC_PATTERN = r"URL\s+?:\s+?http://www\.cip\.cc/(.+)"
TOOL_LU_PATTERN = r"<p>你的外网IP地址是：\s*?(.+)</p>"
IP_SB_PATTERN = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"


def parse_ip_from_response(response, patt):
    if result := re.search(patt, response):
        return result.group(1)


# keep
detect_url = [
    ["https://ifconfig.me", IFCONFIG_ME_PATTERN,
        random.choice(curl_user_agent), "enable"],
    ["http://cip.cc", CIP_CC_PATTERN,
        random.choice(chrome_user_agent), "DISABLE"],
    ["https://tool.lu/ip/", TOOL_LU_PATTERN,
        random.choice(chrome_user_agent), "enable"],
    ["http://ip.sb/", IP_SB_PATTERN, random.choice(curl_user_agent), "enable"]
]
