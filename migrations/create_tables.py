import asyncio
import logging

from psycopg import AsyncConnection, Error

from app.infrastructure.database.connection import get_psql_connection
from config.config import Config, load_config

config: Config = load_config()

logging.basicConfig(
    level=logging.getLevelName(level=config.log.level),
    format=config.log.format,
)

logger = logging.getLogger(__name__)

async def main():
    connection: AsyncConnection | None = None

    try:
        connection = await get_psql_connection()

        async with connection:
            async with connection.transaction():
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        query=
                            """
                                CREATE TABLE IF NOT EXISTS users(
                                    id SERIAL PRIMARY KEY,
                                    telegram_id BIGINT NOT NULL UNIQUE,
                                    username VARCHAR(40),
                                    name VARCHAR NOT NULL,
                                    surname VARCHAR NOT NULL,
                                    patronymic VARCHAR,
                                    role VARCHAR(20) NOT NULL
                                        CONSTRAINT role_check CHECK (role IN ('student', 'admin')),
                                    is_alive BOOLEAN NOT NULL DEFAULT TRUE,
                                    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
                                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                                );
                            """
                    )
                    await cursor.execute(
                        query=
                            """
                                CREATE TABLE IF NOT EXISTS files(
                                    id SERIAL PRIMARY KEY,
                                    type VARCHAR(20) NOT NULL
                                        CONSTRAINT type_check CHECK (type in ('lecture', 'lab', 'submission')),
                                    telegram_file_id VARCHAR NOT NULL,
                                    path VARCHAR
                                );
                            """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS lectures(
                                id SERIAL PRIMARY KEY,
                                name VARCHAR NOT NULL,
                                file_id INT NOT NULL REFERENCES files(id) ON DELETE RESTRICT
                            );
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS tests(
                                id SERIAL PRIMARY KEY,
                                name VARCHAR NOT NULL,
                                lecture_id INT REFERENCES lectures(id) ON DELETE CASCADE
                            );
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS questions(
                                id SERIAL PRIMARY KEY,
                                test_id INT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                                text VARCHAR NOT NULL,
                                max_points INT
                                    CONSTRAINT max_points_positive CHECK (max_points IS NULL OR max_points > 0)
                            );
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS answers(
                                id SERIAL PRIMARY KEY,
                                question_id INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                                text VARCHAR NOT NULL,
                                is_right BOOLEAN DEFAULT FALSE
                            );
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS lab_works(
                                id SERIAL PRIMARY KEY,
                                file_id INT NOT NULL REFERENCES files(id) ON DELETE RESTRICT,
                                name VARCHAR NOT NULL,
                                description VARCHAR,
                                deadline TIMESTAMPTZ,
                                allow_late BOOLEAN DEFAULT TRUE
                            );
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS test_stats(
                                id SERIAL PRIMARY KEY,
                                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                                test_id INT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                                last_score INT,
                                last_submission_time TIMESTAMPTZ,
                                attempts_count INT DEFAULT 0
                                    CONSTRAINT attempts_count_non_neg CHECK (attempts_count >= 0)
                            );
                            
                            CREATE UNIQUE INDEX IF NOT EXISTS idx_test_stats_user_test
                                ON test_stats (user_id, test_id);
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS submissions(
                                id SERIAL PRIMARY KEY,
                                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                                lab_id INT NOT NULL REFERENCES lab_works(id) ON DELETE CASCADE,
                                submission_file_id INT NOT NULL REFERENCES files(id) ON DELETE RESTRICT,
                                submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                is_late BOOLEAN DEFAULT FALSE,
                                status VARCHAR(20) NOT NULL
                                    CONSTRAINT status_check CHECK (status in ('uploaded', 'graded')) DEFAULT 'uploaded',
                                score INT
                                    CONSTRAINT score_non_neg CHECK (score IS NULL OR score >= 0)
                            );
                        """
                    )
                    await cursor.execute(
                        query=
                        """
                            CREATE TABLE IF NOT EXISTS access_requests(
                                id SERIAL PRIMARY KEY,
                                telegram_id BIGINT,
                                username VARCHAR(40),
                                name VARCHAR NOT NULL,
                                surname VARCHAR NOT NULL,
                                patronymic VARCHAR,
                                requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            
                                CONSTRAINT contact_required CHECK (telegram_id IS NOT NULL OR username IS NOT NULL)
                            );
                        """
                    )
                    logger.info("All tables were successfully created")
    except Error:
        logger.exception("Database-specific error during initialization")
    except Exception:
        logger.exception("Unhandled exception during initialization")
    finally:
        if connection and not connection.closed:
            await connection.close()
            logger.info("Connection successfully closed")

asyncio.run(main())