import os

from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi.models import Config
from .defaults import DEFAULT_ENDPOINT


class ClientFactory:
    def __init__(self):
        pass

    # Endpoint to be set according to the region, for example, 'ecs.cn-hangzhou.aliyuncs.com' for Hangzhou region.
    @staticmethod
    def create_client() -> Ecs20140526Client:
        endpoint = os.getenv('ALIBABA_CLOUD_ENDPOINT', DEFAULT_ENDPOINT)
        config = Config(
            # 必填，请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID
            access_key_id=os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'],
            # 必填，请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_SECRET
            access_key_secret=os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'],
            endpoint=endpoint
        )
        return Ecs20140526Client(config)
