import os

_RST = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_CYAN = "\033[36m"

# ---------- 常量 ----------
# Prefix for prefix list names created by EasyWhitelist in Alibaba Cloud ECS.
TEMPLATE_NAME_PREFIX = "Terminal-IPs-"
# Prefix for internal resource IDs (template IDs) used when creating prefix lists.
TEMPLATE_ID_PREFIX = "ipm-"

# 默认并发请求数量（线程池大小），用于跨区域并行检索或更新操作。
DEFAULT_CONCURRENT_WORKERS = 32

# SSL 校验开关：当环境变量 DISABLE_SSL_VERIFY=1 时禁用 SSL 验证。
# 该变量仅在模块导入时读取一次，以避免每次调用都重新检查环境变量。
_IGNORE_SSL: bool = os.getenv('DISABLE_SSL_VERIFY') == '1'
