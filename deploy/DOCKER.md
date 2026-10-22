# Docker 部署与验证

## 范围与当前状态

本方案运行 FastAPI、Gradio 和 CPU YOLO，数据库使用可从容器访问的外部 SQL Server。镜像基于 Python 3.12 slim / Debian 12（bookworm），安装 unixODBC、Microsoft ODBC Driver 18、官方同版本 Ultralytics headless / OpenCV headless，以及 CPU 版 torch 2.14.1+cpu、torchvision 0.29.1+cpu；应用使用 UID 10001 的非 root 用户，直接由 Uvicorn 监听容器的 `0.0.0.0:8000`，不经过原生 Linux 的 `start.sh`。

当前 Docker 镜像构建、容器启动、接口、真实 YOLO 与命名卷重建持久化已通过 GitHub Actions 实机验收。实测提交、原始 JSON 和边界见 [DOCKER_ACCEPTANCE.md](DOCKER_ACCEPTANCE.md)。Qwen、SQL Server 和长期云部署仍需要各自的真实验收。

没有 Qwen 或数据库凭据时，允许启动服务并访问 `/health`、`/docs`；`/ui/` 和 AI 接口需先按 [AUTH.md](AUTH.md) 配置并登录；本地权重和运行依赖正常时可以测试 YOLO。Qwen 调用仍需要有效 API Key，数据库访问仍需要真实可达地址、认证及数据库权限。打开网页并不等于点击“开始分析”能够完整成功；完整分析必须同时完成 YOLO、Qwen 和数据库保存。

## 准备

安装适用于主机的 Docker Engine / Docker Desktop 和 Compose 插件，确认使用 Linux 容器。在本项目目录执行，Compose 配置文件为 `docker-compose.yml`，服务名为 `app`：

```bash
docker version
docker compose version
```

准备自己的 `weights/garbage_detect.pt`，不要使用第二阶段目录作为构建上下文。CPU 推理不需要 GPU 或 NVIDIA Container Toolkit。

创建本地 `.env` 文件。以下只有示例配置和空凭据；请在自己的环境中补齐真实值：

```dotenv
AUTH_USERNAME=
AUTH_PASSWORD_HASH=
JWT_SECRET=
AUTH_COOKIE_SECURE=false
DASHSCOPE_API_KEY=
SQLSERVER_AUTH=sql
SQLSERVER_HOST=not-configured
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=lingjing_stage3
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_USERNAME=
SQLSERVER_PASSWORD=
SQLSERVER_TRUST_SERVER_CERTIFICATE=no
```

Compose 从当前终端环境或项目 `.env` 中读取这些变量，并将配置传入容器；同名终端变量优先。应用本身不会自动加载 `.env`，原生 Windows / systemd 启动仍按 [LINUX.md](LINUX.md) 和 README 的方式注入环境。

`not-configured` 是允许无凭据启动的占位值。接入数据库前必须改成可达地址，并同时设置 SQL Server 用户名、密码。不要把真实凭据写入 Dockerfile、Compose、构建参数、源代码或文档；`.env` 必须排除在 Git 和 Docker 构建上下文之外。命令输出、截图和部署日志也不应包含密钥或密码。镜像只包含运行程序与模型，不包含本机虚拟环境、上传图片和运行缓存。

## 数据库地址、认证与证书

`SQLSERVER_HOST` 是从容器发起连接时使用的 SQL Server 地址，不能填容器自己的 `localhost` 或 `127.0.0.1`，除非数据库确实运行在同一容器中。本方案没有在应用容器内运行 SQL Server。

| 运行位置 | SQL Server 在 Windows 主机时的地址 |
| --- | --- |
| Docker Desktop Linux 容器 | 通常使用 `host.docker.internal` |
| VirtualBox 中的 Ubuntu，虚拟机使用 NAT | 通常使用 NAT 主机地址 `10.0.2.2`；需验证目标端口实际可达 |
| 独立 Linux 主机或其他网络拓扑 | 使用从 Linux / 容器可达的 Windows 局域网 IP 或 DNS 名称 |
| SQL Server 位于其他服务器 | 使用该服务器可达的 TCP 地址和实际端口 |

Docker Engine 原生 Linux 环境不默认提供 Docker Desktop 的 `host.docker.internal` 名称；请根据实际网络配置选择地址。VirtualBox 的 NAT 地址也是拓扑相关的部署选择，不代表 SQL Server 端口已开放。

SQL Server 必须启用 TCP/IP，监听配置的端口，Windows 防火墙允许来自实际部署网络的连接。使用专用账号及必要权限；不要开放到不受控的网络。若实例使用动态端口，请先确认实际 TCP 端口或配置稳定端口，而不是假定 1433 一定可用。

认证变量含义：

- `SQLSERVER_AUTH=sql`：使用 SQL Server 账号认证，设置成对的 `SQLSERVER_USERNAME` 和 `SQLSERVER_PASSWORD`。这是 Linux 容器和 Compose 的默认选择。
- `SQLSERVER_AUTH=windows`：使用 Windows 集成认证。本机 Windows 可沿用原有连接。本项目不实现 Linux Kerberos 集成认证；Linux 设置 windows 会明确报错，应使用 sql，不能继承宿主机登录状态。
- `SQLSERVER_AUTH=auto`：Windows 在提供账号时选择 SQL 认证，否则选择 Windows 集成认证；Linux 默认选择 SQL 认证。

连接保持加密，容器默认 `SQLSERVER_TRUST_SERVER_CERTIFICATE=no`，要求服务器证书链可信且名称与连接地址匹配。通过 IP、`host.docker.internal` 或 NAT 地址连接时，证书名称可能不匹配；正式部署优先使用与证书一致的 DNS 名称并配置可信 CA。使用内部 CA 时，应让容器信任该 CA。仅在明确接受自签名证书或测试环境策略时，临时设置为 `yes`；它跳过服务器证书校验，不应当作默认配置。

## 构建与启动

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 app
```

访问：

- 网页：[http://127.0.0.1:8080/ui/](http://127.0.0.1:8080/ui/)
- API 文档：[http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)
- 存活检查：[http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)

容器 HEALTHCHECK 调用 `/health`。该接口只表示 HTTP 服务存活，不检查 Qwen 凭据、SQL Server 连接、表结构或真实 YOLO 推理。必须继续完成下面的功能验证。

需要从其他计算机访问时，先核对 Compose 的主机端口绑定及防火墙；虚拟机部署还需核对端口转发或网络模式。容器监听 `0.0.0.0` 不等于外部主机必然能访问它。

## 显式初始化数据库

先由数据库管理员创建 `SQLSERVER_DATABASE` 指定的数据库，并授权专用账号。确认环境配置完成后，只创建所需表：

```bash
docker compose exec app python -c "from database import init_db; init_db()"
```

不要使用 `python database.py` 初始化部署，因为其脚本入口还包含演示记录。应用启动和 `/health` 不会代替数据库初始化。

已有数据库应通过数据库管理工具执行 [upgrade_unicode.sql](upgrade_unicode.sql)，将现存 `qwen_answer` 列升级为 `nvarchar(max)`。仅修改 ORM 类型或再次执行 `init_db()` 不会迁移已有列，也不能恢复历史损坏字符。执行前应按自己的数据库管理流程备份并核对目标实例和数据库。

## 接口与持久化验证

以下命令使用 Bash；Windows PowerShell 上传时使用 `curl.exe`，或参考项目 README 的 PowerShell 示例。把图片路径改为自己的真实图片，并使用新文件名，避免与已有上传重名：

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS -H "Authorization: Bearer $TOKEN" -F 'file=@/absolute/path/new-sample.jpg' http://127.0.0.1:8080/upload
```

记录上传响应中的实际 `filename`，将下面的 `new-sample.jpg` 替换为该值：

```bash
curl -fsS -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"filename":"new-sample.jpg"}' http://127.0.0.1:8080/predict/yolo

curl -fsS -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"filename":"new-sample.jpg"}' http://127.0.0.1:8080/predict/qwen

curl -fsS -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"filename":"new-sample.jpg"}' http://127.0.0.1:8080/analyze
```

`/predict/yolo` 不需要 Qwen 或数据库凭据；`/predict/qwen` 需要有效 Qwen 配置；`/analyze` 还需要数据库连接和表可用。缺少这些配置时出现相应错误，不能判定完整流程通过。

验收需记录真实图片的模型结果、`/analyze` 返回的 `record_id`，并在 SQL Server 按编号查询 `dbo.analysis_records`。核对文件名、YOLO JSON 和完整 `qwen_answer` 与原始返回一致，包括中文、换行和 emoji。另需在浏览器访问 `/ui/`，上传图片并点击“开始分析”，验证两个模型、带框图、完整回答和新的记录编号。单纯 HTTP 200 或数据库列非空不够。

## 上传文件与重启

Compose 使用命名卷 `uploads:/app/uploads` 保存真实上传文件。容器以 UID 10001 运行，卷内上传目录必须对该用户可写。默认使用命名卷；如自行改为主机目录挂载，需预先处理目录权限。

```bash
docker compose restart app
docker compose ps
docker compose down
docker compose up -d
```

重启或重建后，应使用之前上传的实际文件名再次调用 YOLO，确认上传文件仍在，并核对数据库原有记录保留。SQL Server 位于容器外，其数据不由应用上传卷管理。

`docker compose down` 默认保留命名卷。不要在保留数据的流程中使用 `docker compose down -v`、手动删除上传卷或清理卷的命令；这些操作会删除持久化上传文件。

## 参考

- [Docker Compose 入门](https://docs.docker.com/compose/gettingstarted/)
- [Compose 环境变量](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)
- [微软 Linux ODBC Driver 18 安装说明](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver17)


## GitHub Actions 验收

工作流位于 `.github/workflows/docker-acceptance.yml`。推送涉及 Docker、应用、模型权重或测试的 main 提交时自动运行，也可以在 GitHub Actions 的 Docker acceptance 页面点击 Run workflow。

它构建当前 Dockerfile，上传 `tests/fixtures/paper.jpg`，测试 /health、/docs、/ui/、YOLO、ODBC/CPU/非 root 配置及命名卷重建后的文件哈希与再次推理。测试样本不进入镜像。CI 不配置真实 Qwen Key 或数据库密码，外部服务的缺配置保护与真实调用分别记录。

构建、运行日志与 JSON 始终上传为 artifact；任何必须检查失败都会使 job 失败。验收后的清理只针对该 run 独有的 Compose 项目，独立命名卷已在清理前完成重建持久化验证。该工作流只验收应用容器，不自动部署长期公网服务。

Docker 内按 requirements.txt 中相同版本使用官方 `ultralytics-opencv-headless` 分发，不改变本地 Windows 依赖文件和 `from ultralytics import YOLO`。pyodbc 与 OpenCV 要求二进制 wheel，避免下载编译器及桌面 OpenGL/LLVM。参见 [Ultralytics 官方安装说明](https://docs.ultralytics.com/quickstart/) 和 [同版本分发](https://pypi.org/project/ultralytics-opencv-headless/8.4.182/)。


## Day5：Nginx 统一入口

Compose 只发布 Nginx 的 `127.0.0.1:${HTTP_PORT:-8080}`，app 的 8000 只对 Compose 网络开放。原生 Windows 开发仍可用原有 `uvicorn app:app --reload`；不要混淆原生 8000 和容器代理 8080。

运行 `docker compose up -d --build` 后访问 `http://127.0.0.1:8080/ui/` 和 `/docs`。`deploy/nginx.conf` 只读挂载到 Nginx，所有 URL 原样转发，支持 WebSocket Upgrade、Gradio SSE，关闭响应缓冲，并允许 12 MiB 请求体（Gradio 单图仍限制 10 MB）。Nginx 使用 Docker DNS 动态解析 app，app 重建后无需重启代理。

执行 `docker compose exec nginx nginx -t` 检查配置，`docker compose logs --tail=100 nginx app` 查看错误。公网部署需另行配置可信 HTTPS 与访问控制，当前仅绑定本机地址，不自动开放公网。

CI 的所有 HTTP 验收经 Nginx 8080 入口，另用 Gradio 客户端经过代理真实上传、运行纸张 YOLO、取回原图和标注图，并检查缺 Key 提示。Gradio 当前使用 SSE；WebSocket Upgrade 配置保留兼容性。CI 同时确认 app 没有发布端口，且 app 重建后 Nginx 本身未重建、上传文件与再次推理仍正常。没有把 Qwen 缺 Key 提示算作上游成功。

参考：[Gradio 官方 Nginx 部署说明](https://www.gradio.app/guides/running-gradio-on-your-web-server-with-nginx)、[Nginx WebSocket 代理](https://nginx.org/en/docs/http/websocket.html)。

JWT 配置及本机启动见 [AUTH.md](AUTH.md)。上面的 HTTP 示例中 `$TOKEN` 是当前登录返回的短时 Token，不能提交或打印到 CI 证据。
