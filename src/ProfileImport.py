from pathlib import Path

import numpy as np

from AerofoilGeometryMaths import normalise_points


def _numbers(line):
    parts = line.replace(",", " ").split()

    try:
        return [float(p) for p in parts[:2]] if len(parts) >= 2 else None
    except ValueError:
        return None


def parse_dat_text(text, fallback_name="Imported profile"):
    """Reads Selig or Lednicer format coordinate files. Returns (name, normalised Selig ordered points)."""
    name = fallback_name
    rows = []
    seen_content = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        values = _numbers(line)
        if values is None:
            if not seen_content:
                name = line[:60]
            seen_content = True
            continue

        seen_content = True
        rows.append(values)

    if len(rows) < 10:
        raise ValueError("Couldn't find enough coordinate points in the file")

    # Lednicer files start with the number of upper and lower points, e.g. "17. 17."
    first = rows[0]
    if first[0] > 1.5 and first[1] > 1.5 and first[0] == int(first[0]) and first[1] == int(first[1]):
        n_upper, n_lower = int(first[0]), int(first[1])
        coords = rows[1:]

        if len(coords) < n_upper + n_lower:
            raise ValueError("The Lednicer file has fewer points than it says")

        upper = np.array(coords[:n_upper])
        lower = np.array(coords[n_upper:n_upper + n_lower])
        points = np.vstack([upper[::-1], lower[1:]])
    else:
        points = np.array(rows)

    if len(points) > 5000:
        raise ValueError("Too many points in the file")

    points = normalise_points(points)

    # Make sure the first half of the file is the upper surface
    nose = int(np.argmin(points[:, 0]))
    if points[:nose + 1, 1].mean() < points[nose:, 1].mean():
        points = points[::-1]

    return name, np.round(points, 6)


def read_dat(path):
    path = Path(path)
    return parse_dat_text(path.read_text(encoding="utf-8", errors="ignore"), fallback_name=path.stem)