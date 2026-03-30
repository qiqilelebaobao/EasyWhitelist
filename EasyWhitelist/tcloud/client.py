import logging

from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.common_client import CommonClient

DEFAULT_REGION = "ap-guangzhou"


def get_common_client(region, proxy_port=None) -> CommonClient:
    # cred = credential.Credential(
    #     os.environ.get("TENCENTCLOUD_SECRET_ID"),
    #     os.environ.get("TENCENTCLOUD_SECRET_KEY"))

    if region is None:
        region = DEFAULT_REGION
        logging.info("[config] Region not set; falling back to %s", region)

    cred = credential.DefaultCredentialProvider().get_credential()

    http_profile = HttpProfile()
    http_profile.endpoint = "vpc.tencentcloudapi.com"
    http_profile.proxy = f"127.0.0.1:{proxy_port}" if proxy_port is not None else None

    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    # clientProfile.signMethod = "HmacSHA256"

    common_client = CommonClient(
        "vpc", "2017-03-12", cred, region, profile=client_profile)

    return common_client
