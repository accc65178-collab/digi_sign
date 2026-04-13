from __future__ import annotations

import os
import shutil
from datetime import datetime
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

    def list_approved_users(self) -> List[User]:
        return self._db.list_users_by_status("Approved")

    def list_pending_users(self) -> List[User]:
        return self._db.list_users_by_status("Pending")

    def signup_user(self, *, name: str, designation: str, password: str) -> User:
        try:
            import bcrypt  # type: ignore
        except ModuleNotFoundError as e:
            raise RuntimeError("bcrypt is required. Install with: pip install bcrypt") from e

        if not name:
            raise ValueError("Name is required")
        if not designation:
            raise ValueError("Designation is required")
        if not password:
            raise ValueError("Password is required")

        username = name.strip().lower().replace(" ", "")
        if not username:
            raise ValueError("Name must contain at least one letter or number")

        existing = self._db.get_user_by_username(username)
        if existing is not None:
            raise ValueError("Username already exists")

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        new_id = self._db.create_user(
            name=name.strip(),
            username=username,
            password_hash=password_hash,
            designation=designation.strip(),
            role="Normal",
            status="Pending",
        )
        user = self._db.get_user(new_id)
        if user is None:
            raise RuntimeError("Failed to create user")
        return user

    def authenticate(self, *, username: str, password: str) -> Optional[User]:
        try:
            import bcrypt  # type: ignore
        except ModuleNotFoundError as e:
            raise RuntimeError("bcrypt is required. Install with: pip install bcrypt") from e

        user = self._db.get_user_by_username(username)
        if user is None:
            return None
        if not user.enabled:
            return None
        if user.status != "Approved":
            return None

        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8"))
        except Exception:
            return None

        return user if ok else None

    def list_all_documents(self) -> List[Document]:
        return self._db.list_all_documents()

    def set_user_enabled(self, *, user_id: int, enabled: bool) -> None:
        self._db.update_user_enabled(user_id=user_id, enabled=enabled)

    def reset_user_password(self, *, user_id: int, new_password: str) -> None:
        try:
            import bcrypt  # type: ignore
        except ModuleNotFoundError as e:
            raise RuntimeError("bcrypt is required. Install with: pip install bcrypt") from e

        if not new_password:
            raise ValueError("Password is required")

        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        self._db.update_user_password_hash(user_id=user_id, password_hash=password_hash)

    def create_password_reset_request(self, *, username: str) -> int:
        if not username:
            raise ValueError("Username is required")
        now = datetime.utcnow().isoformat(timespec="seconds")
        return self._db.create_password_reset_request(username=username, requested_at=now)

    def list_password_reset_requests(self, *, status: Optional[str] = None):
        return self._db.list_password_reset_requests(status=status)

    def handle_password_reset_request(self, *, request_id: int, status: str, handled_by: int) -> None:
        if status not in ("Approved", "Rejected"):
            raise ValueError("Invalid status")
        now = datetime.utcnow().isoformat(timespec="seconds")
        self._db.update_password_reset_request(
            request_id=request_id,
            status=status,
            handled_at=now,
            handled_by=handled_by,
        )

    def approve_user(self, user_id: int) -> None:
        self._db.update_user_status(user_id=user_id, status="Approved")

    def reject_user(self, user_id: int) -> None:
        self._db.update_user_status(user_id=user_id, status="Rejected")

    def can_delete_user(self, user_id: int) -> bool:
        return self._db.can_delete_user(user_id)

    def delete_user(self, user_id: int) -> None:
        self._db.delete_user(user_id)

    def get_user(self, user_id: int) -> Optional[User]:
        return self._db.get_user(user_id)

    def get_user_signature_png(self, *, user_id: int) -> Optional[bytes]:
        return self._db.get_user_signature_png(user_id=user_id)

    def set_user_signature_png(self, *, user_id: int, signature_png: Optional[bytes]) -> None:
        self._db.set_user_signature_png(user_id=user_id, signature_png=signature_png)

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self._db.get_user_by_username(username)

    def create_new_document(self, *, title: str, html_content: str, created_by: int) -> Document:
        doc = Document(
            id=None,
            title=title,
            subject="",
            content=html_content,
            created_by=created_by,
            status="Draft",
            assigned_to=None,
            current_step=0,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        new_id = self._db.create_document(doc)
        doc.id = new_id
        return doc

    def save_document(self, doc: Document) -> Document:
        if doc.id is None:
            if not (doc.created_at or "").strip():
                doc.created_at = datetime.now().isoformat(timespec="seconds")
            new_id = self._db.create_document(doc)
            doc.id = new_id
            return doc

        if not (doc.created_at or "").strip():
            doc.created_at = datetime.now().isoformat(timespec="seconds")
        self._db.update_document(doc)
        return doc

    def daily_sequence_for_document(self, *, document_id: Optional[int], iso_date: str) -> int:
        if document_id is not None:
            return self._db.daily_sequence_for_document(doc_id=int(document_id), iso_date=iso_date)
        return self._db.count_documents_on_date(iso_date=iso_date) + 1

    def get_document(self, doc_id: int) -> Optional[Document]:
        return self._db.get_document(doc_id)

    def delete_document(self, doc_id: int) -> None:
        self._db.delete_document(doc_id)

    def signup_user(self, *, full_name: str, employee_id: str, department: str, lab: str, designation: str, password: str) -> None:
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        # Generate a simple username from full_name (lowercase, no spaces)
        username = full_name.replace(" ", "").lower()
        # Use full_name for legacy name field for compatibility
        self._db.create_user(
            name=full_name,
            full_name=full_name,
            employee_id=employee_id,
            department=department,
            lab=lab,
            username=username,
            password_hash=password_hash,
            designation=designation,
            role="Normal",
            status="Pending",
            enabled=0,
        )

    def my_created_documents(self, user_id: int) -> List[Document]:
        return self._db.list_documents_created_by(user_id)

    def pending_for_me(self, user_id: int) -> List[Document]:
        return self._db.list_documents_assigned_to(user_id)

    def documents_approved_by_me(self, user_id: int) -> List[Document]:
        return self._db.list_documents_approved_by_user(user_id)

    def set_approval_chain(self, *, document_id: int, user_ids_in_order: List[int]) -> None:
        if not user_ids_in_order:
            raise ValueError("Approval chain cannot be empty")
        self._db.replace_approval_chain(document_id, user_ids_in_order)

    def get_approval_chain(self, document_id: int) -> List[ApprovalChainStep]:
        return self._db.list_approval_chain(document_id)

    def set_approval_step_signature(self, *, document_id: int, step_order: int, signature_png: bytes) -> None:
        self._db.update_approval_step_signature(document_id=document_id, step_order=step_order, signature_png=signature_png)

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

    def get_setting(self, key: str, default: str = "") -> str:
        return self._db.get_setting(key, default)

    def update_setting(self, key: str, value: str) -> None:
        self._db.update_setting(key, value)

    def upload_template(self, source_path: str) -> None:
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source template not found: {source_path}")
        
        # Determine the target template location
        # Usually e:\new_sign\digi_sign\letterhead\REF.docx
        target_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "letterhead")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        target_path = os.path.join(target_dir, "REF.docx")
        shutil.copy2(source_path, target_path)

    def update_user_role(self, user_id: int, role: str) -> None:
        self._db.update_user_role(user_id, role)
