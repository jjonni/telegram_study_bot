import logging

from urllib.parse import quote
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from config.config import Config, load_config

config: Config = load_config()

logger = logging.getLogger(__name__)

def build_psql_conn_info(
                name: str,
                host: str,
                port: int,
                user: str,
                password: str) -> str:
    safe_user = quote(user, safe='')
    safe_password = quote(password, safe='')

    conn_info = f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{name}"

    logger.debug(
        "PostgreSQL connection built: postgresql://%s@%s:%s/%s",
        safe_user, host, port, name
    )

    return conn_info

async def log_db_version(connection: AsyncConnection) -> None:
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT version();")
            db_version = await cursor.fetchone()

            if db_version:
                logger.info("PostgreSQL version detected: %s", db_version[0])
            else:
                logger.warning("Database version query returned no result")
    except Exception:
        logger.exception("Could not get database version")

async def get_psql_connection(
                name: str     = config.db.name,
                host: str     = config.db.host,
                port: int     = config.db.port,
                user: str     = config.db.user,
                password: str = config.db.password) -> AsyncConnection:
    conn_info = build_psql_conn_info(name, host, port, user, password)
    connection: AsyncConnection | None = None

    try:
        connection = await AsyncConnection.connect(conn_info)
        await log_db_version(connection)

        return connection
    except Exception:
        logger.exception("PostgreSQL connection failed")

        try:
            if connection and not connection.closed:
                await connection.close()
        except Exception:
            logger.exception("Error while closing failed connection")
        raise

async def get_psql_pool(
                name: str = config.db.name,
                host: str = config.db.host,
                port: int = config.db.port,
                user: str = config.db.user,
                password: str = config.db.password,
                min_size: int = 1,
                max_size: int = 10,
                timeout: float | None = 10.0) -> AsyncConnectionPool:
    if min_size < 1:
        raise ValueError("min_size must be >= 1")
    if max_size < min_size:
        raise ValueError("max_size must be >= min_size")

    conn_info = build_psql_conn_info(name, host, port, user, password)
    pool: AsyncConnectionPool | None = None

    try:
        pool = AsyncConnectionPool(conninfo=conn_info, min_size=min_size, max_size=max_size, timeout=timeout, open=False)

        await pool.open()

        async with pool.connection() as connection:
            await log_db_version(connection)

        return pool
    except Exception:
        logger.exception("PosgreSQL pool initialization failed")

        try:
            if pool and not pool.closed:
                await pool.close()
        except Exception:
            logger.exception("Error while closing failed pool")
        raise
