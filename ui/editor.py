from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCharFormat
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.document import Document
from models.user import User
from services.comment_service import CommentService
from services.workflow_service import WorkflowService


class _ChainDialog(QDialog):
    def __init__(self, workflow: WorkflowService, current_user: User, initial_user_ids: List[int], parent=None) -> None:
        super().__init__(parent)
        self._workflow = workflow
        self._current_user = current_user

        self.setWindowTitle("Approval Chain")
        self.setModal(True)
        self.resize(520, 340)

        self._users_combo = QComboBox(self)
        for u in self._workflow.list_users():
            self._users_combo.addItem(f"{u.name} ({u.role})", u.id)

        self._list = QListWidget(self)
        for uid in initial_user_ids:
            self._append_user(uid)

        add_btn = QPushButton("Add")
        remove_btn = QPushButton("Remove")
        up_btn = QPushButton("Up")
        down_btn = QPushButton("Down")

        add_btn.clicked.connect(self._add_selected)
        remove_btn.clicked.connect(self._remove_selected)
        up_btn.clicked.connect(lambda: self._move(-1))
        down_btn.clicked.connect(lambda: self._move(1))

        controls = QHBoxLayout()
        controls.addWidget(QLabel("User:"))
        controls.addWidget(self._users_combo)
        controls.addWidget(add_btn)
        controls.addStretch(1)

        reorder = QHBoxLayout()
        reorder.addWidget(remove_btn)
        reorder.addWidget(up_btn)
        reorder.addWidget(down_btn)
        reorder.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self._list)
        layout.addLayout(reorder)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _append_user(self, user_id: int) -> None:
        u = self._workflow.get_user(user_id)
        label = str(user_id) if u is None else f"{u.name} ({u.role})"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, int(user_id))
        self._list.addItem(item)

    def _add_selected(self) -> None:
        uid = self._users_combo.currentData()
        if uid is None:
            return
        self._append_user(int(uid))

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _move(self, delta: int) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self._list.count():
            return
        item = self._list.takeItem(row)
        self._list.insertItem(new_row, item)
        self._list.setCurrentRow(new_row)

    def user_ids(self) -> List[int]:
        out: List[int] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            out.append(int(item.data(Qt.UserRole)))
        return out


class EditorWindow(QMainWindow):
    saved = pyqtSignal()

    def __init__(
        self,
        workflow: WorkflowService,
        comment_service: CommentService,
        current_user: User,
        document: Optional[Document],
    ) -> None:
        super().__init__()

        self._workflow = workflow
        self._comments = comment_service
        self._current_user = current_user

        self._doc: Document = document or Document(
            id=None,
            title="Untitled",
            content="",
            created_by=current_user.id,
            status="Draft",
            assigned_to=None,
            current_step=0,
        )
        self._dirty = False

        self._pending_chain_user_ids: List[int] = []

        self.setWindowTitle(self._window_title())
        self.resize(1000, 700)

        self._title = QLineEdit(self)
        self._title.setText(self._doc.title)

        self._editor = QTextEdit(self)
        self._editor.setAcceptRichText(True)
        self._editor.setHtml(self._doc.content or "")

        self._title.textChanged.connect(self._on_changed)
        self._editor.textChanged.connect(self._on_changed)

        self._create_toolbar()

        self._save_btn = QPushButton("Save")
        self._chain_btn = QPushButton("Approval Chain")
        self._send_btn = QPushButton("Send for Approval")
        self._approve_btn = QPushButton("Approve")
        self._reject_btn = QPushButton("Reject")

        self._save_btn.clicked.connect(self.save)
        self._chain_btn.clicked.connect(self.configure_chain)
        self._send_btn.clicked.connect(self.send_for_approval)
        self._approve_btn.clicked.connect(self.approve)
        self._reject_btn.clicked.connect(self.reject)

        btn_bar = QHBoxLayout()
        btn_bar.addWidget(self._save_btn)
        btn_bar.addWidget(self._chain_btn)
        btn_bar.addWidget(self._send_btn)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self._approve_btn)
        btn_bar.addWidget(self._reject_btn)

        self._chain_label = QLabel("Approval: (not configured)")

        self._comment_input = QLineEdit(self)
        self._comment_input.setPlaceholderText("Write a review comment...")
        self._add_comment_btn = QPushButton("Add Comment")
        self._add_comment_btn.clicked.connect(self.add_comment)

        comment_bar = QHBoxLayout()
        comment_bar.addWidget(self._comment_input)
        comment_bar.addWidget(self._add_comment_btn)

        self._comments_list = QListWidget(self)

        form = QFormLayout()
        form.addRow("Title:", self._title)

        root = QWidget(self)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self._chain_label)
        layout.addWidget(self._editor)
        layout.addLayout(btn_bar)
        layout.addWidget(QLabel("Comments"))
        layout.addLayout(comment_bar)
        layout.addWidget(self._comments_list)
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.statusBar()
        self._sync_action_visibility()
        self._update_status()
        self._refresh_chain_label()
        self._reload_comments()

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Formatting", self)
        self.addToolBar(toolbar)

        bold = QAction("Bold", self)
        bold.setCheckable(True)
        bold.setShortcut("Ctrl+B")
        bold.triggered.connect(lambda: self._toggle_bold(bold.isChecked()))

        italic = QAction("Italic", self)
        italic.setCheckable(True)
        italic.setShortcut("Ctrl+I")
        italic.triggered.connect(lambda: self._toggle_italic(italic.isChecked()))

        underline = QAction("Underline", self)
        underline.setCheckable(True)
        underline.setShortcut("Ctrl+U")
        underline.triggered.connect(lambda: self._toggle_underline(underline.isChecked()))

        toolbar.addAction(bold)
        toolbar.addAction(italic)
        toolbar.addAction(underline)

    def _merge_char_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(cursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._editor.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if checked else QFont.Normal)
        self._merge_char_format(fmt)

    def _toggle_italic(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._merge_char_format(fmt)

    def _toggle_underline(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._merge_char_format(fmt)

    def _window_title(self) -> str:
        base = self._doc.title if self._doc.title else "Untitled"
        if self._doc.id is None:
            return f"Editor - {base}"
        return f"Editor - {base} (#{self._doc.id})"

    def _update_status(self) -> None:
        state = "Unsaved" if self._dirty else "Saved"
        if self._doc.assigned_to is None:
            assigned = "None"
        else:
            u = self._workflow.get_user(self._doc.assigned_to)
            assigned = str(self._doc.assigned_to) if u is None else f"{u.name} ({u.role})"
        self.statusBar().showMessage(f"Status: {self._doc.status} | Assigned to: {assigned} | {state}")

    def _on_changed(self) -> None:
        if not self._dirty:
            self._dirty = True
        self._doc.title = self._title.text().strip() or "Untitled"
        self.setWindowTitle(self._window_title())
        self._update_status()

    def _sync_action_visibility(self) -> None:
        is_assignee = self._doc.assigned_to == self._current_user.id
        can_decide = is_assignee and self._doc.status == "Pending"

        self._approve_btn.setVisible(can_decide)
        self._reject_btn.setVisible(can_decide)

    def _refresh_chain_label(self) -> None:
        if self._doc.id is None:
            if not self._pending_chain_user_ids:
                self._chain_label.setText("Approval: (not configured)")
                return
            names = []
            for uid in self._pending_chain_user_ids:
                u = self._workflow.get_user(uid)
                names.append(str(uid) if u is None else u.name)
            self._chain_label.setText("Approval: " + " → ".join(names))
            return

        chain = self._workflow.get_approval_chain(self._doc.id)
        if not chain:
            self._chain_label.setText("Approval: (not configured)")
            return

        parts = []
        for step in chain:
            u = self._workflow.get_user(step.user_id)
            name = str(step.user_id) if u is None else u.name
            label = f"{name}"
            if step.step_order == self._doc.current_step and self._doc.status == "Pending":
                label = f"[{label}]"
            parts.append(label)

        self._chain_label.setText("Approval: " + " → ".join(parts))

    def configure_chain(self) -> None:
        initial = self._pending_chain_user_ids
        if self._doc.id is not None:
            chain = self._workflow.get_approval_chain(self._doc.id)
            initial = [s.user_id for s in chain]

        dlg = _ChainDialog(self._workflow, self._current_user, initial, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        user_ids = dlg.user_ids()
        if not user_ids:
            QMessageBox.warning(self, "Chain", "Approval chain cannot be empty.")
            return

        if self._doc.id is None:
            self._pending_chain_user_ids = user_ids
            self._refresh_chain_label()
            return

        try:
            self._workflow.set_approval_chain(document_id=self._doc.id, user_ids_in_order=user_ids)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._refresh_chain_label()

    def _sync_doc_from_ui(self) -> None:
        self._doc.title = self._title.text().strip() or "Untitled"
        self._doc.content = self._editor.toHtml()

    def save(self) -> None:
        self._sync_doc_from_ui()

        try:
            self._doc = self._workflow.save_document(self._doc)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        if self._pending_chain_user_ids and self._doc.id is not None:
            try:
                self._workflow.set_approval_chain(
                    document_id=self._doc.id,
                    user_ids_in_order=list(self._pending_chain_user_ids),
                )
                self._pending_chain_user_ids = []
            except Exception as exc:
                QMessageBox.critical(self, "Failed", str(exc))
                return

        self._dirty = False
        self._sync_action_visibility()
        self.setWindowTitle(self._window_title())
        self._update_status()
        self._refresh_chain_label()
        self._reload_comments()
        self.saved.emit()

    def send_for_approval(self) -> None:
        if self._doc.id is None or self._dirty:
            res = QMessageBox.question(
                self,
                "Save required",
                "Please save the document before sending for approval. Save now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if res == QMessageBox.Yes:
                self.save()
            else:
                return

        if self._doc.id is None:
            return

        try:
            self._doc = self._workflow.send_for_approval(self._doc)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._dirty = False
        self._sync_action_visibility()
        self._update_status()
        self._refresh_chain_label()
        self.saved.emit()

    def approve(self) -> None:
        if self._doc.assigned_to != self._current_user.id:
            QMessageBox.warning(self, "Not allowed", "This document is not assigned to you.")
            return
        try:
            self._doc = self._workflow.approve(self._doc)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._dirty = False
        self._sync_action_visibility()
        self._update_status()
        self._refresh_chain_label()
        self.saved.emit()

    def reject(self) -> None:
        if self._doc.assigned_to != self._current_user.id:
            QMessageBox.warning(self, "Not allowed", "This document is not assigned to you.")
            return
        try:
            self._doc = self._workflow.reject(self._doc)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._dirty = False
        self._sync_action_visibility()
        self._update_status()
        self._refresh_chain_label()
        self.saved.emit()

    def _reload_comments(self) -> None:
        self._comments_list.clear()
        if self._doc.id is None:
            return

        try:
            comments = self._comments.list_comments(self._doc.id)
        except Exception:
            return

        for c in comments:
            u = self._workflow.get_user(c.user_id)
            name = str(c.user_id) if u is None else u.name
            self._comments_list.addItem(f"{c.timestamp} - {name}: {c.comment}")

    def add_comment(self) -> None:
        if self._doc.id is None:
            QMessageBox.warning(self, "Comments", "Save the document before adding comments.")
            return

        text = self._comment_input.text().strip()
        if not text:
            return

        try:
            self._comments.add_comment(document_id=self._doc.id, user_id=self._current_user.id, comment=text)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._comment_input.clear()
        self._reload_comments()
