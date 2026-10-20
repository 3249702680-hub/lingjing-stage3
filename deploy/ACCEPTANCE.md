# 第三阶段提交前验收记录

日期：2026-10-20（北京时间）。本记录区分 Windows 实测与尚未执行的 Linux 验收。

## 本轮实际结果

| 检查 | 结果 |
| --- | --- |
| 现有虚拟环境 Python | 3.14.7 |
| app.py / database.py / web_ui.py 与两个模型服务语法 | py_compile 通过 |
| 依赖一致性 | pip check 通过，无冲突 |
| GET /health、/docs、/ui/ | 均 200 |
| GET /ui | 307 到 /ui/，最终 200（今日已实测） |
| POST /upload | 200，真实 JPEG 上传 |
| POST /predict/yolo | 200；paper，置信度 0.9664，框 [34.89,17.97,189.86,113.73] |
| POST /predict/qwen | 200；qwen3-vl-plus 真实中文分析完成 |
| POST /analyze | 200；12.645 秒；新记录 6 |
| API 与 SQL Server 比对 | 文件名、YOLO JSON、Qwen 全文（含 emoji）精确一致 |
| Gradio 实际上传、点击开始分析 | 两个模型完成；原图、带框图、JSON、Qwen 和记录编号正常显示 |
| 网页数据库记录 | 编号 7；Qwen 全文 454 字符与数据库逐字一致 |
| SQL Server 记录数 | 本轮结束时 7 条，既有记录保留 |
| 重复上传 / 非图片 MIME / 非法路径 | 409 / 400 / 400，符合预期 |
| YOLO、Qwen、统一分析请求缺失图片 | 均 404 |
| 统一分析缺少 filename | 422 |
| start.sh | Git Bash 执行 bash -n，通过；脚本使用 LF 换行 |
| Git 与敏感内容 | diff --check、已知密钥值及凭据模式扫描、忽略规则均通过 |
| 第二阶段 | 工作区干净，未修改、暂存或提交第二阶段文件 |

## 今日修复与真实边界

连接拒绝时 8000 端口无监听。三个主文件语法与导入可通过；启动 Uvicorn 后实际接口和网页恢复。提交前复查发现此前进程已退出，本轮已重新启动并完成上述实测，不把启动终端退出等同于源码语法故障，也不宣称已配置 Windows 常驻服务。

实际发现旧 qwen_answer 的 VARCHAR(MAX) 会损坏部分 Unicode 字符。已采用 UnicodeText，并将现有表列迁移至 NVARCHAR(MAX)，没有删除已有分析记录；历史已丢失的字符不能由类型迁移自动恢复。新网页与 API 记录已通过全文比对。

今日早前 /analyze 曾两次出现 Qwen 上游错误并返回 502，未保存不完整结果；当时日志不足以追溯具体上游原因。已增加脱敏错误日志，之后复测和本轮完整回归成功。本轮不将外部 Qwen 服务宣称为永不失败，也没有新增重试等功能。

## Linux / Docker：未完成的运行验收

已准备 start.sh、systemd 模板、ODBC/数据库配置说明和可重复执行的 Unicode 迁移 SQL。现有 Windows 默认数据库连接保留；Linux 可通过 SQLSERVER_* 配置远端 SQL Server。

本机没有可用 WSL/Linux 运行环境或 Docker。Git Bash 仅用于 Bash 语法验证，不能代表 Linux 部署通过。

以下尚未执行：Linux 依赖安装与应用启动、Linux YOLO/Qwen 推理、Linux 至 SQL Server 连接、systemd 启停与重启恢复。需要目标 Linux 主机完成，步骤见 LINUX.md。

未取得明确要求 Docker 的考核原文，因此未新增 Dockerfile/Compose，也没有声称 Docker 验收通过。需要先核对原始条款，再决定是否属于必须交付内容。

本记录仅包含验收摘要，不包含 API Key、密码、上传图片、虚拟环境或运行缓存。完整响应与网页截图留在本地验收输出中，不加入本次 Git 提交。
