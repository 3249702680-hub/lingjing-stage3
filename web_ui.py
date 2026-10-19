"""Gradio page for comparing local YOLO detection and Qwen3-VL analysis."""

from pathlib import Path
from uuid import uuid4

import gradio as gr
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from services.yolo_service import detect_objects
from services.qwen_service import (
    QwenAPIError,
    QwenConfigurationError,
    QwenTimeoutError,
    analyze_image,
)


TITLE = "灵境 AI 第三阶段：垃圾视觉识别对比系统"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


def _draw_detections(image: Image.Image, detections: list[dict]) -> Image.Image:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    font = ImageFont.load_default(size=14)
    width, height = annotated.size
    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]
        box = (
            max(0, min(width - 1, x1)),
            max(0, min(height - 1, y1)),
            max(0, min(width - 1, x2)),
            max(0, min(height - 1, y2)),
        )
        draw.rectangle(box, outline="#16a34a", width=2)
        label = f'{detection["class_name"]} {detection["confidence"]:.4f}'
        label_box = draw.textbbox((0, 0), label, font=font)
        text_width = label_box[2] - label_box[0] + 8
        text_height = label_box[3] - label_box[1] + 8
        left = max(0, min(box[0], width - text_width))
        top = max(0, box[1] - text_height)
        draw.rectangle(
            (left, top, left + text_width, top + text_height),
            fill="#16a34a",
        )
        draw.text((left + 4, top + 2), label, font=font, fill="white")
    return annotated


def _reset_results(image):
    original = image.copy() if isinstance(image, Image.Image) else None
    status = "图片已上传，点击“开始分析”。" if original is not None else "请上传一张 PNG、JPEG 等格式的图片。"
    return original, None, {"detections": []}, "", status


def analyze_upload(image):
    if not isinstance(image, Image.Image):
        raise gr.Error("请先上传一张 PNG、JPEG 等格式的图片。", print_exception=False)

    original = ImageOps.exif_transpose(image).convert("RGB")
    image_path = UPLOAD_DIR / f"ui_{uuid4().hex}.png"
    try:
        UPLOAD_DIR.mkdir(exist_ok=True)
        with image_path.open("xb") as destination:
            original.save(destination, format="PNG")
    except OSError:
        raise gr.Error("图片保存失败，请检查上传目录权限后重试。", print_exception=False) from None

    try:
        detections = detect_objects(image_path)
        annotated = _draw_detections(original, detections)
    except (UnidentifiedImageError, OSError):
        return original, None, {"error": "YOLO 无法读取图片。"}, "", "分析失败：请更换图片后重试。"
    except Exception:
        return original, None, {"error": "YOLO 推理失败，请检查本地权重和依赖。"}, "", "分析失败：YOLO 服务暂不可用。"

    try:
        answer = analyze_image(image_path)
    except QwenConfigurationError:
        answer = "Qwen 服务未配置 API Key，请先配置环境变量后重启服务。"
    except QwenTimeoutError:
        answer = "Qwen 分析超时，请稍后重试。"
    except QwenAPIError:
        answer = "Qwen 调用失败，请检查 API Key、额度和网络后重试。"
    except Exception:
        answer = "Qwen 分析暂不可用，请稍后重试。"
    else:
        status = f"分析完成：YOLO 检测到 {len(detections)} 个目标，Qwen3-VL 分析完成。"
        return original, annotated, {"detections": detections}, answer, status

    return original, annotated, {"detections": detections}, answer, "YOLO 检测完成；Qwen 分析未完成，详见右侧提示。"


def create_ui() -> gr.Blocks:
    with gr.Blocks(title=TITLE, analytics_enabled=False) as demo:
        gr.Markdown(f"# {TITLE}\n上传一张垃圾图片，点击“开始分析”，对比目标检测与多模态语义分析结果。")
        with gr.Row():
            image_input = gr.Image(
                label="上传垃圾图片",
                type="pil",
                sources=["upload"],
                image_mode="RGB",
                format="png",
                height=240,
                min_width=220,
                elem_id="garbage-upload",
            )
            original_output = gr.Image(
                label="原始图片",
                type="pil",
                format="png",
                interactive=False,
                height=240,
                min_width=220,
                buttons=["download"],
                elem_id="original-image",
            )
            annotated_output = gr.Image(
                label="YOLO 检测结果（带框）",
                type="pil",
                format="png",
                interactive=False,
                height=240,
                min_width=220,
                buttons=["download"],
                elem_id="yolo-image",
            )
        analyze_button = gr.Button("开始分析", variant="primary")
        status_output = gr.Markdown("请上传一张图片后开始分析。", elem_id="analysis-status")
        with gr.Row():
            detections_output = gr.JSON(
                value={"detections": []},
                label="YOLO 检测信息",
                open=True,
                scale=1,
                min_width=260,
                elem_id="yolo-detections",
            )
            answer_output = gr.Textbox(
                label="Qwen3-VL 分析结果",
                lines=14,
                max_lines=30,
                interactive=False,
                buttons=["copy"],
                scale=2,
                min_width=350,
                elem_id="qwen-answer",
            )
        outputs = [
            original_output,
            annotated_output,
            detections_output,
            answer_output,
            status_output,
        ]
        image_input.change(
            _reset_results,
            inputs=image_input,
            outputs=outputs,
            queue=False,
            api_name=False,
        )
        analyze_button.click(
            analyze_upload,
            inputs=image_input,
            outputs=outputs,
            concurrency_limit=1,
            api_name="analyze_upload",
        )
    return demo
