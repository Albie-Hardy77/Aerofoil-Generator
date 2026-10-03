# Shared colours and stylesheet builders so every window matches.
# The colours are a theme: call switch_theme() and every open window is recoloured live.

import re

from PySide6.QtWidgets import QWidget

import Storage

# Each theme is a window colour, a text colour and three accents (TEAL, AMBER and PINK are the
# names of the three accent roles, whatever colour a theme gives them) plus red/green for errors/success.
# The greys used for panels, buttons and borders are blended from the window colour automatically.
THEMES = {
    "Graphite": dict(background="#202020", text="#ffffff", teal="#70bac4", amber="#ebb734", pink="#e281e6",
                     red="#ff6e6e", green="#71d98c"),
    "Midnight": dict(background="#151b2b", text="#ffffff", teal="#6cb6ff", amber="#ffc857", pink="#ff79c6",
                     red="#ff6e6e", green="#71d98c"),
    "Forest":   dict(background="#18231d", text="#ffffff", teal="#7fd6b0", amber="#e6c35c", pink="#e88fa0",
                     red="#ff6e6e", green="#71d98c"),
    "Plum":     dict(background="#241a2e", text="#ffffff", teal="#b48cf2", amber="#ffd166", pink="#5ccfe6",
                     red="#ff6e6e", green="#71d98c"),
    "Ember":    dict(background="#261b17", text="#ffffff", teal="#ff9f5a", amber="#ffd166", pink="#f0658a",
                     red="#ff6e6e", green="#71d98c"),
    "Ocean":    dict(background="#10252b", text="#ffffff", teal="#5fe0c3", amber="#f2d06b", pink="#9a8cff",
                     red="#ff6e6e", green="#71d98c"),
    "Daylight": dict(background="#ebebeb", text="#202020", teal="#1d7f93", amber="#a87408", pink="#a32d8f",
                     red="#c62828", green="#2e7d32"),
}
DEFAULT_THEME = "Graphite"

APP_VERSION = "V1.0"     # shown in the corner of every window

# How far each grey sits between the window colour (0) and the text colour (1)
GREY_STEPS = {"PANEL": 0.022, "RAISED": 0.072, "PRESSED": 0.143, "GREY": 0.215, "LIGHT_GREY": 0.287, "HOVER": 0.359}

# These are filled in by set_theme(), they're listed here so editors know they exist
BACKGROUND = DARK = PANEL = RAISED = PRESSED = GREY = LIGHT_GREY = HOVER = TEXT = WHITE = ""
TEAL = AMBER = PINK = RED = GREEN = ""
WINDOW_STYLE = LINE_EDIT_STYLE = SLIDER_STYLE = ""

_current_name = ""
_current_roles = {}

_COLOUR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}|\bwhite\b", re.IGNORECASE)


def _blend(start, end, amount):
    start_rgb = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    end_rgb = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(a + (b - a) * amount) for a, b in zip(start_rgb, end_rgb)]

    return "#{:02x}{:02x}{:02x}".format(*mixed)


def build_roles(theme):
    roles = {"BACKGROUND": theme["background"], "TEXT": theme["text"],
             "TEAL": theme["teal"], "AMBER": theme["amber"], "PINK": theme["pink"],
             "RED": theme["red"], "GREEN": theme["green"]}

    for role, amount in GREY_STEPS.items():
        roles[role] = _blend(theme["background"], theme["text"], amount)

    roles["DARK"] = _blend(theme["background"], "#000000", 0.2)     # a little darker than the window, used by inactive tabs

    return roles


def current_theme_name():
    return _current_name


def set_theme(name):
    """Makes `name` the current theme and returns {old colour: new colour} for recolouring existing stylesheets."""
    global _current_name, _current_roles

    if name not in THEMES:
        name = DEFAULT_THEME

    old_roles = _current_roles
    roles = build_roles(THEMES[name])
    _current_name, _current_roles = name, roles

    module = globals()
    for role, value in roles.items():
        module[role] = value
    module["WHITE"] = roles["TEXT"]

    module["WINDOW_STYLE"] = (f"QWidget {{background-color:{BACKGROUND}; color:{TEXT};}}"
                              f"QToolTip {{background-color:{RAISED}; color:{TEXT}; border:1px solid {GREY};"
                              "font-family:Arial; font-size:14px; padding:4px;}")

    module["LINE_EDIT_STYLE"] = f"""
        QLineEdit {{
            background-color:{BACKGROUND}; color:{TEXT};
            border-radius:5px; border-width:2px; border-color:{GREY}; border-style:solid;
            font-family:Arial; font-size:20px; font-weight:bold; padding-bottom:2px;
        }}
        QLineEdit:focus {{
            border-color:{HOVER};
        }}
    """

    module["SLIDER_STYLE"] = f"""
        QSlider::groove:horizontal {{
            background-color: {RAISED}; height: 8px; border-radius: 4px; border: 1px solid {GREY};
        }}
        QSlider::handle:horizontal {{
            background-color: {GREY}; border: 2px solid {BACKGROUND};
            width: 20px; height: 20px; margin: -8px 0; border-radius: 10px;
        }}
        QSlider::handle:horizontal:hover {{ background-color: {HOVER}; }}
        QSlider::sub-page:horizontal {{ background-color: {GREY}; border-radius: 4px; }}
    """

    mapping = {value.lower(): roles[role] for role, value in old_roles.items()}
    if old_roles.get("TEXT", "").lower() == "#ffffff":
        mapping["white"] = roles["TEXT"]

    return mapping


def recolour_window(window, mapping):
    for widget in [window] + window.findChildren(QWidget):
        sheet = widget.styleSheet()

        if sheet:
            new_sheet = _COLOUR_PATTERN.sub(lambda match: mapping.get(match.group(0).lower(), match.group(0)), sheet)

            if new_sheet != sheet:
                widget.setStyleSheet(new_sheet)

        widget.update()      # widgets that paint themselves (theme squares, title bar buttons) read the new colours


def switch_theme(name, windows):
    mapping = set_theme(name)

    for window in windows:
        recolour_window(window, mapping)

    Storage.save_theme_name(_current_name)


def menu_style():
    return f"""
        QMenu {{
            background-color:{BACKGROUND}; color:{TEXT}; border:2px solid {GREY}; border-radius:5px;
            font-family:Arial; font-size:16px; font-weight:bold; padding:4px;
        }}
        QMenu::item {{ padding:8px 26px; border-radius:4px; }}
        QMenu::item:selected {{ background-color:{RAISED}; color:{TEAL}; }}
        QMenu::item:disabled {{ color:{PRESSED}; }}
        QMenu::separator {{ height:2px; background:{GREY}; margin:4px 8px; }}
    """


def tab_style():
    return f"""
        QTabWidget::pane {{ border:2px solid {GREY}; border-radius:5px; background-color:{BACKGROUND}; top:-2px; }}
        QTabBar {{ background-color:transparent; }}
        QTabBar::tab {{
            background-color:{DARK}; color:{LIGHT_GREY}; border:2px solid {GREY};
            border-top-left-radius:6px; border-top-right-radius:6px; padding:6px 26px;
            margin-right:6px; margin-top:10px;
            font-family:Arial; font-size:18px; font-weight:bold;
        }}
        QTabBar::tab:hover {{ background-color:{BACKGROUND}; color:{TEXT}; }}
        QTabBar::tab:selected {{
            background-color:{BACKGROUND}; color:{TEXT}; border-bottom-color:{BACKGROUND};
            margin-top:0px; padding-top:10px; padding-bottom:10px;
        }}
    """


def outline_button_style(colour, font_size, radius=7, border=3, padding=0):
    pad = f"padding:{padding}px;" if padding else ""
    return f"""
        QPushButton {{
            background-color:{BACKGROUND}; color:{colour};
            border-radius:{radius}px; border-width:{border}px; border-color:{colour}; border-style:solid;
            font-family:Arial; font-size:{font_size}px; font-weight:bold; {pad}
        }}
        QPushButton:hover {{
            background-color:{RAISED}; color:{colour};
        }}
        QPushButton:pressed {{
            background-color:{PRESSED}; color:{colour};
        }}
        QPushButton:disabled {{
            background-color:{BACKGROUND}; color:{PRESSED}; border-color:{PRESSED};
        }}
    """


def text_style(colour, font_size, background=False, padding=False):
    bg = f"background-color:{BACKGROUND};" if background else ""
    pad = "padding-top:6px; padding-bottom:8px; padding-left:6px; padding-right:6px;" if padding else ""
    return f"{bg} color:{colour}; font-family:Arial; font-size:{font_size}px; font-weight:bold; {pad}"


def result_style(font_size=20):
    return (f"background-color:{RAISED}; color:{TEXT}; border-radius:3px;"
            f"font-family:Arial; font-size:{font_size}px; font-weight:bold;"
            "padding-top:6px; padding-bottom:8px; padding-left:6px; padding-right:6px;"
            f"border-width:2px; border-color:{RAISED}; border-style:solid;")


set_theme(DEFAULT_THEME)