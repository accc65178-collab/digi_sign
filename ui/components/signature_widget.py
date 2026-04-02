from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class SignatureWidget(QWidget):
    signed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._info = QLabel("Not signed")
        self._info.hide()
        self._btn = QPushButton("Sign")
        self._btn.clicked.connect(self.signed.emit)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(self._btn)
        layout.addStretch(1)
        self.setLayout(layout)

    def set_enabled(self, enabled: bool) -> None:
        self._btn.setEnabled(enabled)

    def set_info_text(self, text: str) -> None:
        # Info text is intentionally hidden in the UI.
        if self._info.isVisible():
            self._info.setText(text)

    @staticmethod
    def signature_html(*, user_name: str) -> str:
        _ = datetime.now()  # keep import stable; no text should be inserted into letter
        _ = user_name
        return ""
