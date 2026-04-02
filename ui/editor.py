from __future__ import annotations

import html
import base64
import io
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QFont, QPixmap, QTextCharFormat, QTextDocument, QPainter, QPen, QColor, QImage, QTextTableFormat, QTextLength
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
    QCheckBox,
    QSpinBox,
    QSizePolicy,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from models.document import Document, _load_ref_body_html
from models.user import User
from services.comment_service import CommentService
from services.workflow_service import WorkflowService
from ui.components.comment_widget import CommentWidget
from ui.components.signature_widget import SignatureWidget


def _build_ref_and_date(*, workflow: WorkflowService, doc: Document, user: User) -> tuple[str, str]:
    created_at = (getattr(doc, "created_at", "") or "").strip()
    dt: datetime
    try:
        dt = datetime.fromisoformat(created_at) if created_at else datetime.now()
    except Exception:
        dt = datetime.now()
    date_str = dt.strftime("%d/%m/%Y")
    day = dt.strftime("%d")
    yy = dt.strftime("%y")
    iso_date = dt.strftime("%Y-%m-%d")
    seq = workflow.daily_sequence_for_document(document_id=getattr(doc, "id", None), iso_date=iso_date)
    dept = (getattr(user, "department", "") or "").strip() or "DEPT"
    lab = (getattr(user, "lab", "") or "").strip() or "LAB"
    dept = dept.replace("/", "-")
    lab = lab.replace("/", "-")
    ref_value = f"NECOP/{dept}/{lab}/{day}{yy}-{day}{seq:02d}"
    return ref_value, date_str


def _is_signature_artifact_line(line: str) -> bool:
    s = (line or "").strip().lower()
    if not s:
        return False
    if s.startswith("approved by"):
        return True
    if s.startswith("timestamp:"):
        return True
    return False


class _HtmlBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: List[dict] = []
        self._in_table = False
        self._in_tr = False
        self._in_td = False
        self._cur_p: List[str] = []
        self._cur_table: List[List[str]] = []
        self._cur_row: List[str] = []
        self._cur_cell: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        t = (tag or "").lower()
        if t == "table":
            self._flush_p()
            self._in_table = True
            self._cur_table = []
            return
        if self._in_table:
            if t == "tr":
                self._in_tr = True
                self._cur_row = []
                return
            if t in ("td", "th"):
                self._in_td = True
                self._cur_cell = []
                return
            if t == "br" and self._in_td:
                self._cur_cell.append("\n")
                return
            return

        if t == "br":
            self._cur_p.append("\n")
            return

    def handle_endtag(self, tag: str) -> None:
        t = (tag or "").lower()
        if t == "table":
            if self._cur_table:
                self.items.append({"type": "table", "rows": self._cur_table})
            self._in_table = False
            self._in_tr = False
            self._in_td = False
            self._cur_table = []
            self._cur_row = []
            self._cur_cell = []
            return

        if self._in_table:
            if t in ("td", "th") and self._in_td:
                cell = "".join(self._cur_cell).strip()
                self._cur_row.append(cell)
                self._in_td = False
                self._cur_cell = []
                return
            if t == "tr" and self._in_tr:
                self._cur_table.append(list(self._cur_row))
                self._in_tr = False
                self._cur_row = []
                return
            return

        if t in ("p", "div"):
            self._flush_p()
            return

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if self._in_table and self._in_td:
            self._cur_cell.append(data)
            return
        self._cur_p.append(data)

    def close(self) -> None:
        self._flush_p()
        super().close()

    def _flush_p(self) -> None:
        txt = "".join(self._cur_p).strip()
        if txt:
            self.items.append({"type": "p", "text": txt})
        self._cur_p = []


def _html_to_docx_items(body_html: str) -> List[dict]:
    p = _HtmlBodyParser()
    p.feed(body_html or "")
    p.close()
    return p.items


def _filtered_lines_from_text(text: str, username_set: set[str]) -> List[str]:
    out: List[str] = []
    for ln in (text or "").splitlines():
        if _is_signature_artifact_line(ln):
            continue
        if username_set and ln.strip().lower() in username_set:
            continue
        out.append(ln)
    return out


class _SignatureCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._img = QImage(520, 180, QImage.Format_ARGB32)
        self._img.fill(Qt.white)
        self._last: Optional[QPoint] = None
        self.setMinimumSize(520, 180)

    def clear(self) -> None:
        self._img.fill(Qt.white)
        self.update()

    def to_png_bytes(self) -> bytes:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        self._img.save(buf, "PNG")
        return bytes(ba.data())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.drawImage(0, 0, self._img)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._last = event.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._last is None:
            return
        p = QPainter(self._img)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(self._last, event.pos())
        self._last = event.pos()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._last = None


class _SignatureDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signature")
        self.setModal(True)
        self.resize(600, 360)

        self._mode_draw = QPushButton("Draw with Mouse")
        self._mode_upload = QPushButton("Upload Image")

        self._canvas = _SignatureCanvas(self)
        self._upload_label = QLabel("No image selected")
        self._upload_label.setWordWrap(True)
        self._uploaded_png: Optional[bytes] = None

        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._canvas.clear)

        self._mode = "draw"
        self._mode_draw.setEnabled(False)
        self._mode_upload.clicked.connect(self._set_mode_upload)
        self._mode_draw.clicked.connect(self._set_mode_draw)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        top = QHBoxLayout()
        top.addWidget(self._mode_draw)
        top.addWidget(self._mode_upload)
        top.addStretch(1)

        upload_row = QHBoxLayout()
        upload_row.addWidget(self._browse_btn)
        upload_row.addWidget(self._upload_label, 1)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self._canvas)
        layout.addWidget(self._clear_btn)
        layout.addLayout(upload_row)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self._apply_mode_visibility()

    def _set_mode_draw(self) -> None:
        self._mode = "draw"
        self._mode_draw.setEnabled(False)
        self._mode_upload.setEnabled(True)
        self._apply_mode_visibility()

    def _set_mode_upload(self) -> None:
        self._mode = "upload"
        self._mode_upload.setEnabled(False)
        self._mode_draw.setEnabled(True)
        self._apply_mode_visibility()

    def _apply_mode_visibility(self) -> None:
        is_draw = self._mode == "draw"
        self._canvas.setVisible(is_draw)
        self._clear_btn.setVisible(is_draw)
        self._browse_btn.setVisible(not is_draw)
        self._upload_label.setVisible(not is_draw)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select signature image", str(Path.home()), "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, "Signature", "Failed to load image")
            return
        # Normalize to PNG bytes
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        self._uploaded_png = bytes(ba.data())
        self._upload_label.setText(path)

    def signature_png_bytes(self) -> Optional[bytes]:
        if self._mode == "upload":
            return self._uploaded_png
        # draw
        return self._canvas.to_png_bytes()


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
    def __init__(self, workflow: WorkflowService, current_user: User, doc: Document, parent=None) -> None:
        super().__init__(parent)
        self._workflow = workflow
        self._current_user = current_user
        self._doc = doc
        self.setWindowTitle("Letter Preview")
        self.setModal(True)
        self.resize(800, 900)

        # Build HTML for preview (header + ref/date + subject + body + initiator)
        header_path = Path(__file__).resolve().parents[1] / "documents" / "header.png"
        header_html = ""
        if header_path.exists():
            header_html = f"<div style='text-align:center; margin-bottom:24px;'><img src='{header_path.as_uri()}' style='max-width:600px; height:auto;'/></div>"

        # REF#/Date line (REF# left, Date right on same line)
        ref_value, date_str = _build_ref_and_date(workflow=self._workflow, doc=self._doc, user=self._current_user)
        ref_html = f"<div style='margin:0 auto; max-width:600px; margin-bottom:12px; display:flex; justify-content:space-between;'><span>REF#: {ref_value}</span><span>Date:{date_str}</span></div>"

        subject_html = f"<div style='margin:0 auto; max-width:600px; margin-bottom:12px;'><b>Subject:</b> {html.escape(doc.subject or '')}</div>"

        qt_doc = QTextDocument()
        qt_doc.setHtml(doc.content or "")
        body_text = qt_doc.toPlainText()
        try:
            username_set = {
                (u.username or "").strip().lower() for u in (self._workflow.list_users() or []) if getattr(u, "username", None)
            }
        except Exception:
            username_set = set()
        body_lines = []
        for ln in body_text.splitlines():
            s = ln.strip()
            if not s:
                body_lines.append("")
                continue
            if _is_signature_artifact_line(s):
                continue
            if username_set and s.lower() in username_set:
                continue
            body_lines.append(ln)
        safe_body_html = "<br>".join(html.escape(ln) for ln in body_lines)
        body_html = f"<div style='margin:0 auto; max-width:600px; white-space:normal;'>{safe_body_html}</div>"

        # Initiator name and designation at the end, right-aligned (use original creator)
        initiator_user = self._workflow.get_user(self._doc.created_by) if self._doc.created_by else self._current_user
        initiator_name = getattr(initiator_user, "full_name", "").strip() or getattr(initiator_user, "name", "").strip()
        initiator_designation = getattr(initiator_user, "designation", "").strip()
        initiator_html = ""
        if initiator_name:
            initiator_html = "<div style='margin:0 auto; max-width:600px; margin-top:24px; text-align:right;'>"
            initiator_html += f"{initiator_name}<br>"
            if initiator_designation:
                initiator_html += f"{initiator_designation}"
            initiator_html += "</div>"

        # Approval chain designations + signatures, left-aligned with line spacing
        approvers_html = ""
        try:
            chain = self._workflow.get_approval_chain(self._doc.id) if self._doc.id else []
            rows = []
            for step in chain:
                u = self._workflow.get_user(int(step.user_id))
                if u is None:
                    continue
                desig = (getattr(u, "designation", "") or "").strip()
                if desig:
                    img_html = ""
                    sig = getattr(step, "signature_png", None)
                    if sig:
                        b64 = base64.b64encode(sig).decode("ascii")
                        img_html = f"<img src='data:image/png;base64,{b64}' style='height:40px; width:auto; vertical-align:middle;'/>"
                    rows.append(
                        "<div style='display:flex; align-items:center; gap:12px; margin-bottom:12px;'>"
                        f"{img_html}<span>{html.escape(desig)}</span>"
                        "</div>"
                    )

            if rows:
                approvers_html = "<div style='margin:0 auto; max-width:600px; margin-top:24px;'>" + "".join(rows) + "</div>"
        except Exception:
            pass

        full_html = f"<html><body style='font-family:Arial; padding:20px;'>{header_html}{ref_html}{subject_html}{body_html}{initiator_html}{approvers_html}</body></html>"

        self._preview = QTextEdit(self)
        self._preview.setAcceptRichText(True)
        self._preview.setHtml(full_html)
        self._preview.setReadOnly(True)

        self._save_pdf_btn = QPushButton("Save letter", self)
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
        out_path = out_dir / f"{safe_title}.docx"

        template_path = Path(__file__).resolve().parents[1] / "documents" / "REF.docx"
        if not template_path.exists():
            QMessageBox.critical(self, "Template missing", f"Template file not found:\n{template_path}")
            return

        import traceback

        try:
            import docx
            from docx.shared import Inches

            # Load the template
            doc = docx.Document(str(template_path))

            # Remove all existing body paragraphs from the template (keep header/footer)
            for paragraph in list(doc.paragraphs):
                p = paragraph._element
                p.getparent().remove(p)

            ref_value, date_str = _build_ref_and_date(workflow=self._workflow, doc=self._doc, user=self._current_user)
            from docx.enum.text import WD_TAB_ALIGNMENT
            # One-line gap after header (template header is in header section)
            doc.add_paragraph()
            ref_p = doc.add_paragraph()
            ref_p.add_run(f"REF#: {ref_value}")
            ref_p.add_run("\t")
            ref_p.add_run(f"Date:{date_str}")
            try:
                section = doc.sections[0]
                tab_pos = section.page_width - section.right_margin
                ref_p.paragraph_format.tab_stops.add_tab_stop(tab_pos, WD_TAB_ALIGNMENT.RIGHT)
            except Exception:
                ref_p.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT)

            # Add subject
            subject_p = doc.add_paragraph()
            subject_p.add_run("Subject: ").bold = True
            subject_p.add_run(self._doc.subject or "")

            try:
                username_set = {
                    (u.username or "").strip().lower()
                    for u in (self._workflow.list_users() or [])
                    if getattr(u, "username", None)
                }
            except Exception:
                username_set = set()

            items = _html_to_docx_items(self._doc.content or "")
            for it in items:
                if it.get("type") == "p":
                    for line in _filtered_lines_from_text(str(it.get("text") or ""), username_set):
                        doc.add_paragraph(line)
                elif it.get("type") == "table":
                    rows = it.get("rows") or []
                    if not rows:
                        continue
                    cols = max((len(r) for r in rows), default=0)
                    if cols <= 0:
                        continue
                    t = doc.add_table(rows=len(rows), cols=cols)
                    try:
                        t.style = "Table Grid"
                    except Exception:
                        pass
                    for r_idx, r in enumerate(rows):
                        for c_idx in range(cols):
                            val = "" if c_idx >= len(r) else str(r[c_idx] or "")
                            val = "\n".join(_filtered_lines_from_text(val, username_set))
                            t.cell(r_idx, c_idx).text = val
                    doc.add_paragraph()

            # Add initiator name and designation at the end, right-aligned (use original creator)
            initiator_user = self._workflow.get_user(self._doc.created_by) if self._doc.created_by else self._current_user
            initiator_name = getattr(initiator_user, "full_name", "").strip() or getattr(initiator_user, "name", "").strip()
            initiator_designation = getattr(initiator_user, "designation", "").strip()
            if initiator_name:
                doc.add_paragraph()
                name_p = doc.add_paragraph(initiator_name)
                name_p.paragraph_format.alignment = WD_TAB_ALIGNMENT.RIGHT
                if initiator_designation:
                    desig_p = doc.add_paragraph(initiator_designation)
                    desig_p.paragraph_format.alignment = WD_TAB_ALIGNMENT.RIGHT

            # Add approval chain designations (configured approvers) + signatures
            try:
                chain = self._workflow.get_approval_chain(self._doc.id) if self._doc.id else []
                if chain:
                    doc.add_paragraph()
                    for step in chain:
                        u = self._workflow.get_user(int(step.user_id))
                        if u is None:
                            continue
                        desig = (getattr(u, "designation", "") or "").strip()
                        if desig:
                            p = doc.add_paragraph()
                            sig = getattr(step, "signature_png", None)
                            if sig:
                                try:
                                    run = p.add_run()
                                    run.add_picture(io.BytesIO(sig), height=Inches(0.45))
                                    p.add_run("  ")
                                except Exception:
                                    pass
                            p.add_run(desig)
                            doc.add_paragraph()
            except Exception:
                pass

            # Save as DOCX
            doc.save(str(out_path))
            QMessageBox.information(self, "Saved", f"Document saved as DOCX:\n{out_path}")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Export failed", f"Failed to export document:\n{e}")


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
        self._send_btn = QPushButton("Send for Approval")
        self._approve_btn = QPushButton("Approve")
        self._reject_btn = QPushButton("Reject")

        self._save_btn.clicked.connect(self.save)
        self._view_btn.clicked.connect(self._view_letter)
        self._delete_btn.clicked.connect(self._delete_document)
        self._send_btn.clicked.connect(self.send_for_approval)
        self._approve_btn.clicked.connect(self.approve)
        self._reject_btn.clicked.connect(self.reject)

        btn_bar = QHBoxLayout()
        btn_bar.addWidget(self._save_btn)
        btn_bar.addWidget(self._view_btn)
        btn_bar.addWidget(self._delete_btn)
        btn_bar.addWidget(self._send_btn)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self._approve_btn)
        btn_bar.addWidget(self._reject_btn)

        self._chain_label = QLabel("Approval: (not configured)")
        self._chain_label.setObjectName("SectionTitle")
        self._chain_label.hide()

        self._signature = SignatureWidget(self)
        self._signature.signed.connect(self.sign_and_approve)

        self._comment_widget = CommentWidget(self._on_comment_added, self)
        self._comment_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        form = QFormLayout()
        form.addRow("Title:", self._title)
        form.addRow("Subject:", self._subject)

        body_label = QLabel("Body")
        body_label.setObjectName("SectionTitle")

        approval_label = QLabel("Approval Chain")
        approval_label.setObjectName("SectionTitle")

        self._approval_chain_btn = QPushButton("Set Approvers")
        self._approval_chain_btn.clicked.connect(self.configure_chain)

        self._approval_chain_value = QLabel("")
        self._approval_chain_value.setWordWrap(True)

        approval_row = QHBoxLayout()
        approval_row.addWidget(self._approval_chain_btn)
        approval_row.addStretch(1)

        left = QWidget(self)
        left_layout = QVBoxLayout()
        left_layout.addLayout(form)
        left_layout.addWidget(self._header_label)
        left_layout.addWidget(body_label)
        left_layout.addWidget(self._editor)
        left_layout.addWidget(approval_label)
        left_layout.addLayout(approval_row)
        left_layout.addWidget(self._approval_chain_value)
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
        self._refresh_approval_chain_section()
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
        # Export a DOCX to the user's Documents folder using REF.docx as a template.
        out_dir = Path.home() / "Documents"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = (self._doc.title or "Untitled").strip().replace("\\", "_").replace("/", "_")
        out_path = out_dir / f"{safe_title}.docx"

        template_path = Path(__file__).resolve().parents[1] / "documents" / "REF.docx"
        if not template_path.exists():
            QMessageBox.critical(self, "Template missing", f"Template file not found:\n{template_path}")
            return

        import traceback

        try:
            import docx
            from docx.shared import Inches

            # Load the template
            doc = docx.Document(str(template_path))

            # Remove all existing paragraphs from the template (keep header/footer)
            for paragraph in list(doc.paragraphs):
                p = paragraph._element
                p.getparent().remove(p)

            # Also remove any empty paragraphs that might be in headers/footers or sections
            for section in doc.sections:
                # Clear header/footer paragraphs if they are empty
                for header in section.header.paragraphs:
                    if not header.text.strip():
                        h = header._element
                        h.getparent().remove(h)
                for footer in section.footer.paragraphs:
                    if not footer.text.strip():
                        f = footer._element
                        f.getparent().remove(f)

            ref_value, date_str = _build_ref_and_date(workflow=self._workflow, doc=self._doc, user=self._current_user)
            from docx.enum.text import WD_TAB_ALIGNMENT
            # One-line gap after header (template header is in header section)
            doc.add_paragraph()
            ref_p = doc.add_paragraph()
            ref_p.add_run(f"REF#: {ref_value}")
            ref_p.add_run("\t")
            ref_p.add_run(f"Date:{date_str}")
            try:
                section = doc.sections[0]
                tab_pos = section.page_width - section.right_margin
                ref_p.paragraph_format.tab_stops.add_tab_stop(tab_pos, WD_TAB_ALIGNMENT.RIGHT)
            except Exception:
                ref_p.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT)

            # Add subject
            subject_p = doc.add_paragraph()
            subject_p.add_run("Subject: ").bold = True
            subject_p.add_run(self._doc.subject or "")

            try:
                username_set = {
                    (u.username or "").strip().lower()
                    for u in (self._workflow.list_users() or [])
                    if getattr(u, "username", None)
                }
            except Exception:
                username_set = set()

            items = _html_to_docx_items(self._doc.content or "")
            for it in items:
                if it.get("type") == "p":
                    for line in _filtered_lines_from_text(str(it.get("text") or ""), username_set):
                        doc.add_paragraph(line)
                elif it.get("type") == "table":
                    rows = it.get("rows") or []
                    if not rows:
                        continue
                    cols = max((len(r) for r in rows), default=0)
                    if cols <= 0:
                        continue
                    t = doc.add_table(rows=len(rows), cols=cols)
                    try:
                        t.style = "Table Grid"
                    except Exception:
                        pass
                    for r_idx, r in enumerate(rows):
                        for c_idx in range(cols):
                            val = "" if c_idx >= len(r) else str(r[c_idx] or "")
                            val = "\n".join(_filtered_lines_from_text(val, username_set))
                            t.cell(r_idx, c_idx).text = val
                    doc.add_paragraph()

            # Add initiator name and designation at the end, right-aligned (use original creator)
            initiator_user = self._workflow.get_user(self._doc.created_by) if self._doc.created_by else self._current_user
            initiator_name = getattr(initiator_user, "full_name", "").strip() or getattr(initiator_user, "name", "").strip()
            initiator_designation = getattr(initiator_user, "designation", "").strip()
            if initiator_name:
                doc.add_paragraph()
                name_p = doc.add_paragraph(initiator_name)
                name_p.paragraph_format.alignment = WD_TAB_ALIGNMENT.RIGHT
                if initiator_designation:
                    desig_p = doc.add_paragraph(initiator_designation)
                    desig_p.paragraph_format.alignment = WD_TAB_ALIGNMENT.RIGHT

            # Add approval chain designations (configured approvers) + signatures
            try:
                chain = self._workflow.get_approval_chain(self._doc.id) if self._doc.id else []
                if chain:
                    doc.add_paragraph()
                    for step in chain:
                        u = self._workflow.get_user(int(step.user_id))
                        if u is None:
                            continue
                        desig = (getattr(u, "designation", "") or "").strip()
                        if desig:
                            p = doc.add_paragraph()
                            sig = getattr(step, "signature_png", None)
                            if sig:
                                try:
                                    run = p.add_run()
                                    run.add_picture(io.BytesIO(sig), height=Inches(0.45))
                                    p.add_run("  ")
                                except Exception:
                                    pass
                            p.add_run(desig)
                            doc.add_paragraph()  # blank line after each approver
            except Exception:
                pass

            # Save as DOCX
            doc.save(str(out_path))
            QMessageBox.information(self, "Saved", f"Document saved as DOCX:\n{out_path}")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Export failed", f"Failed to export document:\n{e}")

    def _view_letter(self) -> None:
        # Sync current UI values into the document model for preview/export
        self._sync_doc_from_ui()
        dlg = _LetterPreviewDialog(self._workflow, self._current_user, self._doc, self)
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

        insert_table = QAction("Table", self)
        insert_table.triggered.connect(self._insert_table)

        table_size = QAction("Table Size", self)
        table_size.triggered.connect(self._resize_table)

        toolbar.addAction(bold)
        toolbar.addAction(italic)
        toolbar.addAction(underline)
        toolbar.addAction(insert_table)
        toolbar.addAction(table_size)

    def _insert_table(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Insert Table")
        dlg.setModal(True)

        rows = QSpinBox(dlg)
        rows.setMinimum(1)
        rows.setMaximum(50)
        rows.setValue(2)

        cols = QSpinBox(dlg)
        cols.setMinimum(1)
        cols.setMaximum(20)
        cols.setValue(2)

        form = QFormLayout()
        form.addRow("Rows:", rows)
        form.addRow("Columns:", cols)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        dlg.setLayout(layout)

        if dlg.exec_() != QDialog.Accepted:
            return

        cursor = self._editor.textCursor()
        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setCellPadding(2)
        fmt.setCellSpacing(0)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        cursor.insertTable(int(rows.value()), int(cols.value()), fmt)

    def _resize_table(self) -> None:
        cursor = self._editor.textCursor()
        table = cursor.currentTable()
        if table is None:
            QMessageBox.information(self, "Table", "Place the cursor inside a table to resize it.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Table Size")
        dlg.setModal(True)

        width_pct = QSpinBox(dlg)
        width_pct.setMinimum(10)
        width_pct.setMaximum(100)
        width_pct.setValue(100)

        equal_cols = QCheckBox("Equal column widths", dlg)
        equal_cols.setChecked(True)

        form = QFormLayout()
        form.addRow("Table width (%):", width_pct)
        form.addRow("", equal_cols)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        dlg.setLayout(layout)

        if dlg.exec_() != QDialog.Accepted:
            return

        tf = table.format()
        tf.setWidth(QTextLength(QTextLength.PercentageLength, float(width_pct.value())))

        if equal_cols.isChecked():
            cols = table.columns()
            if cols > 0:
                each = 100.0 / float(cols)
                tf.setColumnWidthConstraints(
                    [QTextLength(QTextLength.PercentageLength, each) for _ in range(cols)]
                )

        table.setFormat(tf)

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

    def _refresh_approval_chain_section(self) -> None:
        # Show configured approvers under the body (designation only)
        user_ids: List[int] = []
        if self._doc.id is None:
            user_ids = list(self._pending_chain_user_ids)
        else:
            try:
                chain = self._workflow.get_approval_chain(self._doc.id)
                user_ids = [int(s.user_id) for s in chain]
            except Exception:
                user_ids = []

        desigs: List[str] = []
        for uid in user_ids:
            u = self._workflow.get_user(int(uid))
            if u is None:
                continue
            desig = (getattr(u, "designation", "") or "").strip()
            if desig:
                desigs.append(desig)

        self._approval_chain_value.setText("\n\n".join(desigs))

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
            self._refresh_approval_chain_section()
            return

        try:
            self._workflow.set_approval_chain(document_id=self._doc.id, user_ids_in_order=user_ids)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            return

        self._refresh_approval_chain_section()

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
        self._refresh_approval_chain_section()
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
        self._refresh_approval_chain_section()
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
        self._refresh_approval_chain_section()
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
        self._refresh_approval_chain_section()
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

        dlg = _SignatureDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return

        sig_png = dlg.signature_png_bytes()
        if not sig_png:
            QMessageBox.warning(self, "Sign", "No signature provided")
            return

        try:
            self._workflow.set_approval_step_signature(
                document_id=int(self._doc.id),
                step_order=int(self._doc.current_step),
                signature_png=sig_png,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Sign", f"Failed to save signature:\n{exc}")
            return

        self._sync_doc_from_ui()
        self.save()
        if self._doc.assigned_to == self._current_user.id and self._doc.status == "Pending":
            self.approve()
