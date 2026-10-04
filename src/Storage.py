import hashlib
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "aerofoil_data"
SETTINGS_PATH = DATA_DIR / "settings.json"
LIBRARY_PATH = DATA_DIR / "library.json"

SETTING_KEYS = ["resolution", "chord", "span", "wireframe", "tip_chord", "sweep", "twist"]
DEFAULT_SETTINGS = {"resolution": 100, "chord": 100, "span": 75, "wireframe": 3, "tip_chord": 100, "sweep": 0, "twist": 0}
SETTING_RANGES = {"resolution": (1, 100), "chord": (10, 1000), "span": (10, 1000), "wireframe": (1, 5),
                  "tip_chord": (10, 1000), "sweep": (-60, 60), "twist": (-20, 20)}


def _read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return fallback


def _write_json(path, data):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        os.replace(temp_path, path)
        return True
    except OSError:
        return False


# Settings
def load_settings():
    stored = _read_json(SETTINGS_PATH, {})
    settings = dict(DEFAULT_SETTINGS)

    if isinstance(stored, dict):
        for key in SETTING_KEYS:
            value = stored.get(key)
            low, high = SETTING_RANGES[key]
            if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
                settings[key] = value

    return settings


def save_settings(settings):
    return _write_json(SETTINGS_PATH, {key: settings[key] for key in SETTING_KEYS})


# Library
FLOW_PATH = DATA_DIR / "flow.json"
DEFAULT_FLOW = {"airspeed": 50.0, "density": 1.225, "temperature": 15.0, "altitude": 0.0}


def entry_id(entry):
    if entry["kind"] == "naca":
        return f"naca-{entry['designation']}"

    return "custom-" + hashlib.sha1(json.dumps(entry["points"]).encode()).hexdigest()[:10]


def clean_entry(entry):
    """Returns a tidy copy of a library entry, or None if it isn't valid. Old entries (designation only) are upgraded."""
    if not isinstance(entry, dict):
        return None

    kind = entry.get("kind") or ("naca" if "designation" in entry else None)

    if kind == "naca":
        designation = str(entry.get("designation", ""))
        if not (designation.isdigit() and len(designation) in (4, 5)):
            return None
        clean = {"kind": "naca", "designation": designation, "name": str(entry.get("name") or f"NACA {designation}")[:60]}

    elif kind == "custom":
        try:
            points = [[float(a), float(b)] for a, b in entry["points"]]
        except (KeyError, TypeError, ValueError):
            return None
        if len(points) < 10 or not all(math.isfinite(value) for point in points for value in point):
            return None
        clean = {"kind": "custom", "name": str(entry.get("name") or "Custom profile")[:60], "points": points}

    else:
        return None

    clean["notes"] = str(entry.get("notes", ""))[:200]
    clean["saved"] = str(entry.get("saved") or datetime.now().strftime("%Y-%m-%d %H:%M"))
    clean["id"] = entry_id(clean)

    return clean


def load_library():
    stored = _read_json(LIBRARY_PATH, [])
    entries = []

    for entry in stored if isinstance(stored, list) else []:
        clean = clean_entry(entry)
        if clean and all(clean["id"] != other["id"] for other in entries):
            entries.append(clean)

    return entries


def save_library(entries):
    return _write_json(LIBRARY_PATH, entries)


def add_entry(entry):
    """Adds a new entry, returns False if it's invalid or already in the library."""
    clean = clean_entry(entry)
    library = load_library()

    if clean is None or any(clean["id"] == other["id"] for other in library):
        return False

    clean["saved"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    library.append(clean)
    return save_library(library)


def update_entry(identifier, name=None, notes=None):
    library = load_library()

    for entry in library:
        if entry["id"] == identifier:
            if name is not None:
                entry["name"] = name.strip()[:60] or entry["name"]
            if notes is not None:
                entry["notes"] = notes.strip()[:200]

    return save_library(library)


def remove_entry(identifier):
    return save_library([entry for entry in load_library() if entry["id"] != identifier])


def export_library(path):
    with open(path, "w", encoding="utf-8") as file:
        json.dump({"aerofoil_collection": 1, "entries": load_library()}, file, indent=2)


def import_library(path):
    """Merges a collection file into the library. Returns (number added, number skipped)."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        raise ValueError("That isn't a readable collection file")

    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError("That isn't an aerofoil collection file")

    library = load_library()
    added = skipped = 0

    for entry in entries:
        clean = clean_entry(entry)
        if clean is None or any(clean["id"] == other["id"] for other in library):
            skipped += 1
        else:
            library.append(clean)
            added += 1

    save_library(library)
    return added, skipped


# Flow conditions
def load_flow():
    stored = _read_json(FLOW_PATH, {})
    flow = dict(DEFAULT_FLOW)

    if isinstance(stored, dict):
        for key in flow:
            if isinstance(stored.get(key), (int, float)) and not isinstance(stored.get(key), bool):
                flow[key] = float(stored[key])

    return flow


def save_flow(flow):
    return _write_json(FLOW_PATH, flow)


# Theme
THEME_PATH = DATA_DIR / "theme.json"


def load_theme_name():
    stored = _read_json(THEME_PATH, {})

    if isinstance(stored, dict) and isinstance(stored.get("theme"), str):
        return stored["theme"]

    return None


def save_theme_name(name):
    return _write_json(THEME_PATH, {"theme": name})