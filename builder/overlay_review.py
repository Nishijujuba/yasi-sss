from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from builder.config import OVERLAY_CONFIDENCE_GATE, PAGE_ASSET_ROOT, PACK_ROOT, REVIEW_ROOT, SOURCE_DATA_ROOT
from builder.detect_overlays import DetectionError, OVERLAY_PROPOSALS
from builder.models import Overlay


VISION_VALIDATION = SOURCE_DATA_ROOT / "vision-validation.json"
OVERLAY_REVIEW_ROOT = REVIEW_ROOT / "overlays"
PUBLIC_OVERLAYS = PACK_ROOT / "overlays.json"


def _load_json(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _overlay_key(item: dict) -> tuple[str, str | None]:
    return (str(item["questionId"]), item.get("optionId"))


def merge_vision_evidence(
    proposals: Iterable[dict],
    vision_entries: Iterable[dict],
) -> list[Overlay]:
    vision_by_key = {_overlay_key(entry): entry for entry in vision_entries}
    overlays: list[Overlay] = []

    for proposal in proposals:
        key = _overlay_key(proposal)
        vision = vision_by_key.get(key)
        if vision is None:
            raise DetectionError(f"missing vision evidence for {key[0]} {key[1] or ''}".strip())
        if vision.get("status") != "approved":
            raise DetectionError(f"vision evidence rejected {key[0]} {key[1] or ''}".strip())
        vision_confidence = float(vision.get("confidence", 0))
        if vision_confidence < OVERLAY_CONFIDENCE_GATE:
            raise DetectionError(
                f"vision confidence below {OVERLAY_CONFIDENCE_GATE}: "
                f"{key[0]} {key[1] or ''}".strip()
            )

        deterministic = float(proposal["deterministicConfidence"])
        confidence = min(deterministic, vision_confidence)
        evidence = list(proposal["validationEvidence"])
        evidence.append(str(vision["evidence"]))
        overlays.append(
            Overlay.model_validate(
                {
                    **proposal,
                    "visionConfidence": vision_confidence,
                    "confidence": round(confidence, 4),
                    "validationEvidence": evidence,
                }
            )
        )

    return overlays


def draw_review_images(
    proposals_path: Path = OVERLAY_PROPOSALS,
    page_dir: Path = PAGE_ASSET_ROOT,
    output_dir: Path = OVERLAY_REVIEW_ROOT,
) -> list[Path]:
    proposals = _load_json(proposals_path)
    by_page: dict[str, list[dict]] = defaultdict(list)
    for proposal in proposals:
        by_page[str(proposal["page"])].append(proposal)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for page_name, page_proposals in sorted(by_page.items()):
        with Image.open(Path(page_dir) / page_name) as base:
            image = base.convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for proposal in page_proposals:
            pixel = proposal["pixel"]
            x1 = pixel["x"]
            y1 = pixel["y"]
            x2 = x1 + pixel["w"]
            y2 = y1 + pixel["h"]
            is_choice = proposal["interactionType"] == "choice-option"
            fill = (122, 92, 255, 54) if is_choice else (35, 160, 90, 54)
            outline = (122, 92, 255, 230) if is_choice else (35, 160, 90, 230)
            label = proposal["questionId"]
            if proposal.get("optionId"):
                label += f":{proposal['optionId']}"
            label += f" {proposal['deterministicConfidence']:.2f}"
            draw.rectangle((x1, y1, x2, y2), fill=fill, outline=outline, width=3)
            draw.text((x1, max(0, y1 - 16)), label, fill=outline)
        reviewed = Image.alpha_composite(image, overlay).convert("RGB")
        output = output_dir / page_name.replace(".png", "-review.png")
        reviewed.save(output)
        outputs.append(output)
    return outputs


def finalize_overlays(
    proposals_path: Path = OVERLAY_PROPOSALS,
    vision_path: Path = VISION_VALIDATION,
    output_path: Path = PUBLIC_OVERLAYS,
) -> list[Overlay]:
    overlays = merge_vision_evidence(
        _load_json(proposals_path),
        _load_json(vision_path),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([overlay.model_dump() for overlay in overlays], indent=2) + "\n",
        encoding="utf-8",
    )
    return overlays


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()

    if args.finalize:
        overlays = finalize_overlays()
        print(f"wrote {len(overlays)} finalized overlays to {PUBLIC_OVERLAYS}")
        return

    outputs = draw_review_images()
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
