CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(40),
    name VARCHAR NOT NULL,
    surname VARCHAR NOT NULL,
    patronymic VARCHAR,
    role VARCHAR(20) NOT NULL
        CONSTRAINT role_check CHECK (role IN ('student', 'admin')),
    is_banned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS files(
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL
        CONSTRAINT type_check CHECK (type in ('lecture', 'lab', 'submission')),
    telegram_file_id VARCHAR NOT NULL,
    path VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS lectures(
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    file_id INT NOT NULL REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS tests(
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    lecture_id INT REFERENCES lectures(id)
);

CREATE TABLE IF NOT EXISTS questions(
    id SERIAL PRIMARY KEY,
    test_id INT NOT NULL REFERENCES tests(id),
    text VARCHAR NOT NULL,
    max_points INT
);

CREATE TABLE IF NOT EXISTS answers(
    id SERIAL PRIMARY KEY,
    question_id INT NOT NULL REFERENCES questions(id),
    text VARCHAR NOT NULL,
    is_right BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS lab_works(
    id SERIAL PRIMARY KEY,
    file_id INT NOT NULL REFERENCES files(id),
    name VARCHAR NOT NULL,
    description VARCHAR,
    deadline TIMESTAMPTZ,
    allow_late BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS test_stats(
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    test_id INT NOT NULL REFERENCES tests(id),
    last_score INT,
    last_submission_time TIMESTAMPTZ,
    attempts_count INT DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_stats_user_test
    ON test_stats (user_id, test_id);

CREATE TABLE IF NOT EXISTS submissions(
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    lab_id INT NOT NULL REFERENCES lab_works(id),
    submission_file_id INT NOT NULL REFERENCES files(id),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_late BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) NOT NULL
        CONSTRAINT status_check CHECK (status in ('uploaded', 'graded')) DEFAULT 'uploaded',
    score INT
);

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
