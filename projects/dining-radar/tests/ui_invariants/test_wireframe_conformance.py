"""Contract checks for the generated KEN-68 wireframe geometry."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "contracts" / "wireframes" / "geometry.json"


def test_wireframe_geometry_has_all_adopted_board_screens() -> None:
    spec = json.loads(SPEC.read_text())
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
