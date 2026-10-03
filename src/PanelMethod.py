import math

import numpy as np


def solve_panel_method(maths, angle_degrees, points=121):
    """Hess-Smith panel method: constant strength sources on every panel plus one vortex strength,
    with the Kutta condition at the trailing edge. Inviscid, incompressible, includes thickness.

    Returns the pressure coefficient on the upper and lower surface and the lift coefficient."""
    xu, yu, xl, yl = maths.calculate_coordinates(points)

    # Nodes run from the trailing edge, over the top, round the nose and back along the bottom
    x = np.concatenate([xu[::-1], xl[1:]])
    y = np.concatenate([yu[::-1], yl[1:]])

    dx, dy = np.diff(x), np.diff(y)
    length = np.hypot(dx, dy)
    keep = length > 1e-12
    x = np.concatenate([x[:-1][keep], [x[-1]]])
    y = np.concatenate([y[:-1][keep], [y[-1]]])
    dx, dy = np.diff(x), np.diff(y)
    length = np.hypot(dx, dy)

    tx, ty = dx / length, dy / length          # tangent
    mx, my = -ty, tx                           # left normal (into the body)
    nx, ny = ty, -tx                           # outward normal
    cx, cy = (x[:-1] + x[1:]) / 2, (y[:-1] + y[1:]) / 2
    n = len(length)

    rx = cx[:, None] - x[:-1][None, :]
    ry = cy[:, None] - y[:-1][None, :]
    local_x = rx * tx[None, :] + ry * ty[None, :]
    local_y = rx * mx[None, :] + ry * my[None, :]

    with np.errstate(divide="ignore", invalid="ignore"):
        source_u = np.log((local_x ** 2 + local_y ** 2) / ((local_x - length[None, :]) ** 2 + local_y ** 2)) / (4 * np.pi)
        source_v = (np.arctan2(local_y, local_x - length[None, :]) - np.arctan2(local_y, local_x)) / (2 * np.pi)

    diagonal = np.arange(n)
    source_u[diagonal, diagonal] = 0.0
    source_v[diagonal, diagonal] = -0.5       # evaluated on the outside of the panel

    # Unit source and unit vortex velocities in global axes (the vortex is the source turned 90 degrees)
    source_vx = source_u * tx[None, :] + source_v * mx[None, :]
    source_vy = source_u * ty[None, :] + source_v * my[None, :]
    vortex_vx = -source_v * tx[None, :] + source_u * mx[None, :]
    vortex_vy = -source_v * ty[None, :] + source_u * my[None, :]

    source_normal = source_vx * nx[:, None] + source_vy * ny[:, None]
    source_tangent = source_vx * tx[:, None] + source_vy * ty[:, None]
    vortex_normal = (vortex_vx * nx[:, None] + vortex_vy * ny[:, None]).sum(axis=1)
    vortex_tangent = (vortex_vx * tx[:, None] + vortex_vy * ty[:, None]).sum(axis=1)

    alpha = math.radians(angle_degrees)
    free_x, free_y = math.cos(alpha), math.sin(alpha)

    matrix = np.zeros((n + 1, n + 1))
    rhs = np.zeros(n + 1)
    matrix[:n, :n] = source_normal
    matrix[:n, n] = vortex_normal
    rhs[:n] = -(free_x * nx + free_y * ny)

    # Kutta condition: the flow leaves the trailing edge from the top and bottom at the same speed
    matrix[n, :n] = source_tangent[0] + source_tangent[-1]
    matrix[n, n] = vortex_tangent[0] + vortex_tangent[-1]
    rhs[n] = -(free_x * (tx[0] + tx[-1]) + free_y * (ty[0] + ty[-1]))

    solution = np.linalg.solve(matrix, rhs)
    sources, gamma = solution[:n], solution[n]

    surface_speed = free_x * tx + free_y * ty + source_tangent @ sources + vortex_tangent * gamma
    cp = 1 - surface_speed ** 2

    # Lift from the pressure forces on the panels, resolved perpendicular to the free stream
    force_x = -np.sum(cp * nx * length)
    force_y = -np.sum(cp * ny * length)
    chord = float(np.max(x) - np.min(x))
    cl = (force_y * math.cos(alpha) - force_x * math.sin(alpha)) / chord

    nose = int(np.argmin(x))
    upper = slice(0, nose)
    lower = slice(nose, n)

    return {"x_upper": cx[upper][::-1], "cp_upper": cp[upper][::-1],
            "x_lower": cx[lower], "cp_lower": cp[lower],
            "cl": float(cl), "panels": n}