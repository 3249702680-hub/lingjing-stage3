# JWT 身份认证

原始《三阶段思维导图.pdf》要求“登录校验、JWT 与接口身份识别”。本项目提供单个部署账户，不引入注册表或改写模型/数据库业务。

## 配置与登录

安装 requirements.txt 后，在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts/configure_auth.py
docker compose up -d --build
```

脚本交互读取用户名与至少 12 字符的密码（输入不回显），生成带盐 PBKDF2-SHA256 哈希和随机签名密钥，追加到已被 Git 与镜像排除的 `.env`。已有其他配置保留；已有认证配置则拒绝覆盖。原生 Windows 使用 `python scripts/configure_auth.py --run`，配置只留在该进程内存并启动 8000；这里不使用 reload 子进程。不要在命令参数、文档或 Git 中填写真实密码/密钥。

容器网页访问 `http://127.0.0.1:8080/login`，本机原生访问 `http://127.0.0.1:8000/login`。登录成功跳转 `/ui/`。配置变量为 `AUTH_USERNAME`、`AUTH_PASSWORD_HASH`、`JWT_SECRET`、`AUTH_COOKIE_SECURE`。密码哈希含 `$`，写 `.env` 时必须用单引号避免 Compose 插值；生成脚本已处理。真实 HTTPS 部署应设置 `AUTH_COOKIE_SECURE=true`，正确配置可信代理与证书；当前 Compose 仍只绑定回环地址。

## 接口与边界

| 接口 | 行为 |
| --- | --- |
| POST /auth/token | JSON username/password；成功返回 access_token、token_type=bearer、expires_in=900，同时设置 HttpOnly、SameSite=Strict Cookie |
| GET /auth/me | 验证身份后返回 username |
| POST /auth/logout | 清除当前浏览器 Cookie；已签发 Bearer Token 仍在到期前有效 |
| /upload、/predict/*、/analyze、/jobs*、整个 /ui 树 | 需要有效 Bearer Token 或登录 Cookie，包括 Gradio 上传、文件、队列与 WebSocket |
| /、/health、/docs、/openapi.json、/login | 公开，不运行 AI 分析 |

API 客户端使用 `Authorization: Bearer <登录返回的access_token>`；在 `/docs` 先调用 `/auth/token`，再点击 Authorize 输入 Token。网页 Cookie 写请求校验同源 Origin；浏览器自动携带，脚本调用优先使用 Bearer。未登录网页跳转 `/login`，API 缺失/非法/过期 Token 返回 401。缺少认证配置返回 503，不启用内置密码或默认密钥。

JWT 固定 HS256，验证签名、issuer、audience、subject、iat 和 exp，900 秒有效。密码只保存带随机盐的 600000 次 PBKDF2 摘要。当前不实现用户注册、多角色、刷新 Token 或服务端撤销列表，不宣称具备这些能力。

## 验收

`python -m unittest discover -s tests -p test_security.py -v` 覆盖正常/错误登录、缺失/篡改/过期 Token、错误签发方/受众/算法、缺配置、Cookie 跨站保护、HTTP/WebSocket 及 Swagger 标识。CI 在内存生成临时账户与密钥，登录后复测 Nginx、上传、YOLO、Gradio 和持久化，不使用真实 API Key 或数据库密码。

参考：[PyJWT 官方用法](https://pyjwt.readthedocs.io/en/stable/usage.html)。
