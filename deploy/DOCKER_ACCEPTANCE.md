当前包含 JWT 与真实消息队列的最新整体验收见 [DAY5_ACCEPTANCE.md](DAY5_ACCEPTANCE.md)：run 39800419193，39 项容器检查、35 项单元测试全部通过。下文保留各阶段历史。

# Day5 Nginx 实机验收：通过

- [GitHub Actions 39795471809](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39795471809)：success，实测提交 `f1bc5e67c22aad3ae0ef02287545e1bb838fab04`。
- [原始验收 JSON](evidence/nginx-acceptance-39795471809.json)，22 项检查通过；证据包 SHA-256 `691e8594c09f0335740990a9e11247df828ff344093162309b11f5194239c25d`。
- app 没有宿主机端口绑定；所有 HTTP 检查经过 Nginx，/health、/docs、/ui/ 全部 200。
- 真实上传及 YOLO 返回 paper、0.9664、bbox [34.89,17.97,189.86,113.73]。
- Gradio 客户端经过 Nginx 上传、SSE 分析并取回原图、标注图与 detections；缺 Qwen Key 的提示正常。这不是真实 Qwen 上游验收，也不宣称浏览器像素验收。
- Nginx 未重启，app 重建后仍可访问，命名卷文件 SHA-256 一致，再次 YOLO 成功。
- API 在运行时曾出现 run 已 success、job 仍 queued 的平台延迟；本记录依据已下载且摘要匹配的实际日志与 JSON。

以下是之前 Docker 验收与失败历史，保留原始时间和范围。

---

# GitHub Actions Docker 实机验收：通过

验收时间：2026-10-22 20:10–20:12（北京时间）。

- [真实工作流运行 #1](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39776167901)：success。
- 实测代码提交：`05ce97a01c4363d2c54186759ef1e1912d0e10f4`。
- 环境：GitHub 托管 Ubuntu 24.04，真实 Docker Engine；镜像构建约 76 秒，容器自动验收约 25 秒。
- [永久保存的原始验收 JSON](evidence/docker-acceptance-39776167901.json)。完整构建、容器及测试日志位于运行页面的 artifact（保留 7 天）。
- 下载证据包 SHA-256 与 GitHub 公布摘要一致：`1d388f9469bcad46bd45080c457dc3e60cc71c2fbf895a22c3cb33bc55c7860e`。

| 实际检查 | 结果 |
| --- | --- |
| 当前 Dockerfile 构建、pip check | 通过 |
| 容器启动及 Docker HEALTHCHECK | running / healthy |
| GET /health、/docs、/ui/ | 全部 HTTP 200 |
| 真实纸张 JPEG 上传 | HTTP 200，使用独立 UUID 文件名 |
| POST /predict/yolo | HTTP 200；paper；confidence 0.9664 |
| YOLO bbox | [34.89, 17.97, 189.86, 113.73] |
| 非 root / CPU 依赖 | UID 10001；torch 2.14.1+cpu；torchvision 0.29.1+cpu；CUDA 为 null |
| ODBC | ODBC Driver 18 for SQL Server 已加载 |
| 上传持久化 | 新旧容器 ID 不同、命名卷相同，文件 SHA-256 一致，再次 YOLO 成功 |
| 上传文件 SHA-256 | cdfb2e4528c26fb3faebda47fe7732d5a8ae9d96b81bcc629487adc8427dd21f |
| 镜像项目文件检查 | 只包含 8 个白名单文件；无 .env、Git、虚拟环境、缓存或测试图片 |
| Linux 数据库配置回归 | 6 项 unittest 全部通过 |

为解决慢速下载，Docker 使用官方同版本 `ultralytics-opencv-headless==8.4.182`，保留 `ultralytics` Python 导入接口及 CPU PyTorch pin，省去编译器与桌面图形依赖。原 requirements.txt、AI 业务代码和模型权重未改。

**验收边界：** CI 明确清空 DASHSCOPE_API_KEY 和 SQL 账号密码，不需要仓库业务 secrets。缺 Key 的 /predict/qwen、/analyze 实际返回 503；缺 SQL 配置在连接前被拒绝。这些只验证错误保护，不代表真实 Qwen、SQL Server 或完整 /analyze 保存通过。/ui/ 的 HTTP 200 只确认页面可访问，未替代浏览器交互验收。

GitHub Actions 是临时验收环境，工作流结束会清理本次独立容器与卷；命名卷持久化已在清理前完成验证。它不代表长期云服务器或公网部署已完成。其他原始考核缺项见 [STAGE3_GAPS.md](STAGE3_GAPS.md)。

以下保留此前的静态检查、Windows 回归及 VirtualBox 失败历史；不将这些历史结果作为本次容器成功的依据。

---

# Day4 Docker 验收记录

日期：2026-10-22（北京时间）。本记录保留失败与未执行项目，不将 Windows 结果替代 Linux 容器验收。

## 考核与交付范围

已核对原始《三阶段思维导图.pdf》：“用 Linux + Docker 部署服务器”“在 Linux 服务器中用 Docker 运行 Web 应用”“页面、后端接口与模型功能正常联通”。Docker 运行属于正式要求，目前尚未全部验收。

本次交付 Dockerfile、构建上下文白名单、Compose、数据库环境变量认证适配、回归测试和部署说明。app.py、web_ui.py、两个 AI 服务、requirements.txt 和模型权重保持原样，未修改第二阶段。

## 历史记录：此前 VirtualBox 构建尝试

- Windows / Codex 执行环境没有本机 Docker 引擎；不能使用 Windows API 成功来证明容器成功。
- VirtualBox Ubuntu 实际版本为 26.04.1 LTS，x86_64；Docker Engine 29.1.3、Buildx、Compose 2.40.3 已实际安装。
- Docker 官方安装源的签名文件请求曾出现连接重置，随后使用 Ubuntu 官方软件源安装 Engine 与 Compose。
- 初次基础镜像拉取因网络拒绝失败。使用主机既有的无凭据代理后，Docker 官方 registry 与匿名认证端点均实际可达，保持 HTTPS 证书校验；未使用未知镜像站。
- 后续构建通过基础镜像阶段，进入 Debian 系统依赖安装；代理对 Debian HTTP 软件源返回 502，apt 因拿不到签名索引退出 100。没有关闭包签名验证。
- 已将 Dockerfile 中 Debian 官方软件源切换为 HTTPS。该修复后的完整构建尚未通过；本轮恢复虚拟机保存状态返回成功后，再次检查为 poweroff，未继续反复启动。
- 代理仅用于目标虚拟机的临时 Docker 运行环境和构建请求，没有写入 Dockerfile、Compose 或 Git；没有传输 Qwen Key 或数据库密码。

**上述 VirtualBox 尝试当时未成功；本次 Docker 实机验收已由以下 GitHub Actions 运行完成。**

## 已通过检查

| 检查 | 实际结果与执行环境 |
| --- | --- |
| 认证回归测试 | Windows：6 项 unittest 全部通过；涵盖系统默认、显式认证、缺失账号、无集成认证回退、密码掩码及特殊字符转义 |
| Python 与 Compose 静态检查 | Python AST、YAML 配置解析通过；Python 3.12 满足现有直接依赖的版本要求 |
| 原有 AI 文件与权重 | SHA-256 与修改前一致，没有重写 AI 业务逻辑 |
| Git 与源码包扫描 | 未发现配置的真实 API Key 或禁止提交的环境文件、虚拟环境、上传图片和 Python 缓存；Git 历史未匹配配置的 Key |
| 忽略规则 | .env、.venv、真实 uploads、缓存均被忽略；uploads/.gitkeep 保留 |
| 构建包 | 只打包明确列出的应用文件、依赖和垃圾检测权重；paper.jpg 独立于构建包 |
| Git 差异格式 | git diff --check 通过 |

此前同一 Day4 工作区已经实际完成以下 Windows 回归，之后仅修改部署配置与文档：

- FastAPI TestClient：GET /、/health、/docs、/ui/ 均返回 200。
- YOLO：paper.jpg 返回 paper，confidence 0.9664，bbox [34.89, 17.97, 189.86, 113.73]。
- 非法路径返回 400，不存在图片返回 404。
- Qwen3-VL 真实请求返回 200，识别纸张及可回收物。
- 选择 SQL 认证且未配置账号时，/analyze 在模型分析后返回 500 和通用保存失败提示；这是错误处理验证，不代表数据库保存成功。
- Windows localhost 集成认证只读查询成功；服务器允许混合认证，analysis_records 当时有 7 条记录。没有修改数据库安全设置。

## 历史记录：当时的恢复条件（Docker 基础验收现已通过 CI）

1. 在 Ubuntu 保持运行、Docker 客户端和引擎均能通过有效网络访问官方仓库、Debian HTTPS、Microsoft 软件源与 PyTorch CPU 索引后，按 [DOCKER.md](DOCKER.md) 重新构建。
2. 构建成功后仍需启动容器，验证 /health、/docs、/ui/、真实图片上传、YOLO、非 root 权限、ODBC Driver 18 和上传卷重建持久化。
3. 容器内真实 Qwen 需要在该环境安全注入 DASHSCOPE_API_KEY 并确认网络；未将 Windows Key 复制到虚拟机或镜像。
4. 容器 SQL Server 端到端验证需要可用的 SQL 登录账号密码、可达 TCP 地址与端口，以及正确证书信任配置。没有账号就不能证明连接与记录保存成功。Windows 集成认证不等于 Linux 容器认证。
5. 完整 /analyze 与网页记录保存需要同时满足 Qwen 和 SQL Server 条件，再核对数据库中的完整回答与原始返回一致。

运行说明见 [DOCKER.md](DOCKER.md)。Day3 历史验证见 [ACCEPTANCE.md](ACCEPTANCE.md)；其中结果仅代表当时环境。
