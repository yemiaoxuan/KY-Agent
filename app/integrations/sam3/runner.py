from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SAM3 single-image segmentation.")
    parser.add_argument("--sam-project-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--bpe-path")
    return parser


def _render_outputs(
    image_path: Path,
    masks,
    boxes,
    scores,
    output_dir: Path,
    prompt: str,
    device: str,
    confidence_threshold: float,
    top_k: int,
) -> dict:
    import numpy as np
    from PIL import Image, ImageDraw

    output_dir.mkdir(parents=True, exist_ok=True)

    image = Image.open(image_path).convert("RGB")
    image_np = np.array(image)
    mask_path = output_dir / "mask.png"
    overlay_path = output_dir / "overlay.png"

    detections: list[dict] = []
    if scores.numel() == 0:
        image.save(overlay_path)
        empty_mask = Image.new("L", image.size, 0)
        empty_mask.save(mask_path)
        return {
            "ok": True,
            "message": "未检测到满足条件的分割结果。",
            "prompt": prompt,
            "image_path": str(image_path.resolve()),
            "mask_path": str(mask_path.resolve()),
            "overlay_path": str(overlay_path.resolve()),
            "output_dir": str(output_dir.resolve()),
            "device": device,
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "detection_count": 0,
            "detections": detections,
        }

    import torch

    scores = scores.detach().cpu()
    boxes = boxes.detach().cpu()
    masks = masks.detach().cpu()
    order = torch.argsort(scores, descending=True)[:top_k]
    masks = masks[order]
    boxes = boxes[order]
    scores = scores[order]

    union_mask = np.zeros((image_np.shape[0], image_np.shape[1]), dtype=np.uint8)
    overlay_np = image_np.copy()

    for index, (mask_tensor, box_tensor, score_tensor) in enumerate(
        zip(masks, boxes, scores, strict=False),
        start=1,
    ):
        mask_np = mask_tensor.numpy()
        while mask_np.ndim > 2:
            mask_np = mask_np[0]
        mask_np = mask_np.astype(bool)
        area_pixels = int(mask_np.sum())
        union_mask[mask_np] = 255
        overlay_np[mask_np] = (
            overlay_np[mask_np] * 0.45 + np.array([220, 48, 66], dtype=np.float32) * 0.55
        ).astype(np.uint8)

        box = [float(round(value, 2)) for value in box_tensor.tolist()]
        detections.append(
            {
                "index": index,
                "score": float(round(float(score_tensor.item()), 4)),
                "box": box,
                "area_pixels": area_pixels,
            }
        )

    overlay_image = Image.fromarray(overlay_np)
    drawer = ImageDraw.Draw(overlay_image)
    for detection in detections:
        if len(detection["box"]) == 4:
            x0, y0, x1, y1 = detection["box"]
            drawer.rectangle((x0, y0, x1, y1), outline=(255, 214, 10), width=3)
            drawer.text(
                (x0 + 4, y0 + 4),
                f"#{detection['index']} {detection['score']:.2f}",
                fill=(255, 214, 10),
            )

    Image.fromarray(union_mask, mode="L").save(mask_path)
    overlay_image.save(overlay_path)

    return {
        "ok": True,
        "message": "ok",
        "prompt": prompt,
        "image_path": str(image_path.resolve()),
        "mask_path": str(mask_path.resolve()),
        "overlay_path": str(overlay_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "device": device,
        "confidence_threshold": confidence_threshold,
        "top_k": top_k,
        "detection_count": len(detections),
        "detections": detections,
    }


def _main() -> dict:
    parser = _build_parser()
    args = parser.parse_args()

    sam_project_root = Path(args.sam_project_root).expanduser().resolve()
    sys.path.insert(0, str(sam_project_root))

    import torch
    from PIL import Image

    from sam3.model.sam3_image_processor import Sam3Processor
    from sam3.model_builder import build_sam3_image_model

    requested_device = args.device
    if requested_device == "cuda" and not torch.cuda.is_available():
        requested_device = "cpu"

    model = build_sam3_image_model(
        bpe_path=args.bpe_path,
        device=requested_device,
        checkpoint_path=str(Path(args.checkpoint).expanduser().resolve()),
        load_from_HF=False,
        enable_segmentation=True,
        enable_inst_interactivity=False,
    )
    processor = Sam3Processor(
        model,
        device=requested_device,
        confidence_threshold=args.confidence_threshold,
    )
    image_path = Path(args.image).expanduser().resolve()
    image = Image.open(image_path).convert("RGB")
    state = processor.set_image(image)
    output = processor.set_text_prompt(prompt=args.prompt, state=state)

    return _render_outputs(
        image_path=image_path,
        masks=output["masks"],
        boxes=output["boxes"],
        scores=output["scores"],
        output_dir=Path(args.output_dir).expanduser().resolve(),
        prompt=args.prompt,
        device=requested_device,
        confidence_threshold=args.confidence_threshold,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    try:
        result = _main()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": repr(exc)}, ensure_ascii=False))
        raise
