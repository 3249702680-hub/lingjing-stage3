# 灵境 AI 第三阶段：垃圾视觉识别对比 Web 系统

## 当前实现

- FastAPI Web 后端
- 图片上传
- YOLO 垃圾目标检测：返回类别、置信度和边界框
- Qwen3-VL 多模态垃圾理解：识别物体、垃圾类别、是否可回收及判断理由
- YOLO + Qwen 统一分析接口
- Gradio Web UI：一次上传，展示原图、YOLO 带框图、检测信息和 Qwen 完整文本
- 同一图片展示传统视觉模型和多模态模型结果

## 主要接口

- `GET /`
- `GET /health`
- `POST /upload`
- `POST /predict/yolo`
- `POST /predict/qwen`
- `POST /analyze`

## 运行方式

```powershell
uvicorn app:app --reload
```

Web UI：http://127.0.0.1:8000/ui

API 文档：http://127.0.0.1:8000/docs

## Qwen 环境变量

Qwen3-VL 使用环境变量 `DASHSCOPE_API_KEY`。启动服务前，在本机环境中设置该变量。
