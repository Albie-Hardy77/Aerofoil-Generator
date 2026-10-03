import math

GAMMA = 1.4
GAS_CONSTANT = 287.05


def standard_atmosphere(altitude_m):
    """International Standard Atmosphere up to 20 km: returns (temperature in C, density in kg/m3)."""
    h = max(0.0, min(float(altitude_m), 20000.0))

    if h <= 11000:
        temperature = 288.15 - 0.0065 * h
        density = 1.225 * (temperature / 288.15) ** 4.2559
    else:
        temperature = 216.65
        density = 0.3639 * math.exp(-(h - 11000) / 6341.6)

    return temperature - 273.15, density


def flow_conditions(airspeed, density, temperature_c, reference_chord_m):
    temperature = temperature_c + 273.15
    speed_of_sound = math.sqrt(GAMMA * GAS_CONSTANT * temperature)
    viscosity = 1.458e-6 * temperature ** 1.5 / (temperature + 110.4)      # Sutherland's law

    return {"speed_of_sound": speed_of_sound,
            "mach": airspeed / speed_of_sound,
            "viscosity": viscosity,
            "reynolds": density * airspeed * reference_chord_m / viscosity,
            "dynamic_pressure": 0.5 * density * airspeed ** 2}


def wing_geometry(root_chord, tip_chord, semi_span):
    """Span, planform area, aspect ratio and mean aerodynamic chord of the whole tapered wing (any length unit).
    The modelled panel runs from the root to one tip, so the full wing is two of them: b = 2s, S = (cr + ct) s."""
    span = 2 * semi_span
    area = (root_chord + tip_chord) * semi_span
    taper = tip_chord / root_chord
    mean_chord = (2 / 3) * root_chord * (1 + taper + taper ** 2) / (1 + taper)

    return {"span": span, "area": area, "aspect_ratio": span ** 2 / area, "mean_chord": mean_chord}