# Day5 JWT 与消息队列：真实验收通过

日期：2026-10-22（北京时间）。对照原始《三阶段思维导图.pdf》的登录校验/JWT 身份识别、任务生产消费/异步处理/结果返回实现并验收。

| 阶段 | 实测代码 | GitHub Actions |
| --- | --- | --- |
| Nginx | f1bc5e67c22aad3ae0ef02287545e1bb838fab04 | [39795471809：success](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39795471809) |
| JWT | f2adee046a24c4cb7d5f7d63da0bd7f178f60497 | [39798441954：success](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39798441954) |
| Redis / RQ | 48a073a16a1d37b661392bdc6b288031c95887e3 | [39800419193：success](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39800419193) |

最新实际构建、运行和回归全部成功：[永久原始 JSON](evidence/queue-acceptance-39800419193.json)，39 项容器检查全通过；镜像内 35 项 unittest（18 认证、11 队列、6 数据库配置）全部 OK，本地同样 35 项通过。下载的证据包摘要与 GitHub 一致：`b40b57d87021308c132847b752ed0aa4739037defb2f70c698a7fefe6c6238b4`。日志记录 app、nginx、redis、worker 均 healthy。后续仅更新文档和证据的提交不改变上述已验收代码，也不触发重复构建。

## 实际结果

- 正常登录/身份查询 200；缺 Token、错误密码、非法签名、过期 Token 401。网页与 API 全部保护，健康与文档公开。
- 认证后经 Nginx /health、/docs、/ui/ 均 200；真实上传、Gradio SSE、原图及标注图取回成功。
- YOLO paper，confidence 0.9664，bbox [34.89,17.97,189.86,113.73]。同步推理和独立 worker 返回一致结果。
- worker 未运行时 POST /jobs 返回 202，任务 `b36313d1-d9d9-4baf-a189-561ec9909f15` 为 queued；重建 Redis 后仍 queued。
- 启动独立 worker 后任务 finished，消费者 hostname `073b8b4d7003`、pid 9，与 app 容器不同，返回真实 YOLO 结果。
- 联合任务缺 Key 明确 failed，error.status_code=503；路径穿越请求400，未登录任务请求401。owner 隔离另由单元测试覆盖。
- app 重建后命名卷相同，上传 SHA-256 `cdfb2e4528c26fb3faebda47fe7732d5a8ae9d96b81bcc629487adc8427dd21f` 不变，再次 YOLO 成功；Nginx 本身未重建。
- app/Redis 未发布宿主机端口，仅 Nginx 回环8080发布。应用镜像11个白名单项目文件，不含 .env、密钥、Git、虚拟环境、缓存或测试图片。
- 已用 Git 对象核对 web_ui.py、database.py、两个 AI service 与模型权重，和 Day4 ece2ff8 完全一致；app.py 原业务函数 AST 也未变，仅接入认证和任务路由。未修改第二阶段。

## 验收边界

CI 使用随机内存认证凭据，没有真实 Qwen API Key 或 SQL 密码。因此只验证 Qwen/SQL 缺配置保护，不代表真实 Qwen 请求、SQL 连接/记录保存及完整联合链路通过。没有执行真实浏览器截图验收；Gradio 客户端确实完成上传、流式分析及结果图片下载。

GitHub Runner 最终清理本次独立容器/卷；它证明 Linux Docker 可运行，不等于独立云主机持续部署。剩余原始考核项见 [STAGE3_GAPS.md](STAGE3_GAPS.md)。登录配置见 [AUTH.md](AUTH.md)，队列使用见 [QUEUE.md](QUEUE.md)。本轮没有为用户创建真实登录账户或保存真实密码。
