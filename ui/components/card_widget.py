from typing import Optional

from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class CardWidget(QFrame):
    def __init__(self, title: str, value: str = "0", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("Card")

        self._title = QLabel(title, self)
        self._title.setObjectName("CardTitle")

        self._value = QLabel(value, self)
        self._value.setObjectName("CardValue")

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addStretch(1)
        self.setLayout(layout)

    def set_value(self, value: str) -> None:
        self._value.setText(value)
