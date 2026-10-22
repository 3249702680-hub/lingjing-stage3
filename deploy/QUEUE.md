# Redis / RQ 异步分析任务

原始考核要求“任务生产与消费、异步处理与结果返回”。FastAPI 是生产者，Redis 是实际 broker，独立 Linux `worker` 容器是消费者；`POST /jobs` 返回 202，分析在消费者中执行，不占用该 HTTP 请求。原同步 API 和 Gradio 流程保留，模型函数未重写。

## 启动

先完成 [JWT 配置](AUTH.md)，运行：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 worker redis
```

Compose 含 app、nginx、redis、worker；只有 Nginx 发布回环端口 8080。Redis 不发布宿主机端口，启用 AOF 和 `redis_data` 命名卷。app/worker 使用同一镜像和 `uploads` 卷。worker 以 UID 10001 执行现有 `predict_yolo` 或 `analyze`，复用文件名检查、YOLO、Qwen 和 SQL 保存逻辑。

原生启动默认没有可用 Redis 时，`/jobs` 返回 503，其他同步接口仍可正常使用。若自行部署 Redis，给 app/worker 设置 `REDIS_URL`；RQ worker 使用 Linux 进程模型，推荐上述 Docker 启动方式。

## 提交与查询

在 `/docs` 登录并 Authorize，先 `/upload` 上传，再提交：

```json
{"filename":"上传返回的文件名.jpg","mode":"yolo"}
```

`POST /jobs` 成功返回 `{"job_id":"...","status":"queued"}`，HTTP 202 表示入队而非推理完成。`mode` 支持 `yolo` 或 `analyze`，默认 analyze；后者还需真实 Qwen Key 和 SQL Server 配置。调用 `GET /jobs/{job_id}` 查看 queued/started/finished/failed。

成功示意（仅结构示意，实际识别以真实返回为准）：

```json
{"job_id":"...","status":"finished","result":{"filename":"paper.jpg","detections":[{"class_name":"paper","confidence":0.9664,"bbox":[34.89,17.97,189.86,113.73]}]},"worker":{"hostname":"消费者容器ID","pid":123}}
```

业务失败返回 `status=failed` 和脱敏的 `error.status_code/detail`。例如缺 Qwen Key 返回业务错误 503，查询请求本身仍为 200；它不代表模型成功。底层 RQ 保存了失败结果时可能标记 finished，HTTP 查询统一映射为业务 failed。

任务属于提交时的 JWT subject；其他身份、缺失或过期任务统一 404，不返回 traceback。每次任务最多运行 360 秒，排队过期时间和完成后结果保留时间均为 3600 秒。Redis 数据卷会保留排队信息，但不是永久结果库。AOF 每秒刷盘；不承诺断电时零丢失或 exactly-once，不对外部付费 API 自动重试。正常重建勿使用 `docker compose down -v`。

## 验收范围

本地单元测试覆盖路径安全、owner 隔离、失效任务、Redis 故障、JSON 序列化、业务错误和脱敏。CI 真实先在 worker 未启动时入队并查询 queued，重建 Redis 验证任务保留，再启动独立 worker，查询纸张 YOLO 真实结果，并核对消费者容器身份。另测无 Key 的 analyze 任务明确失败。真实 Qwen/SQL 成功链路需凭据，不由这些负向测试替代。

参考：[RQ 官方队列文档](https://python-rq.org/docs/)、[Worker](https://python-rq.org/docs/workers/)。
