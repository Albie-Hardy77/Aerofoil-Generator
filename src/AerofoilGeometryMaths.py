import math
import re

import numpy as np


def tip_section(x, y, chord, tip_chord, span, sweep_degrees, twist_degrees):
    """Moves root-section points onto the wing tip: scaled to the tip chord, twisted about the
    quarter chord (positive = nose up) and swept back by the leading edge sweep angle."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    scale = tip_chord / chord
    qx = (x - 0.25 * chord) * scale
    qy = y * scale

    twist = math.radians(twist_degrees)
    rx = qx * math.cos(twist) + qy * math.sin(twist)
    ry = -qx * math.sin(twist) + qy * math.cos(twist)

    offset = span * math.tan(math.radians(sweep_degrees))

    return rx + 0.25 * tip_chord + offset, ry


def normalise_points(points):
    """Translates, rotates and scales Selig ordered points so the leading edge is (0, 0) and the
    trailing edge is on the x axis at x = 1."""
    pts = np.asarray(points, dtype=float)

    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 10:
        raise ValueError("A profile needs at least 10 points")

    leading_edge = pts[int(np.argmin(pts[:, 0]))]
    trailing_edge = (pts[0] + pts[-1]) / 2
    chord_vector = trailing_edge - leading_edge
    chord = float(np.hypot(*chord_vector))

    if chord < 1e-9:
        raise ValueError("The leading and trailing edge are in the same place")

    angle = math.atan2(chord_vector[1], chord_vector[0])
    shifted = (pts - leading_edge) / chord
    c, s = math.cos(-angle), math.sin(-angle)

    return np.column_stack([shifted[:, 0] * c - shifted[:, 1] * s, shifted[:, 0] * s + shifted[:, 1] * c])


class _Spline:
    """Natural cubic spline"""

    def __init__(self, x, y):
        n = len(x)
        h = np.diff(x)
        matrix = np.zeros((n, n))
        rhs = np.zeros(n)
        matrix[0, 0] = matrix[-1, -1] = 1.0

        for i in range(1, n - 1):
            matrix[i, i - 1] = h[i - 1]
            matrix[i, i] = 2 * (h[i - 1] + h[i])
            matrix[i, i + 1] = h[i]
            rhs[i] = 6 * ((y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1])

        self.x, self.y, self.h = x, y, h
        self.m = np.linalg.solve(matrix, rhs)

    def __call__(self, xq):
        xq = np.asarray(xq, dtype=float)
        i = np.clip(np.searchsorted(self.x, xq) - 1, 0, len(self.x) - 2)
        h = self.h[i]
        a = (self.x[i + 1] - xq) / h
        b = (xq - self.x[i]) / h

        return (a * self.y[i] + b * self.y[i + 1]
                + ((a ** 3 - a) * self.m[i] + (b ** 3 - b) * self.m[i + 1]) * h ** 2 / 6)


# NACA 5-digit camber line constants for a design lift coefficient of 0.3 (first digit 2)
FIVE_DIGIT_STANDARD = {1: (0.0580, 361.400), 2: (0.1260, 51.640), 3: (0.2025, 15.957), 4: (0.2900, 6.643), 5: (0.3910, 3.230)}
FIVE_DIGIT_REFLEX = {2: (0.1300, 51.990, 0.000764), 3: (0.2170, 15.793, 0.00677), 4: (0.3180, 6.520, 0.0303),
                     5: (0.4410, 3.191, 0.1355)}


class AerofoilMaths:
    # 0.1036 (instead of the original 0.1015) gives a thickness of exactly zero at the trailing edge
    TRAILING_EDGE_COEFFICIENT = 0.1036

    def __init__(self):
        self.resolution = 1000
        self.x = self.cosine_spacing(self.resolution)

        self.mode = "naca"
        self.series = 4
        self.design_cl = None
        self.reflex = False
        self._five = None
        self.designation = "0000"
        self.name = "NACA 0000"
        self.m = 0.0
        self.p = 0.0
        self.t = 0.0

        self.raw_points = None
        self._upper = None
        self._lower = None
        self._dense_x = None
        self._dense_dyc = None

    @staticmethod
    def cosine_spacing(points):
        # Clusters points around the leading and trailing edges where the curvature is highest
        beta = np.linspace(0, np.pi, points)
        return (1 - np.cos(beta)) / 2

    @staticmethod
    def from_entry(entry, resolution=1000):
        maths = AerofoilMaths()
        maths.set_resolution(resolution)

        if entry.get("kind") == "custom":
            maths.set_custom_profile(entry.get("name", "Custom profile"), entry["points"])
        else:
            maths.set_designation(entry["designation"])

        return maths

    def set_resolution(self, resolution):
        self.resolution = resolution
        self.x = self.cosine_spacing(self.resolution)

    @property
    def is_custom(self):
        return self.mode == "custom"

    @property
    def display_name(self):
        return self.name

    @property
    def file_stem(self):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", self.name).strip("_") or "aerofoil"

    def to_entry(self):
        if self.mode == "naca":
            return {"kind": "naca", "designation": self.designation, "name": self.name}

        return {"kind": "custom", "name": self.name,
                "points": [[round(float(a), 6), round(float(b), 6)] for a, b in self.raw_points]}

    def set_designation(self, designation):
        if len(designation) not in (4, 5) or not designation.isdigit():
            raise ValueError("Enter a four or five digit NACA code")

        if len(designation) == 5:
            self._set_five_digit(designation)
            return

        m = int(designation[0]) / 100
        p = int(designation[1]) / 10
        t = int(designation[2:4]) / 100

        if t == 0:
            raise ValueError("Maximum thickness can't be 00")

        if m > 0 and p == 0:
            raise ValueError("Camber position can't be 0 when the camber isn't 0")

        self.mode = "naca"
        self.series = 4
        self.design_cl = None
        self.reflex = False
        self._five = None
        self.designation = designation
        self.name = f"NACA {designation}"
        self.m, self.p, self.t = m, p, t
        self.raw_points = None

    def _set_five_digit(self, designation):
        lift, position, reflex, thickness = int(designation[0]), int(designation[1]), int(designation[2]), int(designation[3:5])

        if lift == 0:
            raise ValueError("The first digit (design lift) can't be 0")
        if not 1 <= position <= 5:
            raise ValueError("The second digit (camber position) must be 1 to 5")
        if reflex not in (0, 1):
            raise ValueError("The third digit must be 0 (standard) or 1 (reflex camber)")
        if reflex == 1 and position == 1:
            raise ValueError("Reflex camber needs a camber position of 2 to 5")
        if thickness == 0:
            raise ValueError("Maximum thickness can't be 00")

        scale = lift / 2        # the tabulated constants are for a design lift coefficient of 0.3 (lift digit 2)
        if reflex:
            m, k1, ratio = FIVE_DIGIT_REFLEX[position]
        else:
            (m, k1), ratio = FIVE_DIGIT_STANDARD[position], None

        self.mode = "naca"
        self.series = 5
        self.design_cl = 0.15 * lift
        self.reflex = bool(reflex)
        self._five = {"m": m, "k1": k1 * scale, "ratio": ratio}
        self.designation = designation
        self.name = f"NACA {designation}"
        self.t = thickness / 100
        self.raw_points = None

        x = self.cosine_spacing(2001)
        yc = self.calculate_camber_line(x)[0]
        index = int(np.argmax(np.abs(yc)))
        self.m, self.p = float(yc[index]), float(x[index])

    def _five_digit_camber(self, x):
        m, k1, ratio = self._five["m"], self._five["k1"], self._five["ratio"]
        front = x < m

        if ratio is None:
            yc = np.where(front, k1 / 6 * (x ** 3 - 3 * m * x ** 2 + m ** 2 * (3 - m) * x), k1 / 6 * m ** 3 * (1 - x))
            dyc = np.where(front, k1 / 6 * (3 * x ** 2 - 6 * m * x + m ** 2 * (3 - m)), -k1 / 6 * m ** 3 * np.ones_like(x))
        else:
            common = -ratio * (1 - m) ** 3 * x - m ** 3 * x + m ** 3
            yc = np.where(front, k1 / 6 * ((x - m) ** 3 + common), k1 / 6 * (ratio * (x - m) ** 3 + common))
            dyc = np.where(front, k1 / 6 * (3 * (x - m) ** 2 - ratio * (1 - m) ** 3 - m ** 3),
                           k1 / 6 * (3 * ratio * (x - m) ** 2 - ratio * (1 - m) ** 3 - m ** 3))

        return yc, dyc

    def set_custom_profile(self, name, points):
        pts = normalise_points(points)
        leading_edge = int(np.argmin(pts[:, 0]))

        surfaces = []
        for part in (pts[:leading_edge + 1][::-1], pts[leading_edge:]):
            part = part[np.argsort(part[:, 0], kind="stable")]
            part = part[np.concatenate([[True], np.diff(part[:, 0]) > 1e-7])]
            part = part.copy()
            part[0] = (0.0, 0.0)

            if len(part) < 5:
                raise ValueError("Each surface needs at least 5 points")

            surfaces.append(_Spline(np.sqrt(np.clip(part[:, 0], 0, None)), part[:, 1]))

        upper, lower = surfaces
        if float(upper(math.sqrt(0.5))) < float(lower(math.sqrt(0.5))):
            upper, lower = lower, upper

        self.mode = "custom"
        self.series = None
        self.design_cl = None
        self.reflex = False
        self.designation = ""
        self.name = (name or "Custom profile").strip()[:60]
        self.raw_points = pts
        self._upper, self._lower = upper, lower

        # Camber line slope on a dense grid, used by thin aerofoil theory
        x = self.cosine_spacing(2001)
        yu, yl = self._surface(upper, x), self._surface(lower, x)
        yc = (yu + yl) / 2
        thickness = np.clip(yu - yl, 0, None)

        self._dense_x = x
        self._dense_dyc = np.gradient(yc, x)

        index = int(np.argmax(np.abs(yc)))
        self.m = float(yc[index]) if abs(yc[index]) >= 5e-4 else 0.0
        self.p = float(x[index]) if self.m != 0.0 else 0.0
        self.t = float(thickness.max())

    @staticmethod
    def _surface(spline, x):
        return spline(np.sqrt(np.clip(x, 0, 1)))

    @property
    def is_symmetric(self):
        if self.mode == "custom":
            return self.m == 0.0

        return self.m == 0 or self.p == 0

    def calculate_camber_line(self, x_array):
        x = np.asarray(x_array, dtype=float)

        if self.mode == "custom":
            yc = (self._surface(self._upper, x) + self._surface(self._lower, x)) / 2
            return yc, np.interp(x, self._dense_x, self._dense_dyc)

        if self.series == 5:
            return self._five_digit_camber(x)

        if self.is_symmetric:
            return np.zeros_like(x), np.zeros_like(x)

        m, p = self.m, self.p
        front = x <= p

        yc = np.where(front,
                      (m / p ** 2) * (2 * p * x - x ** 2),
                      (m / (1 - p) ** 2) * ((1 - 2 * p) + 2 * p * x - x ** 2))
        dyc = np.where(front,
                       (2 * m / p ** 2) * (p - x),
                       (2 * m / (1 - p) ** 2) * (p - x))

        return yc, dyc

    def calculate_dyc(self, x_array):
        return self.calculate_camber_line(x_array)[1]

    def calculate_thickness(self, x_array):
        # Half thickness at each x
        x = np.asarray(x_array, dtype=float)

        if self.mode == "custom":
            return np.clip((self._surface(self._upper, x) - self._surface(self._lower, x)) / 2, 0, None)

        return 5 * self.t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2
                             + 0.2843 * x ** 3 - self.TRAILING_EDGE_COEFFICIENT * x ** 4)

    def calculate_coordinates(self, points=None):
        x = self.x if points is None else self.cosine_spacing(points)

        if self.mode == "custom":
            return x.copy(), self._surface(self._upper, x), x.copy(), self._surface(self._lower, x)

        yc, dyc = self.calculate_camber_line(x)
        yt = self.calculate_thickness(x)
        theta = np.arctan(dyc)

        xu = x - yt * np.sin(theta)
        yu = yc + yt * np.cos(theta)

        xl = x + yt * np.sin(theta)
        yl = yc - yt * np.cos(theta)

        return xu, yu, xl, yl

    def leading_edge_radius(self):
        if self.mode == "naca":
            return 1.1019 * self.t ** 2

        x = np.linspace(0.002, 0.01, 9)
        return float(np.mean(self.calculate_thickness(x) ** 2 / (2 * x)))

    def max_thickness_position(self):
        x = self.cosine_spacing(2001)
        return float(x[np.argmax(self.calculate_thickness(x))])

    def cross_section_area(self):
        # Shoelace formula around the full outline, as a fraction of chord squared
        xu, yu, xl, yl = self.calculate_coordinates(1001)
        x = np.concatenate([xu, xl[::-1]])
        y = np.concatenate([yu, yl[::-1]])

        return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))