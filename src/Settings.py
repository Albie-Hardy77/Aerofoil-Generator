from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QLineEdit, QTabWidget
from PySide6.QtCore import Qt, QTimer

import Storage
import Styles
from TitleBar import install_title_bar, TITLE_BAR_HEIGHT


class SettingsWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()

        self.parent_window = main_window

        install_title_bar(self, "Settings")
        self.setFixedSize(800, 920 + TITLE_BAR_HEIGHT)
        self.setStyleSheet(Styles.WINDOW_STYLE)

        self.keys = Storage.SETTING_KEYS
        self.values = Storage.load_settings()
        self.input_default_values = [str(Storage.DEFAULT_SETTINGS[key]) for key in self.keys]
        self.setting_valid_ranges = [Storage.SETTING_RANGES[key] for key in self.keys]
        self.last_changed_setting_index = -1

        self.setting_inputs = [QLineEdit(str(self.values[key])) for key in self.keys]
        self.setting_error_labels = [QLabel() for _ in self.keys]
        self.setting_reset_buttons = [QPushButton("Reset") for _ in self.keys]

        # Main Layout Setup
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        self.setCentralWidget(main_widget)
        main_widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        main_widget.setLayout(main_layout)

        # Subtitle Bar Setup
        subtitle_bar = QHBoxLayout()

        version_label = QLabel(Styles.APP_VERSION)
        version_label.setStyleSheet(Styles.text_style(Styles.GREY, 16, background=True))

        subtitle_bar.setContentsMargins(10, 0, 10, 0)
        subtitle_bar.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(subtitle_bar)

        # Title Setup
        title_label = QLabel("SETTINGS")
        title_label.setStyleSheet(Styles.text_style(Styles.WHITE, 72, background=True))

        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Program Description Setup
        program_description = QLabel("Customise generator settings")
        program_description.setStyleSheet(Styles.text_style(Styles.GREY, 24, background=True))

        main_layout.addWidget(program_description, alignment=Qt.AlignmentFlag.AlignCenter)

        # Main Window Seperator
        seperator = QFrame()
        seperator.setFrameShape(QFrame.Shape.HLine)
        seperator.setFrameShadow(QFrame.Shadow.Plain)
        seperator.setFixedSize(750, 3)
        seperator.setStyleSheet(f"background-color:{Styles.GREY}; color:{Styles.GREY};")

        main_layout.addSpacing(10)
        main_layout.addWidget(seperator, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(10)

        # Settings Tabs Setup
        tabs = QTabWidget()
        tabs.setStyleSheet(Styles.tab_style())

        general_page, general_layout = QWidget(), QVBoxLayout()
        wing_page, wing_layout = QWidget(), QVBoxLayout()
        for page, page_layout in ((general_page, general_layout), (wing_page, wing_layout)):
            page_layout.setContentsMargins(15, 15, 15, 0)
            page.setLayout(page_layout)
            page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        tabs.addTab(general_page, "General")
        tabs.addTab(wing_page, "Wing")
        main_layout.addWidget(tabs, stretch=10)

        self.build_setting(0, "Aerofoil Resolution",
                           "Percentage of the 1000-point maximum. Lower values may increase performance.",
                           "1 - 100", "%", general_layout)
        self.build_setting(3, "3D Wireframe Density",
                           "Density level of the lines connecting the two cross-sections in the 3D view.",
                           "1 - 5", "/5", general_layout)
        self.build_setting(1, "Root Chord Length",
                           "Chord length at the wing root (and of exported profiles), in millimetres.",
                           "10 - 1000", "mm", wing_layout)
        self.build_setting(4, "Tip Chord Length",
                           "Chord length at the wing tip, in millimetres. Smaller than the root gives a tapered wing.",
                           "10 - 1000", "mm", wing_layout)
        self.build_setting(2, "Semi-span",
                           "Root to tip length of the 3D view and STEP model, in mm. The full span is twice this.",
                           "10 - 1000", "mm", wing_layout)
        self.build_setting(5, "Leading Edge Sweep",
                           "Backward sweep of the leading edge, in degrees. Negative values sweep forward.",
                           "-60 - 60", "°", wing_layout)
        self.build_setting(6, "Tip Twist",
                           "Rotation of the tip about its quarter chord, in degrees. Negative is washout (nose down).",
                           "-20 - 20", "°", wing_layout)

        saved_label = QLabel("Settings are saved automatically and restored the next time you open the program.")
        saved_label.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 14))
        saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(saved_label)

    def build_setting(self, index, title, sub_title, placeholder, unit, settings_layout):
        title_label = QLabel(title)
        title_label.setStyleSheet(Styles.text_style(Styles.TEXT, 22))

        sub_label = QLabel(sub_title)
        sub_label.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 14))

        setting_input = self.setting_inputs[index]
        setting_input.setPlaceholderText(placeholder)
        setting_input.setFixedSize(110, 40)
        setting_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setting_input.setStyleSheet(Styles.LINE_EDIT_STYLE)
        # Enter or clicking away (another box, a button, a tab, the background) applies the value
        setting_input.editingFinished.connect(lambda i=index: self.commit_setting(i))

        unit_label = QLabel(unit)
        unit_label.setStyleSheet(Styles.text_style(Styles.GREY, 20))

        reset_button = self.setting_reset_buttons[index]
        reset_button.setFixedSize(80, 40)
        reset_button.setStyleSheet(Styles.outline_button_style(Styles.GREY, 16, radius=5, border=2, padding=6))
        reset_button.clicked.connect(lambda checked=False, i=index: self.reset_setting(i))

        error_label = self.setting_error_labels[index]
        self.change_error_label_style("Error", error_label)

        row = QHBoxLayout()
        row.setContentsMargins(8, 6, 8, 6)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        row.addWidget(setting_input, stretch=0)
        row.addWidget(unit_label, stretch=0)
        row.addSpacing(8)
        row.addWidget(error_label, alignment=Qt.AlignmentFlag.AlignLeft, stretch=1)
        row.addWidget(reset_button, stretch=0)

        background = QFrame()
        background.setStyleSheet(f"background-color:{Styles.PANEL};")
        background.setLayout(row)

        settings_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop, stretch=0)
        settings_layout.addWidget(sub_label, alignment=Qt.AlignmentFlag.AlignTop, stretch=0)
        settings_layout.addSpacing(8)
        settings_layout.addWidget(background)
        settings_layout.addSpacing(12)

    def reset_setting(self, index):
        self.setting_inputs[index].setText(self.input_default_values[index])
        self.commit_setting(index)

    def commit_setting(self, index):
        if self.setting_inputs[index].text() == str(self.values[self.keys[index]]):
            self.setting_inputs[index].clearFocus()
            return

        self.last_changed_setting_index = index
        error_label = self.setting_error_labels[index]
        error_label.setText("")
        self.change_error_label_style("Error", error_label)

        if self.verify_setting_input():
            self.values[self.keys[index]] = int(self.setting_inputs[index].text())
            Storage.save_settings(self.values)
            self.parent_window.apply_settings(self.values)
        else:
            self.setting_inputs[index].setText(str(self.values[self.keys[index]]))

        self.setting_inputs[index].clearFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self.centralWidget().setFocus()

    @staticmethod
    def change_error_label_style(style, error_label):
        if style == "Error":
            error_label.setStyleSheet(f"color:{Styles.RED}; font-family:Arial; font-size:14px; font-weight:bold;")
        elif style == "Success":
            error_label.setStyleSheet(f"color:{Styles.GREEN}; font-family:Arial; font-size:14px; font-weight:bold;")

    def verify_setting_input(self):
        focused_setting = self.setting_inputs[self.last_changed_setting_index]
        focused_error_label = self.setting_error_labels[self.last_changed_setting_index]
        lower_bound, upper_bound = self.setting_valid_ranges[self.last_changed_setting_index]

        try:
            if not (lower_bound <= int(focused_setting.text()) <= upper_bound):
                focused_error_label.setText(f"Choice must be within the range: {lower_bound} - {upper_bound}")
                QTimer.singleShot(1250, lambda: focused_error_label.setText(""))
                return False

            self.change_error_label_style("Success", focused_error_label)
            focused_error_label.setText("Applied & Saved")
            QTimer.singleShot(1250, lambda: focused_error_label.setText(""))
            return True

        except ValueError:
            focused_error_label.setText(f"Choice must be an integer within the range: {lower_bound} - {upper_bound}")
            QTimer.singleShot(1250, lambda: focused_error_label.setText(""))
            return False