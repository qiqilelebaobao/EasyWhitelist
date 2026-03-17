import os
import warnings
from typing import Optional

import certifi
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi.utils_models import Config

from .defaults import _IGNORE_SSL

# Tea SDK bundles certifi's CA into a custom _TLSAdapter ssl_context, so TLS
# verification IS happening correctly.  However, older urllib3 versions only set
# conn.is_verified=True when ca_certs is passed explicitly; they cannot inspect
# the CA loaded into a custom ssl_context and therefore always emit
# InsecureRequestWarning even though the connection IS verified.  Suppress it
# unconditionally here — this is safe because ca=certifi.where() is always set.
if _IGNORE_SSL:
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")


class ClientFactory:
    # The endpoint is derived dynamically from the region: 'ecs.<region>.aliyuncs.com'.
    # Override via the ALIBABA_CLOUD_ENDPOINT environment variable (for private deployments or testing).
    @staticmethod
    def create_client(
        region: str,
        proxy_port: Optional[int] = None,
        proxy_host: str = "localhost",
    ) -> Ecs20140526Client:
        """
        :param region: Alibaba Cloud region, e.g. 'cn-hangzhou'
        :param proxy_port: Proxy port (1–65535); None if no proxy is used
        :param proxy_host: Proxy hostname or IP address; defaults to 'localhost'
        """
        if not region:
            raise ValueError("region must not be empty")

        if proxy_port is not None and not (1 <= proxy_port <= 65535):
            raise ValueError(f"Invalid proxy_port: {proxy_port}. Must be between 1 and 65535.")

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
            ca=certifi.where()
        )

        if proxy_port is not None:
            # Using http:// for the https_proxy value is intentional:
            # the client tunnels HTTPS through HTTP CONNECT rather than connecting to the proxy itself over HTTPS.
            proxy_url = f"http://{proxy_host}:{proxy_port}"
            config_kwargs["http_proxy"] = proxy_url
            config_kwargs["https_proxy"] = proxy_url

        return Ecs20140526Client(Config(**config_kwargs))
