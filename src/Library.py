from pathlib import Path

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
                               QListWidget, QListWidgetItem, QLineEdit, QFileDialog)
from PySide6.QtCore import Qt, QTimer

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

import Storage
import Styles
from TitleBar import install_title_bar, TITLE_BAR_HEIGHT
from AerofoilGeometryMaths import AerofoilMaths
from AerodynamicMaths import AerodynamicMaths


class LibraryWindow(QMainWindow):
    def __init__(self, generator_window):
        super().__init__()

        self.generator_window = generator_window
        self.entries = {}

        install_title_bar(self, "Collection")
        self.setFixedSize(1100, 900 + TITLE_BAR_HEIGHT)
        self.setStyleSheet(Styles.WINDOW_STYLE)

        # Main Layout Setup
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        self.setCentralWidget(main_widget)
        main_widget.setLayout(main_layout)

        # Subtitle Bar Setup
        subtitle_bar = QHBoxLayout()

        version_label = QLabel(Styles.APP_VERSION)
        version_label.setStyleSheet(Styles.text_style(Styles.GREY, 16, background=True))

        subtitle_bar.setContentsMargins(10, 0, 10, 0)
        subtitle_bar.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(subtitle_bar)

        # Title Setup
        title_label = QLabel("COLLECTION")
        title_label.setStyleSheet(Styles.text_style(Styles.WHITE, 72, background=True))

        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Program Description Setup
        self.description_label = QLabel("Your saved aerofoils")
        self.description_label.setStyleSheet(Styles.text_style(Styles.GREY, 24, background=True))

        main_layout.addWidget(self.description_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Seperator
        seperator = QFrame()
        seperator.setFrameShape(QFrame.Shape.HLine)
        seperator.setFrameShadow(QFrame.Shadow.Plain)
        seperator.setFixedSize(1000, 3)
        seperator.setStyleSheet(f"background-color:{Styles.GREY}; color:{Styles.GREY};")

        main_layout.addSpacing(10)
        main_layout.addWidget(seperator, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(10)

        # Body Layout
        body_layout = QHBoxLayout()
        main_layout.addLayout(body_layout, stretch=1)

        edge_margin = 50 - main_layout.contentsMargins().left()
        body_layout.setContentsMargins(edge_margin, 0, edge_margin, 0)

        # Saved Aerofoil List
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(380)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color:{Styles.PANEL}; color:{Styles.TEXT}; border-radius:5px;
                border-width:2px; border-color:{Styles.GREY}; border-style:solid;
                font-family:Arial; font-size:20px; font-weight:bold; outline:0;
            }}
            QListWidget::item {{ padding:10px; border-bottom:1px solid {Styles.RAISED}; }}
            QListWidget::item:hover {{ background-color:{Styles.RAISED}; }}
            QListWidget::item:selected {{ background-color:{Styles.RAISED}; color:{Styles.TEAL}; }}
        """)
        self.list_widget.currentItemChanged.connect(self.selection_changed)
        self.list_widget.itemDoubleClicked.connect(lambda item: self.load_clicked())

        body_layout.addWidget(self.list_widget)

        # Preview Layout
        preview_layout = QVBoxLayout()
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        body_layout.addLayout(preview_layout, stretch=1)

        self.fig = Figure(figsize=(6.4, 2.4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setFixedSize(640, 240)
        self.fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        self.style_axes()

        preview_layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.name_label = QLabel("")
        self.name_label.setStyleSheet(Styles.text_style(Styles.WHITE, 32))
        preview_layout.addWidget(self.name_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.detail_labels = [QLabel("") for _ in range(4)]
        for detail_label in self.detail_labels:
            detail_label.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 16))
            preview_layout.addWidget(detail_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        preview_layout.addSpacing(8)

        # Name and Notes
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name")
        self.name_input.setMaxLength(60)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes (optional)")
        self.notes_input.setMaxLength(200)

        for line_edit in (self.name_input, self.notes_input):
            line_edit.setFixedHeight(40)
            line_edit.setStyleSheet(Styles.LINE_EDIT_STYLE)
            line_edit.returnPressed.connect(self.save_changes_clicked)
            preview_layout.addWidget(line_edit)

        preview_layout.addSpacing(10)

        # Buttons
        self.load_button = QPushButton("Open")
        self.compare_button = QPushButton("Compare")
        self.save_button = QPushButton("Save changes")
        self.delete_button = QPushButton("Delete")
        self.import_button = QPushButton("Import")
        self.export_button = QPushButton("Export")

        tooltips = {self.load_button: "Open this aerofoil in the generator",
                    self.compare_button: "Overlay this aerofoil on the generator's 2D view and in the analysis window",
                    self.save_button: "Save the name and notes",
                    self.delete_button: "Remove this aerofoil from the collection",
                    self.import_button: "Add the aerofoils from a collection file",
                    self.export_button: "Save the whole collection to a file to back it up or share it"}

        first_row = QHBoxLayout()
        second_row = QHBoxLayout()
        for row, buttons in ((first_row, [(self.load_button, Styles.TEAL), (self.compare_button, Styles.AMBER),
                                          (self.delete_button, Styles.RED)]),
                             (second_row, [(self.save_button, Styles.GREEN), (self.import_button, Styles.PINK),
                                           (self.export_button, Styles.PINK)])):
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for button, colour in buttons:
                button.setFixedSize(180, 56)
                button.setToolTip(tooltips[button])
                button.setStyleSheet(Styles.outline_button_style(colour, 22))
                row.addWidget(button)

        preview_layout.addLayout(first_row)
        preview_layout.addLayout(second_row)

        self.load_button.clicked.connect(self.load_clicked)
        self.compare_button.clicked.connect(self.compare_clicked)
        self.save_button.clicked.connect(self.save_changes_clicked)
        self.delete_button.clicked.connect(self.delete_clicked)
        self.import_button.clicked.connect(self.import_clicked)
        self.export_button.clicked.connect(self.export_clicked)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(Styles.text_style(Styles.GREEN, 14))
        preview_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.PlotMaths = AerofoilMaths()
        self.PlotMaths.set_resolution(500)
        self.AeroMaths = AerodynamicMaths(self.PlotMaths)

        self.refresh_list()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_list()

    def style_axes(self):
        self.fig.patch.set_facecolor(Styles.BACKGROUND)
        self.ax.patch.set_facecolor(Styles.PANEL)

        for side in ("top", "bottom", "left", "right"):
            self.ax.spines[side].set_color(Styles.TEXT)
            self.ax.spines[side].set_linewidth(2)

        self.ax.set_xticks([])
        self.ax.set_yticks([])

    def theme_changed(self):
        self.selection_changed(self.list_widget.currentItem(), None)

    def refresh_list(self):
        selected = self.current_id()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        library = Storage.load_library()
        self.entries = {entry["id"]: entry for entry in library}

        for entry in library:
            subtitle = entry["notes"] if entry["notes"] else entry["saved"]
            item = QListWidgetItem(f"{entry['name']}\n{subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self.list_widget.addItem(item)

            if entry["id"] == selected:
                self.list_widget.setCurrentItem(item)

        self.list_widget.blockSignals(False)

        count = len(library)
        self.description_label.setText(f"{count} saved aerofoil{'s' if count != 1 else ''}" if count
                                       else "No saved aerofoils yet")
        self.list_widget.setToolTip("Double-click an aerofoil to open it in the generator")

        if self.list_widget.currentItem() is None and count:
            self.list_widget.setCurrentRow(0)

        self.selection_changed(self.list_widget.currentItem(), None)

    def current_id(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def current_entry(self):
        return self.entries.get(self.current_id())

    def selection_changed(self, current, previous):
        has_selection = current is not None

        for widget in (self.load_button, self.compare_button, self.save_button, self.delete_button,
                       self.name_input, self.notes_input):
            widget.setEnabled(has_selection)

        self.ax.clear()
        self.style_axes()

        if not has_selection:
            self.name_label.setText("")
            self.name_input.setText("")
            self.notes_input.setText("")
            for detail_label in self.detail_labels:
                detail_label.setText("")
            self.canvas.draw()
            return

        entry = self.entries[current.data(Qt.ItemDataRole.UserRole)]

        try:
            maths = AerofoilMaths.from_entry(entry, 500)
        except (ValueError, KeyError):
            self.name_label.setText(entry["name"])
            self.name_input.setText(entry["name"])
            self.notes_input.setText(entry["notes"])
            for detail_label in self.detail_labels:
                detail_label.setText("")
            self.detail_labels[0].setText("This profile couldn't be read")
            self.canvas.draw()
            return

        self.PlotMaths = maths
        self.AeroMaths = AerodynamicMaths(maths)
        xu, yu, xl, yl = maths.calculate_coordinates()

        self.ax.plot(xu, yu, color=Styles.TEXT)
        self.ax.plot(xl, yl, color=Styles.TEXT)
        self.ax.set_aspect("equal", adjustable="datalim")
        self.canvas.draw()

        self.name_label.setText(entry["name"])
        self.name_input.setText(entry["name"])
        self.notes_input.setText(entry["notes"])

        self.detail_labels[0].setText(
            "Symmetric aerofoil" if maths.is_symmetric
            else f"Max camber {maths.m * 100:.1f}% at {maths.p * 100:.0f}% chord")
        self.detail_labels[1].setText(
            f"Max thickness {maths.t * 100:.1f}% at {maths.max_thickness_position() * 100:.0f}% chord")
        self.detail_labels[2].setText(f"Zero lift angle {self.AeroMaths.calculate_zero_lift_angle_of_attack():.2f}°")
        self.detail_labels[3].setText(f"Ideal lift coefficient {self.AeroMaths.calculate_ideal_lift_coefficient():.3f}"
                                      + ("  ·  imported profile" if maths.is_custom else ""))

    def show_message(self, text, error=False):
        self.status_label.setStyleSheet(Styles.text_style(Styles.RED if error else Styles.GREEN, 14))
        self.status_label.setText(text)
        QTimer.singleShot(2500, lambda: self.status_label.setText(""))

    def load_clicked(self):
        entry = self.current_entry()
        if entry:
            self.generator_window.load_entry(entry)
            self.generator_window.show()
            self.generator_window.raise_()

    def compare_clicked(self):
        entry = self.current_entry()
        if entry:
            self.generator_window.set_comparison(entry)
            self.show_message(f"Comparing against {entry['name']}")

    def save_changes_clicked(self):
        identifier = self.current_id()
        if identifier:
            saved = Storage.update_entry(identifier, name=self.name_input.text(), notes=self.notes_input.text())
            self.refresh_list()
            self.show_message("Saved" if saved else "Couldn't write the library file", error=not saved)

    def delete_clicked(self):
        entry = self.current_entry()
        if entry:
            removed = Storage.remove_entry(entry["id"])
            self.refresh_list()
            self.show_message(f"{entry['name']} removed" if removed else "Couldn't write the library file", error=not removed)

    def import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import collection", "", "Collection files (*.json)")
        if not path:
            return

        try:
            added, skipped = Storage.import_library(path)
            self.refresh_list()
            self.show_message(f"Added {added}, skipped {skipped} already in the collection")
        except ValueError as e:
            self.show_message(str(e), error=True)

    def export_clicked(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export collection", str(Path.home() / "aerofoil_collection.json"),
                                              "Collection files (*.json)")
        if path:
            try:
                Storage.export_library(path)
                self.show_message("Collection exported")
            except OSError as e:
                self.show_message(f"Export failed: {e}", error=True)