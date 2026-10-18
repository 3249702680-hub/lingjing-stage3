"""Run local garbage detection with the copied stage-two YOLO weights."""

from functools import lru_cache
from pathlib import Path
from threading import Lock

from PIL import Image


MODEL_PATH = Path(__file__).resolve().parents[1] / "weights" / "garbage_detect.pt"
MODEL_LOCK = Lock()


@lru_cache(maxsize=1)
def _get_model():
    if not MODEL_PATH.is_file():
        raise RuntimeError(f"YOLO weights file is missing: {MODEL_PATH}")

    from ultralytics import YOLO

    model = YOLO(str(MODEL_PATH))
    if model.task != "detect":
        raise RuntimeError("The YOLO weights must be for the detect task")
    return model


def detect_objects(image_path: Path) -> list[dict]:
    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")

    try:
        with MODEL_LOCK:
            model = _get_model()
            result = model.predict(
                source=image,
                conf=0.25,
                device="cpu",
                save=False,
                verbose=False,
            )[0]

            detections = []
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0].item())
                    detections.append({
                        "class_name": result.names[class_id],
                        "confidence": round(float(box.conf[0].item()), 4),
                        "bbox": [round(float(value), 2) for value in box.xyxy[0].tolist()],
                    })
            return detections
    finally:
        image.close()
