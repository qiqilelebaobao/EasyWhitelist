import os
import warnings
from typing import Optional

import certifi
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi.utils_models import Config

# Tracks proxy hosts for which InsecureRequestWarning has already been suppressed,
# preventing duplicate filter entries when create_client() is called repeatedly.
_suppressed_warning_hosts: set = set()


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

            # Suppress InsecureRequestWarning for localhost proxy connections.
            # The SDK uses `requests` internally, which bundles its own urllib3 at
            # requests.packages.urllib3 — a separate instance from the standalone urllib3
            # package.  urllib3.disable_warnings() only silences the standalone instance;
            # matching on the warning message text via warnings.filterwarnings works for
            # both instances regardless of how the warning was emitted.
            if proxy_host in ("localhost", "127.0.0.1", "::1") and proxy_host not in _suppressed_warning_hosts:
                warnings.filterwarnings(
                    "ignore",
                    message="Unverified HTTPS request",
                )
                _suppressed_warning_hosts.add(proxy_host)

        return Ecs20140526Client(Config(**config_kwargs))
