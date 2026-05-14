"""Initialize the PostgreSQL database with schema and seed data."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

PG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id      SERIAL PRIMARY KEY,
    name    TEXT   NOT NULL,
    email   TEXT   UNIQUE NOT NULL,
    cohort  TEXT   NOT NULL,
    score   REAL   DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS courses (
    id         SERIAL PRIMARY KEY,
    title      TEXT    NOT NULL,
    credits    INTEGER NOT NULL DEFAULT 3,
    department TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id          SERIAL PRIMARY KEY,
    student_id  INTEGER NOT NULL REFERENCES students(id),
    course_id   INTEGER NOT NULL REFERENCES courses(id),
    grade       TEXT,
    enrolled_at TEXT DEFAULT current_date::text
);
"""

PG_SEED_SQL = """
INSERT INTO students (name, email, cohort, score) VALUES
    ('Alice Nguyen',   'alice@lab.io',   'A1', 92.5),
    ('Bob Tran',       'bob@lab.io',     'A1', 78.0),
    ('Carol Le',       'carol@lab.io',   'B2', 85.5),
    ('David Pham',     'david@lab.io',   'B2', 61.0),
    ('Eva Hoang',      'eva@lab.io',     'A1', 95.0),
    ('Frank Do',       'frank@lab.io',   'C3', 70.5),
    ('Grace Vu',       'grace@lab.io',   'C3', 88.0)
ON CONFLICT (email) DO NOTHING;

INSERT INTO courses (title, credits, department) VALUES
    ('Intro to Python',    3, 'CS'),
    ('Data Structures',    4, 'CS'),
    ('Machine Learning',   3, 'AI'),
    ('Database Systems',   3, 'CS'),
    ('Cloud Architecture', 2, 'DevOps')
ON CONFLICT DO NOTHING;

INSERT INTO enrollments (student_id, course_id, grade)
SELECT s.id, c.id, e.grade
FROM (VALUES
    ('alice@lab.io',  'Intro to Python',    'A'),
    ('alice@lab.io',  'Data Structures',    'A'),
    ('alice@lab.io',  'Machine Learning',   'B+'),
    ('bob@lab.io',    'Intro to Python',    'B'),
    ('bob@lab.io',    'Database Systems',   'C+'),
    ('carol@lab.io',  'Data Structures',    'A-'),
    ('carol@lab.io',  'Machine Learning',   'A'),
    ('david@lab.io',  'Intro to Python',    'C'),
    ('david@lab.io',  'Database Systems',   'B-'),
    ('eva@lab.io',    'Intro to Python',    'A+'),
    ('eva@lab.io',    'Data Structures',    'A'),
    ('eva@lab.io',    'Cloud Architecture', 'A'),
    ('frank@lab.io',  'Machine Learning',   'B'),
    ('frank@lab.io',  'Cloud Architecture', 'B+'),
    ('grace@lab.io',  'Data Structures',    'A-'),
    ('grace@lab.io',  'Machine Learning',   'A'),
    ('grace@lab.io',  'Database Systems',   'A+')
) AS e(email, title, grade)
JOIN students s ON s.email = e.email
JOIN courses  c ON c.title = e.title
WHERE NOT EXISTS (
    SELECT 1 FROM enrollments ex
    WHERE ex.student_id = s.id AND ex.course_id = c.id
);
"""


def init_postgres(dsn: str) -> None:
    import psycopg2
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(PG_SCHEMA_SQL)
            cur.execute(PG_SEED_SQL)
        conn.commit()
        print(f"PostgreSQL database initialized: {dsn}")
    finally:
        conn.close()


if __name__ == "__main__":
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        print("ERROR: POSTGRES_DSN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    init_postgres(dsn)
