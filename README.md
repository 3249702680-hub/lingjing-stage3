# 灵境 AI 第三阶段：垃圾视觉识别对比 Web 系统

FastAPI + Gradio 提供图片上传、YOLO 垃圾检测、Qwen3-VL 分析和 SQL Server 持久化。网页显示原图、带框图、检测信息、Qwen 文本和数据库记录编号。

## 本机启动（PowerShell）

在本项目目录中使用现有虚拟环境；不要从第二阶段目录启动：

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py web_ui.py database.py
.\.venv\Scripts\python.exe scripts/configure_auth.py --run
```

如需安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

本次 Windows 环境使用 Python 3.14.7；requirements.txt 固定了本机现有的直接依赖版本。Linux Docker 与 Nginx 已通过真实 CI 验收；独立云主机部署仍未验证。

- 网页：[http://127.0.0.1:8000/ui/](http://127.0.0.1:8000/ui/)
- 接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 存活检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

`ERR_CONNECTION_REFUSED` 表示当前端口未接受连接。查看启动终端的实际错误，确认 Uvicorn 保持运行；语法通过不等于服务或模型分析成功。

## 模型与数据库配置

- 项目需要自己的 `weights/garbage_detect.pt`；不修改第二阶段目录。
- Qwen 使用 `qwen3-vl-plus`，从进程环境读取 `DASHSCOPE_API_KEY`。请通过本机安全配置设置，不把值写入代码或文档。
- SQL Server 需要数据库 `lingjing_stage3` 和 Microsoft ODBC Driver 18 for SQL Server。默认保留本机 Windows 集成认证；Linux / Docker 默认使用 SQL Server 账号认证。
- 可使用以下环境变量覆盖数据库配置：`SQLSERVER_AUTH`（`auto`、`windows`、`sql`）、`SQLSERVER_HOST`、`SQLSERVER_DATABASE`、`SQLSERVER_DRIVER`、`SQLSERVER_PORT`、`SQLSERVER_USERNAME`、`SQLSERVER_PASSWORD`。`auto` 在 Windows 有账号时使用 SQL 认证，否则使用集成认证；Linux 默认使用 SQL 认证。用户名与密码成对配置，仅置于安全的进程环境或受限的服务环境文件。
- `SQLSERVER_TRUST_SERVER_CERTIFICATE` 可设置为 `yes` 或 `no`。Windows 默认 `yes` 以兼容现有本机配置，Linux 默认 `no`，需要有效的服务器证书或可信 CA。若使用自签名证书，仅在明确接受证书信任策略时覆盖该值。
- 应用本身不会自动加载 `.env`；原生启动使用当前终端环境或 Linux 的 systemd `EnvironmentFile`，Docker Compose 则从终端 / `.env` 读取并注入配置。

首次部署可以只建表，不插入模拟分析结果：

```powershell
.\.venv\Scripts\python.exe -c "from database import init_db; init_db()"
```

已有数据库还需应用 [deploy/upgrade_unicode.sql](deploy/upgrade_unicode.sql)，使 Qwen 文本列使用 `nvarchar(max)`。旧 `varchar` 列会损坏 emoji 等 Unicode 字符；仅修改 ORM 类型不会自动升级现有表。此迁移保留现有记录，但不能恢复此前已丢失的字符：

```powershell
@'
from pathlib import Path
from database import engine

sql = Path('deploy/upgrade_unicode.sql').read_text(encoding='utf-8')
with engine.begin() as connection:
    connection.exec_driver_sql(sql)
'@ | .\.venv\Scripts\python.exe -
```

网页与 `/analyze` 仅在 YOLO 和 Qwen 均成功后写入 `dbo.analysis_records`，保存 `filename`、`yolo_result`、`qwen_answer` 和 `created_at`。数据库写入失败时不能把模型分析成功当作持久化成功。`/predict/yolo`、`/predict/qwen` 单独调用不会保存分析记录。

## 身份认证

先按 [JWT 配置与登录说明](deploy/AUTH.md) 设置自己的账户。网页从 `/login` 登录，API 使用 `/auth/token` 返回的 Bearer Token。Token 15 分钟过期；上传、推理、联合分析与整个 Gradio 路径均受保护。未配置认证时保护接口返回 503，健康检查和文档仍可访问。Docker 通过 Nginx `http://127.0.0.1:8080` 访问；原生服务仍为 8000。

## API 实际使用

| 方法 | 路径 | 请求与返回 |
| --- | --- | --- |
| GET | `/health` | 返回 `{"status":"ok"}`，仅检查 HTTP 服务存活 |
| GET | `/docs` | Swagger 页面 |
| GET | `/ui` | 重定向至 `/ui/`，显示 Gradio 网页 |
| POST | `/upload` | multipart 字段 `file`；返回 `filename` 等信息 |
| POST | `/predict/yolo` | JSON `{"filename":"上传接口返回的文件名"}`；返回 detections |
| POST | `/predict/qwen` | 同上；返回 model 与 answer |
| POST | `/analyze` | 同上；返回两种模型的真实结果和 record_id |

例如先将 `/auth/token` 返回的 access_token 保存在当前终端 `$token` 变量，再上传并分析本机图片（不要保存 Token 到脚本）：

```powershell
curl.exe -H "Authorization: Bearer $token" -F "file=@C:\path\sample.jpg" http://127.0.0.1:8000/upload
$headers = @{ Authorization = "Bearer $token" }
$body = @{ filename = 'sample.jpg' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Headers $headers -Uri http://127.0.0.1:8000/analyze -ContentType 'application/json' -Body $body
```

使用新文件名上传；同名文件返回 409，非图片类型返回 400。Qwen 配置缺失、上游失败或超时分别返回 503、502、504。

## 验收与部署

网页验收必须实际上传图片并点击“开始分析”，看到两种模型结果和记录编号，再按该编号查询 SQL Server：

```sql
SELECT id, filename, yolo_result, qwen_answer, created_at
FROM dbo.analysis_records
WHERE id = 123; -- 替换为网页显示的实际编号
```

除记录存在外，必须核对数据库中的完整 `qwen_answer` 与网页/API 原始回答逐字相等，包括中文、换行和 emoji；不能仅检查非空或中文片段。

Linux 启动脚本、systemd 模板及目标环境验证步骤见 [deploy/LINUX.md](deploy/LINUX.md)。Docker 构建、Compose 启动、网络与数据库配置、上传卷和验收步骤见 [deploy/DOCKER.md](deploy/DOCKER.md)；部署文件齐备不等于已通过目标环境运行验收。

不要提交密钥、`.env`、`.venv`、上传图片和运行缓存；提交前检查忽略规则与 Git 状态。

Day3 历史验证见 [deploy/ACCEPTANCE.md](deploy/ACCEPTANCE.md)，Day4 Docker 实际结果与未验收项见 [deploy/DOCKER_ACCEPTANCE.md](deploy/DOCKER_ACCEPTANCE.md)。

## 异步消息队列

新增 JWT 保护的 `POST /jobs` 和 `GET /jobs/{job_id}`。Redis 存储真实队列，独立 RQ worker 处理 YOLO 或联合分析；提交立即返回 202 和任务编号，查询返回状态、结果或明确失败。使用方式、任务过期及持久化边界见 [QUEUE.md](deploy/QUEUE.md)。启动 `docker compose up -d --build` 会一起启动消费者。原有同步接口与网页行为保留。

Day5 Nginx、JWT 与 Redis/RQ 的真实测试、提交及剩余范围见 [DAY5_ACCEPTANCE.md](deploy/DAY5_ACCEPTANCE.md) 和 [STAGE3_GAPS.md](deploy/STAGE3_GAPS.md)。
