import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "lab.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    cohort TEXT NOT NULL,
    score REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 3,
    department TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    grade TEXT,
    enrolled_at TEXT DEFAULT (date('now'))
);
"""

SEED_SQL = """
INSERT OR IGNORE INTO students (name, email, cohort, score) VALUES
    ('Alice Nguyen',   'alice@lab.io',   'A1', 92.5),
    ('Bob Tran',       'bob@lab.io',     'A1', 78.0),
    ('Carol Le',       'carol@lab.io',   'B2', 85.5),
    ('David Pham',     'david@lab.io',   'B2', 61.0),
    ('Eva Hoang',      'eva@lab.io',     'A1', 95.0),
    ('Frank Do',       'frank@lab.io',   'C3', 70.5),
    ('Grace Vu',       'grace@lab.io',   'C3', 88.0);

INSERT OR IGNORE INTO courses (title, credits, department) VALUES
    ('Intro to Python',       3, 'CS'),
    ('Data Structures',       4, 'CS'),
    ('Machine Learning',      3, 'AI'),
    ('Database Systems',      3, 'CS'),
    ('Cloud Architecture',    2, 'DevOps');

INSERT OR IGNORE INTO enrollments (student_id, course_id, grade) VALUES
    (1, 1, 'A'), (1, 2, 'A'), (1, 3, 'B+'),
    (2, 1, 'B'), (2, 4, 'C+'),
    (3, 2, 'A-'), (3, 3, 'A'),
    (4, 1, 'C'), (4, 4, 'B-'),
    (5, 1, 'A+'), (5, 2, 'A'), (5, 5, 'A'),
    (6, 3, 'B'), (6, 5, 'B+'),
    (7, 2, 'A-'), (7, 3, 'A'), (7, 4, 'A+');
"""


def create_database(db_path: str = DB_PATH) -> str:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()
    return db_path


if __name__ == "__main__":
    path = create_database()
    print(f"Database created at: {path}")
