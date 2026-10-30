"""
DATABASE LAYER  -  database/db_manager.py

The only file in the project that imports sqlite3 and contains SQL table definitions.
Backend classes never open the database themselves; they call the methods of
DatabaseManager (connect, insert, update, delete, fetch_all, fetch_one).

Explain in viva: the 11 tables (users, admins, faculty, students, quizzes, questions,
options, attempts, answers, results, score_analysis), the foreign keys with cascade
deletes, and how execute_query() wraps sqlite errors into our own DatabaseError.
"""
import sqlite3

from exceptions import DatabaseError


class DatabaseManager:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('Admin','Faculty','Student')),
        status TEXT NOT NULL DEFAULT 'Active',
        created_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS admins (
        admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        permissions TEXT
    );
    CREATE TABLE IF NOT EXISTS faculty (
        faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        department TEXT,
        designation TEXT
    );
    CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        roll_no TEXT UNIQUE,
        class_grade TEXT
    );
    CREATE TABLE IF NOT EXISTS quizzes (
        quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_id INTEGER NOT NULL REFERENCES faculty(faculty_id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        subject TEXT,
        topic TEXT,
        description TEXT,
        difficulty_level TEXT DEFAULT 'Easy',
        total_marks INTEGER DEFAULT 0,
        time_limit INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Draft',
        created_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS questions (
        question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
        question_text TEXT NOT NULL,
        question_type TEXT DEFAULT 'MCQ',
        topic TEXT,
        marks INTEGER DEFAULT 1,
        created_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS options (
        option_id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
        option_text TEXT NOT NULL,
        is_correct BOOLEAN DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS attempts (
        attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
        quiz_id INTEGER NOT NULL REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
        started_at TIMESTAMP,
        submitted_at TIMESTAMP,
        status TEXT DEFAULT 'InProgress'
    );
    CREATE TABLE IF NOT EXISTS answers (
        answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL REFERENCES attempts(attempt_id) ON DELETE CASCADE,
        question_id INTEGER NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
        selected_option_id INTEGER REFERENCES options(option_id) ON DELETE SET NULL,
        is_correct BOOLEAN DEFAULT 0,
        marks_awarded INTEGER DEFAULT 0,
        answered_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS results (
        result_id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempts(attempt_id) ON DELETE CASCADE,
        student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
        quiz_id INTEGER NOT NULL REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
        total_questions INTEGER,
        correct_count INTEGER,
        incorrect_count INTEGER,
        total_score INTEGER,
        percentage REAL,
        time_taken INTEGER,
        generated_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS score_analysis (
        analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER REFERENCES students(student_id) ON DELETE CASCADE,
        quiz_id INTEGER REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
        analysis_type TEXT,
        total_attempts INTEGER,
        average_score REAL,
        highest_score REAL,
        lowest_score REAL,
        performance_trend TEXT,
        weak_topic TEXT,
        generated_at TIMESTAMP
    );
    """

    def __init__(self, db_name="quiz_app.db"):
        self.__db_name = db_name
        self.__connection = None

    def connect(self):
        if self.__connection is None:
            try:
                self.__connection = sqlite3.connect(self.__db_name)
                self.__connection.row_factory = sqlite3.Row
                self.__connection.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error as exc:
                raise DatabaseError(f"Cannot open database: {exc}") from exc
        return self.__connection

    def close(self):
        if self.__connection is not None:
            self.__connection.close()
            self.__connection = None

    def create_tables(self):
        conn = self.connect()
        try:
            conn.executescript(self.SCHEMA)
            conn.commit()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Cannot create tables: {exc}") from exc

    def execute_query(self, sql, params=()):
        conn = self.connect()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(str(exc)) from exc

    def fetch_all(self, sql, params=()):
        return [dict(r) for r in self.execute_query(sql, params).fetchall()]

    def fetch_one(self, sql, params=()):
        row = self.execute_query(sql, params).fetchone()
        return dict(row) if row else None

    def insert(self, table, data):
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        return self.execute_query(
            f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values())
        ).lastrowid

    def update(self, table, data, where, where_params=()):
        sets = ", ".join(f"{c} = ?" for c in data)
        self.execute_query(
            f"UPDATE {table} SET {sets} WHERE {where}", tuple(data.values()) + tuple(where_params)
        )

    def delete(self, table, where, params=()):
        self.execute_query(f"DELETE FROM {table} WHERE {where}", params)
