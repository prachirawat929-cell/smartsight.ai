"""Object detection with a pretrained YOLO model (no training required)."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps

MODEL_NAME = "yolov8n.pt"  # small COCO model; downloaded automatically on first use
MAX_SIDE = 1280  # downscale very large photos for speed


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels


def load_model(name: str = MODEL_NAME):
    from ultralytics import YOLO

    return YOLO(name)


def prepare_image(img: Image.Image) -> Image.Image:
    """Fix phone-camera rotation, force RGB, and cap the size."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def detect(model, img: Image.Image, conf: float = 0.35) -> tuple[Image.Image, list[Detection]]:
    """Run detection. Returns (annotated RGB image, detections sorted by confidence)."""
    img = prepare_image(img)
    arr = np.array(img)
    result = model.predict(arr, conf=conf, verbose=False)[0]

    detections: list[Detection] = []
    names = result.names
    for box in result.boxes:
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        detections.append(
            Detection(label=names[int(box.cls[0])], confidence=float(box.conf[0]),
                      box=(x1, y1, x2, y2))
        )
    detections.sort(key=lambda d: d.confidence, reverse=True)

    annotated_bgr = result.plot()  # draws boxes + "label conf" text (BGR)
    annotated = Image.fromarray(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB))
    return annotated, detections
