"""Default configuration values used by aliyun helpers.

Keep cloud-specific defaults here (region, vpc, endpoint, limits).
Do NOT store secrets or credentials in this file.
"""

import logging
from typing import Callable, Optional, TypeVar

from darabonba.runtime import RuntimeOptions
from Tea.exceptions import UnretryableException, TeaException
from ..util.nm import _IGNORE_SSL

T = TypeVar('T')

DEFAULT_REGION_1 = 'cn-hangzhou'
DEFAULT_REGION_2 = 'cn-chengdu'


# NOTE: DEFAULT_VPC_ID is a placeholder only; inject a real VPC ID via ALIBABA_CLOUD_VPC_ID env var in production.
DEFAULT_VPC_ID = ''
DEFAULT_MAX_ENTRIES = 20


def _runtime(use_proxy: bool = False) -> RuntimeOptions:
    """Return a RuntimeOptions instance; ignore_ssl is enabled when DISABLE_SSL_VERIFY=1 (local debugging only)."""
    return RuntimeOptions(ignore_ssl=_IGNORE_SSL and use_proxy)


def _ecs_api_call(fn: Callable[[], T], action: str, default: Optional[T] = None) -> Optional[T]:
    """Call *fn* and handle the common Tea SDK exception trio.

    Returns fn()'s result on success, or *default* on failure.
    """
    try:
        return fn()
    except UnretryableException:
        logging.exception("[aliyun] Network error when %s", action)
    except TeaException:
        logging.exception("[aliyun] Tea API error when %s", action)
    except Exception:
        logging.exception("[aliyun] Unexpected error when %s", action)
    return default
