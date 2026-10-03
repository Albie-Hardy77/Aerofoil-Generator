from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                               QPushButton, QGridLayout, QSlider, QFileDialog)
from PySide6.QtWidgets import QMenu, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, QRegularExpression, QTimer, QEvent
from PySide6.QtGui import QRegularExpressionValidator

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

import Storage
import Styles
import StepExporter
import CoordinateExport
import ProfileImport
import Flow
from AerofoilGeometryMaths import AerofoilMaths
from AerodynamicMaths import AerodynamicMaths
from GeneratorPlots import GeneratorPlots
from Settings import SettingsWindow
from Analysis import AnalysisWindow
from NacaInput import NacaInput
from TitleBar import install_title_bar, TITLE_BAR_HEIGHT

DEFAULT_DESIGNATION_HINT = "4-digit: camber  ·  position  ·  thickness          5-digit: lift  ·  position  ·  reflex  ·  thickness"
STALL_WARNING_ANGLE = 15

PLOT_FRAME_SIZE = (694, 390)       # outer size of the plot frame, border included
PLOT_CANVAS_SIZE = (688, 384)
NORMAL_WINDOW_SIZE = (1200, 1040 + TITLE_BAR_HEIGHT)
UNLIMITED = 16777215


class GeneratorWindow(GeneratorPlots, QMainWindow):
    def __init__(self):
        super().__init__()

        self.PlotMaths = AerofoilMaths()
        self.AeroMaths = AerodynamicMaths(self.PlotMaths)

        self.chord_mm = 100
        self.span_mm = 75

        self.wire_counts_3d = [3, 5, 9, 17, 34]
        self.wire_count_index = 2

        self.xu = np.array([])
        self.yu = np.array([])
        self.xl = np.array([])
        self.yl = np.array([])
        self.has_profile = False

        self.is_3d = False
        self.library_window = None      # set by the main window, used by the COLLECTION shortcut
        self.annotations_on = False
        self.grid_on = False
        self.grid_note = None
        self.view_zoom = 1.0          # the user's mouse wheel zoom, on top of the automatic fit
        self.base_zoom_3d = 1.0
        self.offset_3d = (0.0, 0.0)     # middle of the 3D drawing relative to the canvas at zoom 1
        self.grid_step_3d = 10
        self.grid_extent_3d = None

        self.tip_chord_mm = 100
        self.sweep_deg = 0
        self.twist_deg = 0
        self.comparison = None

        self.settings_window = SettingsWindow(self)
        self.apply_settings(self.settings_window.values, redraw=False)

        self.dimension_label = QLabel("2D")

        self.fig = Figure()
        self.ax_2d = self.fig.add_subplot(111)
        self.ax_3d = self.fig.add_subplot(111, projection='3d')
        self.ax_3d.set_visible(False)

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setFixedSize(*PLOT_CANVAS_SIZE)
        self.canvas.mpl_connect("scroll_event", self.scroll_zoom_3d)
        self.ax_2d.set_position([0, 0, 1, 1])
        self.ax_3d.set_position([0, 0, 1, 1])

        # The frame and its grey background are a normal widget, so they never change between 2D and 3D
        self.plot_frame = QFrame()
        self.plot_frame.setObjectName("plotFrame")
        self.plot_frame.setStyleSheet(f"#plotFrame {{ background-color:{Styles.PANEL}; border:3px solid {Styles.TEXT}; }}")
        self.plot_frame.setFixedSize(*PLOT_FRAME_SIZE)
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(self.canvas)
        self.plot_frame.setLayout(frame_layout)
        self.plot_frame.installEventFilter(self)

        self.result_style = Styles.result_style()

        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(lambda: self.error_label.setText(""))

        self.error_label = QLabel()
        self.error_label.setStyleSheet(Styles.text_style(Styles.RED, 14))

        self.angle_of_attack_result = QLabel("0°")
        self.angle_of_attack_slider = QSlider(Qt.Orientation.Horizontal)

        install_title_bar(self, "Generator", maximisable=True)
        self.setFixedSize(*NORMAL_WINDOW_SIZE)
        self.is_maximised = False

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.redraw)
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

        settings_button = QPushButton("SETTINGS")
        settings_button.setFixedSize(100, 38)
        settings_button.setStyleSheet(Styles.outline_button_style(Styles.GREY, 16, radius=5, border=2))
        settings_button.setToolTip("Resolution, chord lengths, semi-span, sweep, twist and wireframe density")
        settings_button.clicked.connect(self.settings_window_clicked)

        analysis_button = QPushButton("ANALYSIS")
        analysis_button.setFixedSize(110, 38)
        analysis_button.setStyleSheet(Styles.outline_button_style(Styles.TEAL, 16, radius=5, border=2))
        analysis_button.setToolTip("Flow conditions, lift curve, pressure distribution and comparison")
        analysis_button.clicked.connect(self.analysis_window_clicked)

        collection_button = QPushButton("COLLECTION")
        collection_button.setFixedSize(134, 38)
        collection_button.setStyleSheet(Styles.outline_button_style(Styles.PINK, 16, radius=5, border=2))
        collection_button.setToolTip("Open your saved aerofoils")
        collection_button.clicked.connect(self.collection_window_clicked)

        subtitle_bar.setContentsMargins(10, 0, 10, 0)
        subtitle_bar.addWidget(settings_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        subtitle_bar.addSpacing(8)
        subtitle_bar.addWidget(analysis_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        subtitle_bar.addSpacing(8)
        subtitle_bar.addWidget(collection_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        subtitle_bar.addStretch(1)
        subtitle_bar.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(subtitle_bar)

        # Title Label
        title_label = QLabel("AEROFOIL GENERATOR")
        title_label.setStyleSheet(Styles.text_style(Styles.WHITE, 72, background=True))

        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Program Description Setup
        program_description = QLabel("Enter aerofoil profile to generate")
        program_description.setStyleSheet(Styles.text_style(Styles.GREY, 24, background=True))

        main_layout.addWidget(program_description, alignment=Qt.AlignmentFlag.AlignCenter)

        # Seperator
        seperator = QFrame()
        seperator.setFrameShape(QFrame.Shape.HLine)
        seperator.setFrameShadow(QFrame.Shadow.Plain)
        seperator.setFixedSize(1100, 3)
        seperator.setStyleSheet(f"background-color:{Styles.GREY}; color:{Styles.GREY};")

        main_layout.addSpacing(10)
        self.separator = seperator
        main_layout.addWidget(seperator, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(20)

        # Input Box Layout
        input_box_layout = QHBoxLayout()
        input_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addLayout(input_box_layout)

        # Input Boxes and Label
        NACA_label = QLabel("NACA:")
        NACA_label.setStyleSheet(Styles.text_style(Styles.WHITE, 64, background=True))

        self.input_box = NacaInput()
        self.input_box.setFixedSize(235, 70)
        self.input_box.setMaxLength(5)
        self.input_box.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9]*")))
        self.input_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_box.setContentsMargins(0,0,5,0)
        self.input_box.setToolTip("NACA 4-digit code (2412 = 2% camber at 40% chord, 12% thick) or 5-digit code (23012 = design Cl 0.3, camber at 15% chord, standard camber, 12% thick)")
        self.input_box.setStyleSheet(f"background-color:{Styles.BACKGROUND}; color:{Styles.TEXT};"
                                     "font-family:Arial; font-size:64px; font-weight:bold;"
                                     f"border-radius:0px; border-width:3px; border-color:{Styles.TEXT}; border-style:solid;"
                                     "letter-spacing:5px; padding-right:0px; padding-bottom:2px")

        input_box_layout.addWidget(NACA_label, alignment=Qt.AlignmentFlag.AlignCenter)
        input_box_layout.addWidget(self.input_box, alignment=Qt.AlignmentFlag.AlignCenter)
        self.input_box.clearFocus()

        self.input_box.textChanged.connect(self.input_box_changed)

        # Designation Description Label
        self.designation_label = QLabel(DEFAULT_DESIGNATION_HINT)
        self.designation_label.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 16))
        main_layout.addWidget(self.designation_label, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(10)

        # Dimension Mode Label
        self.dimension_label.setStyleSheet(f"color:{Styles.AMBER}; font-family:Arial; font-size:25px; font-weight:bold;"
                                           "padding-top:6px; padding-bottom:8px; padding-left:6px; padding-right:6px;")

        self.dimension_label.setFixedSize(50, 40)
        self.dimension_label.setParent(main_widget)

        # Scale Grid Toggle (sits beside the 2D/3D label)
        self.grid_button = QPushButton("GRID", main_widget)
        self.grid_button.setFixedSize(100, 34)
        self.grid_button.setToolTip("Show a millimetre grid so you can see the real size of the exported model")
        self.grid_button.setStyleSheet(Styles.outline_button_style(Styles.GREY, 16, radius=5, border=2))
        self.grid_button.clicked.connect(self.toggle_grid_clicked)

        # Plotting window layout
        filler_layout = QVBoxLayout()
        plot_layout = QHBoxLayout()

        canvas_layout = QVBoxLayout()
        canvas_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        filler_layout.addLayout(plot_layout)
        main_layout.addLayout(filler_layout, stretch=1)

        # Aerodynamics Layout
        analysis_layout = QGridLayout()
        analysis_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        plot_layout.addLayout(analysis_layout, stretch=0)
        self.frame_row = QHBoxLayout()
        self.frame_row.setContentsMargins(13, 0, 0, 0)
        self.frame_row.addWidget(self.plot_frame, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        canvas_layout.addLayout(self.frame_row)
        canvas_layout.addWidget(self.error_label, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, stretch=0)
        plot_layout.addLayout(canvas_layout, stretch=1)

        # Aerodynamics Labels Setup
        label_style = Styles.text_style(Styles.WHITE, 20, padding=True)

        row_definitions = [
            ("leading_edge_radius", "Leading edge radius:", "Nose radius as a fraction of chord: r = 1.1019 t²"),
            ("a0", "Fourier coefficient A₀:", "Thin aerofoil theory: A₀ = -(1/π) ∫ dyc/dx dθ"),
            ("a1", "Fourier coefficient A₁:", "Thin aerofoil theory: A₁ = (2/π) ∫ dyc/dx cos θ dθ"),
            ("a2", "Fourier coefficient A₂:", "Thin aerofoil theory: A₂ = (2/π) ∫ dyc/dx cos 2θ dθ"),
            ("zero_lift_angle", "Zero lift angle of attack:", "Angle at which the aerofoil produces no lift: α₀ = -A₀ - A₁/2"),
            ("zero_lift_moment", "Zero lift pitching moment:", "Moment coefficient about the quarter-chord: Cm = (π/4)(A₂ - A₁)"),
            ("ideal_lift_coefficient", "Ideal lift coefficient:", "Design lift coefficient, where the flow meets the leading edge smoothly: Cli = π A₁"),
            ("ideal_angle", "Ideal angle of attack:", "Angle of attack at the ideal lift coefficient"),
            ("lift_curve_slope", "Lift curve slope:", "Thin aerofoil theory gives dCl/dα = 2π per radian"),
            ("aerodynamic_centre", "Aerodynamic centre:", "Point where the pitching moment doesn't change with angle of attack"),
            ("lift_coefficient", "Lift coefficient:", "Cl = 2π (α - α₀) at the current angle of attack"),
            ("quarter_chord_moment", "Moment about quarter-chord:", "Equal to the zero lift pitching moment"),
            ("leading_edge_moment", "Moment about leading edge:", "Cm,LE = Cm,c/4 - Cl/4"),
            ("centre_of_pressure", "Centre of pressure:", "Position along the chord where the lift acts. Undefined near zero lift"),
        ]

        self.result_labels = {}

        analysis_layout.setContentsMargins(30, 0, 0, 0)
        for row_index, (key, text, tooltip) in enumerate(row_definitions):
            label = QLabel(text)
            label.setStyleSheet(label_style)
            label.setToolTip(tooltip)

            result = QLabel("-")
            result.setStyleSheet(self.result_style)
            result.setToolTip(tooltip)
            result.setAlignment(Qt.AlignmentFlag.AlignCenter)
            result.setFixedWidth(90)
            self.result_labels[key] = result

            analysis_layout.addWidget(label, row_index, 0,
                                      alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            analysis_layout.addWidget(result, row_index, 1,
                                      alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Canvas Setup
        self.style_2d_axes()
        self.canvas.draw()

        # Canvas Buttons Setup
        canvas_button_layout = QHBoxLayout()
        canvas_button_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        canvas_button_layout.setContentsMargins(13, 0, 0, 0)

        # 3D Toggle Button
        toggle_3D_button = QPushButton("Toggle 3D/2D")
        toggle_3D_button.clicked.connect(self.toggle_3D_button_clicked)
        toggle_3D_button.setFixedSize(225, 70)
        toggle_3D_button.setToolTip("Switch between the 2D cross-section and a 3D wireframe of the wing")
        toggle_3D_button.setStyleSheet(Styles.outline_button_style(Styles.AMBER, 30))

        canvas_button_layout.addWidget(toggle_3D_button, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Export as STEP Button
        export_step_button = QPushButton("Export")
        export_step_button.setFixedSize(215, 70)
        export_step_button.setToolTip("Export the wing as a STEP solid, the profile as coordinates or a DXF sketch, or an image")
        export_step_button.setStyleSheet(Styles.outline_button_style(Styles.TEAL, 30)
                                         + "QPushButton::menu-indicator {image:none; width:0px;}")

        export_menu = QMenu(self)
        export_menu.setStyleSheet(Styles.menu_style())
        export_menu.addAction("STEP solid model (.step)", self.export_as_step_clicked)
        export_menu.addAction("Coordinates, Selig format (.dat)", lambda: self.export_coordinates("dat"))
        export_menu.addAction("Coordinates, spreadsheet (.csv)", lambda: self.export_coordinates("csv"))
        export_menu.addAction("Sketch profile (.dxf)", lambda: self.export_coordinates("dxf"))
        export_menu.addSeparator()
        export_menu.addAction("Image of the current view (.png)", self.export_image_clicked)
        export_step_button.setMenu(export_menu)

        canvas_button_layout.addWidget(export_step_button, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Save to Library Button
        save_to_library_button = QPushButton("Save to Library")
        save_to_library_button.setFixedSize(242, 70)
        save_to_library_button.setToolTip("Add this aerofoil to your collection")
        save_to_library_button.setStyleSheet(Styles.outline_button_style(Styles.PINK, 30))
        save_to_library_button.clicked.connect(self.save_to_library_clicked)

        canvas_button_layout.addWidget(save_to_library_button, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        empty_space = QWidget()
        canvas_button_layout.addWidget(empty_space, alignment=Qt.AlignmentFlag.AlignCenter)
        canvas_button_layout.setStretch(3, 1)

        canvas_layout.addLayout(canvas_button_layout, stretch=0)

        # Annotations / Import / Compare Row
        annotation_layout = QHBoxLayout()
        annotation_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        annotation_layout.setContentsMargins(13, 0, 0, 0)

        self.annotation_button = QPushButton("Annotations: OFF")
        self.annotation_button.setFixedSize(225, 50)     # same widths as the buttons above
        self.annotation_button.setToolTip("Label the chord, camber line, thickness, leading and trailing edge (2D only)")
        self.annotation_button.setStyleSheet(Styles.outline_button_style(Styles.GREY, 20, border=2))
        self.annotation_button.clicked.connect(self.toggle_annotations_clicked)

        import_button = QPushButton("Import .dat")
        import_button.setFixedSize(215, 50)
        import_button.setToolTip("Load an aerofoil from a coordinate file (Selig or Lednicer format)")
        import_button.setStyleSheet(Styles.outline_button_style(Styles.TEAL, 20, border=2))
        import_button.clicked.connect(self.import_profile_clicked)

        self.compare_button = QPushButton("Compare: OFF")
        self.compare_button.setFixedSize(242, 50)
        self.compare_button.setToolTip("Overlay a second aerofoil from your collection")
        self.style_compare_button()

        self.compare_menu = QMenu(self)
        self.compare_menu.setStyleSheet(Styles.menu_style())
        self.compare_menu.aboutToShow.connect(self.populate_compare_menu)
        self.compare_button.setMenu(self.compare_menu)

        top_centre = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        annotation_layout.addWidget(self.annotation_button, alignment=top_centre)
        annotation_layout.addWidget(import_button, alignment=top_centre)
        annotation_layout.addWidget(self.compare_button, alignment=top_centre)

        annotation_empty_space = QWidget()
        annotation_layout.addWidget(annotation_empty_space, alignment=Qt.AlignmentFlag.AlignCenter)
        annotation_layout.setStretch(3, 1)

        canvas_layout.addSpacing(8)
        canvas_layout.addLayout(annotation_layout)

        # Angle of Attack Setup
        angle_of_attack_layout = QHBoxLayout()

        angle_of_attack_label = QLabel("Angle of Attack:")
        angle_of_attack_label.setStyleSheet(Styles.text_style(Styles.WHITE, 24, padding=True))

        self.angle_of_attack_result.setStyleSheet(Styles.result_style(24))
        self.angle_of_attack_result.setFixedSize(80, 50)
        self.angle_of_attack_result.setAlignment(Qt.AlignmentFlag.AlignCenter)

        angle_of_attack_layout.addWidget(angle_of_attack_label)
        angle_of_attack_layout.addWidget(self.angle_of_attack_result)

        self.gap_above = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        canvas_layout.addItem(self.gap_above)
        canvas_layout.addLayout(angle_of_attack_layout)

        # Angle of Attack Slider
        self.angle_of_attack_slider.setFixedWidth(340)
        self.angle_of_attack_slider.setStyleSheet(Styles.SLIDER_STYLE)

        self.angle_of_attack_slider.setMinimum(-25)
        self.angle_of_attack_slider.setMaximum(25)
        self.angle_of_attack_slider.setValue(0)
        self.angle_of_attack_slider.valueChanged.connect(self.angle_of_attack_changed)

        angle_of_attack_layout.addWidget(self.angle_of_attack_slider)

        # Reset Angle of Attack
        reset_angle_of_attack = QPushButton("Reset")
        reset_angle_of_attack.setStyleSheet(Styles.outline_button_style(Styles.GREY, 16, padding=6))
        reset_angle_of_attack.clicked.connect(self.reset_angle_of_attack_clicked)

        angle_of_attack_layout.addWidget(reset_angle_of_attack)

        empty_space2 = QWidget()
        angle_of_attack_layout.addWidget(empty_space2, alignment=Qt.AlignmentFlag.AlignCenter, stretch=1)

        self.angle_note_label = QLabel("")
        self.angle_note_label.setStyleSheet(Styles.text_style(Styles.AMBER, 14))
        canvas_layout.addWidget(self.angle_note_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.gap_below = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        canvas_layout.addItem(self.gap_below)
        self.canvas_layout = canvas_layout
        self.centred_rows = [canvas_button_layout, annotation_layout, angle_of_attack_layout]

        # Information Strip
        info_strip = QHBoxLayout()
        info_strip.setContentsMargins(10, 0, 10, 0)

        theory_label = QLabel("Thin aerofoil theory  ·  inviscid")
        theory_label.setStyleSheet(Styles.text_style(Styles.GREY, 14))

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(Styles.text_style(Styles.LIGHT_GREY, 14))

        info_strip.addWidget(theory_label, alignment=Qt.AlignmentFlag.AlignLeft)
        info_strip.addWidget(self.stats_label, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(info_strip)

        self.update_info_labels()

        self.analysis_window = AnalysisWindow(self)

    # Settings / library / export ------------------------------------------------------------------------------

    def apply_settings(self, values, redraw=True):
        self.PlotMaths.set_resolution(10 * values["resolution"])
        if self.comparison is not None:
            self.comparison.set_resolution(self.PlotMaths.resolution)
        self.chord_mm = values["chord"]
        self.span_mm = values["span"]
        self.wire_count_index = values["wireframe"] - 1
        self.tip_chord_mm = values["tip_chord"]
        self.sweep_deg = values["sweep"]
        self.twist_deg = values["twist"]

        if self.has_profile and redraw:
            self.calculate_coordinates()
            self.update_info_labels()
            self.redraw()
        elif redraw:
            self.update_info_labels()

        self.notify_analysis()

    def toggle_maximise(self):
        if self.is_maximised:
            self.is_maximised = False
            self.apply_layout_mode(False)
            self.showNormal()
            self.setFixedSize(*NORMAL_WINDOW_SIZE)
        else:
            self.is_maximised = True
            self.setMinimumSize(0, 0)
            self.setMaximumSize(UNLIMITED, UNLIMITED)
            self.showMaximized()
            self.apply_layout_mode(True)

        self.title_bar.set_maximised(self.is_maximised)

    def apply_layout_mode(self, maximised):
        """The restored window has the original fixed layout; the maximised one lets the plot grow."""
        if maximised:
            self.plot_frame.setMinimumSize(300, 220)
            self.plot_frame.setMaximumSize(UNLIMITED, UNLIMITED)
            self.canvas.setMinimumSize(0, 0)
            self.canvas.setMaximumSize(UNLIMITED, UNLIMITED)
            self.frame_row.setAlignment(self.plot_frame, Qt.AlignmentFlag(0))
            self.canvas_layout.setStretchFactor(self.frame_row, 1)
            gap = (QSizePolicy.Policy.Fixed, 10)
        else:
            self.plot_frame.setFixedSize(*PLOT_FRAME_SIZE)
            self.canvas.setFixedSize(*PLOT_CANVAS_SIZE)
            self.frame_row.setAlignment(self.plot_frame, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.canvas_layout.setStretchFactor(self.frame_row, 0)
            gap = (QSizePolicy.Policy.Expanding, 0)

        for spacer in (self.gap_above, self.gap_below):
            spacer.changeSize(0, gap[1], QSizePolicy.Policy.Minimum, gap[0])

        # Centre the rows of buttons under a wide plot, left aligned (as before) when restored
        for row in self.centred_rows:
            if maximised and not getattr(row, "is_centred", False):
                row.insertStretch(0, 1)
                row.is_centred = True
            elif not maximised and getattr(row, "is_centred", False):
                row.takeAt(0)
                row.is_centred = False

        self.canvas_layout.invalidate()
        self.fit_separator()
        self.resize_timer.start(80)

    def fit_separator(self):
        if self.is_maximised:
            self.separator.setFixedSize(max(1100, self.width() - 100), 3)
        else:
            self.separator.setFixedSize(1100, 3)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.is_maximised:
            self.fit_separator()

    def eventFilter(self, obj, event):
        if obj is self.plot_frame and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self.reposition_overlays()

            if event.type() == QEvent.Type.Resize and self.has_profile:
                self.resize_timer.start(80)

        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.reposition_overlays)

    def reposition_overlays(self):
        corner = self.plot_frame.mapTo(self.centralWidget(), self.plot_frame.rect().topRight())
        self.dimension_label.move(corner.x() - 49, corner.y() - 46)
        self.grid_button.move(corner.x() - 157, corner.y() - 44)

    def theme_changed(self):
        self.redraw()
        self.style_compare_button()
        self.analysis_window.theme_changed()

    def settings_window_clicked(self):
        self.settings_window.show()
        self.settings_window.raise_()

    def collection_window_clicked(self):
        if self.library_window is not None:
            self.library_window.show()
            self.library_window.raise_()

    def analysis_window_clicked(self):
        self.analysis_window.show()
        self.analysis_window.raise_()

    def notify_analysis(self):
        if hasattr(self, "analysis_window"):
            self.analysis_window.refresh()

    # Loading aerofoils -------------------------------------------------------------------------------------------

    def load_designation(self, designation):
        if self.input_box.text() == designation:
            self.input_box_changed()
        else:
            self.input_box.setText(designation)

    def load_entry(self, entry):
        if entry.get("kind") == "custom":
            self.load_custom(entry["name"], entry["points"])
        else:
            self.load_designation(entry["designation"])

    def load_custom(self, name, points):
        try:
            self.PlotMaths.set_custom_profile(name, points)
        except Exception as e:
            self.show_message(f"Couldn't use that profile: {e}", "Error", 4000)
            return

        self.input_box.blockSignals(True)
        self.input_box.setText("")
        self.input_box.blockSignals(False)
        self.show_profile()

    def import_profile_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import aerofoil", "",
                                              "Coordinate files (*.dat *.txt *.csv);;All files (*)")
        if not path:
            return

        try:
            name, points = ProfileImport.read_dat(path)
        except (OSError, ValueError) as e:
            self.show_message(f"Couldn't read that file: {e}", "Error", 4000)
            return

        self.load_custom(name, points)

    def show_profile(self):
        self.calculate_coordinates()
        self.calculate_aerodynamic_properties()
        self.update_info_labels()
        self.show_message("")
        self.redraw()
        self.notify_analysis()

    # Comparison --------------------------------------------------------------------------------------------------

    def style_compare_button(self):
        if self.comparison is None:
            self.compare_button.setText("Compare: OFF")
            colour = Styles.GREY
        else:
            name = self.comparison.display_name
            self.compare_button.setText(f"Compare: {name[:10]}" + ("…" if len(name) > 10 else ""))
            colour = Styles.PINK

        self.compare_button.setStyleSheet(Styles.outline_button_style(colour, 20, border=2)
                                          + "QPushButton::menu-indicator {image:none; width:0px;}")

    def populate_compare_menu(self):
        self.compare_menu.clear()
        library = Storage.load_library()

        if not library:
            self.compare_menu.addAction("The collection is empty").setEnabled(False)

        for entry in library:
            self.compare_menu.addAction(entry["name"], lambda e=entry: self.set_comparison(e))

        if self.comparison is not None:
            self.compare_menu.addSeparator()
            self.compare_menu.addAction("Clear comparison", lambda: self.set_comparison(None))

    def set_comparison(self, entry):
        if entry is None:
            self.comparison = None
        else:
            try:
                self.comparison = AerofoilMaths.from_entry(entry, self.PlotMaths.resolution)
            except (ValueError, KeyError) as e:
                self.show_message(f"Couldn't compare with that aerofoil: {e}", "Error", 4000)
                return

        self.style_compare_button()
        self.redraw()
        self.notify_analysis()

    # Saving and exporting ----------------------------------------------------------------------------------------

    def save_to_library_clicked(self):
        if not self.has_profile:
            self.show_message("Generate an aerofoil before saving it", "Error", 2500)
            return

        name = self.PlotMaths.display_name

        if Storage.add_entry(self.PlotMaths.to_entry()):
            self.show_message(f"{name} saved to the library", "Success", 2500)
            if self.library_window is not None and self.library_window.isVisible():
                self.library_window.refresh_list()
        elif any(entry["id"] == Storage.clean_entry(self.PlotMaths.to_entry())["id"] for entry in Storage.load_library()):
            self.show_message(f"{name} is already in the library", "Error", 2500)
        else:
            self.show_message("Couldn't write the library file", "Error", 2500)

    def ask_save_path(self, title, suffix, file_filter):
        if not self.has_profile:
            self.show_message("Generate an aerofoil before exporting", "Error", 2500)
            return None

        default_path = str(Path.home() / f"{self.PlotMaths.file_stem}{suffix}")
        path, _ = QFileDialog.getSaveFileName(self, title, default_path, file_filter)

        return path or None

    def export_as_step_clicked(self):
        path = self.ask_save_path("Export STEP", ".step", "STEP files (*.step *.stp)")
        if path is None:
            return

        try:
            StepExporter.export_step(path, self.PlotMaths, self.chord_mm, self.span_mm, self.PlotMaths.file_stem,
                                     tip_chord_mm=self.tip_chord_mm, sweep_deg=self.sweep_deg, twist_deg=self.twist_deg)
            self.show_message(f"Exported {Path(path).name}  (chord {self.chord_mm} to {self.tip_chord_mm} mm, "
                              f"semi-span {self.span_mm} mm)",
                              "Success", 4000)
        except Exception as e:
            self.show_message(f"Export failed: {e}", "Error", 4000)

    def export_coordinates(self, kind):
        filters = {"dat": ("Selig coordinates (*.dat)", ".dat"), "csv": ("Spreadsheet (*.csv)", ".csv"),
                   "dxf": ("DXF sketch (*.dxf)", ".dxf")}
        file_filter, suffix = filters[kind]
        path = self.ask_save_path("Export coordinates", suffix, file_filter)
        if path is None:
            return

        try:
            if kind == "dat":
                CoordinateExport.write_dat(path, self.PlotMaths)
            elif kind == "csv":
                CoordinateExport.write_csv(path, self.PlotMaths, self.chord_mm)
            else:
                CoordinateExport.write_dxf(path, self.PlotMaths, self.chord_mm)

            self.show_message(f"Exported {Path(path).name}", "Success", 4000)
        except Exception as e:
            self.show_message(f"Export failed: {e}", "Error", 4000)

    def export_image_clicked(self):
        path = self.ask_save_path("Save image", ".png", "PNG image (*.png);;SVG image (*.svg)")
        if path is None:
            return

        try:
            self.fig.savefig(path, dpi=300, facecolor=self.fig.get_facecolor())
            self.show_message(f"Saved {Path(path).name}", "Success", 4000)
        except Exception as e:
            self.show_message(f"Couldn't save the image: {e}", "Error", 4000)

    def show_message(self, text, kind="Error", timeout=0):
        self.status_timer.stop()
        colour = Styles.GREEN if kind == "Success" else Styles.RED
        self.error_label.setStyleSheet(Styles.text_style(colour, 14))
        self.error_label.setText(text)

        if timeout:
            self.status_timer.start(timeout)

    # Calculations --------------------------------------------------------------------------------------------

    @staticmethod
    def fmt(value, digits=4):
        return f"{round(float(value), digits) + 0.0:.{digits}f}"

    def set_result(self, key, text):
        self.result_labels[key].setText(text)

    def calculate_coordinates(self):
        self.xu, self.yu, self.xl, self.yl = self.PlotMaths.calculate_coordinates()
        self.has_profile = True

    def calculate_aerodynamic_properties(self):
        aero = self.AeroMaths

        self.set_result("leading_edge_radius", self.fmt(aero.calculate_leading_edge_radius()))
        self.set_result("a0", self.fmt(aero.calculate_fourier_coefficient_A0()))
        self.set_result("a1", self.fmt(aero.calculate_fourier_coefficient_A1()))
        self.set_result("a2", self.fmt(aero.calculate_fourier_coefficient_A2()))
        self.set_result("zero_lift_angle", f"{self.fmt(aero.calculate_zero_lift_angle_of_attack(), 3)}°")
        self.set_result("zero_lift_moment", self.fmt(aero.calculate_zero_lift_pitching_moment()))
        self.set_result("ideal_lift_coefficient", self.fmt(aero.calculate_ideal_lift_coefficient()))
        self.set_result("ideal_angle", f"{self.fmt(aero.calculate_ideal_angle_of_attack(), 3)}°")
        self.set_result("lift_curve_slope", "2π")
        self.set_result("aerodynamic_centre", "25%")
        self.set_result("quarter_chord_moment", self.fmt(aero.calculate_moment_quarter_chord()))
        self.update_angle_dependent_results()

    def update_angle_dependent_results(self):
        aero = self.AeroMaths
        angle = self.angle_of_attack_slider.value()

        self.set_result("lift_coefficient", self.fmt(aero.calculate_lift_coefficient(angle)))
        self.set_result("leading_edge_moment", self.fmt(aero.calculate_moment_leading_edge(angle)))

        centre_of_pressure = aero.calculate_centre_of_pressure(angle)
        if centre_of_pressure is None:
            self.set_result("centre_of_pressure", "-")
        else:
            self.set_result("centre_of_pressure", f"{self.fmt(100 * centre_of_pressure, 2)}%")

        if abs(angle) > STALL_WARNING_ANGLE:
            self.angle_note_label.setText("Beyond a typical stall angle: thin aerofoil theory overestimates lift")
        else:
            self.angle_note_label.setText("")

    def clear_results(self):
        for label in self.result_labels.values():
            label.setText("-")
        self.angle_note_label.setText("")

    def stats_text(self, extra=""):
        geometry = Flow.wing_geometry(self.chord_mm, self.tip_chord_mm, self.span_mm)
        text = (f"Root chord {self.chord_mm} mm  ·  Tip chord {self.tip_chord_mm} mm  ·  Semi-span {self.span_mm} mm  ·  "
                f"Aspect ratio {geometry['aspect_ratio']:.2f}")

        if self.sweep_deg:
            text += f"  ·  Sweep {self.sweep_deg}°"
        if self.twist_deg:
            text += f"  ·  Twist {self.twist_deg}°"

        return text + extra

    def update_info_labels(self):
        if not self.has_profile:
            self.designation_label.setText(DEFAULT_DESIGNATION_HINT)
            self.stats_label.setText(self.stats_text())
            return

        maths = self.PlotMaths
        thickness_position = maths.max_thickness_position() * 100

        if maths.series == 5:
            self.designation_label.setText(
                f"5-digit series  ·  design Cl {maths.design_cl:.2f}  ·  {maths.m * 100:.1f}% camber at {maths.p * 100:.0f}% chord"
                f"{'  ·  reflex' if maths.reflex else ''}  ·  {maths.t * 100:.0f}% thick at {thickness_position:.0f}% chord")
        else:
            camber_text = ("Symmetric aerofoil" if maths.is_symmetric
                           else f"Cambered aerofoil  ·  {maths.m * 100:.0f}% max camber at {maths.p * 100:.0f}% chord")
            prefix = f"Imported: {maths.name}  ·  " if maths.is_custom else ""
            self.designation_label.setText(
                f"{prefix}{camber_text}  ·  {maths.t * 100:.0f}% max thickness at {thickness_position:.0f}% chord")

        area = maths.cross_section_area() * self.chord_mm ** 2
        self.stats_label.setText(self.stats_text(f"  ·  Root section area {area:.0f} mm²"))

    # Input / events ------------------------------------------------------------------------------------------

    def input_box_changed(self):
        text = self.input_box.text()

        if len(text) in (4, 5):
            try:
                self.PlotMaths.set_designation(text)
                self.show_profile()

            except Exception as e:
                self.reset_profile()
                self.show_message(f"Error: {e}")
        else:
            self.show_message("")
            self.reset_profile()

    def reset_profile(self):
        self.has_profile = False
        self.clear_results()
        self.update_info_labels()
        self.redraw()
        self.notify_analysis()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        if self.input_box.hasFocus():
            self.input_box.clearFocus()

    def reset_angle_of_attack_clicked(self):
        self.angle_of_attack_slider.setValue(0)

        if self.is_3d and self.has_profile:
            self.view_zoom = 1.0
            self.set_zoom_3d(self.base_zoom_3d)
            self.ax_3d.view_init(elev=100, azim=-95, roll=0, vertical_axis='z')
            self.canvas.draw()

    def angle_of_attack_changed(self, value):
        self.angle_of_attack_result.setText(f"{value}°")

        if self.has_profile:
            self.update_angle_dependent_results()

            if not self.is_3d:
                self.update_2d_rotation(value)

        self.notify_analysis()

    def toggle_grid_clicked(self):
        self.grid_on = not self.grid_on
        colour = Styles.GREEN if self.grid_on else Styles.GREY
        self.grid_button.setStyleSheet(Styles.outline_button_style(colour, 16, radius=5, border=2))

        self.redraw()

    def toggle_annotations_clicked(self):
        self.annotations_on = not self.annotations_on

        if self.annotations_on:
            self.annotation_button.setText("Annotations: ON")
            self.annotation_button.setStyleSheet(Styles.outline_button_style(Styles.GREEN, 20, border=2))
        else:
            self.annotation_button.setText("Annotations: OFF")
            self.annotation_button.setStyleSheet(Styles.outline_button_style(Styles.GREY, 20, border=2))

        self.redraw()

    def toggle_3D_button_clicked(self):
        self.is_3d = not self.is_3d
        self.view_zoom = 1.0
        self.angle_of_attack_slider.setValue(0)
        self.ax_3d.set_visible(self.is_3d)
        self.ax_2d.set_visible(not self.is_3d)
        self.angle_of_attack_slider.setEnabled(not self.is_3d)
        self.annotation_button.setEnabled(not self.is_3d)
        self.dimension_label.setText("3D" if self.is_3d else "2D")
        self.annotation_button.setToolTip("Annotations are only available in 2D" if self.is_3d
                                          else "Label the chord, camber line, thickness, leading and trailing edge (2D only)")

        self.redraw()
