import os

# ---------- 常量 ----------
TEMPLATE_NAME_PREFIX = "Terminal-IPs-"
TEMPLATE_ID_PREFIX = "ipm-"

DEFAULT_CONCURRENT_WORKERS = 32

# Evaluated once at import time so the env-var is not re-read on every API call.
_IGNORE_SSL: bool = os.getenv('DISABLE_SSL_VERIFY') == '1'
