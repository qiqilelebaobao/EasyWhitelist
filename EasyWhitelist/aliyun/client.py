import os
import warnings
import certifi
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi.utils_models import Config

from ..config.settings import IGNORE_SSL
from ..config import settings

# The Tea SDK embeds certifi's CA into a custom _TLSAdapter ssl_context, so TLS
# verification is performed correctly. Older urllib3 releases, however, set
# `conn.is_verified = True` only when `ca_certs` is passed explicitly and cannot
# detect a CA loaded into a custom ssl_context. That can trigger spurious
# `InsecureRequestWarning`s despite a verified connection. Because we always
# pass `ca=certifi.where()`, it is safe to suppress that specific warning here.
if IGNORE_SSL:
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")


class ClientFactory:
    # The endpoint is derived dynamically from the region: 'ecs.<region>.aliyuncs.com'.
    # Override via the ALIBABA_CLOUD_ENDPOINT environment variable (for private deployments or testing).
    @staticmethod
    def create_client(
        region: str,
        proxy_host: str = "localhost",
    ) -> Ecs20140526Client:
        """Create an authenticated ECS client for the given region.

        Args:
            region: Alibaba Cloud region, e.g. 'cn-hangzhou'.
            proxy_host: Proxy hostname or IP address; defaults to 'localhost'.
        """
        if not region:
            raise ValueError("region must not be empty")

        if settings.proxy_port is not None and not (1 <= settings.proxy_port <= 65535):
            raise ValueError(f"Invalid proxy_port: {settings.proxy_port}. Must be between 1 and 65535.")

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

        if settings.proxy_port is not None:
            # Using http:// for the https_proxy value is intentional:
            # the client tunnels HTTPS through HTTP CONNECT rather than connecting to the proxy itself over HTTPS.
            proxy_url = f"http://{proxy_host}:{settings.proxy_port}"
            config_kwargs["http_proxy"] = proxy_url
            config_kwargs["https_proxy"] = proxy_url

        return Ecs20140526Client(Config(**config_kwargs))
