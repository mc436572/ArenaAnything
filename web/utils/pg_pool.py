"""PostgreSQL 异步连接池（asyncpg）"""

import logging

import asyncpg

from web.config.postgres import PostgresConfig

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

PG_POOL_MIN_SIZE = 2


async def init_pool():
    """创建进程级 PostgreSQL 连接池（在 FastAPI lifespan 启动时调用）"""
    global _pool
    if _pool is not None:
        return _pool

    _pool = await asyncpg.create_pool(
        host=PostgresConfig.PG_HOST,
        port=PostgresConfig.PG_PORT,
        user=PostgresConfig.PG_USER,
        password=PostgresConfig.PG_PASSWORD,
        database=PostgresConfig.PG_DATABASE,
        min_size=PG_POOL_MIN_SIZE,
        max_size=PostgresConfig.POOL_SIZE,
    )
    logger.info(
        'PostgreSQL pool created: %s:%s/%s (min=%s, max=%s)',
        PostgresConfig.PG_HOST,
        PostgresConfig.PG_PORT,
        PostgresConfig.PG_DATABASE,
        PG_POOL_MIN_SIZE,
        PostgresConfig.POOL_SIZE,
    )
    return _pool


async def close_pool():
    """关闭 PostgreSQL 连接池（在 FastAPI lifespan 退出时调用）"""
    global _pool
    if _pool is None:
        return

    await _pool.close()
    _pool = None
    logger.info('PostgreSQL pool closed')


def get_pool() -> asyncpg.Pool:
    """获取当前进程的 PostgreSQL 连接池"""
    if _pool is None:
        raise RuntimeError('PostgreSQL pool is not initialized')
    return _pool


async def verify_db_connection():
    """PostgreSQL 连通性自检（SELECT 1）"""
    pool = get_pool()
    async with pool.acquire() as conn:
        value = await conn.fetchval('SELECT 1')
    if value != 1:
        raise RuntimeError(f'PostgreSQL health check failed: SELECT 1 => {value}')
    logger.info('PostgreSQL health check passed: SELECT 1 ok')
