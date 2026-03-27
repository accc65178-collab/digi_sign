from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QTableWidget, QWidget


class TableWidget(QTableWidget):
    def __init__(self, columns: list[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(0, len(columns), parent)
        self.setHorizontalHeaderLabels(columns)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_empty_message(self, message: str) -> None:
        self.setProperty("emptyMessage", message)
        self.style().unpolish(self)
        self.style().polish(self)
