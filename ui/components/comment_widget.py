from __future__ import annotations

from typing import Callable, List

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget


class CommentWidget(QWidget):
    def __init__(self, on_add: Callable[[str], None], parent=None) -> None:
        super().__init__(parent)
        self._on_add = on_add

        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Write a review comment...")
        self._add_btn = QPushButton("Add")
        self._add_btn.clicked.connect(self._add_clicked)

        top = QHBoxLayout()
        top.addWidget(self._input)
        top.addWidget(self._add_btn)

        self._list = QListWidget(self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Comments"))
        layout.addLayout(top)
        layout.addWidget(self._list)
        self.setLayout(layout)

    def _add_clicked(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._on_add(text)
        self._input.clear()

    def set_comments(self, lines: List[str]) -> None:
        self._list.clear()
        for line in lines:
            self._list.addItem(line)

    def set_add_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)
