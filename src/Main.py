import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, QEvent

import Storage
import Styles
from TitleBar import install_title_bar, TITLE_BAR_HEIGHT
from ThemeButton import ThemeButton
from Generator import GeneratorWindow
from Library import LibraryWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.generator_window = GeneratorWindow()
        self.library_window = LibraryWindow(self.generator_window)
        self.generator_window.library_window = self.library_window

        install_title_bar(self, "Aerofoil Generator")
        self.setFixedSize(1000, 640 + TITLE_BAR_HEIGHT)
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
        title_label = QLabel("AEROFOIL GENERATOR")
        title_label.setStyleSheet(Styles.text_style(Styles.WHITE, 72, background=True))

        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Program Description Setup
        program_description = QLabel("A NACA 4 and 5-digit aerofoil profile generator")
        program_description.setStyleSheet(Styles.text_style(Styles.GREY, 24, background=True))

        main_layout.addWidget(program_description, alignment=Qt.AlignmentFlag.AlignCenter)

        # Main Window Seperator
        seperator = QFrame()
        seperator.setFrameShape(QFrame.Shape.HLine)
        seperator.setFrameShadow(QFrame.Shadow.Plain)
        seperator.setFixedSize(900, 3)
        seperator.setStyleSheet(f"background-color:{Styles.GREY}; color:{Styles.GREY};")

        main_layout.addSpacing(10)
        main_layout.addWidget(seperator, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(10)

        # Program Buttons Setup
        button_background = QFrame()
        button_background.setStyleSheet(f"background-color:{Styles.PANEL}; margin:5px")

        frame_layout = QVBoxLayout()
        button_background.setLayout(frame_layout)

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        frame_layout.addLayout(button_layout, stretch=1)

        generator_button = QPushButton("Generator")
        generator_button.clicked.connect(self.generator_button_click)
        generator_button.setFixedSize(295, 100)
        generator_button.setStyleSheet(Styles.outline_button_style(Styles.TEAL, 50, radius=10, border=4))

        self.library_button = QPushButton("Collection")
        self.library_button.clicked.connect(self.library_button_click)
        self.library_button.setFixedSize(295, 100)
        self.library_button.setStyleSheet(Styles.outline_button_style(Styles.TEAL, 50, radius=10, border=4))

        generator_description = QLabel("Build and analyse a profile")
        generator_description.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 16) + "margin:0px;")
        generator_description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.library_description = QLabel("")
        self.library_description.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 16) + "margin:0px;")
        self.library_description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        generator_column = QVBoxLayout()
        generator_column.addWidget(generator_button, alignment=Qt.AlignmentFlag.AlignCenter)
        generator_column.addWidget(generator_description)

        library_column = QVBoxLayout()
        library_column.addWidget(self.library_button, alignment=Qt.AlignmentFlag.AlignCenter)
        library_column.addWidget(self.library_description)

        button_layout.addLayout(generator_column)
        button_layout.addLayout(library_column)

        # Theme Buttons Setup
        theme_layout = QHBoxLayout()
        theme_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        theme_layout.setContentsMargins(10, 0, 0, 10)
        theme_layout.setSpacing(10)

        self.theme_buttons = []
        for name, theme in Styles.THEMES.items():
            theme_button = ThemeButton(name, theme)
            theme_button.clicked.connect(lambda checked=False, theme_name=name: self.apply_theme(theme_name))
            theme_layout.addWidget(theme_button)
            self.theme_buttons.append(theme_button)

        frame_layout.addLayout(theme_layout)

        main_layout.addWidget(button_background, stretch=10)

        # Footer
        footer_label = QLabel("Thin aerofoil theory  ·  Panel method  ·  Annotated 2D view  ·  3D wing  ·  STEP, DXF and coordinate export")
        footer_label.setStyleSheet(Styles.text_style(Styles.GREY, 14))
        main_layout.addWidget(footer_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.update_library_description()

        # Every window is built in the default theme, then recoloured to the saved one
        saved_theme = Storage.load_theme_name()
        if saved_theme in Styles.THEMES and saved_theme != Styles.DEFAULT_THEME:
            self.apply_theme(saved_theme)
        else:
            self.update_theme_buttons()


    def themed_windows(self):
        return [self, self.generator_window, self.generator_window.settings_window, self.generator_window.analysis_window,
                self.library_window]

    def apply_theme(self, name):
        Styles.switch_theme(name, self.themed_windows())

        self.generator_window.theme_changed()
        self.library_window.theme_changed()
        self.update_theme_buttons()

    def update_theme_buttons(self):
        for theme_button in self.theme_buttons:
            theme_button.set_selected(theme_button.theme_name == Styles.current_theme_name())

    def update_library_description(self):
        count = len(Storage.load_library())
        self.library_description.setText("No saved aerofoils" if count == 0
                                         else f"{count} saved aerofoil{'s' if count != 1 else ''}")

    def changeEvent(self, event):
        super().changeEvent(event)

        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.update_library_description()

    def closeEvent(self, event):
        self.generator_window.settings_window.close()
        self.generator_window.analysis_window.close()
        self.generator_window.close()
        self.library_window.close()
        super().closeEvent(event)

    def generator_button_click(self):
        self.generator_window.show()
        self.generator_window.raise_()

    def library_button_click(self):
        self.library_window.show()
        self.library_window.raise_()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())