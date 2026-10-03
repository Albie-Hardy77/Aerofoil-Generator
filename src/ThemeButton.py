from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPolygonF, QColor, QPen

import Styles

SIZE = 44
RADIUS = 7


class ThemeButton(QPushButton):
    """A square split along its '/' diagonal: the window colour bottom-right, three accent strips top-left."""

    def __init__(self, name, theme, parent=None):
        super().__init__(parent)

        self.theme_name = name
        self.theme = theme
        self.selected = False
        self.hovered = False

        self.setFixedSize(SIZE, SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)
        self.setStyleSheet("QPushButton {background:transparent; border:none; margin:0px; padding:0px;}")

    def set_selected(self, selected):
        self.selected = selected
        self.update()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def half_plane(offset, size):
        # Everything on the side of the line x - y = offset that contains the top-right corner
        k = 2 * size
        path = QPainterPath()
        path.addPolygon(QPolygonF([QPointF(offset - k, -k), QPointF(offset + k, k),
                                   QPointF(offset + 3 * k, k), QPointF(offset + 3 * k, -k)]))
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = float(self.width())
        inset = 2.0
        rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)

        shape = QPainterPath()
        shape.addRoundedRect(rect, RADIUS, RADIUS)

        # Bottom diagonal: the theme's window colour
        painter.fillPath(shape, QColor(self.theme["background"]))

        # Top diagonal: three strips running the opposite way to the split
        triangle = QPainterPath()
        triangle.addPolygon(QPolygonF([QPointF(0, 0), QPointF(size, 0), QPointF(0, size)]))
        triangle.closeSubpath()
        top_half = shape.intersected(triangle)

        painter.fillPath(top_half, QColor(self.theme["pink"]))
        # The strip edges sit at +/- 0.1835 of the side so that all three strips have the same area
        painter.fillPath(top_half.intersected(self.half_plane(-0.1835 * size, size)), QColor(self.theme["amber"]))
        painter.fillPath(top_half.intersected(self.half_plane(0.1835 * size, size)), QColor(self.theme["teal"]))

        # Outline: bright when selected, lighter on hover
        if self.selected:
            pen = QPen(QColor(Styles.TEXT), 2.5)
        elif self.hovered:
            pen = QPen(QColor(Styles.HOVER), 2)
        else:
            pen = QPen(QColor(Styles.GREY), 1.5)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, RADIUS, RADIUS)