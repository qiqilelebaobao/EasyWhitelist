import os
from typing import Optional

from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi.models import Config


class ClientFactory:
    # Endpoint 根据 region 动态派生，格式为 'ecs.<region>.aliyuncs.com'。
    # 可通过环境变量 ALIBABA_CLOUD_ENDPOINT 覆盖（用于私有化部署或测试）。
    @staticmethod
    def create_client(region: str, proxy: Optional[str] = None) -> Ecs20140526Client:
        """
        :param proxy: 完整代理 URL，例如 'http://proxy.example.com:8080'
        """
        endpoint = os.getenv('ALIBABA_CLOUD_ENDPOINT') or f"ecs.{region}.aliyuncs.com"

        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')

        missing = []
        if not access_key_id:
            missing.append('ALIBABA_CLOUD_ACCESS_KEY_ID')
        if not access_key_secret:
            missing.append('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        if missing:
            raise RuntimeError(
                f"Missing required environment variables for Alibaba Cloud SDK: {', '.join(missing)}."
            )

        config_kwargs: dict = dict(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
        )
        if proxy:
            # https_proxy 同样使用 http:// 协议是正确的：
            # 代理客户端通过 HTTP CONNECT 隧道建立 HTTPS 连接，而非直连代理服务器用 HTTPS。
            config_kwargs["http_proxy"] = proxy
            config_kwargs["https_proxy"] = proxy

        return Ecs20140526Client(Config(**config_kwargs))
