from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor

import Styles

TITLE_BAR_HEIGHT = 32
BUTTON_WIDTH = 46


class TitleButton(QPushButton):
    """A flat window button drawn by hand: kind is 'minimise', 'maximise', 'restore' or 'close'."""

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.hovered = False

        self.setFixedSize(BUTTON_WIDTH, TITLE_BAR_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton {background:transparent; border:none; margin:0px; padding:0px;}")
        self.setToolTip({"minimise": "Minimise", "maximise": "Maximise", "restore": "Restore", "close": "Close"}[kind])

    def set_kind(self, kind):
        self.kind = kind
        self.setToolTip({"minimise": "Minimise", "maximise": "Maximise", "restore": "Restore", "close": "Close"}[kind])
        self.update()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.hovered:
            painter.fillRect(self.rect(), QColor(Styles.RED if self.kind == "close" else Styles.RAISED))

        if self.hovered and self.kind == "close":
            colour = QColor(Styles.BACKGROUND)
        else:
            colour = QColor(Styles.TEXT if self.hovered else Styles.LIGHT_GREY)

        painter.setPen(QPen(colour, 1.5))
        cx, cy, s = self.width() / 2, self.height() / 2, 5.0

        if self.kind == "minimise":
            painter.drawLine(QPointF(cx - s, cy), QPointF(cx + s, cy))
        elif self.kind == "maximise":
            painter.drawRect(QRectF(cx - s, cy - s, 2 * s, 2 * s))
        elif self.kind == "restore":
            painter.drawRect(QRectF(cx - s, cy - s + 3, 2 * s - 3, 2 * s - 3))
            painter.drawPolyline([QPointF(cx - s + 3, cy - s + 3), QPointF(cx - s + 3, cy - s), QPointF(cx + s, cy - s),
                                  QPointF(cx + s, cy + s - 3), QPointF(cx + s - 3, cy + s - 3)])
        else:
            painter.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
            painter.drawLine(QPointF(cx - s, cy + s), QPointF(cx + s, cy - s))


class TitleBar(QWidget):
    """Replaces the native title bar: drag to move, minimise and close (and maximise where allowed)."""

    def __init__(self, window, maximisable=False):
        super().__init__()
        self.target = window
        self.maximisable = maximisable
        self.drag_offset = None

        self.setObjectName("titleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"#titleBar {{ background-color:{Styles.DARK}; }}")
        self.setFixedHeight(TITLE_BAR_HEIGHT)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        layout.addStretch(1)

        self.minimise_button = TitleButton("minimise")
        self.minimise_button.clicked.connect(window.showMinimized)
        layout.addWidget(self.minimise_button)

        self.maximise_button = None
        if maximisable:
            self.maximise_button = TitleButton("maximise")
            self.maximise_button.clicked.connect(window.toggle_maximise)
            layout.addWidget(self.maximise_button)

        self.close_button = TitleButton("close")
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.close_button)

    def set_maximised(self, maximised):
        if self.maximise_button is not None:
            self.maximise_button.set_kind("restore" if maximised else "maximise")

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.target.isMaximized():
            return

        handle = self.target.windowHandle()
        if handle is not None and handle.startSystemMove():
            return

        self.drag_offset = event.globalPosition().toPoint() - self.target.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.target.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None

    def mouseDoubleClickEvent(self, event):
        if self.maximisable and event.button() == Qt.MouseButton.LeftButton:
            self.target.toggle_maximise()


def install_title_bar(window, title, maximisable=False):
    """Hides the native title bar and puts a TitleBar at the top of the window."""
    window.setWindowTitle(title)
    window.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinimizeButtonHint)

    bar = TitleBar(window, maximisable)
    window.setMenuWidget(bar)
    window.title_bar = bar

    return bar