import os
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    proxy_port: Optional[int] = None
    db_conn: Optional[sqlite3.Connection] = None
    # SSL 校验开关：当环境变量 DISABLE_SSL_VERIFY=1 时禁用 SSL 验证。
    # 该变量仅在模块导入时读取一次，以避免每次调用都重新检查环境变量。
    ssl_bypass: bool = field(default_factory=lambda: os.getenv('DISABLE_SSL_VERIFY') == '1')


# 全局单例，程序启动后在 _core.py 中初始化字段
ctx: Settings = Settings()
