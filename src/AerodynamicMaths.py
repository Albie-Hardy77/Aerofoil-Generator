import math
import numpy as np

_trapezoid = getattr(np, "trapezoid", None) or np.trapz


class AerodynamicMaths:
    # Thin aerofoil theory integrals use their own fixed resolution so the results
    # stay accurate however low the display resolution is set
    INTEGRATION_POINTS = 2001

    def __init__(self, aerofoil_maths):
        self.AeroMaths = aerofoil_maths

    def calculate_leading_edge_radius(self):
        return self.AeroMaths.leading_edge_radius()

    def get_theta_and_dyc(self):
        theta = np.linspace(0, np.pi, self.INTEGRATION_POINTS)
        x_theta = (1 - np.cos(theta)) / 2
        dyc_theta = np.asarray(self.AeroMaths.calculate_dyc(x_theta))

        return theta, dyc_theta

    def calculate_fourier_coefficient_A0(self):
        theta, dyc_theta = self.get_theta_and_dyc()
        return -(1 / np.pi) * _trapezoid(dyc_theta, theta)

    def calculate_fourier_coefficient_A1(self):
        theta, dyc_theta = self.get_theta_and_dyc()
        return (2 / np.pi) * _trapezoid(dyc_theta * np.cos(theta), theta)

    def calculate_fourier_coefficient_A2(self):
        theta, dyc_theta = self.get_theta_and_dyc()
        return (2 / np.pi) * _trapezoid(dyc_theta * np.cos(2 * theta), theta)

    def calculate_zero_lift_angle_of_attack(self):
        A0 = self.calculate_fourier_coefficient_A0()
        A1 = self.calculate_fourier_coefficient_A1()

        return math.degrees(-A0 - (A1 / 2))

    def calculate_zero_lift_pitching_moment(self):
        A1 = self.calculate_fourier_coefficient_A1()
        A2 = self.calculate_fourier_coefficient_A2()

        return (np.pi / 4) * (A2 - A1)

    def calculate_ideal_lift_coefficient(self):
        # FIX: at the ideal angle the true A0 is zero, so Cli = pi * A1.
        # The old pi * (2*A0 + A1) used the camber-only A0 and over/under-shot.
        return np.pi * self.calculate_fourier_coefficient_A1()

    def calculate_ideal_angle_of_attack(self):
        alpha_0_rad = math.radians(self.calculate_zero_lift_angle_of_attack())
        Cli = self.calculate_ideal_lift_coefficient()

        return math.degrees(alpha_0_rad + (Cli / (2 * np.pi)))

    def calculate_lift_coefficient(self, angle_degrees):
        alpha_rad = math.radians(angle_degrees)
        alpha_0_rad = math.radians(self.calculate_zero_lift_angle_of_attack())

        return 2 * np.pi * (alpha_rad - alpha_0_rad)

    def calculate_wing_lift_coefficient(self, angle_degrees, aspect_ratio):
        # Finite wing: the 2D lift slope 2 pi is reduced to a0 / (1 + a0 / (pi AR))
        a0 = 2 * np.pi
        slope = a0 / (1 + a0 / (np.pi * aspect_ratio))

        return slope * (math.radians(angle_degrees) - math.radians(self.calculate_zero_lift_angle_of_attack()))

    def calculate_moment_quarter_chord(self):
        return self.calculate_zero_lift_pitching_moment()

    def calculate_moment_leading_edge(self, angle_degrees):
        Cl = self.calculate_lift_coefficient(angle_degrees)
        return self.calculate_moment_quarter_chord() - (Cl / 4)

    def calculate_centre_of_pressure(self, angle_degrees):
        Cl = self.calculate_lift_coefficient(angle_degrees)
        Cm_c4 = self.calculate_moment_quarter_chord()

        if abs(Cl) < 0.05:
            return None

        xcp = 0.25 - (Cm_c4 / Cl)

        if xcp < 0 or xcp >= 1:
            return None

        return xcp