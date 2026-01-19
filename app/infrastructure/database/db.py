import logging
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from app.bot.enums.enums import UserRole, FileType, SubmissionStatus
from psycopg import AsyncConnection

logger = logging.getLogger(__name__)


async def add_user(
        connection: AsyncConnection,
        *,
        telegram_id: int,
        username: str | None = None,
        name: str,
        surname: str,
        patronymic: str | None = None,
        role: UserRole | str = UserRole.STUDENT ,
        is_alive: bool = True,
        is_banned: bool = False
) -> None:
    role_value = role.value if hasattr(role, "value") else str(role).strip()

    async with connection.cursor() as cursor:
        await cursor.execute(
            query=
                 """
                    INSERT INTO users(telegram_id, username, name, surname, patronymic, role, is_alive, is_banned)
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING;
                 """,
            params=(telegram_id, username, name, surname, patronymic, role_value, is_alive, is_banned)
        )

    logger.info(
        "New user added.\n "
        "Table=`%s`, telegram_id=%d, username=%s, name=%s, surname=%s, patronymic=%s, role=%s, is_alive=%s, is_banned=%s",
        "users", telegram_id, username, name, surname, patronymic, role, is_alive, is_banned
    )

async def get_users(
        connection: AsyncConnection,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        data = await cursor.execute(
            query="""
                SELECT id, telegram_id, username, name, surname, patronymic, role, is_alive, is_banned, created_at
                FROM users
                ORDER BY id;
            """
        )

        rows = await data.fetchall()

        if not rows:
            logger.warning("No users found in table 'users'")
            return None

        columns = [desc.name for desc in cursor.description]
        users = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched %d users from table 'users'", len(users))
        return users

async def get_user(
        connection: AsyncConnection,
        *,
        telegram_id: int
) -> dict | None:
    async with connection.cursor() as cursor:
        data = await cursor.execute(
            query=
                """
                    SELECT id, telegram_id, username, name, surname, patronymic, role, is_alive, is_banned, created_at
                    FROM users WHERE telegram_id = %s;
                """,
            params=(telegram_id,)
        )

        row = await data.fetchone()

        if row is None:
            logger.warning("User with telegram_id=%s not found", telegram_id)
            return None

        columns = [desc.name for desc in cursor.description]
        user_dict = dict(zip(columns, row))

        logger.info("Fetched user: %s", user_dict)
        return user_dict

async def get_user_banned_status_by_id(
        connection: AsyncConnection,
        *,
        telegram_id: int
) -> bool | None:
    async with connection.cursor() as cursor:
        data = await cursor.execute(
            query="SELECT is_banned FROM users WHERE telegram_id = %s;",
            params=(telegram_id,)
        )

        row = await data.fetchone()

    if row:
        logger.info("User with telegram_id %s banned status is %s", telegram_id, row[0])
    else:
        logger.warning("No user found with telegram_id %s", telegram_id)

    return row[0] if row else None

async def get_user_banned_status_by_username(
        connection: AsyncConnection,
        *,
        username: str
) -> bool | None:
    async with connection.cursor() as cursor:
        data = await cursor.execute(
            query="SELECT is_banned FROM users WHERE username = %s;",
            params=(username,)
        )

        row = await data.fetchone()

    if row:
        logger.info("User with username %s banned status is %s", username, row[0])
    else:
        logger.warning("No user found with username %s", username)

    return row[0] if row else None

async def get_user_role(
    conn: AsyncConnection,
    *,
    telegram_id: int,
) -> UserRole | None:
    async with conn.cursor() as cursor:
        data = await cursor.execute(
            query="""
                SELECT role FROM users WHERE telegram_id = %s;
            """,
            params=(telegram_id,),
        )
        row = await data.fetchone()

    if row:
        logger.info("User `telegram_id`=%s has role %s", telegram_id, row[0])
    else:
        logger.warning("User with telegram_id=%s not found", telegram_id)

    return UserRole(row[0]) if row else None

async def update_user(
        connection: AsyncConnection,
        *,
        telegram_id: int,
        username: str | None = None,
        name: str | None = None,
        surname: str | None = None,
        patronymic: str | None = None,
        role: UserRole | None = None,
        is_alive: bool = True,
        is_banned: bool = False
) -> None:
    fields = []
    params = []

    if username is not None:
        fields.append("username = %s")
        params.append(username)
    if name is not None:
        fields.append("name = %s")
        params.append(name)
    if surname is not None:
        fields.append("surname = %s")
        params.append(surname)
    if patronymic is not None:
        fields.append("patronymic = %s")
        params.append(patronymic)
    if role is not None:
        fields.append("role = %s")
        params.append(role)
    if is_alive is not None:
        fields.append("is_alive = %s")
        params.append(is_alive)
    if is_banned is not None:
        fields.append("is_banned = %s")
        params.append(is_banned)
    if not fields:
        logger.warning("No fields to update for telegram_id=%s", telegram_id)
        return

    query= f"""
        UPDATE users
        SET {', '.join(fields)}
        WHERE telegram_id = %s
    """

    params.append(telegram_id)

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("User %d updated: %s", telegram_id, ", ".join(fields))

async def update_user_by_user_name(
connection: AsyncConnection,
        *,
        username: str,
        name: str | None = None,
        surname: str | None = None,
        patronymic: str | None = None,
        role: UserRole | None = None,
        is_alive: bool = True,
        is_banned: bool = False
) -> None:
    fields = []
    params = []

    if name is not None:
        fields.append("name = %s")
        params.append(name)
    if surname is not None:
        fields.append("surname = %s")
        params.append(surname)
    if patronymic is not None:
        fields.append("patronymic = %s")
        params.append(patronymic)
    if role is not None:
        fields.append("role = %s")
        params.append(role)
    if is_alive is not None:
        fields.append("is_alive = %s")
        params.append(is_alive)
    if is_banned is not None:
        fields.append("is_banned = %s")
        params.append(is_banned)
    if not fields:
        logger.warning("No fields to update for username=%s", username)
        return

    query = f"""
            UPDATE users
            SET {', '.join(fields)}
            WHERE username = %s
        """

    params.append(username)

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("User %s updated: %s", username, ", ".join(fields))

async def ban_user(
        connection: AsyncConnection,
        *,
        telegram_id: int
) -> None:
    await update_user(connection, telegram_id=telegram_id, is_banned=True)

async def unban_user(
        connection: AsyncConnection,
        *,
        telegram_id: int
) -> None:
    await update_user(connection, telegram_id=telegram_id, is_banned=False)


async def add_file(
    connection: AsyncConnection,
    *,
    file_type: str,
    telegram_file_id: str,
    path: str | None = None,
) -> int | None:
    effective_path = path if path is not None else telegram_file_id

    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO files(type, telegram_file_id, path)
                VALUES (%s, %s, %s)
                RETURNING id;
            """,
            params=(file_type, telegram_file_id, effective_path),
        )
        row = await cursor.fetchone()

    file_id = row[0] if row else None
    logger.info(
        "New file record. Table=`%s`, id=%s, file_type=%s, telegram_file_id=%s, path=%s",
        "files", file_id, file_type, telegram_file_id, effective_path
    )
    return file_id

async def get_file(
        connection: AsyncConnection,
        *,
        telegram_file_id: str
) -> dict | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                SELECT id, type, telegram_file_id, path
                FROM files
                WHERE id = %s;
            """,
            params=(telegram_file_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            logger.warning("File with telegram_file_id=%s not found", telegram_file_id)
            return None

        columns = [desc.name for desc in cursor.description]
        file_dict = dict(zip(columns, row))

        logger.info("Fetched file: %s", file_dict)
        return file_dict


async def get_files_by_type(
        connection: AsyncConnection,
        *,
        file_type: str
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, type, telegram_file_id, path
            FROM files
            WHERE type = %s;
            """,
            (file_type,)
        )

        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No files found with type=%s", file_type)
            return None

        columns = [desc.name for desc in cursor.description]
        files = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched files: %s", files)
        return files


async def update_file(
        connection: AsyncConnection,
        *,
        file_id: int,
        file_type: str | None = None,
        telegram_file_id: str | None = None,
        path: str | None = None,
) -> None:
    fields = []
    params = []

    if file_type is not None:
        fields.append("type = %s")
        params.append(file_type)
    if telegram_file_id is not None:
        fields.append("telegram_file_id = %s")
        params.append(telegram_file_id)
    if path is not None:
        fields.append("path = %s")
        params.append(path)
    if not fields:
        logger.warning("No fields to update for file_id=%s", file_id)
        return

    query = f"""
            UPDATE files
            SET {', '.join(fields)}
            WHERE id = %s
        """

    params.append(file_id)

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("File %s updated: %s", file_id, ", ".join(fields))

async def delete_file(
        connection: AsyncConnection,
        *,
        file_id: int
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM files
                WHERE id = %s;
            """,
            params=(file_id,),
        )
    logger.info("Deleted file id=%s", file_id)


async def add_lecture_with_file(
    connection: AsyncConnection,
    *,
    lecture_name: str,
    telegram_file_id: str,
    file_name: str
) -> int | None:

    local_path = Path("media/lecture") /file_name

    file_id = await add_file(
        connection,
        file_type=FileType.LECTURE,
        telegram_file_id=telegram_file_id,
        path=str(local_path)
    )

    if not file_id:
        logger.error("Failed to add file for lecture: %s", lecture_name)
        return None

    lecture_id = await add_lecture(
        connection,
        name=lecture_name,
        file_id=file_id
    )

    if lecture_id:
        logger.info("Lecture with file added successfully: %s", lecture_name)
    else:
        logger.error("Failed to add lecture: %s", lecture_name)

    return lecture_id


async def add_lecture(
    connection: AsyncConnection,
    *,
    name: str,
    file_id: int,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO lectures(name, file_id)
                VALUES (%s, %s)
                RETURNING id;
            """,
            params=(name, file_id),
        )
        row = await cursor.fetchone()
    lecture_id = row[0] if row else None
    logger.info("New lecture added. Table=`%s`, id=%s, name=%s, file_id=%s", "lectures", lecture_id, name, file_id)

    return lecture_id

async def get_lectures_with_file_ids(connection: AsyncConnection) -> list[dict[str, Any]] | None:
    lectures = await get_lectures(connection)
    if not lectures:
        return None


    files = await get_files_by_type(connection, file_type="lecture") or []


    files_dict = {f["id"]: f for f in files}


    for lecture in lectures:
        file_id = lecture.get("file_id")
        lecture_file = files_dict.get(file_id)
        lecture["telegram_file_id"] = lecture_file["telegram_file_id"] if lecture_file else None

    return lectures

async def get_lectures(connection: AsyncConnection) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        data = await cursor.execute(
            query="""
                SELECT id, name, file_id
                FROM lectures
                ORDER BY id;
            """
        )

        rows = await data.fetchall()

        if not rows:
            logger.warning("No lectures found in table 'lectures'")
            return None

        columns = [desc.name for desc in cursor.description]
        lectures = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched %d lectures from table 'lectures'", len(lectures))
        return lectures

async def get_lecture(
    connection: AsyncConnection,
    *,
    lecture_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, name, file_id
            FROM lectures
            WHERE id = %s;
            """,
            (lecture_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No lecture found with id=%s", lecture_id)
            return None

        columns = [desc.name for desc in cursor.description]
        lecture = dict(zip(columns, row))

        logger.info("Fetched lecture: %s", lecture)
        return lecture

async def get_lectures_by_file(
    connection: AsyncConnection,
    *,
    file_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, name, file_id
            FROM lectures
            WHERE file_id = %s;
            """,
            (file_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No lectures found for file_id=%s", file_id)
            return None

        columns = [desc.name for desc in cursor.description]
        lectures = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched lectures: %s", lectures)
        return lectures

async def update_lecture_file(
    connection: AsyncConnection,
    *,
    lecture_id: int,
    telegram_file_id: str,
    file_type: str = "lecture",
) -> None:
    """
    Обновляет файл лекции: создаёт или обновляет запись в таблице files
    и обновляет ссылку на file_id в таблице lectures.
    """

    files = await get_files_by_type(connection, file_type=file_type)
    file_id = None

    if files:

        for f in files:
            if f.get("id") == lecture_id:
                file_id = f["id"]
                query = """
                    UPDATE files
                    SET telegram_file_id = %s
                    WHERE id = %s
                """
                async with connection.cursor() as cursor:
                    await cursor.execute(query, (telegram_file_id, file_id))
                break

    if file_id is None:

        query = """
            INSERT INTO files (type, telegram_file_id)
            VALUES (%s, %s)
            RETURNING id
        """
        async with connection.cursor() as cursor:
            await cursor.execute(query, (file_type, telegram_file_id))
            row = await cursor.fetchone()
            file_id = row[0]


    await update_lecture(connection, lecture_id=lecture_id, file_id=file_id)

async def update_lecture(
    connection: AsyncConnection,
    *,
    lecture_id: int,
    name: str | None = None,
    file_id: int | None = None,
) -> None:
    fields = []
    params = []
    if name is not None:
        fields.append("name = %s")
        params.append(name)
    if file_id is not None:
        fields.append("file_id = %s")
        params.append(file_id)
    if not fields:
        logger.warning("No fields to update for lecture_id=%s", lecture_id)
        return

    params.append(lecture_id)
    query = f"""
        UPDATE lectures
        SET {', '.join(fields)}
        WHERE id = %s
    """

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("Lecture %s updated: %s", lecture_id, ", ".join(fields))

async def delete_lecture(
    connection: AsyncConnection,
    *,
    lecture_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM lectures WHERE id = %s;
            """,
            params=(lecture_id,),
        )
    logger.info("Deleted lecture id=%s", lecture_id)



async def add_test(
    connection: AsyncConnection,
    *,
    name: str,
    lecture_id: int | None = None,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO tests(name, lecture_id)
                VALUES (%s, %s)
                RETURNING id;
            """,
            params=(name, lecture_id),
        )
        row = await cursor.fetchone()
    test_id = row[0] if row else None
    logger.info("New test added. Table=`%s`, id=%s, name=%s, lecture_id=%s", "tests", test_id, name, lecture_id)
    return test_id

async def get_test(
    connection: AsyncConnection,
    *,
    test_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, name, lecture_id
            FROM tests
            WHERE id = %s;
            """,
            (test_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No test found with test_id=%s", test_id)
            return None

        columns = [desc.name for desc in cursor.description]
        test = dict(zip(columns, row))

        logger.info("Fetched test: %s", test)
        return test

async def get_tests_by_lecture(
    connection: AsyncConnection,
    *,
    lecture_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, name, lecture_id
            FROM tests
            WHERE lecture_id = %s;
            """,
            (lecture_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No tests found for lecture_id=%s", lecture_id)
            return None

        columns = [desc.name for desc in cursor.description]
        tests = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched tests: %s", tests)
        return tests

async def update_test(
    connection: AsyncConnection,
    *,
    test_id: int,
    name: str | None = None,
    lecture_id: int | None = None,
) -> None:
    fields = []
    params = []
    if name is not None:
        fields.append("name = %s")
        params.append(name)
    if lecture_id is not None:
        fields.append("lecture_id = %s")
        params.append(lecture_id)
    if not fields:
        logger.warning("No fields to update for test_id=%s", test_id)
        return

    params.append(test_id)
    query = f"""
        UPDATE tests
        SET {', '.join(fields)}
        WHERE id = %s
    """

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("Test %s updated: %s", test_id, ", ".join(fields))

async def delete_test(
    connection: AsyncConnection,
    *,
    test_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM tests WHERE id = %s;
            """,
            params=(test_id,),
        )
    logger.info("Deleted test id=%s", test_id)



async def add_question(
    connection: AsyncConnection,
    *,
    test_id: int,
    text: str,
    max_points: int | None = None,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO questions(test_id, text, max_points)
                VALUES (%s, %s, %s)
                RETURNING id;
            """,
            params=(test_id, text, max_points),
        )
        row = await cursor.fetchone()
    question_id = row[0] if row else None
    logger.info("New question added. Table=`%s`, id=%s, test_id=%s", "questions", question_id, test_id)
    return question_id

async def get_question(
    connection: AsyncConnection,
    *,
    question_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, test_id, text, max_points
            FROM questions
            WHERE id = %s;
            """,
            (question_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No question found with question_id=%s", question_id)
            return None

        columns = [desc.name for desc in cursor.description]
        question = dict(zip(columns, row))

        logger.info("Fetched question: %s", question)
        return question

async def get_questions_by_test(
    connection: AsyncConnection,
    *,
    test_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, test_id, text, max_points
            FROM questions
            WHERE test_id = %s;
            """,
            (test_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No questions found for test_id=%s", test_id)
            return None

        columns = [desc.name for desc in cursor.description]
        questions = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched questions: %s", questions)
        return questions

async def update_question(
    connection: AsyncConnection,
    *,
    question_id: int,
    text: str | None = None,
    max_points: int | None = None,
) -> None:
    fields = []
    params = []
    if text is not None:
        fields.append("text = %s")
        params.append(text)
    if max_points is not None:
        fields.append("max_points = %s")
        params.append(max_points)
    if not fields:
        logger.warning("No fields to update for question_id=%s", question_id)
        return

    params.append(question_id)
    query = f"""
        UPDATE questions
        SET {', '.join(fields)}
        WHERE id = %s
    """

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("Question %s updated: %s", question_id, ", ".join(fields))

async def delete_question(
    connection: AsyncConnection,
    *,
    question_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM questions WHERE id = %s;
            """,
            params=(question_id,),
        )
    logger.info("Deleted question id=%s", question_id)



async def add_answer(
    connection: AsyncConnection,
    *,
    question_id: int,
    text: str,
    is_right: bool = False,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO answers(question_id, text, is_right)
                VALUES (%s, %s, %s)
                RETURNING id;
            """,
            params=(question_id, text, is_right),
        )
        row = await cursor.fetchone()
    answer_id = row[0] if row else None
    logger.info("New answer added. Table=`%s`, id=%s, question_id=%s", "answers", answer_id, question_id)
    return answer_id

async def get_answer(
    connection: AsyncConnection,
    *,
    answer_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, question_id, text, is_right
            FROM answers
            WHERE id = %s;
            """,
            (answer_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No answer found with answer_id=%s", answer_id)
            return None

        columns = [desc.name for desc in cursor.description]
        answer = dict(zip(columns, row))

        logger.info("Fetched answer: %s", answer)
        return answer

async def get_answers_by_question(
    connection: AsyncConnection,
    *,
    question_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, question_id, text, is_right
            FROM answers
            WHERE question_id = %s;
            """,
            (question_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No answers found for question_id=%s", question_id)
            return None

        columns = [desc.name for desc in cursor.description]
        answers = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched answers: %s", answers)
        return answers

async def update_answer(
    connection: AsyncConnection,
    *,
    answer_id: int,
    text: str | None = None,
    is_right: bool | None = None,
) -> None:
    fields = []
    params = []
    if text is not None:
        fields.append("text = %s")
        params.append(text)
    if is_right is not None:
        fields.append("is_right = %s")
        params.append(is_right)
    if not fields:
        logger.warning("No fields to update for answer_id=%s", answer_id)
        return

    params.append(answer_id)
    query = f"""
        UPDATE answers
        SET {', '.join(fields)}
        WHERE id = %s
    """

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("Answer %s updated: %s", answer_id, ", ".join(fields))

async def delete_answer(
    connection: AsyncConnection,
    *,
    answer_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM answers WHERE id = %s;
            """,
            params=(answer_id,),
        )
    logger.info("Deleted answer id=%s", answer_id)



async def add_lab_work(
    connection: AsyncConnection,
    *,
    file_id: int,
    name: str,
    description: str | None = None,
    deadline: datetime | None = None,
    allow_late: bool = True,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO lab_works(file_id, name, description, deadline, allow_late)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """,
            params=(file_id, name, description, deadline, allow_late),
        )
        row = await cursor.fetchone()
    lab_id = row[0] if row else None
    logger.info("New lab_work added. Table=`%s`, id=%s, name=%s", "lab_works", lab_id, name)
    return lab_id

async def get_lab_work(
    connection: AsyncConnection,
    *,
    lab_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, file_id, name, description, deadline, allow_late
            FROM lab_works
            WHERE id = %s;
            """,
            (lab_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No lab work found with id=%s", lab_id)
            return None

        columns = [desc.name for desc in cursor.description]
        lab_work = dict(zip(columns, row))
        logger.info("Fetched lab work: %s", lab_work)
        return lab_work


async def get_lab_works_by_file(
    connection: AsyncConnection,
    *,
    file_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, file_id, name, description, deadline, allow_late
            FROM lab_works
            WHERE file_id = %s;
            """,
            (file_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No lab works found for file_id=%s", file_id)
            return None

        columns = [desc.name for desc in cursor.description]
        lab_works = [dict(zip(columns, row)) for row in rows]
        logger.info("Fetched lab works: %s", lab_works)
        return lab_works

async def get_lab_works(connection: AsyncConnection) -> list[dict[str, Any]] | None:
    """
    Получить все лабораторные из таблицы lab_works.
    Возвращает список словарей или None, если записей нет.
    """
    async with connection.cursor() as cursor:
        data = await cursor.execute(
            query="""
                SELECT id, name, file_id, description, deadline, allow_late
                FROM lab_works
                ORDER BY id;
            """
        )

        rows = await data.fetchall()

        if not rows:
            logger.warning("No lab works found in table 'lab_works'")
            return None

        columns = [desc.name for desc in cursor.description]
        labs = [dict(zip(columns, row)) for row in rows]

        logger.info("Fetched %d lab works from table 'lab_works'", len(labs))
        return labs


async def get_lab_works_with_file_ids(connection: AsyncConnection) -> list[dict[str, Any]] | None:
    """
    Возвращает lab_works с подклеенным telegram_file_id (и path) из таблицы files.
    Если у лабораторной нет файла — telegram_file_id будет None.
    """
    labs = await get_lab_works(connection)
    if not labs:
        return None


    files = await get_files_by_type(connection, file_type="lab") or []


    files_dict = {f["id"]: f for f in files}

    for lab in labs:
        file_id = lab.get("file_id")
        lab_file = files_dict.get(file_id)
        lab["telegram_file_id"] = lab_file["telegram_file_id"] if lab_file else None
        lab["file_path"] = lab_file["path"] if lab_file else None

    return labs



async def update_lab_work(
    connection: AsyncConnection,
    *,
    lab_id: int,
    file_id: int | None = None,
    name: str | None = None,
    description: str | None = None,
    deadline: datetime | None = None,
    allow_late: bool | None = None,
) -> None:
    fields = []
    params = []
    if file_id is not None:
        fields.append("file_id = %s")
        params.append(file_id)
    if name is not None:
        fields.append("name = %s")
        params.append(name)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if deadline is not None:
        fields.append("deadline = %s")
        params.append(deadline)
    if allow_late is not None:
        fields.append("allow_late = %s")
        params.append(allow_late)
    if not fields:
        logger.warning("No fields to update for lab_id=%s", lab_id)
        return

    params.append(lab_id)
    query = f"""
        UPDATE lab_works
        SET {', '.join(fields)}
        WHERE id = %s
    """

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("Lab work %s updated: %s", lab_id, ", ".join(fields))

async def delete_lab_work(
    connection: AsyncConnection,
    *,
    lab_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM lab_works WHERE id = %s;
            """,
            params=(lab_id,),
        )
    logger.info("Deleted lab_work id=%s", lab_id)



async def add_or_update_test_stat(
    connection: AsyncConnection,
    *,
    user_id: int,
    test_id: int,
    last_score: int | None = None,
    last_submission_time: datetime | None = None,
    attempts_count: int | None = None,
) -> None:
    """
    Upsert for test_stats: insert if not exists, otherwise update fields provided.
    """
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO test_stats(user_id, test_id, last_score, last_submission_time, attempts_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, test_id) DO UPDATE
                SET
                    last_score = EXCLUDED.last_score,
                    last_submission_time = EXCLUDED.last_submission_time,
                    attempts_count = COALESCE(EXCLUDED.attempts_count, test_stats.attempts_count);
            """,
            params=(user_id, test_id, last_score, last_submission_time, attempts_count),
        )
    logger.info("Upserted test_stat for user_id=%s test_id=%s", user_id, test_id)

async def get_test_stat(
    connection: AsyncConnection,
    *,
    user_id: int,
    test_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, user_id, test_id, last_score, last_submission_time, attempts_count
            FROM test_stats
            WHERE user_id = %s AND test_id = %s;
            """,
            (user_id, test_id),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No test_stat found for user_id=%s, test_id=%s", user_id, test_id)
            return None

        columns = [desc.name for desc in cursor.description]
        test_stat = dict(zip(columns, row))
        logger.info("Fetched test_stat: %s", test_stat)
        return test_stat

async def delete_test_stat(
    connection: AsyncConnection,
    *,
    user_id: int,
    test_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM test_stats WHERE user_id = %s AND test_id = %s;
            """,
            params=(user_id, test_id),
        )
    logger.info("Deleted test_stat user_id=%s test_id=%s", user_id, test_id)



async def add_submission(
    connection: AsyncConnection,
    *,
    user_id: int,
    lab_id: int,
    submission_file_id: int,
    submitted_at: datetime | None = None,
    is_late: bool = False,
    status: SubmissionStatus = SubmissionStatus.UPLOADED,
    score: int | None = None,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO submissions(
                    user_id, lab_id, submission_file_id, submitted_at, is_late, status, score
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """,
            params=(user_id, lab_id, submission_file_id, submitted_at, is_late, status, score),
        )
        row = await cursor.fetchone()
    submission_id = row[0] if row else None
    logger.info("New submission added. Table=`%s`, id=%s, user_id=%s, lab_id=%s", "submissions", submission_id, user_id, lab_id)
    return submission_id

async def get_submission(
    connection: AsyncConnection,
    *,
    submission_id: int,
) -> dict[str, Any] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, user_id, lab_id, submission_file_id, submitted_at, is_late, status, score
            FROM submissions
            WHERE id = %s;
            """,
            (submission_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("No submission found for submission_id=%s", submission_id)
            return None

        columns = [desc.name for desc in cursor.description]
        submission = dict(zip(columns, row))
        logger.info("Fetched submission: %s", submission)
        return submission

async def get_submissions_by_user(
    connection: AsyncConnection,
    *,
    user_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, user_id, lab_id, submission_file_id, submitted_at, is_late, status, score
            FROM submissions
            WHERE user_id = %s;
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No submissions found for user_id=%s", user_id)
            return None

        columns = [desc.name for desc in cursor.description]
        submissions = [dict(zip(columns, row)) for row in rows]
        logger.info("Fetched submissions: %s", submissions)
        return submissions

async def update_submission(
    connection: AsyncConnection,
    *,
    submission_id: int,
    submission_file_id: int | None = None,
    is_late: bool | None = None,
    status: SubmissionStatus | None = None,
    score: int | None = None,
) -> None:
    fields = []
    params = []
    if submission_file_id is not None:
        fields.append("submission_file_id = %s")
        params.append(submission_file_id)
    if is_late is not None:
        fields.append("is_late = %s")
        params.append(is_late)
    if status is not None:
        fields.append("status = %s")
        params.append(status)
    if score is not None:
        fields.append("score = %s")
        params.append(score)
    if not fields:
        logger.warning("No fields to update for submission_id=%s", submission_id)
        return

    params.append(submission_id)
    query = f"""
        UPDATE submissions
        SET {', '.join(fields)}
        WHERE id = %s
    """

    async with connection.cursor() as cursor:
        await cursor.execute(query, params)

    logger.info("Submission %s updated: %s", submission_id, ", ".join(fields))

async def delete_submission(
    connection: AsyncConnection,
    *,
    submission_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM submissions WHERE id = %s;
            """,
            params=(submission_id,),
        )
    logger.info("Deleted submission id=%s", submission_id)



async def add_access_request(
    connection: AsyncConnection,
    *,
    telegram_id: int | None = None,
    username: str | None = None,
    name: str,
    surname: str,
    patronymic: str | None = None,
) -> int | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                INSERT INTO access_requests(telegram_id, username, name, surname, patronymic)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """,
            params=(telegram_id, username, name, surname, patronymic),
        )
        row = await cursor.fetchone()
    req_id = row[0] if row else None
    logger.info("New access_request added. Table=`%s`, id=%s, telegram_id=%s, username=%s", "access_requests", req_id, telegram_id, username)
    return req_id

async def create_user_from_request(
    connection: AsyncConnection,
    *,
    request_id: int,
    role: str = "student"
) -> None:
    """
    Создаёт новую запись в таблице users на основе access_requests.
    """
    async with connection.cursor() as cursor:
        await cursor.execute(
            query=
                """
                    SELECT telegram_id, username, name, surname, patronymic
                    FROM access_requests
                    WHERE id = %s;
                """,
            params=(request_id,),
        )
        row = await cursor.fetchone()

        if not row:
            logger.warning("Access request with id=%s not found", request_id)
            return

        telegram_id, username, name, surname, patronymic = row

    await add_user(
        connection,
        telegram_id=telegram_id,
        username=username,
        name=name,
        surname=surname,
        patronymic=patronymic,
        role=role
    )

    logger.info("User created from access_request id=%s", request_id)

async def get_access_requests(
    connection: AsyncConnection,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, telegram_id, username, name, surname, patronymic, requested_at
            FROM access_requests;
            """
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No access requests found")
            return None

        columns = [desc.name for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in rows]
        logger.info("Fetched access requests: %s", results)
        return results


async def get_access_request(
    connection: AsyncConnection,
    *,
    telegram_id: int,
) -> list[dict[str, Any]] | None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT id, telegram_id, username, name, surname, patronymic, requested_at
            FROM access_requests
            WHERE telegram_id = %s;
            """,
            (telegram_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.warning("No access requests found for telegram_id=%s", telegram_id)
            return None

        columns = [desc.name for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in rows]
        logger.info("Fetched access requests: %s", results)
        return results

async def delete_access_request(
    connection: AsyncConnection,
    *,
    request_id: int,
) -> None:
    async with connection.cursor() as cursor:
        await cursor.execute(
            query="""
                DELETE FROM access_requests WHERE id = %s;
            """,
            params=(request_id,),
        )
    logger.info("Deleted access_request id=%s", request_id)