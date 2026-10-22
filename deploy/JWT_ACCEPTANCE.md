# JWT 实际验收

- 实测提交 `f2adee046a24c4cb7d5f7d63da0bd7f178f60497`。
- [GitHub Actions 39798441954](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39798441954)。最终已核实 completed/success。平台曾延迟显示运行状态；已下载原始 artifact，并验证摘要 `ab182bf5952d479905f4d9cde8b4e39f3398290f6474c8f480102d896e2056a5`。
- [永久原始 JSON](evidence/jwt-acceptance-39798441954.json)：28 项容器检查通过，镜像内 24 项 unittest 全部 OK。
- 正确登录和身份查询 200；缺 Token、错误密码、篡改签名、过期 Token 均 401。
- 登录后 Nginx /health、/docs、/ui/、上传、YOLO、Gradio SSE/原图/标注图、app 重建持久化均通过；paper 0.9664。
- 本机另运行真实挂载 app 的 TestClient：匿名拒绝、登录 UI 200、已登录的不存在图片在原三个推理接口仍返回 404。没有调用外部模型/数据库。
- CI 账户与签名密钥仅在内存中随机生成，未写入证据或 Git。真实 Qwen、SQL Server、云主机仍未由本轮 CI 验证。
