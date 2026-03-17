"""Default configuration values used by aliyun helpers.

Keep cloud-specific defaults here (region, vpc, endpoint, limits).
Do NOT store secrets or credentials in this file.
"""

from darabonba.runtime import RuntimeOptions
from ..util.nm import _IGNORE_SSL

DEFAULT_REGION = 'cn-hangzhou'
# NOTE: DEFAULT_VPC_ID is a placeholder only; inject a real VPC ID via ALIBABA_CLOUD_VPC_ID env var in production.
DEFAULT_VPC_ID = ''
DEFAULT_MAX_ENTRIES = 20


def _runtime() -> RuntimeOptions:
    """Return a RuntimeOptions instance; ignore_ssl is enabled when DISABLE_SSL_VERIFY=1 (local debugging only)."""
    return RuntimeOptions(ignore_ssl=_IGNORE_SSL)
