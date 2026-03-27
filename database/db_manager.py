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
                    role TEXT NOT NULL
                )
                """
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
                conn.executemany(
                    "INSERT INTO users(name, role) VALUES(?, ?)",
                    [
                        ("Admin", "Admin"),
                        ("Manager", "Manager"),
                        ("Officer", "Officer"),
                    ],
                )

    def list_users(self) -> List[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, name, role FROM users ORDER BY id").fetchall()
        return [User(id=row["id"], name=row["name"], role=row["role"]) for row in rows]

    def get_user(self, user_id: int) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return User(id=row["id"], name=row["name"], role=row["role"])

    def create_document(self, doc: Document) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents(title, content, created_by, status, assigned_to, current_step)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (doc.title, doc.content, doc.created_by, doc.status, doc.assigned_to, doc.current_step),
            )
            return int(cur.lastrowid)

    def update_document(self, doc: Document) -> None:
        if doc.id is None:
            raise ValueError("Document id is required for update")

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET title = ?, content = ?, created_by = ?, status = ?, assigned_to = ?, current_step = ?
                WHERE id = ?
                """,
                (
                    doc.title,
                    doc.content,
                    doc.created_by,
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
                SELECT id, title, content, created_by, status, assigned_to, current_step
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
                SELECT id, title, content, created_by, status, assigned_to, current_step
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
                SELECT id, title, content, created_by, status, assigned_to, current_step
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
