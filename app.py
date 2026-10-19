from pathlib import Path
import shutil

import gradio as gr

from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import UnidentifiedImageError
from pydantic import BaseModel

from web_ui import create_ui
from services.yolo_service import detect_objects
from services.qwen_service import (
    MODEL_NAME,
    QwenAPIError,
    QwenConfigurationError,
    QwenTimeoutError,
    analyze_image,
)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{number}"
    for prefix in ("COM", "LPT")
    for number in "123456789¹²³"
}


def _validate_filename(filename: str) -> None:
    if (
        not filename
        or filename in {".", ".."}
        or filename.endswith((" ", "."))
        or any(char in '<>:"/\\|?*' or ord(char) < 32 for char in filename)
        or filename.split(".", 1)[0].rstrip(" ").upper() in RESERVED_NAMES
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")


def _get_uploaded_image(filename: str) -> Path:
    _validate_filename(filename)
    image_path = (UPLOAD_DIR / filename).resolve()
    if image_path.parent != UPLOAD_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Uploaded image not found")
    return image_path


def _run_qwen(image_path: Path) -> str:
    try:
        return analyze_image(image_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded image not found") from None
    except QwenConfigurationError:
        raise HTTPException(status_code=503, detail="DASHSCOPE_API_KEY is not configured") from None
    except QwenTimeoutError:
        raise HTTPException(status_code=504, detail="Qwen request timed out") from None
    except QwenAPIError:
        raise HTTPException(status_code=502, detail="Qwen request failed; check the API key, quota, and network") from None


@app.get("/")
def root():
    return {
        "message": "Lingjing Stage3 API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/upload")
def upload(file: UploadFile = File(...)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    filename = Path((file.filename or "").replace("\\", "/")).name
    _validate_filename(filename)

    saved_path = (UPLOAD_DIR / filename).resolve()
    if saved_path.parent != UPLOAD_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid file path")

    try:
        with saved_path.open("xb") as destination:
            shutil.copyfileobj(file.file, destination)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="A file with this name already exists")
    finally:
        file.file.close()

    return {
        "filename": filename,
        "content_type": file.content_type,
        "saved_path": (Path("uploads") / filename).as_posix()
    }

class YoloPredictRequest(BaseModel):
    filename: str


@app.post("/predict/yolo")
def predict_yolo(request: YoloPredictRequest):
    filename = request.filename
    image_path = _get_uploaded_image(filename)

    try:
        detections = detect_objects(image_path)
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image")

    return {
        "filename": filename,
        "detections": detections
    }

class QwenPredictRequest(BaseModel):
    filename: str


@app.post("/predict/qwen")
def predict_qwen(request: QwenPredictRequest):
    filename = request.filename
    image_path = _get_uploaded_image(filename)

    answer = _run_qwen(image_path)

    return {
        "filename": filename,
        "model": MODEL_NAME,
        "answer": answer,
    }


class AnalyzeRequest(BaseModel):
    filename: str


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    filename = request.filename
    image_path = _get_uploaded_image(filename)

    try:
        detections = detect_objects(image_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded image not found") from None
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image") from None

    answer = _run_qwen(image_path)
    return {
        "filename": filename,
        "yolo": {"detections": detections},
        "qwen": {"model": MODEL_NAME, "answer": answer},
    }

app = gr.mount_gradio_app(
    app,
    create_ui(),
    path="/ui",
    root_path="/ui",
    allowed_paths=[],
    blocked_paths=[
        str(BASE_DIR / name)
        for name in (
            ".env", ".git", ".venv", "weights", "services", "uploads",
            "app.py", "web_ui.py", "requirements.txt",
        )
    ] + [str(BASE_DIR.parent / "lingjing-stage2"), str(BASE_DIR.parent / "lingjing")],
    show_error=False,
    max_file_size="10mb",
    ssr_mode=False,
    footer_links=[],
    run_history=False,
    enable_monitoring=False,
    mcp_server=False,
)
