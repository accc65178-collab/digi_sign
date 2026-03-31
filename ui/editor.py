from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QTextCharFormat
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.document import Document, _load_ref_body_html
from models.user import User
from services.comment_service import CommentService
from services.workflow_service import WorkflowService
from ui.components.comment_widget import CommentWidget
from ui.components.signature_widget import SignatureWidget


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
            self._users_combo.addItem(u.display_label(), u.id)

        from PyQt5.QtWidgets import QListWidget

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
        label = str(user_id) if u is None else u.display_label()
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


class _LetterPreviewDialog(QDialog):
    def __init__(self, doc: Document, parent=None) -> None:
        super().__init__(parent)
        self._doc = doc
        self.setWindowTitle("Letter Preview")
        self.setModal(True)
        self.resize(800, 900)

        # Build HTML for preview (header + subject + body)
        header_path = Path(__file__).resolve().parents[1] / "documents" / "header.png"
        header_html = ""
        if header_path.exists():
            header_html = f"<div style='text-align:center; margin-bottom:12px;'><img src='{header_path.as_uri()}' style='max-width:100%; height:auto;'/></div>"

        subject_html = f"<div style='margin-bottom:12px;'><b>Subject:</b> {doc.subject}</div>"
        body_html = doc.content or ""
        full_html = f"<html><body>{header_html}{subject_html}{body_html}</body></html>"

        self._preview = QTextEdit(self)
        self._preview.setAcceptRichText(True)
        self._preview.setHtml(full_html)
        self._preview.setReadOnly(True)

        self._save_pdf_btn = QPushButton("Save PDF", self)
        self._save_pdf_btn.clicked.connect(self._save_pdf)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._save_pdf_btn)

        layout = QVBoxLayout()
        layout.addWidget(self._preview)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _save_pdf(self) -> None:
        out_dir = Path.home() / "Documents"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = (self._doc.title or "Untitled").strip().replace("\\", "_").replace("/", "_")
        out_path = out_dir / f"{safe_title}.pdf"

        # Rebuild HTML for export (same as preview)
        header_path = Path(__file__).resolve().parents[1] / "documents" / "header.png"
        header_html = ""
        if header_path.exists():
            header_html = f"<div style='text-align:center; margin-bottom:12px;'><img src='{header_path.as_uri()}' style='max-width:100%; height:auto;'/></div>"
        subject_html = f"<div style='margin-bottom:12px;'><b>Subject:</b> {self._doc.subject}</div>"
        body_html = self._doc.content or ""
        full_html = f"<html><body>{header_html}{subject_html}{body_html}</body></html>"

        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtPrintSupport import QPrinter

        doc_export = QTextDocument()
        doc_export.setHtml(full_html)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(out_path))
        printer.setPageMargins(12, 12, 12, 12, QPrinter.Millimeter)
        doc_export.print_(printer)

        QMessageBox.information(self, "Saved", f"PDF saved to:\n{out_path}")


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
            subject="",
            content=_load_ref_body_html(),
            created_by=current_user.id,
            status="Draft",
            assigned_to=None,
            current_step=0,
        )
        self._dirty = False

        self._pending_chain_user_ids: List[int] = []

        self.setWindowTitle(self._window_title())
        self.resize(1000, 700)
        self.setWindowState(Qt.WindowMaximized)

        self._header_label = QLabel(self)
        self._header_label.setAlignment(Qt.AlignHCenter)
        self._header_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._header_label.setMinimumHeight(60)
        self._header_label.setMaximumHeight(150)
        header_path = Path(__file__).resolve().parents[1] / "documents" / "header.png"
        if header_path.exists():
            pm = QPixmap(str(header_path))
            self._header_pixmap = pm
            self._header_label.setPixmap(pm)
        else:
            self._header_pixmap = QPixmap()
            self._header_label.setText("")

        self._title = QLineEdit(self)
        self._title.setText(self._doc.title)

        self._subject = QLineEdit(self)
        self._subject.setText(getattr(self._doc, 'subject', ''))
        self._subject.setPlaceholderText("Enter subject")

        self._editor = QTextEdit(self)
        self._editor.setAcceptRichText(True)
        self._editor.setHtml(self._doc.content or "")
        self._editor.setStyleSheet("background: #f8f9fa; color: #000000;")
        # Force document text color
        self._editor.document().setDefaultStyleSheet("body { color: #000000; }")

        self._title.textChanged.connect(self._on_changed)
        self._subject.textChanged.connect(self._on_changed)
        self._editor.textChanged.connect(self._on_changed)

        self._create_toolbar()

        self._save_btn = QPushButton("Save")
        self._view_btn = QPushButton("View Letter")
        self._delete_btn = QPushButton("Delete")
        self._chain_btn = QPushButton("Approval Chain")
        self._send_btn = QPushButton("Send for Approval")
        self._approve_btn = QPushButton("Approve")
        self._reject_btn = QPushButton("Reject")

        self._save_btn.clicked.connect(self.save)
        self._view_btn.clicked.connect(self._view_letter)
        self._delete_btn.clicked.connect(self._delete_document)
        self._chain_btn.clicked.connect(self.configure_chain)
        self._send_btn.clicked.connect(self.send_for_approval)
        self._approve_btn.clicked.connect(self.approve)
        self._reject_btn.clicked.connect(self.reject)

        btn_bar = QHBoxLayout()
        btn_bar.addWidget(self._save_btn)
        btn_bar.addWidget(self._view_btn)
        btn_bar.addWidget(self._delete_btn)
        btn_bar.addWidget(self._chain_btn)
        btn_bar.addWidget(self._send_btn)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self._approve_btn)
        btn_bar.addWidget(self._reject_btn)

        self._chain_label = QLabel("Approval: (not configured)")
        self._chain_label.setObjectName("SectionTitle")

        self._signature = SignatureWidget(self)
        self._signature.signed.connect(self.sign_and_approve)

        self._comment_widget = CommentWidget(self._on_comment_added, self)
        self._comment_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        form = QFormLayout()
        form.addRow("Title:", self._title)
        form.addRow("Subject:", self._subject)

        body_label = QLabel("Body")
        body_label.setObjectName("SectionTitle")

        left = QWidget(self)
        left_layout = QVBoxLayout()
        left_layout.addLayout(form)
        left_layout.addWidget(self._header_label)
        left_layout.addWidget(body_label)
        left_layout.addWidget(self._editor)
        left_layout.addLayout(btn_bar)
        left.setLayout(left_layout)

        right = QWidget(self)
        right.setFixedWidth(340)
        right_layout = QVBoxLayout()
        right_layout.addWidget(self._chain_label)
        right_layout.addWidget(self._signature)
        right_layout.addWidget(self._comment_widget)
        right.setLayout(right_layout)

        root = QWidget(self)
        main_layout = QHBoxLayout()
        main_layout.addWidget(left, 1)
        main_layout.addWidget(right)
        root.setLayout(main_layout)
        self.setCentralWidget(root)

        self.statusBar()
        self._sync_action_visibility()
        self._update_status()
        self._refresh_chain_label()
        self._reload_comments()
        self._refresh_signature_info()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._header_pixmap.isNull():
            return
        # Limit max width to keep image crisp and professional
        max_w = 600
        w = min(max_w, max(1, self._header_label.width()))
        scaled = self._header_pixmap.scaledToWidth(w, Qt.SmoothTransformation)
        self._header_label.setPixmap(scaled)

    def _export_pdf_to_pc(self) -> None:
        # Export a PDF to the user's Documents folder.
        out_dir = Path.home() / "Documents"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = (self._doc.title or "Untitled").strip().replace("\\", "_").replace("/", "_")
        out_path = out_dir / f"{safe_title}.pdf"

        header_path = Path(__file__).resolve().parents[1] / "documents" / "header.png"
        header_html = ""
        if header_path.exists():
            header_html = f"<div style='text-align:center; margin-bottom:12px;'><img src='{header_path.as_uri()}' style='max-width:100%; height:auto;'/></div>"

        subject_html = f"<div style='margin-bottom:12px;'><b>Subject:</b> {self._doc.subject}</div>"
        body_html = self._doc.content or ""

        full_html = f"<html><body>{header_html}{subject_html}{body_html}</body></html>"

        from PyQt5.QtGui import QTextDocument

        doc = QTextDocument()
        doc.setHtml(full_html)

        from PyQt5.QtPrintSupport import QPrinter

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(out_path))
        printer.setPageMargins(12, 12, 12, 12, QPrinter.Millimeter)
        doc.print_(printer)

    def _view_letter(self) -> None:
        # Sync current UI values into the document model for preview/export
        self._sync_doc_from_ui()
        dlg = _LetterPreviewDialog(self._doc, self)
        dlg.exec_()

    def _delete_document(self) -> None:
        if self._doc.id is None:
            QMessageBox.information(self, "Info", "This document has not been saved yet.")
            return
        reply = QMessageBox.question(
            self,
            "Delete Document",
            f"Are you sure you want to delete '{self._doc.title}'?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self._workflow.delete_document(self._doc.id)
            QMessageBox.information(self, "Deleted", "Document deleted successfully.")
            self.saved.emit()
            self.close()
        except Exception as exc:
            QMessageBox.critical(self, "Delete failed", str(exc))

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
            assigned = str(self._doc.assigned_to) if u is None else f"{u.username} ({u.role})"
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

        self._approve_btn.setEnabled(can_decide)
        self._reject_btn.setEnabled(can_decide)
        self._signature.set_enabled(can_decide)
        self._refresh_signature_info()

    def _refresh_signature_info(self) -> None:
        if self._doc.id is None:
            self._signature.set_info_text("Save the document to enable signing")
            return

        if self._doc.status != "Pending":
            self._signature.set_info_text(f"Signing available when status is Pending (current: {self._doc.status})")
            return

        if self._doc.assigned_to is None:
            self._signature.set_info_text("No approver assigned")
            return

        assignee = self._workflow.get_user(self._doc.assigned_to)
        assignee_label = str(self._doc.assigned_to) if assignee is None else assignee.display_label()
        if self._doc.assigned_to == self._current_user.id:
            self._signature.set_info_text(f"You can sign as {assignee_label}")
        else:
            self._signature.set_info_text(f"Only {assignee_label} can sign this step")

    def _refresh_chain_label(self) -> None:
        if self._doc.id is None:
            if not self._pending_chain_user_ids:
                self._chain_label.setText("Approval: (not configured)")
                return
            names = []
            for uid in self._pending_chain_user_ids:
                u = self._workflow.get_user(uid)
                names.append(str(uid) if u is None else u.display_label())
            self._chain_label.setText("Approval: " + " → ".join(names))
            return

        chain = self._workflow.get_approval_chain(self._doc.id)
        if not chain:
            self._chain_label.setText("Approval: (not configured)")
            return

        parts = []
        for step in chain:
            u = self._workflow.get_user(step.user_id)
            name = str(step.user_id) if u is None else u.display_label()
            label = f"{name}"
            if step.step_order == self._doc.current_step and self._doc.status == "Pending":
                label += " (current)"
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
        self._doc.subject = self._subject.text().strip()
        self._doc.content = self._editor.toHtml()

    def save(self) -> None:
        self._sync_doc_from_ui()

        try:
            self._doc = self._workflow.save_document(self._doc)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        try:
            self._export_pdf_to_pc()
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

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

        res = QMessageBox.question(
            self,
            "Approve",
            "Approve this step and move to the next approver?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if res != QMessageBox.Yes:
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

        res = QMessageBox.question(
            self,
            "Reject",
            "Reject this document?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
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
        lines: List[str] = []
        if self._doc.id is None:
            self._comment_widget.set_comments(lines)
            self._comment_widget.set_add_enabled(False)
            return

        try:
            comments = self._comments.list_comments(self._doc.id)
        except Exception:
            self._comment_widget.set_comments(lines)
            return

        for c in comments:
            u = self._workflow.get_user(c.user_id)
            name = str(c.user_id) if u is None else u.username
            lines.append(f"{c.timestamp} - {name}: {c.comment}")

        self._comment_widget.set_comments(lines)
        self._comment_widget.set_add_enabled(True)

    def _on_comment_added(self, text: str) -> None:
        if self._doc.id is None:
            QMessageBox.warning(self, "Comments", "Save the document before adding comments.")
            return

        try:
            self._comments.add_comment(document_id=self._doc.id, user_id=self._current_user.id, comment=text)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._reload_comments()

    def sign_and_approve(self) -> None:
        if self._doc.id is None:
            QMessageBox.warning(self, "Sign", "Save the document before signing.")
            return

        if not (self._doc.status == "Pending" and self._doc.assigned_to == self._current_user.id):
            QMessageBox.warning(self, "Sign", "You can only sign documents assigned to you.")
            return

        res = QMessageBox.question(
            self,
            "Sign",
            "Add your digital signature and approve this step?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if res != QMessageBox.Yes:
            return

        signature_html = SignatureWidget.signature_html(user_name=self._current_user.username)
        self._editor.moveCursor(self._editor.textCursor().End)
        self._editor.insertHtml(signature_html)
        self._sync_doc_from_ui()
        self.save()
        if self._doc.assigned_to == self._current_user.id and self._doc.status == "Pending":
            self.approve()
