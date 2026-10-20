# Linux 部署与验收

## 范围与验证边界

现有项目与本次可读取的上下文中未发现具体的 Linux/Docker 考核条款。本目录提供原生 Linux 部署文件；没有创建 Dockerfile 或 Compose 文件。

本机是 Windows，`wsl --list --quiet` 提示尚未安装 WSL，没有可用的 Docker 命令。进一步检查发现 Git for Windows 附带 Bash；已使用 `C:\Program Files\Git\bin\bash.exe -n start.sh` 对实际启动脚本完成语法检查，退出码为 0。Git Bash 不等于 Linux 运行环境；本次未执行 Linux 依赖安装、systemd 启停、Linux YOLO/Qwen 推理或 Linux 至 SQL Server 的连接验证。以下内容是待目标 Linux 主机执行的步骤，不代表已通过这些验收。

## 准备主机

1. 使用受支持的 Linux、Python 与独立虚拟环境，将第三阶段目录部署到 `/opt/lingjing-stage3`，不要复制 Windows `.venv`、上传图片、缓存或密钥。模型权重放在 `weights/garbage_detect.pt`。
2. 安装 Microsoft ODBC Driver 18 for SQL Server；按发行版使用 [Microsoft 官方安装说明](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver17)，安装相应 unixODBC 依赖。YOLO/OpenCV 还可能需要发行版的 OpenGL/GLib 运行库（Ubuntu 通常是 `libgl1`、`libglib2.0-0`），以实际安装错误为准。
3. 从 Linux 能访问 SQL Server 的 TCP 地址和端口；服务端启用所需的 TCP 与账号认证。Windows 主机名和本机集成认证不能直接视作 Linux 可用配置。使用专用 SQL 账号，或另行正确配置 Kerberos 集成认证。
4. 安装 Python 依赖并确认驱动可见：

```bash
cd /opt/lingjing-stage3
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -c 'import pyodbc; print(pyodbc.drivers())'
```

## 注入环境变量

通过受限的服务环境文件设置真实配置。以下仅为占位示例，不能直接当作凭据：

```ini
DASHSCOPE_API_KEY=replace-with-real-key
SQLSERVER_HOST=sql-server.example.internal
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=lingjing_stage3
SQLSERVER_DRIVER="ODBC Driver 18 for SQL Server"
SQLSERVER_USERNAME=replace-with-dedicated-user
SQLSERVER_PASSWORD=replace-with-real-password
SQLSERVER_TRUST_SERVER_CERTIFICATE=no
```

将真实文件保存为 `/etc/lingjing-stage3.env` 并限制权限（如 `root:root`、`0600`），不要把它放入仓库。systemd 会读取该文件；`start.sh` 不会自动加载 `.env`。前台运行时先在当前进程环境中安全设置同名变量。

Linux 默认校验服务器证书（`SQLSERVER_TRUST_SERVER_CERTIFICATE=no`），需要有效证书或可信 CA；Windows 默认 `yes` 保持现有本机行为。若明确需要使用自签名证书，按实际部署信任策略配置该变量。

由数据库管理员先创建数据库并授予必要权限；仅在需要时初始化表：

```bash
.venv/bin/python -c 'from database import init_db; init_db()'
```

该操作只建表，不插入模拟分析记录；不要用 `python database.py` 代替，因为当前脚本入口含数据库演示记录。

已有数据库必须应用 Unicode 列迁移；ORM 类型改变不会更新现存表。迁移将 Qwen 回答保存为 `nvarchar(max)`，避免旧 `varchar` 列损坏 emoji 等字符，不删除现有记录，也不能恢复历史已损坏内容：

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from database import engine

sql = Path('deploy/upgrade_unicode.sql').read_text(encoding='utf-8')
with engine.begin() as connection:
    connection.exec_driver_sql(sql)
PY
```

## 启动

前台运行：

```bash
bash -n start.sh
bash start.sh
```

脚本默认绑定 `127.0.0.1:8000`，单进程加载 CPU YOLO。需要远程访问时，通过受控反向代理暴露服务，或根据部署环境设置 `HOST`；不要在生产使用 `--reload`。

systemd 模板固定项目目录为 `/opt/lingjing-stage3`、服务用户为 `lingjing`。先创建该专用用户，确保项目及模型可读，`uploads` 和 Gradio/Ultralytics 所需的临时与用户缓存目录可写。若使用其他安装路径或账号，先同步修改模板。

```bash
sudo cp deploy/lingjing-stage3.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lingjing-stage3
sudo systemctl status lingjing-stage3
sudo journalctl -u lingjing-stage3 -n 100 --no-pager
```

## 目标 Linux 主机必须完成的验收

- `bash -n start.sh`、Python 语法/导入和 `pip check`。
- 实际启动后 `curl -i http://127.0.0.1:8000/health` 与 `/docs` 返回 200，`curl -iL http://127.0.0.1:8000/ui` 最终返回 200。
- 使用新的实际图片依次调用 `/upload`、`/predict/yolo`、`/predict/qwen`、`/analyze`，记录状态码与结果；确认 `/analyze` 返回的 `record_id` 在 SQL Server 中存在，完整 `qwen_answer` 与 API 原始回答逐字相等，包括中文、换行和 emoji。
- 浏览器实际访问 `/ui/`，上传图片并点击“开始分析”，确认两个模型结果、带框图和新的记录编号，按编号查询 `dbo.analysis_records`；将数据库完整回答与网页回答逐字比对，包括 emoji。
- systemd 重启后服务恢复，权重、SQL Server 记录和配置保持可用；进程日志不包含密钥。

只有这些步骤在 Linux 实际执行并保存结果后，才能认定 Linux 运行验收完成。
