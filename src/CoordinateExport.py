import numpy as np

MAX_POINTS = 200


def selig_points(maths):
    """Outline from the trailing edge, over the top, round the nose and back along the bottom (chord = 1)."""
    xu, yu, xl, yl = maths.calculate_coordinates(min(maths.resolution, MAX_POINTS))

    return np.concatenate([xu[::-1], xl[1:]]), np.concatenate([yu[::-1], yl[1:]])


def write_dat(path, maths):
    x, y = selig_points(maths)

    with open(path, "w", encoding="utf-8") as file:
        file.write(f"{maths.display_name}\n")
        for a, b in zip(x, y):
            file.write(f"{a:10.6f} {b:10.6f}\n")


def write_csv(path, maths, chord_mm):
    xu, yu, xl, yl = maths.calculate_coordinates(min(maths.resolution, MAX_POINTS))

    with open(path, "w", encoding="utf-8") as file:
        file.write(f"# {maths.display_name}, chord {chord_mm} mm\n")
        file.write("surface,x_over_c,y_over_c,x_mm,y_mm\n")

        for label, xs, ys in (("upper", xu, yu), ("lower", xl, yl)):
            for a, b in zip(xs, ys):
                file.write(f"{label},{a:.6f},{b:.6f},{a * chord_mm:.4f},{b * chord_mm:.4f}\n")


def write_dxf(path, maths, chord_mm):
    """A closed 2D polyline of the profile in millimetres (DXF R12, opens in any CAD package)."""
    x, y = selig_points(maths)
    if np.hypot(x[-1] - x[0], y[-1] - y[0]) < 1e-9:
        x, y = x[:-1], y[:-1]       # the last point repeats the first, the polyline is closed (kept for a blunt trailing edge)
    x, y = x * chord_mm, y * chord_mm

    lines = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "0", "ENDSEC",
             "0", "SECTION", "2", "ENTITIES",
             "0", "POLYLINE", "8", "AEROFOIL", "66", "1", "70", "1"]

    for a, b in zip(x, y):
        lines += ["0", "VERTEX", "8", "AEROFOIL", "10", f"{a:.6f}", "20", f"{b:.6f}", "30", "0.0"]

    lines += ["0", "SEQEND", "8", "AEROFOIL", "0", "ENDSEC", "0", "EOF"]

    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")