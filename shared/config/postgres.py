"""PostgreSQL 连接配置（Web / CLI 共用，WSL 本机实例）"""

import os


class PostgresConfig:
    """PostgreSQL 连接参数（应用账号，连业务库 ssaiyan）"""

    PG_HOST = os.environ.get('SSJ_PG_HOST', '127.0.0.1')
    PG_PORT = int(os.environ.get('SSJ_PG_PORT', '5432'))
    PG_USER = os.environ.get('SSJ_PG_USER', 'ssaiyan')
    PG_PASSWORD = os.environ.get('SSJ_PG_PASSWORD', 'ssaiyan')
    PG_DATABASE = os.environ.get('SSJ_PG_DATABASE', 'ssaiyan')

    POOL_SIZE = int(os.environ.get('SSJ_PG_POOL_SIZE', '5'))
