import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from models.approval_chain import ApprovalChainStep
from models.comment import Comment
from models.document import Document
from models.user import User


@dataclass(frozen=True)
class DbConfig:
    db_path: Path


class DbManager:
    def __init__(self, config: DbConfig) -> None:
        self._config = config
        self._config.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._config.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Approved'
                )
                """
            )

            # Migration: add auth/status columns if the database was created before they existed.
            user_cols = conn.execute("PRAGMA table_info(users)").fetchall()
            user_col_names = {row["name"] for row in user_cols}
            if "status" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'Approved'")
            if "username" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
            if "password_hash" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            if "designation" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN designation TEXT")
            if "enabled" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
            # New fields for employee info
            if "full_name" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
            if "employee_id" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN employee_id TEXT")
            if "department" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN department TEXT")
            if "lab" not in user_col_names:
                conn.execute("ALTER TABLE users ADD COLUMN lab TEXT")

            conn.execute("UPDATE users SET status = 'Approved' WHERE status IS NULL OR status = ''")

            conn.execute("UPDATE users SET designation = '' WHERE designation IS NULL")

            conn.execute("UPDATE users SET enabled = 1 WHERE enabled IS NULL")

            conn.execute("UPDATE users SET full_name = name WHERE full_name IS NULL OR full_name = ''")
            conn.execute("UPDATE users SET employee_id = '' WHERE employee_id IS NULL")
            conn.execute("UPDATE users SET department = '' WHERE department IS NULL")
            conn.execute("UPDATE users SET lab = '' WHERE lab IS NULL")

            # Backfill username from legacy name.
            # Note: Keep legacy name column for compatibility with already-created DBs.
            conn.execute(
                "UPDATE users SET username = LOWER(REPLACE(name, ' ', '')) WHERE username IS NULL OR username = ''"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    assigned_to INTEGER,
                    current_step INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(created_by) REFERENCES users(id),
                    FOREIGN KEY(assigned_to) REFERENCES users(id)
                )
                """
            )

            # Migration: add current_step if the database was created before this column existed.
            cols = conn.execute("PRAGMA table_info(documents)").fetchall()
            col_names = {row["name"] for row in cols}
            if "current_step" not in col_names:
                conn.execute("ALTER TABLE documents ADD COLUMN current_step INTEGER NOT NULL DEFAULT 0")
            # Migration: add subject if the database was created before this column existed.
            if "subject" not in col_names:
                conn.execute("ALTER TABLE documents ADD COLUMN subject TEXT DEFAULT ''")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_chain (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    step_order INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )

            user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            if user_count == 0:
                try:
                    import bcrypt  # type: ignore
                except ModuleNotFoundError as e:
                    raise RuntimeError("bcrypt is required. Install with: pip install bcrypt") from e

                def _hash(pw: str) -> str:
                    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

                conn.executemany(
                    "INSERT INTO users(name, full_name, employee_id, department, lab, role, status, username, password_hash, designation, enabled) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        ("Admin", "Admin", "", "", "", "Admin", "Approved", "admin", _hash("admin"), "Admin", 1),
                        ("Manager", "Manager", "", "", "", "Manager", "Approved", "manager", _hash("manager"), "Manager", 1),
                        ("Officer", "Officer", "", "", "", "Officer", "Approved", "officer", _hash("officer"), "Officer", 1),
                    ],
                )
            else:
                # Ensure any existing users have a password_hash. Use a temporary default equal to username.
                # Admin can later change this once a proper UI exists.
                try:
                    import bcrypt  # type: ignore
                except ModuleNotFoundError:
                    bcrypt = None

                if bcrypt is not None:
                    rows = conn.execute(
                        "SELECT id, username, password_hash FROM users WHERE password_hash IS NULL OR password_hash = ''"
                    ).fetchall()
                    for r in rows:
                        username = r["username"] or "user"
                        ph = bcrypt.hashpw(username.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (ph, r["id"]))

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_requests (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    handled_at TEXT,
                    handled_by INTEGER,
                    FOREIGN KEY(handled_by) REFERENCES users(id)
                )
                """
            )

    def list_users(self) -> List[User]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, full_name, employee_id, department, lab, username, password_hash, designation, role, status, enabled FROM users ORDER BY id"
            ).fetchall()
        return [
            User(
                id=row["id"],
                name=row["name"],
                full_name=row["full_name"] if "full_name" in row.keys() else "",
                employee_id=row["employee_id"] if "employee_id" in row.keys() else "",
                department=row["department"] if "department" in row.keys() else "",
                lab=row["lab"] if "lab" in row.keys() else "",
                username=row["username"],
                password_hash=row["password_hash"],
                designation=row["designation"] or "",
                role=row["role"],
                status=row["status"],
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def get_user(self, user_id: int) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, full_name, employee_id, department, lab, username, password_hash, designation, role, status, enabled FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            name=row["name"],
            full_name=row["full_name"] if "full_name" in row.keys() else "",
            employee_id=row["employee_id"] if "employee_id" in row.keys() else "",
            department=row["department"] if "department" in row.keys() else "",
            lab=row["lab"] if "lab" in row.keys() else "",
            username=row["username"],
            password_hash=row["password_hash"],
            designation=row["designation"] or "",
            role=row["role"],
            status=row["status"],
            enabled=bool(row["enabled"]),
        )

    def get_user_by_username(self, username: str) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, full_name, employee_id, department, lab, username, password_hash, designation, role, status, enabled FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            name=row["name"],
            full_name=row["full_name"] if "full_name" in row.keys() else "",
            employee_id=row["employee_id"] if "employee_id" in row.keys() else "",
            department=row["department"] if "department" in row.keys() else "",
            lab=row["lab"] if "lab" in row.keys() else "",
            username=row["username"],
            password_hash=row["password_hash"],
            designation=row["designation"] or "",
            role=row["role"],
            status=row["status"],
            enabled=bool(row["enabled"]),
        )

    def create_user(
        self, *, name: str, full_name: str, employee_id: str, department: str, lab: str, username: str, password_hash: str, designation: str, role: str, status: str, enabled: int = 1
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users(name, full_name, employee_id, department, lab, username, password_hash, designation, role, status, enabled) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, full_name, employee_id, department, lab, username, password_hash, designation, role, status, int(enabled)),
            )
            return int(cur.lastrowid)

    def update_user_status(self, *, user_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))

    def update_user_enabled(self, *, user_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))

    def update_user_password_hash(self, *, user_id: int, password_hash: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))

    def list_users_by_status(self, status: str) -> List[User]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, full_name, employee_id, department, lab, username, password_hash, designation, role, status, enabled FROM users WHERE status = ? ORDER BY id",
                (status,),
            ).fetchall()
        return [
            User(
                id=row["id"],
                name=row["name"],
                full_name=row["full_name"] if "full_name" in row.keys() else "",
                employee_id=row["employee_id"] if "employee_id" in row.keys() else "",
                department=row["department"] if "department" in row.keys() else "",
                lab=row["lab"] if "lab" in row.keys() else "",
                username=row["username"],
                password_hash=row["password_hash"],
                designation=row["designation"] or "",
                role=row["role"],
                status=row["status"],
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def create_password_reset_request(self, *, username: str, requested_at: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO password_reset_requests(username, requested_at, status) VALUES(?, ?, 'Pending')",
                (username, requested_at),
            )
            return int(cur.lastrowid)

    def list_password_reset_requests(self, *, status: Optional[str] = None) -> List[sqlite3.Row]:
        with self._connect() as conn:
            if status:
                return conn.execute(
                    "SELECT id, username, requested_at, status, handled_at, handled_by FROM password_reset_requests WHERE status = ? ORDER BY id DESC",
                    (status,),
                ).fetchall()
            return conn.execute(
                "SELECT id, username, requested_at, status, handled_at, handled_by FROM password_reset_requests ORDER BY id DESC"
            ).fetchall()

    def update_password_reset_request(self, *, request_id: int, status: str, handled_at: str, handled_by: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE password_reset_requests SET status = ?, handled_at = ?, handled_by = ? WHERE id = ?",
                (status, handled_at, handled_by, request_id),
            )

    def list_all_documents(self) -> List[Document]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, subject, content, created_by, status, assigned_to, current_step FROM documents ORDER BY id DESC"
            ).fetchall()
        return [
            Document(
                id=row["id"],
                title=row["title"],
                subject=row["subject"] if "subject" in row.keys() else "",
                content=row["content"],
                created_by=row["created_by"],
                status=row["status"],
                assigned_to=row["assigned_to"],
                current_step=row["current_step"],
            )
            for row in rows
        ]

    def can_delete_user(self, user_id: int) -> bool:
        with self._connect() as conn:
            doc_ref = conn.execute(
                "SELECT 1 FROM documents WHERE created_by = ? OR assigned_to = ? LIMIT 1",
                (user_id, user_id),
            ).fetchone()
            if doc_ref is not None:
                return False

            chain_ref = conn.execute(
                "SELECT 1 FROM approval_chain WHERE user_id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
            if chain_ref is not None:
                return False

            comment_ref = conn.execute(
                "SELECT 1 FROM comments WHERE user_id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
            if comment_ref is not None:
                return False

        return True

    def delete_user(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def delete_document(self, doc_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def create_document(self, doc: Document) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents(title, subject, content, created_by, status, assigned_to, current_step)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (doc.title, doc.subject, doc.content, doc.created_by, doc.status, doc.assigned_to, doc.current_step),
            )
            return int(cur.lastrowid)

    def update_document(self, doc: Document) -> None:
        if doc.id is None:
            raise ValueError("Document id is required for update")

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET title = ?, subject = ?, content = ?, status = ?, assigned_to = ?, current_step = ?
                WHERE id = ?
                """,
                (
                    doc.title,
                    doc.subject,
                    doc.content,
                    doc.status,
                    doc.assigned_to,
                    doc.current_step,
                    doc.id,
                ),
            )

    def get_document(self, doc_id: int) -> Optional[Document]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, subject, content, created_by, status, assigned_to, current_step
                FROM documents
                WHERE id = ?
                """,
                (doc_id,),
            ).fetchone()
        if row is None:
            return None

        return Document(
            id=row["id"],
            title=row["title"],
            subject=row["subject"] if "subject" in row.keys() else "",
            content=row["content"],
            created_by=row["created_by"],
            status=row["status"],
            assigned_to=row["assigned_to"],
            current_step=row["current_step"],
        )

    def list_documents_created_by(self, user_id: int) -> List[Document]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, subject, content, created_by, status, assigned_to, current_step
                FROM documents
                WHERE created_by = ?
                ORDER BY id DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            Document(
                id=row["id"],
                title=row["title"],
                subject=row["subject"] if "subject" in row.keys() else "",
                content=row["content"],
                created_by=row["created_by"],
                status=row["status"],
                assigned_to=row["assigned_to"],
                current_step=row["current_step"],
            )
            for row in rows
        ]

    def list_documents_assigned_to(self, user_id: int) -> List[Document]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, subject, content, created_by, status, assigned_to, current_step
                FROM documents
                WHERE assigned_to = ?
                ORDER BY
                    CASE status
                        WHEN 'Pending' THEN 0
                        WHEN 'Rejected' THEN 1
                        WHEN 'Approved' THEN 2
                        ELSE 3
                    END,
                    id DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            Document(
                id=row["id"],
                title=row["title"],
                subject=row["subject"] if "subject" in row.keys() else "",
                content=row["content"],
                created_by=row["created_by"],
                status=row["status"],
                assigned_to=row["assigned_to"],
                current_step=row["current_step"],
            )
            for row in rows
        ]

    def replace_approval_chain(self, document_id: int, user_ids: List[int]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM approval_chain WHERE document_id = ?", (document_id,))
            conn.executemany(
                """
                INSERT INTO approval_chain(document_id, user_id, step_order, status)
                VALUES(?, ?, ?, ?)
                """,
                [(document_id, uid, idx, "Pending") for idx, uid in enumerate(user_ids)],
            )

    def list_approval_chain(self, document_id: int) -> List[ApprovalChainStep]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, document_id, user_id, step_order, status
                FROM approval_chain
                WHERE document_id = ?
                ORDER BY step_order ASC
                """,
                (document_id,),
            ).fetchall()
        return [
            ApprovalChainStep(
                id=row["id"],
                document_id=row["document_id"],
                user_id=row["user_id"],
                step_order=row["step_order"],
                status=row["status"],
            )
            for row in rows
        ]

    def get_approval_step(self, *, document_id: int, step_order: int) -> Optional[ApprovalChainStep]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, document_id, user_id, step_order, status
                FROM approval_chain
                WHERE document_id = ? AND step_order = ?
                """,
                (document_id, step_order),
            ).fetchone()
        if row is None:
            return None
        return ApprovalChainStep(
            id=row["id"],
            document_id=row["document_id"],
            user_id=row["user_id"],
            step_order=row["step_order"],
            status=row["status"],
        )

    def update_approval_step_status(self, *, document_id: int, step_order: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE approval_chain
                SET status = ?
                WHERE document_id = ? AND step_order = ?
                """,
                (status, document_id, step_order),
            )

    def add_comment(self, comment: Comment) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO comments(document_id, user_id, comment, timestamp)
                VALUES(?, ?, ?, ?)
                """,
                (comment.document_id, comment.user_id, comment.comment, comment.timestamp),
            )
            return int(cur.lastrowid)

    def list_comments(self, document_id: int) -> List[Comment]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, document_id, user_id, comment, timestamp
                FROM comments
                WHERE document_id = ?
                ORDER BY id ASC
                """,
                (document_id,),
            ).fetchall()
        return [
            Comment(
                id=row["id"],
                document_id=row["document_id"],
                user_id=row["user_id"],
                comment=row["comment"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]
