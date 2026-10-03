from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QColor

import Styles


class NacaInput(QLineEdit):
    """Line edit that shows 00000 as its placeholder, with the optional fifth digit in a dimmer shade."""

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.text():
            return

        painter = QPainter(self)
        painter.setFont(self.font())
        metrics = painter.fontMetrics()

        x = (self.width() - metrics.horizontalAdvance("00000")) / 2
        y = (self.height() + metrics.ascent() - metrics.descent()) / 2 - 1

        painter.setPen(QColor(Styles.LIGHT_GREY))
        painter.drawText(QPointF(x, y), "0000")
        painter.setPen(QColor(Styles.PRESSED))
        painter.drawText(QPointF(x + metrics.horizontalAdvance("0000"), y), "0")