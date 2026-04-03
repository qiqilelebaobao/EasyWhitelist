
_RST = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_CYAN = "\033[36m"

# ---------- 常量 ----------
# Prefix for resource names (prefix lists / address templates) created by EasyWhitelist.
RESOURCE_NAME_PREFIX = "ClientIPs-"
# Prefix for internal resource IDs (template IDs) used when creating prefix lists.
TEMPLATE_ID_PREFIX = "ipm-"

# 默认并发请求数量（线程池大小），用于跨区域并行检索或更新操作。
DEFAULT_CONCURRENT_WORKERS = 32
