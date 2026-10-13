"""Generate normalized geometry expectations from the adopted wireframes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WIREFRAMES = ROOT / "contracts" / "wireframes"

AREA_SELECTORS = {
    "header": ".bar",
    "menu": ".menu",
    "step": ".step",
    "step_body": ".body",
    "map": '[aria-label="地図"]',
    "pane": ".pane",
    "bottom_nav": ".nav",
    "card": ".stepc",
    "primary_button": ".btn.pri",
}

SCREENS = {
    "HC-PcList": (1280, 920),
    "HC-SpList": (390, 844),
    "GC-PcSelecting": (1280, 920),
    "GC-PcScheduling": (1280, 920),
    "S3-PcScheduling": (1280, 920),
    "S3-SpScheduling": (390, 844),
    "GC-PcFinal": (1280, 920),
    "GC-SpFinal": (390, 844),
    "Nav-PcPane": (1280, 800),
    "Nav-SpN1": (390, 844),
}

COMPARE = {
    "HC-PcList": "home__multiple__1440x900.png",
    "HC-SpList": "home__multiple__390x844.png",
    "Dense-C": "home__one__1440x900.png",
    "Empty-Pc": "home__empty__1440x900.png",
    "Empty-Sp": "home__empty__390x844.png",
    "GC-PcSelecting": "dashboard_selecting__shops_5__1440x900.png",
    "GC-SpSelecting": "dashboard_selecting__shops_5__390x844.png",
    "GC-PcScheduling": "dashboard_scheduling__candidate_dates_14_with_answers__1440x900.png",
    "GC-SpScheduling": "dashboard_scheduling__candidate_dates_14_with_answers__390x844.png",
    "S3-PcScheduling": "dashboard_scheduling__candidate_dates_3_no_answers__1440x900.png",
    "S3-SpScheduling": "dashboard_scheduling__candidate_dates_3_no_answers__390x844.png",
    "GC-PcFinal": "dashboard_finalized__initial__1440x900.png",
    "GC-SpFinal": "dashboard_finalized__initial__390x844.png",
    "Nav-PcPane": "candidates__menu_open__1440x900.png",
    "Nav-SpN1": "home__multiple__390x844.png",
    "Cand-PcGathering": "candidates__gathering_mode__1440x900.png",
    "Cand-SpFree": "candidates__normal__390x844.png",
}


def rects(page, width: int, height: int) -> dict[str, list[dict[str, float]]]:
    result = {}
    for name, selector in AREA_SELECTORS.items():
        result[name] = page.locator(selector).evaluate_all(
            "(nodes) => nodes.map((node) => {"
            " const r = node.getBoundingClientRect();"
            " return {x:r.x, y:r.y, w:r.width, h:r.height}; })"
        )
        result[name] = [
            {
                key: round(value / (width if key in ("x", "w") else height), 6)
                for key, value in box.items()
            }
            for box in result[name]
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=WIREFRAMES / "geometry.json")
    parser.add_argument("--compare-dir", type=Path)
    args = parser.parse_args()
    generated = {"source": "canvas-ken58", "tolerance": 0.08, "screens": {}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for screen, (width, height) in SCREENS.items():
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto((WIREFRAMES / "project" / f"{screen}.dc.html").as_uri())
            page.wait_for_timeout(50)
            generated["screens"][screen] = {
                "viewport": {"width": width, "height": height},
                "areas": rects(page, width, height),
                "notes": "Board geometry generated from the adopted static HTML.",
            }
            page.close()
        browser.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(generated, ensure_ascii=False, indent=2) + "\n")
    if args.compare_dir:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise SystemExit("compare generation requires Pillow: pip install Pillow") from exc
        compare_dir = args.compare_dir / "compare"
        compare_dir.mkdir(parents=True, exist_ok=True)
        for screen, capture_name in COMPARE.items():
            board = Image.open(WIREFRAMES / "png" / f"{screen}.png").convert("RGB")
            capture = Image.open(args.compare_dir / capture_name).convert("RGB")
            capture = capture.resize(board.size)
            combined = Image.new("RGB", (board.width * 2, board.height), "white")
            combined.paste(board, (0, 0))
            combined.paste(capture, (board.width, 0))
            draw = ImageDraw.Draw(combined)
            draw.text((8, 6), "BOARD", fill="black")
            draw.text((board.width + 8, 6), "IMPLEMENTATION", fill="black")
            combined.save(compare_dir / f"{screen}.png")


if __name__ == "__main__":
    main()
