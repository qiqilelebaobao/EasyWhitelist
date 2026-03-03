import os
import logging

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

        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')

        missing = []
        if not access_key_id:
            missing.append('ALIBABA_CLOUD_ACCESS_KEY_ID')
        if not access_key_secret:
            missing.append('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        if missing:
            example = (
                "export ALIBABA_CLOUD_ACCESS_KEY_ID=your_id && export ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_secret"
            )
            msg = (
                f"Missing required environment variables for Alibaba Cloud SDK: {', '.join(missing)}. "
                f"Set them, for example: {example}"
            )
            logging.error(msg)
            raise RuntimeError(msg)

        config = Config(
            access_key_id=access_key_id,  # type: ignore
            access_key_secret=access_key_secret,  # type: ignore
            endpoint=endpoint,
        )

        return Ecs20140526Client(config)
