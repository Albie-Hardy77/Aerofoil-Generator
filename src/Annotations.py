import math
import numpy as np

import Styles

FONT = ["Arial", "DejaVu Sans"]
FONT_SIZE = 8



def draw_annotations(ax, maths, xu, yu, xl, yl, angle_degrees):
    """Draws labelled key features on the 2D axes. Everything is rotated with the aerofoil."""
    # Read at draw time so the annotations follow the current theme
    CHORD_COLOUR = Styles.RED
    CAMBER_COLOUR = Styles.GREEN
    THICKNESS_COLOUR = Styles.PINK
    EDGE_COLOUR = Styles.AMBER
    SURFACE_COLOUR = Styles.TEAL

    angle = math.radians(-angle_degrees)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def rot(x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        return x * cos_a - y * sin_a, x * sin_a + y * cos_a

    def pt(x, y):
        rx, ry = rot(x, y)
        return float(rx), float(ry)

    def line(xs, ys, colour, style="-", width=1.2):
        rx, ry = rot(xs, ys)
        ax.plot(rx, ry, color=colour, linestyle=style, linewidth=width, zorder=3)

    def double_arrow(a, b, colour):
        ax.annotate("", xy=pt(*b), xytext=pt(*a), zorder=4,
                    arrowprops=dict(arrowstyle="<->", color=colour, lw=1.2, shrinkA=0, shrinkB=0, mutation_scale=8))

    def label(text, x, y, colour, ha="center", va="center"):
        px, py = pt(x, y)
        ax.text(px, py, text, color=colour, ha=ha, va=va, fontsize=FONT_SIZE, fontfamily=FONT,
                fontweight="bold", zorder=5, linespacing=1.1)

    def pointer(text, text_xy, target_xy, colour):
        ax.annotate(text, xy=pt(*target_xy), xytext=pt(*text_xy), color=colour, ha="center", va="center",
                    fontsize=FONT_SIZE, fontfamily=FONT, fontweight="bold", zorder=5,
                    arrowprops=dict(arrowstyle="->", color=colour, lw=1.0, shrinkA=2, shrinkB=1, mutation_scale=8))

    def surface_point(x_array, y_array, x_target):
        index = int(np.argmin(np.abs(x_array - x_target)))
        return float(x_array[index]), float(y_array[index])

    m, p, t = maths.m, maths.p, maths.t
    symmetric = maths.is_symmetric

    y_top = float(np.max(yu))
    y_bottom = float(np.min(yl))

    # Camber line and chord line
    x_fine = np.linspace(0, 1, 300)
    yc_fine, dyc_fine = maths.calculate_camber_line(x_fine)

    line([0, 1], [0, 0], CHORD_COLOUR)
    line(x_fine, yc_fine, CAMBER_COLOUR, style="--", width=1.6)

    # Nose circle (leading edge) and trailing edge ring
    nose_radius = maths.leading_edge_radius()
    draw_radius = max(nose_radius, 0.018)
    slope_angle = math.atan(float(dyc_fine[0]))
    centre = (draw_radius * math.cos(slope_angle), draw_radius * math.sin(slope_angle))

    circle_angles = np.linspace(0, 2 * np.pi, 120)
    line(centre[0] + draw_radius * np.cos(circle_angles), centre[1] + draw_radius * np.sin(circle_angles), EDGE_COLOUR)
    line(1 + 0.022 * np.cos(circle_angles), 0.022 * np.sin(circle_angles), EDGE_COLOUR)

    # Pointer labels above the aerofoil
    row_y = y_top + 0.14
    pointer("Leading edge", (-0.12, row_y), (0.0, 0.0), EDGE_COLOUR)
    pointer("Upper surface", (0.14, row_y), surface_point(xu, yu, 0.14), SURFACE_COLOUR)

    t_index = int(np.argmax(maths.calculate_thickness(maths.x)))
    x_t = float(xu[t_index])
    top = (x_t, float(np.interp(x_t, xu, yu)))
    bottom = (x_t, float(np.interp(x_t, xl, yl)))

    pointer("Maximum thickness", (0.40, row_y),
            (top[0] + 0.25 * (bottom[0] - top[0]), top[1] + 0.25 * (bottom[1] - top[1])), THICKNESS_COLOUR)

    yc_62, _ = maths.calculate_camber_line(np.array([0.62]))
    pointer("Mean camber line" if not symmetric else "Mean camber line\n(= chord line)",
            (0.68, row_y), (0.62, float(yc_62[0])), CAMBER_COLOUR)
    pointer("Trailing edge", (1.10, row_y), (1.0, 0.0), EDGE_COLOUR)

    # Thickness arrow
    double_arrow(bottom, top, THICKNESS_COLOUR)

    # Lower surface and chord line labels
    lower_x, lower_y = surface_point(xl, yl, 0.80)
    pointer("Lower surface", (0.80, lower_y - 0.10), (lower_x, lower_y), SURFACE_COLOUR)
    label("Chord line", 0.86, -0.016, CHORD_COLOUR, va="top")

    # Maximum camber arrow and label
    if not symmetric:
        yc_max, _ = maths.calculate_camber_line(np.array([p]))
        yc_max = float(yc_max[0])
        double_arrow((p, 0.0), (p, yc_max), CAMBER_COLOUR)
        pointer("Maximum camber", (p + 0.16, -0.045), (p, yc_max * 0.5), CAMBER_COLOUR)

    # Nose circle label
    pointer(f"Nose circle\nr = {nose_radius * 100:.2f}% c", (-0.15, -0.05 - draw_radius), (centre[0], centre[1] - draw_radius * 0.3),
            EDGE_COLOUR)

    # Dimension lines below the aerofoil
    y_dim_t = y_bottom - 0.10
    y_dim_c = y_bottom - 0.20
    y_dim_chord = y_bottom - 0.30

    line([x_t, x_t], [bottom[1], y_dim_t - 0.02], THICKNESS_COLOUR, style=":", width=1.0)
    line([0, 0], [-0.02, y_dim_chord - 0.02], CHORD_COLOUR, style=":", width=1.0)
    line([1, 1], [-0.02, y_dim_chord - 0.02], CHORD_COLOUR, style=":", width=1.0)

    double_arrow((0, y_dim_t), (x_t, y_dim_t), THICKNESS_COLOUR)
    label("Location of\nmaximum thickness", x_t / 2, y_dim_t + 0.008, THICKNESS_COLOUR, va="bottom")

    if not symmetric:
        line([p, p], [0.0, y_dim_c - 0.02], CAMBER_COLOUR, style=":", width=1.0)
        double_arrow((0, y_dim_c), (p, y_dim_c), CAMBER_COLOUR)
        label("Location of\nmaximum camber", p / 2, y_dim_c + 0.008, CAMBER_COLOUR, va="bottom")

    double_arrow((0, y_dim_chord), (1, y_dim_chord), CHORD_COLOUR)
    label("Chord", 0.5, y_dim_chord + 0.008, CHORD_COLOUR, va="bottom")

    # Axis limits that fit every annotation, including when the aerofoil is rotated
    corners = [pt(-0.30, y_dim_chord - 0.06), pt(1.28, y_dim_chord - 0.06),
               pt(-0.30, row_y + 0.08), pt(1.28, row_y + 0.08)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    box = ax.get_window_extent()
    ratio = box.width / box.height
    centre_x, centre_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    width = max(max(xs) - min(xs), (max(ys) - min(ys)) * ratio)
    height = width / ratio

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(centre_x - width / 2, centre_x + width / 2)
    ax.set_ylim(centre_y - height / 2, centre_y + height / 2)