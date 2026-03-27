from __future__ import annotations

from typing import List, Optional

from database.db_manager import DbManager
from models.approval_chain import ApprovalChainStep
from models.document import Document
from models.user import User


class WorkflowService:
    def __init__(self, db: DbManager) -> None:
        self._db = db

    def list_users(self) -> List[User]:
        return self._db.list_users()

    def get_user(self, user_id: int) -> Optional[User]:
        return self._db.get_user(user_id)

    def create_new_document(self, *, title: str, html_content: str, created_by: int) -> Document:
        doc = Document(
            id=None,
            title=title,
            content=html_content,
            created_by=created_by,
            status="Draft",
            assigned_to=None,
            current_step=0,
        )
        new_id = self._db.create_document(doc)
        doc.id = new_id
        return doc

    def save_document(self, doc: Document) -> Document:
        if doc.id is None:
            new_id = self._db.create_document(doc)
            doc.id = new_id
            return doc

        self._db.update_document(doc)
        return doc

    def get_document(self, doc_id: int) -> Optional[Document]:
        return self._db.get_document(doc_id)

    def my_created_documents(self, user_id: int) -> List[Document]:
        return self._db.list_documents_created_by(user_id)

    def pending_for_me(self, user_id: int) -> List[Document]:
        return self._db.list_documents_assigned_to(user_id)

    def set_approval_chain(self, *, document_id: int, user_ids_in_order: List[int]) -> None:
        if not user_ids_in_order:
            raise ValueError("Approval chain cannot be empty")
        self._db.replace_approval_chain(document_id, user_ids_in_order)

    def get_approval_chain(self, document_id: int) -> List[ApprovalChainStep]:
        return self._db.list_approval_chain(document_id)

    def send_for_approval(self, doc: Document) -> Document:
        if doc.id is None:
            raise ValueError("Save the document before sending for approval")

        chain = self._db.list_approval_chain(doc.id)
        if not chain:
            raise ValueError("Approval chain is not configured")

        doc.status = "Pending"
        doc.current_step = 0
        doc.assigned_to = chain[0].user_id
        self._db.update_document(doc)
        return doc

    def approve(self, doc: Document) -> Document:
        if doc.id is None:
            raise ValueError("Document must be saved")

        if doc.status != "Pending":
            raise ValueError("Only pending documents can be approved")

        step = self._db.get_approval_step(document_id=doc.id, step_order=doc.current_step)
        if step is None:
            raise ValueError("Approval chain step not found")

        self._db.update_approval_step_status(document_id=doc.id, step_order=doc.current_step, status="Approved")

        chain = self._db.list_approval_chain(doc.id)
        next_step_order = doc.current_step + 1

        if next_step_order < len(chain):
            doc.current_step = next_step_order
            doc.assigned_to = chain[next_step_order].user_id
            self._db.update_document(doc)
            return doc

        doc.status = "Approved"
        doc.assigned_to = None
        self._db.update_document(doc)
        return doc

    def reject(self, doc: Document) -> Document:
        if doc.id is None:
            raise ValueError("Document must be saved")

        if doc.status != "Pending":
            raise ValueError("Only pending documents can be rejected")

        step = self._db.get_approval_step(document_id=doc.id, step_order=doc.current_step)
        if step is None:
            raise ValueError("Approval chain step not found")

        self._db.update_approval_step_status(document_id=doc.id, step_order=doc.current_step, status="Rejected")
        doc.status = "Rejected"
        doc.assigned_to = None
        self._db.update_document(doc)
        return doc
