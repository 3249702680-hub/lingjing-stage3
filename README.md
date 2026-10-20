# 灵境 AI 第三阶段：垃圾视觉识别对比 Web 系统

FastAPI + Gradio 提供图片上传、YOLO 垃圾检测、Qwen3-VL 分析和 SQL Server 持久化。网页显示原图、带框图、检测信息、Qwen 文本和数据库记录编号。

## 本机启动（PowerShell）

在本项目目录中使用现有虚拟环境；不要从第二阶段目录启动：

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py web_ui.py database.py
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

如需安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

本次 Windows 环境使用 Python 3.14.7；requirements.txt 固定了本机现有的直接依赖版本。Linux 尚需在目标环境安装与运行验证。

- 网页：[http://127.0.0.1:8000/ui/](http://127.0.0.1:8000/ui/)
- 接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 存活检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

`ERR_CONNECTION_REFUSED` 表示当前端口未接受连接。查看启动终端的实际错误，确认 Uvicorn 保持运行；语法通过不等于服务或模型分析成功。

## 模型与数据库配置

- 项目需要自己的 `weights/garbage_detect.pt`；不修改第二阶段目录。
- Qwen 使用 `qwen3-vl-plus`，从进程环境读取 `DASHSCOPE_API_KEY`。请通过本机安全配置设置，不把值写入代码或文档。
- SQL Server 需要数据库 `lingjing_stage3` 和 Microsoft ODBC Driver 18 for SQL Server。默认保留本机 Windows 集成认证。
- 可使用以下环境变量覆盖数据库配置：`SQLSERVER_HOST`、`SQLSERVER_DATABASE`、`SQLSERVER_DRIVER`、`SQLSERVER_PORT`、`SQLSERVER_USERNAME`、`SQLSERVER_PASSWORD`。设置用户名时采用 SQL Server 账号认证；密码仅置于安全的进程环境或受限的服务环境文件。
- `SQLSERVER_TRUST_SERVER_CERTIFICATE` 可设置为 `yes` 或 `no`。Windows 默认 `yes` 以兼容现有本机配置，Linux 默认 `no`，需要有效的服务器证书或可信 CA。若使用自签名证书，仅在明确接受证书信任策略时覆盖该值。
- `.env` 不会自动加载；使用当前终端环境，或由 Linux 的 systemd `EnvironmentFile` 注入。

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

例如在 PowerShell 中上传并分析本机图片：

```powershell
curl.exe -F "file=@C:\path\sample.jpg" http://127.0.0.1:8000/upload
$body = @{ filename = 'sample.jpg' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analyze -ContentType 'application/json' -Body $body
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

Linux 启动脚本、systemd 模板及目标环境验证步骤见 [deploy/LINUX.md](deploy/LINUX.md)。目前未取得要求 Docker 的考核原文，因此不新增 Docker 配置，也不将 Docker 认定为已验收。

不要提交密钥、`.env`、`.venv`、上传图片和运行缓存；提交前检查忽略规则与 Git 状态。

本次提交前的实际验证结果和未执行项目见 [deploy/ACCEPTANCE.md](deploy/ACCEPTANCE.md)。
