"""User-facing shelf controls, bounded to the existing dock/creation contract."""
import math
from pathlib import Path
from .contracts import load, require

CONTROLS = [
    dict(key="object_height_m", group="shelf", label="Creation size", description="Height of creations while docked.", min=.12, max=.20, step=.01, unit="cm"),
    dict(key="slot_spacing_m", group="shelf", label="Spacing", description="Space between dock slots.", min=.12, max=.30, step=.01, unit="cm"),
    dict(key="opacity", group="shelf", label="Shelf opacity", description="Transparency of the shelf surface.", min=.20, max=1., step=.10, unit="%"),
    dict(key="launcher_only", group="shelf", label="Show shelf", description="Where the shelf appears in SteamVR.", choices=[dict(label="Steam home", value=True), dict(label="Every page", value=False)]),
    dict(key="right_edge_m", group="placement", label="Horizontal position", description="Move left or right relative to the Steam dashboard.", min=-2., max=2., step=.05, unit="cm"),
    dict(key="center_y_m", group="placement", label="Height", description="Move the shelf down or up.", min=-1., max=1., step=.05, unit="cm"),
    dict(key="depth_m", group="placement", label="Depth", description="Move back or forward from the dashboard.", min=-2., max=2., step=.05, unit="cm"),
    dict(key="join_yaw_degrees", group="placement", label="Angle", description="Turn the shelf around its right edge.", min=-90., max=90., step=5., unit="degrees"),
    dict(key="lean_degrees", group="placement", label="Creation lean", description="Tilt creations back or forward while docked.", min=-25., max=25., step=1., unit="degrees"),
    dict(key="dashboard_width_m", group="app", label="Window size", description="Width of the MagicShelf app in VR.", min=1.2, max=2.4, step=.1, unit="m"),
    dict(key="start_view", group="app", label="Starting view", description="The page shown when MagicShelf starts.", choices=[dict(label="Discover", value="discover"), dict(label="My Shelf", value="library")]),
]
BY_KEY = {control["key"]: control for control in CONTROLS}
APP_KEYS = {c["key"] for c in CONTROLS if c["group"] == "app"}
PLACEMENT_KEYS = set(BY_KEY) - APP_KEYS - {"opacity", "launcher_only"}
CREDITS = [
    dict(name="josethevrtech", role="MagicShelf creator and developer", url="https://github.com/josethevrtech"),
    dict(name="MagicShelf", role="Source code, releases and issue tracker · MIT", url="https://github.com/josethevrtech/magicshelf"),
    dict(name="Valve OpenVR", role="SteamVR integration · BSD 3-Clause", url="https://github.com/ValveSoftware/openvr"),
]

def defaults():
    shelf = load(Path(__file__).resolve().parent.parent / "shelf.json")
    return {**{key: shelf[key] for key in BY_KEY if key not in APP_KEYS}, "dashboard_width_m": 1.8, "start_view": "discover"}

def validate(changes):
    require(isinstance(changes, dict) and changes, "Choose a setting to change")
    require(all(key in BY_KEY for key in changes), "Unknown app setting")
    for key, value in changes.items():
        control = BY_KEY[key]
        if "choices" in control:
            require(any(type(value) is type(c["value"]) and value == c["value"] for c in control["choices"]), "Invalid choice for " + control["label"])
        else:
            require(type(value) in (int, float) and math.isfinite(value) and control["min"] <= value <= control["max"], "Invalid value for " + control["label"])
    return changes

def snapshot(layout):
    values = defaults()
    for key in values:
        if key in layout:
            try:
                validate({key: layout[key]})
                values[key] = layout[key]
            except ValueError:
                pass
    return dict(values=values, controls=CONTROLS, credits=CREDITS)
