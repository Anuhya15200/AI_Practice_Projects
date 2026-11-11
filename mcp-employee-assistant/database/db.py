import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent / "employees.db"


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                salary REAL NOT NULL CHECK(salary >= 0)
            )
            """
        )

        count = connection.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]

        if count == 0:
            employees = [
                ("Rahul", "IT", 50000),
                ("Priya", "HR", 45000),
                ("Kiran", "IT", 60000),
                ("Anjali", "Finance", 55000)
            ]

            connection.executemany(
                """
                INSERT INTO employees (name, department, salary)
                VALUES (?, ?, ?)
                """,
                employees
            )


initialize_database()