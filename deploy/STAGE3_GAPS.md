# 灵境第三阶段：考核要求与完成情况

更新日期：2026-10-24（北京时间）。本次更新前基准仓库：`3249702680-hub/lingjing-stage3`，`main`，提交 `70099a23f42c47e91213f03bb9032ffc5c4717c6`。

本文件替代仓库 `deploy/STAGE3_GAPS.md` 的 2026-10-22 旧状态。依据原始《三阶段思维导图.pdf》、仓库代码/既有验收报告、用户提供的修正版及本轮明确补充的 2026-10-23 真实验收结果。本次只更新文档，没有重新测试、执行 CRUD 或调用模型。

## 原始成果要求

1. 将第二阶段两种识别方案整理为可操作的 Web 项目，同一图片并排呈现 YOLO/SAM 与多模态模型结果。
2. 在 Linux 服务器中用 Docker 运行 Web 应用，页面、后端接口和模型功能正常联通；记录环境、依赖和启动步骤。
3. 持续使用 GitHub/Gitee 管理代码与依赖，保留真实提交历史。
4. 提交介绍项目和个人感悟的文档，以及展示项目运行和主要结果的视频；原文件不限定字数、格式或视频时长。

原文件没有指定云厂商、域名、全天在线、付费或 4 GB 内存要求。临时 CI 的 Linux 运行证据与独立目标服务器部署应分别记录，不能互相替代。

## 逐项核对

| 项目 | 当前结论 | 已有证据与边界 |
| --- | --- | --- |
| Web 与双方案展示 | 已实现，有历史运行证据 | FastAPI + Gradio；上传图片、YOLO 检测框、Qwen 文本、记录编号。使用 YOLO 方案，不宣称另做了 SAM。 |
| JWT 登录与身份识别 | 已实现并验收 | `/auth/token`、`/auth/me`、网页/API 保护及令牌异常测试；单部署账户。见仓库 `deploy/JWT_ACCEPTANCE.md` 和 `deploy/DAY5_ACCEPTANCE.md`。 |
| 消息队列与异步处理 | 已实现并验收 | Redis + 独立 RQ worker；`POST /jobs`、`GET /jobs/{job_id}`；既有排队/重建/消费测试。本地 Docker Desktop 真实联合任务 `8186a6b4-8147-42b1-af9e-5c58ca9c290f` 最终 `finished`，生成 SQL Server 记录 ID `2005`。 |
| Nginx 反向代理与网页服务 | 已实现并验收 | Compose 四服务结构，Nginx 为入口；代理、上传、SSE、图片返回和重建检查见既有 CI 报告。 |
| Linux + Docker 基础运行 | 已有真实 Linux CI 证据 | 镜像导出工作流 [39928501391](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39928501391) 实际构建并运行 35 项单元测试；此前四服务 healthy、39 项容器检查见 [DAY5_ACCEPTANCE.md](DAY5_ACCEPTANCE.md)。CI 未配置真实 Qwen/SQL 业务凭据，不代表真实联调或独立服务器完整部署。 |
| 真实 Qwen 与 SQL Server 持久化 | 本地 Docker Desktop 联调已通过 | 2026-10-23，容器内 Qwen 调用返回 `QWEN_SUCCESS`，模型 `qwen3-vl-plus`；真实联合任务完成，SQL Server `dbo.analysis_records.id=2005` 的 `yolo_result` 和 `qwen_answer` 均存在。此证据来自本地 Docker Desktop，不来自无业务凭据的 CI。 |
| SQLAlchemy CRUD 学习项 | 临时行完整验收已通过 | 临时 SQLAlchemy 记录的 `CREATE`、`READ`、`Unicode roundtrip`、`UPDATE`、`DELETE`、`TEMP_ROW_ABSENT` 均通过；临时记录已清理，真实记录 `2004`、`2005` 未删除。这是 ORM 数据操作验收，不宣称新增了 CRUD HTTP 路由。 |
| 文本编码核对 | 本次文本还原与数据库比对通过 | PowerShell 曾错误解码 UTF-8；正确还原后数据库文本一致，`REVERSED_TEXT_MATCHES_DB=True`。这是本次文本还原比对结果，不把显示乱码误判为数据库写入失败，也不扩大为所有链路的通用编码保证。 |
| 独立 Linux 目标服务器部署 | **完整部署尚未验收** | 本地 Docker Desktop 已有真实 Qwen + SQL Server 联调证据；独立 Linux 服务器上的页面、后端、模型和数据库完整链路仍需实际部署验收，不能将本地或临时 CI 结果替代目标服务器验收。 |
| 演示视频 | **真实运行视频尚未录制** | 演示脚本、历史截图和验收日志不等于实际运行录像，不能标记视频已完成。 |

## 镜像交付证据

- GitHub Actions：[运行39928501391](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39928501391)。
- 镜像构建源提交：`70099a23f42c47e91213f03bb9032ffc5c4717c6`。
- Artifact：`12489914451`，约1.88GB；[下载入口](https://github.com/3249702680-hub/lingjing-stage3/actions/runs/39928501391/artifacts/12489914451)。
- Artifact ZIP SHA256：`4745f0a4dc6fc996bb14f47aefc5310d2863e74c26b6a89613f300b5d8ec4bee`。此值不是内部镜像 tar 的校验值；tar 采用包内 `image-tar.sha256`。
- 过期时间：2026-10-26 17:00:30（北京时间；UTC 09:00:30）。这是临时下载交付，不是长期镜像仓库。

## 尚需收口的成果

1. 完成独立 Linux 服务器上的完整应用部署与真实联调，保存页面、后端、模型和数据库正常联通的证据。当前不能声称这一项已完成。
2. 录制展示项目启动、操作和主要结果的真实运行视频；目前尚未录制。
3. 按实际考核渠道核对项目说明、个人感悟、仓库链接和视频并提交。本次文档同步不等于已向考核方完成正式提交。
