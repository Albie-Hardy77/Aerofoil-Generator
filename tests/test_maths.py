"""Checks the maths and file formats against known results. Run from the project folder with:
    python -m unittest discover tests
"""
import math
import sys, os
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np

import CoordinateExport
import Flow
import ProfileImport
import StepExporter
import Storage
from AerodynamicMaths import AerodynamicMaths
from AerofoilGeometryMaths import AerofoilMaths
from PanelMethod import solve_panel_method


def naca(designation):
    maths = AerofoilMaths()
    maths.set_designation(designation)
    return maths


class ThinAerofoilTheory(unittest.TestCase):
    def test_symmetric_section_has_no_camber_effects(self):
        aero = AerodynamicMaths(naca("0012"))
        self.assertAlmostEqual(aero.calculate_zero_lift_angle_of_attack(), 0.0, places=6)
        self.assertAlmostEqual(aero.calculate_zero_lift_pitching_moment(), 0.0, places=6)
        self.assertAlmostEqual(aero.calculate_lift_coefficient(5), 2 * math.pi * math.radians(5), places=6)

    def test_naca_2412(self):
        # Textbook thin aerofoil results: alpha_0 = -2.08 deg, Cm_c/4 = -0.053
        aero = AerodynamicMaths(naca("2412"))
        self.assertAlmostEqual(aero.calculate_zero_lift_angle_of_attack(), -2.077, delta=0.01)
        self.assertAlmostEqual(aero.calculate_zero_lift_pitching_moment(), -0.053, delta=0.001)

    def test_five_digit_design_lift(self):
        # The first digit sets the design lift coefficient: 0.15 per unit, so 23012 is designed for Cl = 0.3
        for designation, design_cl in (("23012", 0.3), ("43012", 0.6), ("23112", 0.3)):
            aero = AerodynamicMaths(naca(designation))
            self.assertAlmostEqual(aero.calculate_ideal_lift_coefficient(), design_cl, delta=0.005, msg=designation)

    def test_centre_of_pressure_is_aft_of_quarter_chord_for_positive_camber(self):
        aero = AerodynamicMaths(naca("2412"))
        self.assertGreater(aero.calculate_centre_of_pressure(4), 0.25)
        self.assertIsNone(aero.calculate_centre_of_pressure(-2.077))      # no lift, so no centre of pressure


class Geometry(unittest.TestCase):
    def test_designation_validation(self):
        for bad in ("12", "2400", "2012", "03012", "26012", "23212", "21112", "abcd"):
            with self.assertRaises(ValueError, msg=bad):
                naca(bad)

    def test_thickness_and_closed_trailing_edge(self):
        maths = naca("2412")
        xu, yu, xl, yl = maths.calculate_coordinates(400)
        self.assertAlmostEqual(float(np.max(yu - yl)), 0.12, delta=0.002)
        self.assertAlmostEqual(yu[-1], yl[-1], places=6)
        self.assertAlmostEqual(maths.max_thickness_position(), 0.30, delta=0.01)

    def test_cross_section_area(self):
        # A NACA 00xx section has an area of about 0.685 t c^2
        self.assertAlmostEqual(naca("0012").cross_section_area(), 0.685 * 0.12, delta=0.001)


class PanelMethod(unittest.TestCase):
    def test_symmetric_section_has_no_lift_at_zero_angle(self):
        self.assertAlmostEqual(solve_panel_method(naca("0012"), 0)["cl"], 0.0, places=4)

    def test_lift_is_close_to_thin_aerofoil_theory(self):
        # Thickness adds a few percent of lift on top of thin aerofoil theory
        maths = naca("2412")
        panel = solve_panel_method(maths, 5)["cl"]
        thin = AerodynamicMaths(maths).calculate_lift_coefficient(5)
        self.assertGreater(panel, thin)
        self.assertLess(panel, 1.2 * thin)


class Files(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def test_dat_round_trip(self):
        original = naca("4415")
        path = self.folder / "profile.dat"
        CoordinateExport.write_dat(path, original)

        name, points = ProfileImport.read_dat(path)
        imported = AerofoilMaths()
        imported.set_custom_profile(name, points)

        # An imported file's chord runs to the nose point farthest from the trailing edge, not to the start of
        # the NACA camber line, so a cambered section comes back rotated by about 0.3 degrees
        self.assertEqual(name, "NACA 4415")
        self.assertAlmostEqual(imported.t, original.t, delta=0.002)
        self.assertAlmostEqual(imported.m, original.m, delta=0.004)
        self.assertAlmostEqual(AerodynamicMaths(imported).calculate_zero_lift_angle_of_attack(),
                               AerodynamicMaths(original).calculate_zero_lift_angle_of_attack(), delta=0.25)

    def test_lednicer_format(self):
        maths = naca("2412")
        xu, yu, xl, yl = maths.calculate_coordinates(30)
        lines = ["NACA 2412 Lednicer", "30. 30.", ""] + [f"{a:.6f} {b:.6f}" for a, b in zip(xu, yu)] + [""] \
            + [f"{a:.6f} {b:.6f}" for a, b in zip(xl, yl)]

        name, points = ProfileImport.parse_dat_text("\n".join(lines))
        self.assertEqual(name, "NACA 2412 Lednicer")
        self.assertEqual(len(points), 59)
        self.assertGreater(points[5, 1], 0)       # the upper surface comes first

    def test_dxf_and_csv(self):
        maths = naca("2412")
        CoordinateExport.write_dxf(self.folder / "profile.dxf", maths, 100)
        CoordinateExport.write_csv(self.folder / "profile.csv", maths, 100)

        dxf = (self.folder / "profile.dxf").read_text()
        self.assertTrue(dxf.rstrip().endswith("EOF"))
        self.assertEqual(dxf.count("VERTEX"), len(CoordinateExport.selig_points(maths)[0]) - 1)

    def test_step_file(self):
        path = self.folder / "wing.step"
        StepExporter.export_step(path, naca("2412"), 100, 75, "wing", tip_chord_mm=60, sweep_deg=10, twist_deg=-3)

        text = path.read_text()
        self.assertTrue(text.startswith("ISO-10303-21;"))
        self.assertEqual(text.count("ADVANCED_FACE"), 4)
        self.assertIn("MANIFOLD_SOLID_BREP", text)


class Library(unittest.TestCase):
    def test_entries_are_cleaned(self):
        self.assertEqual(Storage.clean_entry({"designation": "2412"})["id"], "naca-2412")      # old format upgraded
        self.assertIsNone(Storage.clean_entry({"kind": "naca", "designation": "24"}))
        self.assertIsNone(Storage.clean_entry({"kind": "custom", "points": [[float("nan"), 0]] * 12}))

    def test_custom_entry_round_trip(self):
        maths = naca("2412")
        name, points = ProfileImport.parse_dat_text(
            "test\n" + "\n".join(f"{a} {b}" for a, b in zip(*CoordinateExport.selig_points(maths))))
        custom = AerofoilMaths()
        custom.set_custom_profile(name, points)

        entry = Storage.clean_entry(custom.to_entry())
        reloaded = AerofoilMaths.from_entry(entry)
        self.assertAlmostEqual(reloaded.t, custom.t, places=4)


class Wing(unittest.TestCase):
    def test_rectangular_wing(self):
        # Semi-span 75 with a 100 chord: full span 150, area 15000, aspect ratio 1.5
        geometry = Flow.wing_geometry(100, 100, 75)
        self.assertEqual(geometry["span"], 150)
        self.assertEqual(geometry["area"], 15000)
        self.assertAlmostEqual(geometry["aspect_ratio"], 1.5)
        self.assertAlmostEqual(geometry["mean_chord"], 100)

    def test_tapered_wing(self):
        geometry = Flow.wing_geometry(2.0, 1.0, 5.0)
        self.assertAlmostEqual(geometry["area"], 15.0)
        self.assertAlmostEqual(geometry["aspect_ratio"], 100 / 15)
        self.assertAlmostEqual(geometry["mean_chord"], 2 * 2 / 3 * (1 + 0.5 + 0.25) / 1.5)

    def test_standard_atmosphere(self):
        temperature, density = Flow.standard_atmosphere(0)
        self.assertAlmostEqual(temperature, 15.0)
        self.assertAlmostEqual(density, 1.225)
        self.assertAlmostEqual(Flow.standard_atmosphere(11000)[1], 0.3639, delta=0.001)


if __name__ == "__main__":
    unittest.main()
