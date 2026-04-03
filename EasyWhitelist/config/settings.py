import os
import sqlite3
from typing import Optional

proxy_port: Optional[int] = None
db_conn: Optional[sqlite3.Connection] = None

# SSL 校验开关：当环境变量 DISABLE_SSL_VERIFY=1 时禁用 SSL 验证。
# 该变量仅在模块导入时读取一次，以避免每次调用都重新检查环境变量。
_IGNORE_SSL: bool = os.getenv('DISABLE_SSL_VERIFY') == '1'
