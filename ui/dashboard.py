from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.document import Document
from models.user import User
from services.workflow_service import WorkflowService
from ui.editor import EditorWindow


@dataclass(frozen=True)
class _RowRef:
    doc_id: int


class DashboardWindow(QMainWindow):
    def __init__(self, workflow: WorkflowService, current_user: User) -> None:
        super().__init__()

        self._workflow = workflow
        self._current_user = current_user

        self.setWindowTitle(f"Dashboard - {current_user.name} ({current_user.role})")
        self.resize(1100, 700)

        root = QWidget(self)
        self.setCentralWidget(root)

        self._created_table = self._make_table()
        self._pending_table = self._make_table()

        self._new_btn = QPushButton("New Document")
        self._refresh_btn = QPushButton("Refresh")

        self._new_btn.clicked.connect(self._new_document)
        self._refresh_btn.clicked.connect(self.refresh)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self._new_btn)
        top_bar.addWidget(self._refresh_btn)
        top_bar.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(top_bar)

        layout.addWidget(QLabel("My Created Documents"))
        layout.addWidget(self._created_table)

        layout.addWidget(QLabel("Pending for Me"))
        layout.addWidget(self._pending_table)

        root.setLayout(layout)

        self._created_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._created_table))
        self._pending_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._pending_table))

        self.refresh()

    def _make_table(self) -> QTableWidget:
        table = QTableWidget(0, 4, self)
        table.setHorizontalHeaderLabels(["ID", "Title", "Status", "Assigned To"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnHidden(0, True)
        return table

    def refresh(self) -> None:
        created = self._workflow.my_created_documents(self._current_user.id)
        pending = self._workflow.pending_for_me(self._current_user.id)

        self._fill_table(self._created_table, created)
        self._fill_table(self._pending_table, pending, highlight_pending=True)

    def _assignee_label(self, assigned_to: Optional[int]) -> str:
        if assigned_to is None:
            return ""

        user = self._workflow.get_user(assigned_to)
        if user is None:
            return str(assigned_to)
        return f"{user.name} ({user.role})"

    def _fill_table(self, table: QTableWidget, docs: list[Document], *, highlight_pending: bool = False) -> None:
        table.setRowCount(0)
        for doc in docs:
            row = table.rowCount()
            table.insertRow(row)

            id_item = QTableWidgetItem(str(doc.id))
            id_item.setData(Qt.UserRole, _RowRef(doc_id=int(doc.id)))

            title_item = QTableWidgetItem(doc.title)
            status_item = QTableWidgetItem(doc.status)
            assigned_to_item = QTableWidgetItem(self._assignee_label(doc.assigned_to))

            if highlight_pending and doc.status == "Pending":
                for item in (title_item, status_item, assigned_to_item):
                    item.setBackground(QColor(255, 248, 204))

            table.setItem(row, 0, id_item)
            table.setItem(row, 1, title_item)
            table.setItem(row, 2, status_item)
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
            try:
                return int(item.text())
            except ValueError:
                return None
        return ref.doc_id

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
