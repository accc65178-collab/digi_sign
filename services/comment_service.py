from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from database.db_manager import DbManager
from models.comment import Comment


class CommentService:
    def __init__(self, db: DbManager) -> None:
        self._db = db

    def add_comment(self, *, document_id: int, user_id: int, comment: str) -> Comment:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        c = Comment(id=None, document_id=document_id, user_id=user_id, comment=comment, timestamp=ts)
        new_id = self._db.add_comment(c)
        c.id = new_id
        return c

    def list_comments(self, document_id: int) -> List[Comment]:
        return self._db.list_comments(document_id)
