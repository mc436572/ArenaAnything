"""PostgreSQL 空库 bootstrap（Web / scripts 共用）。"""

from __future__ import annotations

import logging
import os

import psycopg
from psycopg import sql

from shared.config.postgres import PostgresConfig

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USER = 'postgres'


def _admin_dsn() -> str:
    user = os.environ.get('SSJ_PG_ADMIN_USER', DEFAULT_ADMIN_USER)
    password = os.environ.get('SSJ_PG_ADMIN_PASSWORD', '')
    if not password:
        password = os.environ.get('PG_PASSWORD', 'abc54321')
    host = os.environ.get('SSJ_PG_HOST', PostgresConfig.PG_HOST)
    port = os.environ.get('SSJ_PG_PORT', str(PostgresConfig.PG_PORT))
    return (
        f'host={host} port={port} dbname=postgres user={user} '
        f'password={password}'
    )


def _role_exists(conn: psycopg.Connection, role: str) -> bool:
    row = conn.execute(
        'SELECT 1 FROM pg_roles WHERE rolname = %s',
        (role,),
    ).fetchone()
    return row is not None


def _database_exists(conn: psycopg.Connection, dbname: str) -> bool:
    row = conn.execute(
        'SELECT 1 FROM pg_database WHERE datname = %s',
        (dbname,),
    ).fetchone()
    return row is not None


def ensure_role_and_database(
    *,
    app_user: str,
    app_password: str,
    database: str,
    dry_run: bool = False,
) -> None:
    dsn = _admin_dsn()
    logger.info('Connecting as admin to postgres (host=%s)', PostgresConfig.PG_HOST)

    with psycopg.connect(dsn, autocommit=True) as conn:
        if _role_exists(conn, app_user):
            logger.info('Role %r already exists, skip CREATE ROLE', app_user)
        else:
            stmt = sql.SQL('CREATE ROLE {} WITH LOGIN PASSWORD {}').format(
                sql.Identifier(app_user),
                sql.Literal(app_password),
            )
            logger.info('Creating role %r', app_user)
            if not dry_run:
                conn.execute(stmt)

        if _database_exists(conn, database):
            logger.info('Database %r already exists, skip CREATE DATABASE', database)
        else:
            stmt = sql.SQL(
                'CREATE DATABASE {} WITH OWNER = {} ENCODING {} TEMPLATE template0'
            ).format(
                sql.Identifier(database),
                sql.Identifier(app_user),
                sql.Literal('UTF8'),
            )
            logger.info('Creating database %r owned by %r', database, app_user)
            if not dry_run:
                conn.execute(stmt)

        grant = sql.SQL('GRANT ALL PRIVILEGES ON DATABASE {} TO {}').format(
            sql.Identifier(database),
            sql.Identifier(app_user),
        )
        if not dry_run:
            conn.execute(grant)

    logger.info(
        'Done. App DSN: %s:%s/%s user=%s',
        PostgresConfig.PG_HOST,
        PostgresConfig.PG_PORT,
        database,
        app_user,
    )
