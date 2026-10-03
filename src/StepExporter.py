import datetime
import numpy as np

from AerofoilGeometryMaths import tip_section

DEGREE = 3


def _real(value):
    return f"{float(value):.8f}"


def _find_span(n, p, u, knots):
    if u >= knots[n + 1]:
        return n

    low, high = p, n + 1
    mid = (low + high) // 2

    while u < knots[mid] or u >= knots[mid + 1]:
        if u < knots[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2

    return mid


def _basis_functions(span, u, p, knots):
    N = [0.0] * (p + 1)
    left = [0.0] * (p + 1)
    right = [0.0] * (p + 1)
    N[0] = 1.0

    for j in range(1, p + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0

        for r in range(j):
            temp = N[r] / (right[r + 1] + left[j - r])
            N[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp

        N[j] = saved

    return N


def interpolate_curve(points):
    # Global cubic B-spline interpolation through the points (chord-length parameterised)
    points = np.asarray(points, dtype=float)
    n = len(points)

    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    params = np.concatenate([[0.0], np.cumsum(distances)])
    params /= params[-1]

    knots = np.zeros(n + DEGREE + 1)
    knots[-(DEGREE + 1):] = 1.0
    for j in range(1, n - DEGREE):
        knots[j + DEGREE] = np.sum(params[j:j + DEGREE]) / DEGREE

    matrix = np.zeros((n, n))
    for row, u in enumerate(params):
        span = _find_span(n - 1, DEGREE, u, knots)
        matrix[row, span - DEGREE:span + 1] = _basis_functions(span, u, DEGREE, knots)

    control_points = np.linalg.solve(matrix, points)
    control_points[0], control_points[-1] = points[0], points[-1]

    unique, counts = np.unique(knots, return_counts=True)

    return control_points, unique, counts


class _StepFile:
    def __init__(self):
        self.lines = []

    def add(self, text):
        self.lines.append(text)
        return len(self.lines)

    def point(self, xyz):
        return self.add(f"CARTESIAN_POINT('',({_real(xyz[0])},{_real(xyz[1])},{_real(xyz[2])}))")

    def direction(self, xyz):
        return self.add(f"DIRECTION('',({_real(xyz[0])},{_real(xyz[1])},{_real(xyz[2])}))")


def _refs(ids):
    return ",".join(f"#{i}" for i in ids)


def export_step(path, maths, chord_mm, span_mm, name, points=100, tip_chord_mm=None, sweep_deg=0.0, twist_deg=0.0):
    xu, yu, xl, yl = maths.calculate_coordinates(points)
    zeros = np.zeros(len(xu))

    upper = np.column_stack([xu, yu, zeros]) * [chord_mm, chord_mm, 1.0]
    lower = np.column_stack([xl, yl, zeros]) * [chord_mm, chord_mm, 1.0]

    # Make the leading and trailing edge points shared exactly
    upper[0] = lower[0] = (0.0, 0.0, 0.0)
    upper[-1] = lower[-1] = (chord_mm, 0.0, 0.0)

    tip_chord_mm = chord_mm if tip_chord_mm is None else tip_chord_mm

    def tip(xy):
        xy = np.atleast_2d(xy)
        tx, ty = tip_section(xy[:, 0], xy[:, 1], chord_mm, tip_chord_mm, span_mm, sweep_deg, twist_deg)
        return np.column_stack([tx, ty])

    f = _StepFile()

    # Product structure (ids are fixed by insertion order)
    app_context = f.add("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    f.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#{app_context})")
    product_context = f.add(f"PRODUCT_CONTEXT('',#{app_context},'mechanical')")
    product = f.add(f"PRODUCT('{name}','{name}','',(#{product_context}))")
    formation = f.add(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
    definition_context = f.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_context},'design')")
    definition = f.add(f"PRODUCT_DEFINITION('design','',#{formation},#{definition_context})")
    definition_shape = f.add(f"PRODUCT_DEFINITION_SHAPE('','',#{definition})")

    # Units and context
    length_unit = f.add("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.))")
    angle_unit = f.add("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))")
    solid_angle_unit = f.add("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())")
    uncertainty = f.add(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),#{length_unit},"
                        "'distance_accuracy_value','confusion accuracy')")
    context = f.add(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty})) "
                    f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length_unit},#{angle_unit},#{solid_angle_unit})) "
                    "REPRESENTATION_CONTEXT('',''))")

    # Shared geometry
    origin = f.point((0, 0, 0))
    dir_x = f.direction((1, 0, 0))
    dir_z = f.direction((0, 0, 1))
    world_axis = f.add(f"AXIS2_PLACEMENT_3D('',#{origin},#{dir_z},#{dir_x})")

    # Control points for each curve at z = 0 and z = span
    def control_points_ids(curve_points, z):
        return [f.point((p[0], p[1], z)) for p in curve_points]

    upper_cp, upper_knots, upper_mults = interpolate_curve(upper)
    lower_cp, lower_knots, lower_mults = interpolate_curve(lower)

    upper_ids_0 = control_points_ids(upper_cp, 0.0)
    upper_tip = tip(upper_cp[:, :2])
    lower_tip = tip(lower_cp[:, :2])
    upper_ids_1 = [f.point((p[0], p[1], span_mm)) for p in upper_tip]
    lower_ids_0 = control_points_ids(lower_cp, 0.0)
    lower_ids_1 = [f.point((p[0], p[1], span_mm)) for p in lower_tip]

    def curve(ids, knots, mults):
        return f.add(f"B_SPLINE_CURVE_WITH_KNOTS('',{DEGREE},({_refs(ids)}),.UNSPECIFIED.,.F.,.F.,"
                     f"({','.join(str(int(m)) for m in mults)}),({','.join(_real(k) for k in knots)}),.UNSPECIFIED.)")

    def surface(ids_0, ids_1, knots, mults):
        rows = ",".join(f"(#{a},#{b})" for a, b in zip(ids_0, ids_1))
        return f.add(f"B_SPLINE_SURFACE_WITH_KNOTS('',{DEGREE},1,({rows}),.UNSPECIFIED.,.F.,.F.,.F.,"
                     f"({','.join(str(int(m)) for m in mults)}),(2,2),"
                     f"({','.join(_real(k) for k in knots)}),(0.,1.),.UNSPECIFIED.)")

    upper_curve_0 = curve(upper_ids_0, upper_knots, upper_mults)
    upper_curve_1 = curve(upper_ids_1, upper_knots, upper_mults)
    lower_curve_0 = curve(lower_ids_0, lower_knots, lower_mults)
    lower_curve_1 = curve(lower_ids_1, lower_knots, lower_mults)

    upper_surface = surface(upper_ids_0, upper_ids_1, upper_knots, upper_mults)
    lower_surface = surface(lower_ids_0, lower_ids_1, lower_knots, lower_mults)

    # Vertices
    vertices = {}
    tip_edges = tip(np.array([[0.0, 0.0], [chord_mm, 0.0]]))
    positions = {"LE0": (0, 0, 0), "TE0": (chord_mm, 0, 0),
                 "LE1": (tip_edges[0, 0], tip_edges[0, 1], span_mm), "TE1": (tip_edges[1, 0], tip_edges[1, 1], span_mm)}
    for key, xyz in positions.items():
        vertices[key] = f.add(f"VERTEX_POINT('',#{f.point(xyz)})")

    # Straight edges along the span at the leading and trailing edge
    def line_edge(start_key, end_key, start_xyz):
        delta = np.array(positions[end_key], dtype=float) - np.array(positions[start_key], dtype=float)
        line_point = f.point(start_xyz)
        line_direction = f.direction(delta / np.linalg.norm(delta))
        vector = f.add(f"VECTOR('',#{line_direction},{_real(np.linalg.norm(delta))})")
        line = f.add(f"LINE('',#{line_point},#{vector})")
        return f.add(f"EDGE_CURVE('',#{vertices[start_key]},#{vertices[end_key]},#{line},.T.)")

    def curve_edge(start_key, end_key, curve_id):
        return f.add(f"EDGE_CURVE('',#{vertices[start_key]},#{vertices[end_key]},#{curve_id},.T.)")

    E1 = curve_edge("LE0", "TE0", upper_curve_0)
    E2 = curve_edge("LE0", "TE0", lower_curve_0)
    E3 = curve_edge("LE1", "TE1", upper_curve_1)
    E4 = curve_edge("LE1", "TE1", lower_curve_1)
    E5 = line_edge("LE0", "LE1", (0, 0, 0))
    E6 = line_edge("TE0", "TE1", (chord_mm, 0, 0))

    def face(edges_with_sense, surface_id, same_sense):
        oriented = [f.add(f"ORIENTED_EDGE('',*,*,#{edge},{'.T.' if sense else '.F.'})")
                    for edge, sense in edges_with_sense]
        loop = f.add(f"EDGE_LOOP('',({_refs(oriented)}))")
        bound = f.add(f"FACE_OUTER_BOUND('',#{loop},.T.)")
        return f.add(f"ADVANCED_FACE('',(#{bound}),#{surface_id},{'.T.' if same_sense else '.F.'})")

    plane_0 = f.add(f"PLANE('',#{world_axis})")
    cap_origin = f.point((0, 0, span_mm))
    cap_axis = f.add(f"AXIS2_PLACEMENT_3D('',#{cap_origin},#{dir_z},#{dir_x})")
    plane_1 = f.add(f"PLANE('',#{cap_axis})")

    faces = [
        face([(E1, True), (E2, False)], plane_0, False),                               # cap at z = 0
        face([(E4, True), (E3, False)], plane_1, True),                                # cap at z = span
        face([(E1, False), (E5, True), (E3, True), (E6, False)], upper_surface, False),  # upper surface
        face([(E2, True), (E6, True), (E4, False), (E5, False)], lower_surface, True),   # lower surface
    ]

    shell = f.add(f"CLOSED_SHELL('',({_refs(faces)}))")
    brep = f.add(f"MANIFOLD_SOLID_BREP('{name}',#{shell})")

    representation = f.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',(#{world_axis},#{brep}),#{context})")
    f.add(f"SHAPE_DEFINITION_REPRESENTATION(#{definition_shape},#{representation})")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    header = ("ISO-10303-21;\nHEADER;\n"
              f"FILE_DESCRIPTION(('{name} wing, root chord {chord_mm} mm, tip chord {tip_chord_mm} mm, span {span_mm} mm'),'2;1');\n"
              f"FILE_NAME('{name}.step','{timestamp}',('Aerofoil Generator'),(''),'','Aerofoil Generator','');\n"
              "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n")

    body = "\n".join(f"#{i} = {line};" for i, line in enumerate(f.lines, start=1))

    with open(path, "w", encoding="utf-8") as file:
        file.write(header + body + "\nENDSEC;\nEND-ISO-10303-21;\n")