"""Conservative SQL validation for a disposable SQLite evaluation database."""
import math
import re
import sqlite3
import time
from pathlib import Path

# Deliberately conservative: this project automatically executes SELECT only.
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|"
    r"PRAGMA|VACUUM|REINDEX|GRANT|REVOKE|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)

_READ_ONLY_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}
_FORBIDDEN_FUNCTIONS = {"load_extension", "readfile", "writefile"}


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()

def validate_select(sql: str) -> tuple[bool, str, str]:
    """Return (allowed, cleaned_sql, reason). Conservative by design."""
    if not isinstance(sql, str) or not sql.strip():
        return False, "", "No SQL was returned."
    cleaned = strip_sql_comments(sql).strip()
    # Allow at most one statement; permit a single trailing semicolon.
    body = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned
    if ";" in body:
        return False, cleaned, "Multiple SQL statements are blocked."
    if not re.match(r"^(SELECT|WITH)\b", body, flags=re.IGNORECASE):
        return False, cleaned, "Only SELECT queries (including WITH ... SELECT) are allowed."
    if FORBIDDEN.search(body):
        return False, cleaned, "A prohibited SQL operation was detected."
    if re.search(r"\bINTO\s+OUTFILE\b", body, re.IGNORECASE):
        return False, cleaned, "File-writing SQL is blocked."
    return True, body, "Allowed for read-only evaluation."


def execute_readonly(
    db_path: str,
    sql: str,
    max_rows: int = 1000,
    max_execution_seconds: float = 2.0,
) -> dict:
    """Execute read-only SQL with SQLite authorization, row, and time limits."""
    allowed, cleaned, reason = validate_select(sql)
    if not allowed:
        return {"ok": False, "blocked": True, "reason": reason, "rows": [], "columns": []}
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer.")
    if (
        isinstance(max_execution_seconds, bool)
        or not isinstance(max_execution_seconds, (int, float))
        or not math.isfinite(max_execution_seconds)
        or max_execution_seconds <= 0
    ):
        raise ValueError("max_execution_seconds must be a finite number greater than zero.")

    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    deadline = time.monotonic() + max_execution_seconds
    con = None
    try:
        con = sqlite3.connect(uri, uri=True, timeout=min(3.0, max_execution_seconds))
        con.set_authorizer(_read_only_authorizer)
        con.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
        cur = con.cursor()
        cur.execute(cleaned)
        columns = [d[0] for d in (cur.description or [])]
        rows = cur.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            return {"ok": False, "blocked": True, "reason": f"Result exceeded {max_rows} rows.",
                    "rows": [], "columns": columns}
        con.close()
        con = None
        return {"ok": True, "blocked": False, "reason": "Executed successfully.",
                "rows": [list(r) for r in rows], "columns": columns}
    except sqlite3.Error as exc:
        return {"ok": False, "blocked": False, "reason": str(exc), "rows": [], "columns": []}
    finally:
        if con is not None:
            con.close()

def _read_only_authorizer(action, arg1, arg2, db_name, trigger_name):
    """Allow only query reads and reject sensitive functions at SQLite's boundary."""
    if action not in _READ_ONLY_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _FORBIDDEN_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK
