from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import UnidentifiedImageError
from pydantic import BaseModel

from services.yolo_service import detect_objects

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{number}"
    for prefix in ("COM", "LPT")
    for number in "123456789¹²³"
}


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
    if (
        not filename
        or filename in {".", ".."}
        or filename.endswith((" ", "."))
        or any(char in '<>:"/\\|?*' or ord(char) < 32 for char in filename)
        or filename.split(".", 1)[0].rstrip(" ").upper() in RESERVED_NAMES
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

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
    if (
        not filename
        or filename in {".", ".."}
        or filename.endswith((" ", "."))
        or any(char in '<>:"/\\|?*' or ord(char) < 32 for char in filename)
        or filename.split(".", 1)[0].rstrip(" ").upper() in RESERVED_NAMES
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    image_path = (UPLOAD_DIR / filename).resolve()
    if image_path.parent != UPLOAD_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Uploaded image not found")

    try:
        detections = detect_objects(image_path)
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image")

    return {
        "filename": filename,
        "detections": detections
    }
