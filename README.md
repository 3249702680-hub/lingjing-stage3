# 灵境 AI 第三阶段

## 项目目标

将第二阶段 YOLO + 多模态视觉项目包装成 Web 应用。

## Day1 当前功能

- `GET /`：服务首页
- `GET /health`：健康检查
- `POST /upload`：上传并保存图片
- `POST /predict/yolo`：对已上传图片进行 YOLO 垃圾检测
- FastAPI Swagger 文档：`/docs`
- YOLO 垃圾检测：返回类别、置信度和边界框

## 运行方式

```powershell
uvicorn app:app --reload
```

访问：http://127.0.0.1:8000/docs
