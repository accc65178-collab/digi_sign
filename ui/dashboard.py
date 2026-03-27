from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.document import Document
from models.user import User
from services.comment_service import CommentService
from services.workflow_service import WorkflowService
from ui.admin_panel import AdminPanelDialog
from ui.editor import EditorWindow
from ui.components.card_widget import CardWidget
from ui.components.sidebar import Sidebar, default_nav_items
from ui.components.table_widget import TableWidget
from ui.components.topbar import TopBar


@dataclass(frozen=True)
class _RowRef:
    doc_id: int


class DashboardWindow(QMainWindow):
    def __init__(self, workflow: WorkflowService, comment_service: CommentService, current_user: User) -> None:
        super().__init__()

        self._workflow = workflow
        self._comments = comment_service
        self._current_user = current_user

        self.setWindowTitle(f"Dashboard - {current_user.username} ({current_user.role})")
        self.resize(1100, 700)

        root = QWidget(self)
        root.setObjectName("AppShell")
        self.setCentralWidget(root)

        self._sidebar = Sidebar(default_nav_items(), self)
        self._sidebar.nav_changed.connect(self._on_nav_changed)

        self._topbar = TopBar(f"{current_user.username} ({current_user.role})", self)
        self._topbar.logout_requested.connect(self._logout)
        self._topbar.admin_requested.connect(self._open_admin)
        self._topbar.search_changed.connect(self._on_search_changed)
        self._topbar.set_admin_visible(current_user.role == "Admin")

        self._stack = QStackedWidget(self)

        self._dashboard_page = self._build_dashboard_page()
        self._my_docs_page = self._build_table_page("My Documents")
        self._pending_page = self._build_table_page("Pending Approvals")
        self._completed_page = self._build_table_page("Completed Documents")

        self._stack.addWidget(self._dashboard_page)
        self._stack.addWidget(self._my_docs_page)
        self._stack.addWidget(self._pending_page)
        self._stack.addWidget(self._completed_page)

        right = QWidget(self)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._topbar)
        right_layout.addWidget(self._stack, 1)
        right.setLayout(right_layout)

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar)
        shell.addWidget(right, 1)
        root.setLayout(shell)

        self._my_docs_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._my_docs_table))
        self._pending_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._pending_table))
        self._completed_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._completed_table))
        self._recent_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._recent_table))

        self._sidebar.set_active("dashboard")
        self.refresh()

    def _make_table(self) -> QTableWidget:
        return TableWidget(["Title", "Status", "Current Step", "Assigned To"], self)

    def _build_table_page(self, title: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        header = QWidget(self)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(QLabel(title))
        header_layout.addStretch(1)
        if title == "My Documents":
            btn = QPushButton("New Document", self)
            btn.setObjectName("ButtonPrimary")
            btn.clicked.connect(self._new_document)
            header_layout.addWidget(btn)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.setObjectName("ButtonSecondary")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        header.setLayout(header_layout)

        table = self._make_table()
        empty = QLabel("", self)
        empty.setObjectName("EmptyState")
        empty.setAlignment(Qt.AlignCenter)

        layout.addWidget(header)
        layout.addWidget(table, 1)
        layout.addWidget(empty)
        page.setLayout(layout)

        if title == "My Documents":
            self._my_docs_table = table
            self._my_docs_empty = empty
        elif title == "Pending Approvals":
            self._pending_table = table
            self._pending_empty = empty
        else:
            self._completed_table = table
            self._completed_empty = empty

        return page

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Dashboard", self)
        title.setObjectName("PageTitle")

        cards = QWidget(self)
        cards_layout = QHBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)
        self._total_card = CardWidget("Total Documents", "0", self)
        self._pending_card = CardWidget("Pending Approvals", "0", self)
        self._approved_card = CardWidget("Approved", "0", self)
        cards_layout.addWidget(self._total_card)
        cards_layout.addWidget(self._pending_card)
        cards_layout.addWidget(self._approved_card)
        cards.setLayout(cards_layout)

        recent_header = QWidget(self)
        recent_header_layout = QHBoxLayout()
        recent_header_layout.setContentsMargins(0, 0, 0, 0)
        recent_header_layout.addWidget(QLabel("Recent Activity"))
        recent_header_layout.addStretch(1)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.setObjectName("ButtonSecondary")
        refresh_btn.clicked.connect(self.refresh)
        recent_header_layout.addWidget(refresh_btn)
        recent_header.setLayout(recent_header_layout)

        self._recent_table = self._make_table()
        self._recent_empty = QLabel("", self)
        self._recent_empty.setObjectName("EmptyState")
        self._recent_empty.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(cards)
        layout.addSpacing(6)
        layout.addWidget(recent_header)
        layout.addWidget(self._recent_table, 1)
        layout.addWidget(self._recent_empty)
        page.setLayout(layout)
        return page

    def _set_empty_state(self, table: QTableWidget, label: QLabel, message: str) -> None:
        has_rows = table.rowCount() > 0
        label.setVisible(not has_rows)
        if not has_rows:
            label.setText(message)

    def refresh(self) -> None:
        created = self._workflow.my_created_documents(self._current_user.id)
        pending = self._workflow.pending_for_me(self._current_user.id)

        completed = [d for d in created if d.status in ("Approved", "Rejected")]
        my_docs = [d for d in created if d.status not in ("Approved", "Rejected")]

        pending_count = sum(1 for d in pending if d.status == "Pending")
        self._sidebar.set_badge("pending", pending_count)

        all_docs = created + pending
        total = len({d.id for d in all_docs if d.id is not None})
        approved = sum(1 for d in all_docs if d.status == "Approved")

        self._total_card.set_value(str(total))
        self._pending_card.set_value(str(pending_count))
        self._approved_card.set_value(str(approved))

        self._fill_table(self._my_docs_table, my_docs)
        self._fill_table(self._pending_table, pending, highlight_pending=True)
        self._fill_table(self._completed_table, completed)

        recent = (pending + created)[:]
        recent.sort(key=lambda d: (d.id or 0), reverse=True)
        self._fill_table(self._recent_table, recent[:10], highlight_pending=True)

        self._set_empty_state(self._my_docs_table, self._my_docs_empty, "No documents found")
        self._set_empty_state(self._pending_table, self._pending_empty, "No pending approvals")
        self._set_empty_state(self._completed_table, self._completed_empty, "No completed documents")
        self._set_empty_state(self._recent_table, self._recent_empty, "No recent activity")

    def _assignee_label(self, assigned_to: Optional[int]) -> str:
        if assigned_to is None:
            return ""

        user = self._workflow.get_user(assigned_to)
        if user is None:
            return str(assigned_to)
        return f"{user.username} ({user.role})"

    def _fill_table(self, table: QTableWidget, docs: list[Document], *, highlight_pending: bool = False) -> None:
        table.setRowCount(0)
        for doc in docs:
            row = table.rowCount()
            table.insertRow(row)

            title_item = QTableWidgetItem(doc.title)
            title_item.setData(Qt.UserRole, _RowRef(doc_id=int(doc.id)))
            status_item = QTableWidgetItem(doc.status)
            step_item = QTableWidgetItem(str(doc.current_step + 1) if doc.status == "Pending" else "-")
            assigned_to_item = QTableWidgetItem(self._assignee_label(doc.assigned_to))

            if highlight_pending and doc.status == "Pending":
                for item in (title_item, status_item, step_item, assigned_to_item):
                    item.setBackground(QColor(255, 248, 204))

            table.setItem(row, 0, title_item)
            table.setItem(row, 1, status_item)
            table.setItem(row, 2, step_item)
            table.setItem(row, 3, assigned_to_item)

        table.resizeColumnsToContents()

    def _selected_doc_id(self, table: QTableWidget) -> Optional[int]:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        ref = item.data(Qt.UserRole)
        if ref is None:
            return None
        return ref.doc_id

    def _on_nav_changed(self, key: str) -> None:
        mapping = {
            "dashboard": 0,
            "my_docs": 1,
            "pending": 2,
            "completed": 3,
        }
        index = mapping.get(key)
        if index is not None:
            self._stack.setCurrentIndex(index)

    def _on_search_changed(self, text: str) -> None:
        table = self._current_table()
        if table is None:
            return
        query = text.strip().lower()
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            title = "" if item is None else item.text().lower()
            table.setRowHidden(row, bool(query) and query not in title)

    def _current_table(self) -> Optional[QTableWidget]:
        idx = self._stack.currentIndex()
        if idx == 0:
            return self._recent_table
        if idx == 1:
            return self._my_docs_table
        if idx == 2:
            return self._pending_table
        if idx == 3:
            return self._completed_table
        return None

    def _logout(self) -> None:
        self.close()

    def _open_admin(self) -> None:
        if self._current_user.role != "Admin":
            return
        dlg = AdminPanelDialog(self._workflow, self)
        dlg.exec_()
        self.refresh()

    def _open_selected(self, table: QTableWidget) -> None:
        doc_id = self._selected_doc_id(table)
        if doc_id is None:
            return

        doc = self._workflow.get_document(doc_id)
        if doc is None:
            QMessageBox.warning(self, "Not found", "Document no longer exists.")
            self.refresh()
            return

        editor = EditorWindow(self._workflow, self._comments, self._current_user, doc)
        editor.saved.connect(self.refresh)
        editor.show()

    def _new_document(self) -> None:
        editor = EditorWindow(self._workflow, self._comments, self._current_user, None)
        editor.saved.connect(self.refresh)
        editor.show()
