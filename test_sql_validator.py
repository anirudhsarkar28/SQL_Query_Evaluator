import sqlite3
import tempfile
import unittest
from pathlib import Path

from sql_validator import execute_readonly


class ExecuteReadonlyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "sample database.db")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("CREATE TABLE students (id INTEGER, name TEXT)")
            connection.executemany(
                "INSERT INTO students VALUES (?, ?)",
                [(1, "Asha"), (2, "Ravi")],
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_select_and_read_only_cte_are_allowed(self):
        result = execute_readonly(
            self.db_path,
            "WITH selected AS (SELECT name FROM students) SELECT name FROM selected",
        )

        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(result["rows"], [["Asha"], ["Ravi"]])

    def test_write_is_blocked_without_modifying_database(self):
        result = execute_readonly(self.db_path, "UPDATE students SET name = 'changed'")

        self.assertTrue(result["blocked"])
        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                connection.execute("SELECT name FROM students ORDER BY id").fetchall(),
                [("Asha",), ("Ravi",)],
            )
        finally:
            connection.close()

    def test_sensitive_sql_function_is_denied_by_authorizer(self):
        result = execute_readonly(self.db_path, "SELECT load_extension('example')")

        self.assertFalse(result["ok"])
        self.assertIn("not authorized", result["reason"].lower())

    def test_result_limit_is_enforced(self):
        result = execute_readonly(self.db_path, "SELECT name FROM students", max_rows=1)

        self.assertTrue(result["blocked"])
        self.assertEqual(result["rows"], [])

    def test_execution_deadline_must_be_finite(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            execute_readonly(
                self.db_path,
                "SELECT name FROM students",
                max_execution_seconds=float("inf"),
            )

    def test_execution_deadline_interrupts_expensive_query(self):
        query = """
            WITH RECURSIVE numbers(value) AS (
                VALUES (1)
                UNION ALL
                SELECT value + 1 FROM numbers WHERE value < 100000000
            )
            SELECT sum(value) FROM numbers
        """

        result = execute_readonly(
            self.db_path,
            query,
            max_execution_seconds=0.01,
        )

        self.assertFalse(result["ok"])
        self.assertIn("interrupt", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
