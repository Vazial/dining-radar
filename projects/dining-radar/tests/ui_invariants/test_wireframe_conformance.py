"""Contract checks for the generated KEN-68 wireframe geometry."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "contracts" / "wireframes" / "geometry.json"
IMPLEMENTATION_STYLES = (
    ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "organizer.css",
    ROOT / "src" / "dining_radar" / "web" / "templates" / "web" / "home.html",
)
PROPOSAL_DIR = ROOT / "contracts" / "wireframes" / "proposed"

DESIGN_TOKEN_LITERALS = {
    "face": "#F2F4F0",
    "card": "#FFF",  # accepts the equivalent six-digit #FFFFFF spelling
    "border": "#DFE4DE",
    "border-strong": "#C6CFC6",
    "ink": "#17201B",
    "green": "#14614A",
    "tap-target": "44px",
    "small-radius": "10px",
    "panel-radius": "12px",
}

BOARD_SCREENS = (
    "HC-PcList",
    "HC-SpList",
    "GC-PcSelecting",
    "GC-PcScheduling",
    "S3-PcScheduling",
    "S3-SpScheduling",
    "GC-PcFinal",
    "GC-SpFinal",
    "Empty-Pc",
    "Empty-Sp",
    "Nav-PcPane",
    "Nav-SpN1",
    "Cand-PcGathering",
    "Cand-SpFree",
    "GC-SpSelecting",
    "GC-SpScheduling",
    "TabA-Sp",
    "Dense-C",
    "S3-PcEditing",
    "SelA",
    "SumA",
    "ColorFinal",
    "ZeroState-A-Pc",
    "ZeroState-A-Sp",
)


def _geometry() -> dict:
    return json.loads(SPEC.read_text())


def test_wireframe_geometry_includes_every_board_screen_in_the_ledger() -> None:
    screens = _geometry()["screens"]
    missing = [name for name in BOARD_SCREENS if name not in screens]
    assert not missing, f"board screens missing from geometry.json: {missing}"
    for name in BOARD_SCREENS:
        screen = screens[name]
        assert screen["viewport"]["width"] > 0
        assert screen["viewport"]["height"] > 0
        assert screen["notes"].startswith("Board geometry generated")


def test_wireframe_design_tokens_report_drift_against_implementation() -> None:
    """Keep the first token audit cheap until the CSS migration is agreed.

    This intentionally reports literal drift rather than silently normalizing
    the boards.  The proposed boards already use the same token names, while
    the shipped CSS still uses literals; moving to custom properties is a
    separate human-approved change recorded in LEDGER.md.
    """
    implementation = "\n".join(path.read_text() for path in IMPLEMENTATION_STYLES).upper()
    proposal = (PROPOSAL_DIR / "ZeroState-A-Pc.html").read_text().upper()
    missing = [
        name
        for name, literal in DESIGN_TOKEN_LITERALS.items()
        if literal.upper() not in implementation or literal.upper() not in proposal
    ]
    assert not missing, f"wireframe/implementation token drift: {missing}"


def test_wireframe_geometry_has_all_adopted_board_screens() -> None:
    spec = _geometry()
    screens = spec["screens"]
    for name in (
        "HC-PcList",
        "HC-SpList",
        "GC-PcSelecting",
        "S3-PcScheduling",
        "GC-PcFinal",
        "Nav-PcPane",
    ):
        assert name in screens
        assert screens[name]["viewport"]["width"] > 0
        assert screens[name]["viewport"]["height"] > 0
        assert "header" in screens[name]["areas"]


def test_wireframe_geometry_records_right_pane_and_steps() -> None:
    spec = json.loads(SPEC.read_text())["screens"]
    selecting = spec["GC-PcSelecting"]["areas"]
    scheduling = spec["S3-PcScheduling"]["areas"]
    scheduling_map = spec["GC-PcScheduling"]["areas"]
    assert selecting["step"] and selecting["map"]
    assert scheduling["card"] and scheduling_map["map"]
    assert selecting["map"][0]["x"] > selecting["step"][0]["x"]
    assert scheduling_map["map"][0]["x"] > scheduling["card"][0]["x"]
