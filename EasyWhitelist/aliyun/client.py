import os
import logging
from typing import Optional

from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi.models import Config
from .defaults import DEFAULT_REGION


class ClientFactory:
    # Endpoint 根据 region 动态派生，格式为 'ecs.<region>.aliyuncs.com'。
    # 可通过环境变量 ALIBABA_CLOUD_ENDPOINT 覆盖（用于私有化部署或测试）。
    @staticmethod
    def create_client(region: str = DEFAULT_REGION, proxy: Optional[int] = None) -> Ecs20140526Client:
        endpoint = os.getenv('ALIBABA_CLOUD_ENDPOINT') or f"ecs.{region}.aliyuncs.com"

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

        if proxy:
            config = Config(
                access_key_id=access_key_id,  # type: ignore
                access_key_secret=access_key_secret,  # type: ignore
                endpoint=endpoint,
                http_proxy=f"http://127.0.0.1:{proxy}",
            )
        else:
            config = Config(
                access_key_id=access_key_id,  # type: ignore
                access_key_secret=access_key_secret,  # type: ignore
                endpoint=endpoint,
            )

        return Ecs20140526Client(config)
