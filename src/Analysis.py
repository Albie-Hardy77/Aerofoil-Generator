import numpy as np

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
                               QPushButton, QLineEdit, QTabWidget, QSlider, QSizePolicy)
from PySide6.QtCore import Qt, QTimer

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

import Flow
import Storage
import Styles
from TitleBar import install_title_bar, TITLE_BAR_HEIGHT
from AerodynamicMaths import AerodynamicMaths
from PanelMethod import solve_panel_method

STALL_ANGLE = 15
FONT = ["Arial", "DejaVu Sans"]

FLOW_RANGES = {"airspeed": (1, 400), "density": (0.05, 2.0), "temperature": (-80, 60), "altitude": (0, 20000)}


class AnalysisWindow(QMainWindow):
    def __init__(self, generator_window):
        super().__init__()

        self.generator = generator_window
        self.flow = Storage.load_flow()

        install_title_bar(self, "Analysis")
        self.setFixedSize(1100, 900 + TITLE_BAR_HEIGHT)
        self.setStyleSheet(Styles.WINDOW_STYLE)

        # Main Layout Setup
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        self.setCentralWidget(main_widget)
        main_widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)      # clicking the background takes the focus from a box
        main_widget.setLayout(main_layout)

        # Subtitle Bar Setup
        subtitle_bar = QHBoxLayout()

        version_label = QLabel(Styles.APP_VERSION)
        version_label.setStyleSheet(Styles.text_style(Styles.GREY, 16, background=True))

        subtitle_bar.setContentsMargins(10, 0, 10, 0)
        subtitle_bar.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(subtitle_bar)

        # Title Setup
        title_label = QLabel("ANALYSIS")
        title_label.setStyleSheet(Styles.text_style(Styles.WHITE, 72, background=True))

        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Program Description Setup
        self.description_label = QLabel("Flow conditions, lift curve, pressure distribution and comparison")
        self.description_label.setStyleSheet(Styles.text_style(Styles.GREY, 22, background=True))

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

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(Styles.tab_style())
        main_layout.addWidget(self.tabs, stretch=1)

        self.build_flow_tab()
        self.build_lift_tab()
        self.build_pressure_tab()
        self.build_compare_tab()

        self.tabs.currentChanged.connect(lambda index: self.refresh())

    # Helpers -------------------------------------------------------------------------------------------------

    @staticmethod
    def label(text, colour=None, size=20):
        label = QLabel(text)
        label.setStyleSheet(Styles.text_style(colour or Styles.WHITE, size, padding=True))
        return label

    @staticmethod
    def result_box(width=130):
        box = QLabel("-")
        box.setStyleSheet(Styles.result_style())
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setFixedWidth(width)
        return box

    @staticmethod
    def make_canvas(width=9.6, height=4.3):
        figure = Figure(figsize=(width, height), dpi=100)
        canvas = FigureCanvasQTAgg(figure)
        canvas.setFixedSize(int(width * 100), int(height * 100))
        return figure, canvas

    @staticmethod
    def style_axes(figure, ax):
        figure.patch.set_facecolor(Styles.PANEL)
        ax.patch.set_facecolor(Styles.BACKGROUND)

        for side in ax.spines.values():
            side.set_color(Styles.GREY)
            side.set_linewidth(1.5)

        ax.tick_params(colors=Styles.LIGHT_GREY, labelsize=9)
        ax.grid(True, color=Styles.RAISED, linewidth=0.8)
        ax.xaxis.label.set_color(Styles.TEXT)
        ax.yaxis.label.set_color(Styles.TEXT)
        figure.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.14)

    @staticmethod
    def legend(ax):
        legend = ax.legend(facecolor=Styles.PANEL, edgecolor=Styles.GREY, labelcolor=Styles.TEXT, fontsize=9)
        return legend

    def profiles(self):
        """(label, maths, colour, linestyle) for the aerofoil on the generator and the comparison aerofoil."""
        g = self.generator
        if not g.has_profile:
            return []

        profiles = [(g.PlotMaths.display_name, g.PlotMaths, Styles.TEAL, "-")]
        if g.comparison is not None:
            profiles.append((g.comparison.display_name, g.comparison, Styles.PINK, "--"))

        return profiles

    def angle(self):
        return self.generator.angle_of_attack_slider.value()

    # Flow tab ------------------------------------------------------------------------------------------------

    def build_flow_tab(self):
        page = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(25, 20, 25, 20)
        page.setLayout(layout)

        inputs = QGridLayout()
        inputs.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addLayout(inputs, stretch=1)

        heading = self.label("Flow conditions", Styles.TEAL, 26)
        inputs.addWidget(heading, 0, 0, 1, 4)
        inputs.setColumnStretch(3, 1)

        self.flow_inputs = {}
        self.flow_error_labels = {}
        definitions = [("airspeed", "Airspeed", "m/s"), ("density", "Air density", "kg/m³"),
                       ("temperature", "Air temperature", "°C"), ("altitude", "Altitude", "m")]

        for index, (key, text, unit) in enumerate(definitions):
            row = 1 + 2 * index

            line_edit = QLineEdit(self.flow_text(key))
            line_edit.setFixedSize(110, 40)
            line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line_edit.setStyleSheet(Styles.LINE_EDIT_STYLE)
            # No validator, as in the settings: Qt doesn't apply a box a validator calls unfinished (such as an
            # empty one), so anything typed is checked when it's applied instead. Enter or clicking away (another box, a button, a tab, the background) applies the value
            line_edit.editingFinished.connect(lambda k=key: self.commit_flow_input(k))
            self.flow_inputs[key] = line_edit

            # The messages are too long to sit beside the box, so each box has a line underneath for them
            error_label = QLabel()
            error_label.setFixedHeight(18)
            self.change_error_label_style("Error", error_label)
            self.flow_error_labels[key] = error_label

            inputs.addWidget(self.label(text + ":"), row, 0)
            inputs.addWidget(line_edit, row, 1)
            inputs.addWidget(self.label(unit, Styles.GREY), row, 2)
            inputs.addWidget(error_label, row + 1, 1, 1, 3)

        self.flow_inputs["altitude"].setToolTip("Only used by the button below to fill in the density and temperature")

        altitude_button = QPushButton("Set from altitude")
        altitude_button.setFixedHeight(50)
        altitude_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        altitude_button.setToolTip("Fills in the density and temperature of the International Standard Atmosphere")
        altitude_button.setStyleSheet(Styles.outline_button_style(Styles.TEAL, 22, border=2))
        altitude_button.clicked.connect(self.set_from_altitude)
        button_row = QVBoxLayout()
        button_row.setContentsMargins(6, 5, 0, 0)     # 6px in line with the labels' text (they have 6px of padding)
        button_row.addWidget(altitude_button)
        inputs.addLayout(button_row, 9, 0, 1, 2)

        self.flow_note = QLabel("")
        self.flow_note.setWordWrap(True)
        self.flow_note.setStyleSheet(Styles.text_style(Styles.AMBER, 14))
        inputs.addWidget(self.flow_note, 10, 0, 1, 4)

        results = QGridLayout()
        results.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addLayout(results, stretch=1)

        results.addWidget(self.label("Results", Styles.TEAL, 26), 0, 0, 1, 2)

        self.flow_results = {}
        result_rows = [("q", "Dynamic pressure (Pa)"), ("a", "Speed of sound (m/s)"), ("mach", "Mach number"),
                       ("re", "Reynolds number"), ("cl", "Section lift coefficient Cl"),
                       ("wing_cl", "Wing lift coefficient CL"), ("lift_span", "Section lift (N per m of span)"),
                       ("lift", "Wing lift force (N)")]
        tooltips = {"re": "Based on the mean aerodynamic chord of the wing",
                    "wing_cl": "Finite wing: lift slope reduced to 2π / (1 + 2/AR)",
                    "lift_span": "2D section lift on the mean aerodynamic chord",
                    "lift": "CL × dynamic pressure × planform area of the whole wing (both halves)"}

        for row, (key, text) in enumerate(result_rows, start=1):
            label = self.label(text + ":")
            box = self.result_box(150)
            label.setToolTip(tooltips.get(key, ""))
            box.setToolTip(tooltips.get(key, ""))
            self.flow_results[key] = box
            results.addWidget(label, row, 0)
            results.addWidget(box, row, 1)

        self.tabs.addTab(page, "Flow")

    def flow_text(self, key):
        return f"{self.flow[key]:g}"

    def set_from_altitude(self):
        # Clicking the button takes the focus from the altitude box, so a new altitude is already applied here
        temperature, density = Flow.standard_atmosphere(self.flow["altitude"])
        self.flow["temperature"] = round(temperature, 2)
        self.flow["density"] = round(density, 4)
        Storage.save_flow(self.flow)

        for key in ("temperature", "density"):
            self.flow_inputs[key].setText(self.flow_text(key))
            self.show_flow_message(key, "Applied & Saved", success=True)

        self.refresh()

    def commit_flow_input(self, key):
        line_edit = self.flow_inputs[key]

        if line_edit.text() == self.flow_text(key):
            line_edit.clearFocus()
            return

        low, high = FLOW_RANGES[key]

        try:
            value = float(line_edit.text())
        except ValueError:
            self.show_flow_message(key, f"Choice must be a number within the range: {low:g} - {high:g}")
            line_edit.setText(self.flow_text(key))
        else:
            if low <= value <= high:
                self.flow[key] = value
                Storage.save_flow(self.flow)
                line_edit.setText(self.flow_text(key))
                self.show_flow_message(key, "Applied & Saved", success=True)
                self.refresh()
            else:
                self.show_flow_message(key, f"Choice must be within the range: {low:g} - {high:g}")
                line_edit.setText(self.flow_text(key))

        line_edit.clearFocus()

    def show_flow_message(self, key, text, success=False):
        error_label = self.flow_error_labels[key]
        self.change_error_label_style("Success" if success else "Error", error_label)
        error_label.setText(text)
        QTimer.singleShot(1250, lambda: error_label.setText(""))

    @staticmethod
    def change_error_label_style(style, error_label):
        colour = Styles.GREEN if style == "Success" else Styles.RED
        error_label.setStyleSheet(f"color:{colour}; font-family:Arial; font-size:14px; font-weight:bold;")

    def refresh_flow(self):
        g = self.generator
        values = self.flow

        for box in self.flow_results.values():
            box.setText("-")

        geometry = Flow.wing_geometry(g.chord_mm / 1000, g.tip_chord_mm / 1000, g.span_mm / 1000)
        conditions = Flow.flow_conditions(values["airspeed"], values["density"], values["temperature"],
                                          geometry["mean_chord"])

        self.flow_results["q"].setText(f"{conditions['dynamic_pressure']:,.1f}")
        self.flow_results["a"].setText(f"{conditions['speed_of_sound']:.1f}")
        self.flow_results["mach"].setText(f"{conditions['mach']:.3f}")
        self.flow_results["re"].setText(f"{conditions['reynolds']:,.0f}")

        note = "Mach number above 0.3: compressibility is ignored, so lift is underestimated." if conditions["mach"] > 0.3 else ""

        if g.has_profile:
            aero = g.AeroMaths
            alpha = self.angle()
            cl = aero.calculate_lift_coefficient(alpha)
            wing_cl = aero.calculate_wing_lift_coefficient(alpha, geometry["aspect_ratio"])
            q = conditions["dynamic_pressure"]

            self.flow_results["cl"].setText(f"{cl:.4f}")
            self.flow_results["wing_cl"].setText(f"{wing_cl:.4f}")
            self.flow_results["lift_span"].setText(f"{cl * q * geometry['mean_chord']:,.2f}")
            self.flow_results["lift"].setText(f"{wing_cl * q * geometry['area']:,.2f}")

            if abs(alpha) > STALL_ANGLE:
                note = "Beyond a typical stall angle: thin aerofoil theory overestimates lift. " + note

        self.flow_note.setText(note.strip())

    # Lift curve tab ------------------------------------------------------------------------------------------

    def build_lift_tab(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 20, 25, 20)
        page.setLayout(layout)
        layout.addStretch(1)

        self.lift_figure, self.lift_canvas = self.make_canvas()
        self.lift_ax = self.lift_figure.add_subplot(111)
        layout.addWidget(self.lift_canvas, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.lift_note = QLabel("")
        self.lift_note.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 16))
        layout.addWidget(self.lift_note, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        self.tabs.addTab(page, "Lift curve")

    def refresh_lift(self):
        ax = self.lift_ax
        ax.clear()
        self.style_axes(self.lift_figure, ax)

        profiles = self.profiles()
        alpha_range = np.linspace(-20, 20, 81)

        ax.axvspan(STALL_ANGLE, 20, color=Styles.AMBER, alpha=0.12, lw=0)
        ax.axvspan(-20, -STALL_ANGLE, color=Styles.AMBER, alpha=0.12, lw=0)
        ax.text(17.5, 0.0, "Beyond typical stall\ntheory overestimates", color=Styles.AMBER, ha="center", va="center",
                fontsize=8, fontfamily=FONT, rotation=90, fontweight="bold")
        ax.axhline(0, color=Styles.GREY, linewidth=1)
        ax.axvline(0, color=Styles.GREY, linewidth=1)

        for index, (name, maths, colour, style) in enumerate(profiles):
            aero = AerodynamicMaths(maths)
            cl = np.array([aero.calculate_lift_coefficient(a) for a in alpha_range])
            ax.plot(alpha_range, cl, color=colour, linestyle=style, linewidth=2, label=name)

            # The comparison's label goes on the line below, so two similar zero lift angles don't overlap
            alpha_0 = aero.calculate_zero_lift_angle_of_attack()
            ax.plot([alpha_0], [0], marker="o", color=colour, markersize=7)
            ax.annotate(f"α₀ = {alpha_0:.2f}°", (alpha_0, 0), textcoords="offset points", xytext=(8, -16 - 13 * index),
                        color=colour, fontsize=8, fontfamily=FONT, fontweight="bold")

            alpha = self.angle()
            ax.plot([alpha], [aero.calculate_lift_coefficient(alpha)], marker="D", color=Styles.TEXT,
                    markeredgecolor=colour, markersize=8, zorder=5)

        ax.set_xlim(-20, 20)
        ax.set_xlabel("Angle of attack α (°)", fontfamily=FONT)
        ax.set_ylabel("Lift coefficient Cl", fontfamily=FONT)

        if profiles:
            self.legend(ax)
            self.lift_note.setText(f"Thin aerofoil theory, slope 2π per radian  ·  white marker: current angle of attack ({self.angle()}°)")
        else:
            ax.text(0.5, 0.5, "Enter an aerofoil in the generator", transform=ax.transAxes, ha="center", va="center",
                    color=Styles.LIGHT_GREY, fontsize=14, fontfamily=FONT, fontweight="bold")
            self.lift_note.setText("")

        self.lift_canvas.draw()

    # Pressure tab --------------------------------------------------------------------------------------------

    def build_pressure_tab(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 20, 25, 20)
        page.setLayout(layout)
        layout.addStretch(1)

        self.pressure_figure, self.pressure_canvas = self.make_canvas(9.6, 4.0)
        self.pressure_ax = self.pressure_figure.add_subplot(111)
        layout.addWidget(self.pressure_canvas, alignment=Qt.AlignmentFlag.AlignHCenter)

        slider_row = QHBoxLayout()

        angle_label = QLabel("Angle of Attack:")
        angle_label.setStyleSheet(Styles.text_style(Styles.WHITE, 24, padding=True))

        self.pressure_angle_result = QLabel("0°")
        self.pressure_angle_result.setStyleSheet(Styles.result_style(24))
        self.pressure_angle_result.setFixedSize(80, 50)
        self.pressure_angle_result.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pressure_slider = QSlider(Qt.Orientation.Horizontal)
        self.pressure_slider.setFixedWidth(340)
        self.pressure_slider.setStyleSheet(Styles.SLIDER_STYLE)
        self.pressure_slider.setRange(-25, 25)
        self.pressure_slider.valueChanged.connect(lambda value: self.generator.angle_of_attack_slider.setValue(value))

        reset_button = QPushButton("Reset")
        reset_button.setStyleSheet(Styles.outline_button_style(Styles.GREY, 16, padding=6))
        reset_button.clicked.connect(self.generator.reset_angle_of_attack_clicked)

        slider_row.addStretch(1)
        slider_row.addWidget(angle_label)
        slider_row.addWidget(self.pressure_angle_result)
        slider_row.addWidget(self.pressure_slider)
        slider_row.addWidget(reset_button)
        slider_row.addStretch(1)
        layout.addLayout(slider_row)

        self.pressure_note = QLabel("")
        self.pressure_note.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 16))
        layout.addWidget(self.pressure_note, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        self.tabs.addTab(page, "Pressure")

    def refresh_pressure(self):
        ax = self.pressure_ax
        ax.clear()
        self.style_axes(self.pressure_figure, ax)

        alpha = self.angle()
        self.pressure_slider.blockSignals(True)
        self.pressure_slider.setValue(alpha)
        self.pressure_slider.blockSignals(False)
        self.pressure_angle_result.setText(f"{alpha}°")

        profiles = self.profiles()
        notes = []

        ax.axhline(0, color=Styles.GREY, linewidth=1)

        for name, maths, colour, style in profiles:
            result = solve_panel_method(maths, alpha)
            ax.plot(result["x_upper"], result["cp_upper"], color=colour, linestyle=style, linewidth=2,
                    label=f"{name}  upper")
            ax.plot(result["x_lower"], result["cp_lower"], color=Styles.AMBER if style == "-" else Styles.TEXT,
                    linestyle=style, linewidth=2, label=f"{name}  lower")

            thin = AerodynamicMaths(maths).calculate_lift_coefficient(alpha)
            notes.append(f"{name}: panel Cl {result['cl']:.3f}, thin aerofoil Cl {thin:.3f}")

        ax.invert_yaxis()
        ax.set_xlim(-0.02, 1.02)
        ax.set_xlabel("Position along the chord x/c", fontfamily=FONT)
        ax.set_ylabel("Pressure coefficient Cp", fontfamily=FONT)

        if profiles:
            self.legend(ax)
        else:
            ax.text(0.5, 0.5, "Enter an aerofoil in the generator", transform=ax.transAxes, ha="center", va="center",
                    color=Styles.LIGHT_GREY, fontsize=14, fontfamily=FONT, fontweight="bold")

        self.pressure_note.setText(("Panel method: inviscid, includes thickness\n" + "\n".join(notes)) if notes else "")
        self.pressure_canvas.draw()

    # Compare tab ---------------------------------------------------------------------------------------------

    def build_compare_tab(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 15, 25, 15)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page.setLayout(layout)

        self.compare_message = QLabel("No aerofoil is being compared.\nUse the Compare button on the generator,\n"
                                      "or in the collection, to choose one.")
        self.compare_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compare_message.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 22))
        layout.addWidget(self.compare_message, alignment=Qt.AlignmentFlag.AlignCenter, stretch=1)

        self.compare_container = QWidget()
        grid = QGridLayout()
        grid.setVerticalSpacing(2)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.compare_container.setLayout(grid)
        layout.addWidget(self.compare_container)

        self.compare_rows = [
            ("Max camber (% chord)", lambda m, a, al: 100 * m.m, 2),
            ("Max thickness (% chord)", lambda m, a, al: 100 * m.t, 2),
            ("Leading edge radius", lambda m, a, al: a.calculate_leading_edge_radius(), 4),
            ("Zero lift angle (°)", lambda m, a, al: a.calculate_zero_lift_angle_of_attack(), 3),
            ("Zero lift pitching moment", lambda m, a, al: a.calculate_zero_lift_pitching_moment(), 4),
            ("Ideal lift coefficient", lambda m, a, al: a.calculate_ideal_lift_coefficient(), 4),
            ("Ideal angle of attack (°)", lambda m, a, al: a.calculate_ideal_angle_of_attack(), 3),
            ("Lift coefficient (thin aerofoil)", lambda m, a, al: a.calculate_lift_coefficient(al), 4),
            ("Lift coefficient (panel method)", lambda m, a, al: solve_panel_method(m, al)["cl"], 4),
            ("Moment about leading edge", lambda m, a, al: a.calculate_moment_leading_edge(al), 4),
            ("Section area (% chord²)", lambda m, a, al: 100 * m.cross_section_area(), 3),
        ]

        self.compare_headers = [self.label("", Styles.WHITE, 20) for _ in range(4)]
        for column, header in enumerate(self.compare_headers):
            header.setAlignment(Qt.AlignmentFlag.AlignCenter if column else Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(header, 0, column)

        self.compare_cells = []
        for row, (text, _, _) in enumerate(self.compare_rows, start=1):
            grid.addWidget(self.label(text + ":", Styles.WHITE, 18), row, 0)
            cells = [self.result_box(150) for _ in range(3)]
            for column, cell in enumerate(cells, start=1):
                grid.addWidget(cell, row, column)
            self.compare_cells.append(cells)

        self.tabs.addTab(page, "Compare")

    def refresh_compare(self):
        g = self.generator
        active = g.has_profile and g.comparison is not None

        self.compare_message.setVisible(not active)
        self.compare_container.setVisible(active)

        if not active:
            if not g.has_profile:
                self.compare_message.setText("Enter an aerofoil in the generator first.")
            else:
                self.compare_message.setText("No aerofoil is being compared.\nUse the Compare button on the generator,\n"
                                             "or in the collection, to choose one.")
            return

        profiles = [g.PlotMaths, g.comparison]
        aeros = [AerodynamicMaths(p) for p in profiles]
        alpha = self.angle()

        names = [f"{g.PlotMaths.display_name}", f"{g.comparison.display_name}", "Difference"]
        for header, text, colour in zip(self.compare_headers[1:], names, (Styles.TEAL, Styles.PINK, Styles.LIGHT_GREY)):
            header.setText(text)
            header.setStyleSheet(Styles.text_style(colour, 20, padding=True))
        self.compare_headers[0].setText(f"At α = {alpha}°")
        self.compare_headers[0].setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 20, padding=True))

        for (text, function, digits), cells in zip(self.compare_rows, self.compare_cells):
            a, b = (float(function(m, ae, alpha)) for m, ae in zip(profiles, aeros))
            cells[0].setText(f"{round(a, digits) + 0.0:.{digits}f}")
            cells[1].setText(f"{round(b, digits) + 0.0:.{digits}f}")
            cells[2].setText(f"{round(b - a, digits) + 0.0:+.{digits}f}")

    # Refreshing ----------------------------------------------------------------------------------------------

    def refresh(self):
        if not self.isVisible():
            return

        index = self.tabs.currentIndex()
        (self.refresh_flow, self.refresh_lift, self.refresh_pressure, self.refresh_compare)[index]()

    def showEvent(self, event):
        super().showEvent(event)
        self.centralWidget().setFocus()
        self.refresh()

    def theme_changed(self):
        self.refresh()