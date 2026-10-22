"""JWT login and request protection, independent of the AI model services."""
from dataclasses import dataclass
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.datastructures import Headers
from starlette.requests import HTTPConnection


COOKIE_NAME = "lingjing_access_token"
TOKEN_TTL_SECONDS = 900
JWT_ISSUER = "lingjing-stage3"
JWT_AUDIENCE = "lingjing-stage3-users"
HASH_ITERATIONS = 600_000


@dataclass(frozen=True)
class AuthSettings:
    username: str
    password_hash: str
    secret: str
    cookie_secure: bool


def hash_password(password: str) -> str:
    """Generate a salted password hash; never store a plaintext login password."""
    if not isinstance(password, str) or not password or len(password) > 1024:
        raise ValueError("Password must contain 1 to 1024 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, HASH_ITERATIONS)
    return "$".join(("pbkdf2_sha256", str(HASH_ITERATIONS), salt.hex(), digest.hex()))


def _parse_hash(value: str) -> tuple[int, bytes, bytes]:
    algorithm, rounds, salt_hex, digest_hex = value.split("$")
    iterations = int(rounds)
    salt, digest = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    if (
        algorithm != "pbkdf2_sha256"
        or not 100_000 <= iterations <= 2_000_000
        or len(salt) < 16
        or len(digest) != 32
    ):
        raise ValueError("Invalid password hash")
    return iterations, salt, digest


def _settings() -> AuthSettings:
    username = os.getenv("AUTH_USERNAME", "").strip()
    password_hash = os.getenv("AUTH_PASSWORD_HASH", "")
    secret = os.getenv("JWT_SECRET", "")
    secure = os.getenv("AUTH_COOKIE_SECURE", "false").lower()
    try:
        if not username or len(username) > 128 or len(secret.encode()) < 32:
            raise ValueError("Missing authentication settings")
        if secure not in {"true", "false"}:
            raise ValueError("Invalid cookie setting")
        _parse_hash(password_hash)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured; set AUTH_USERNAME, AUTH_PASSWORD_HASH and JWT_SECRET",
        ) from None
    return AuthSettings(username, password_hash, secret, secure == "true")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or expired authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authenticated_subject(scope) -> tuple[str, bool]:
    settings = _settings()
    connection = HTTPConnection(scope)
    authorization = connection.headers.get("authorization")
    cookie_auth = authorization is None
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _unauthorized()
        token = token.strip()
    else:
        token = connection.cookies.get(COOKIE_NAME, "")
    if not token:
        raise _unauthorized()
    try:
        claims = jwt.decode(
            token,
            settings.secret,
            algorithms=["HS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        if not hmac.compare_digest(claims["sub"].encode(), settings.username.encode()):
            raise _unauthorized()
    except jwt.InvalidTokenError:
        raise _unauthorized() from None
    return claims["sub"], cookie_auth


def require_user(request: Request) -> str:
    """Return the authenticated username for route dependencies."""
    username, _ = _authenticated_subject(request.scope)
    return username


def _protected_path(path: str) -> bool:
    return (
        path in {"/upload", "/upload/", "/analyze", "/analyze/", "/jobs", "/ui"}
        or path.startswith(("/predict/", "/jobs/", "/ui/"))
    )


def _origin_tuple(value: str):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid origin")
    return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)


def _check_origin(scope) -> None:
    headers = Headers(scope=scope)
    scheme = {"ws": "http", "wss": "https"}.get(scope["scheme"], scope["scheme"])
    try:
        if _origin_tuple(headers.get("origin", "")) != _origin_tuple(
            scheme + "://" + headers.get("host", "")
        ):
            raise ValueError("Cross-origin request")
    except ValueError:
        raise HTTPException(status_code=403, detail="Same-origin request required") from None


class AuthMiddleware:
    """Protect both HTTP and WebSocket requests, including every Gradio route."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or not _protected_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        try:
            username, cookie_auth = _authenticated_subject(scope)
            if cookie_auth and (
                scope["type"] == "websocket"
                or scope.get("method", "GET") not in {"GET", "HEAD", "OPTIONS"}
            ):
                _check_origin(scope)
            scope.setdefault("state", {})["auth_user"] = username
        except HTTPException as error:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1011 if error.status_code == 503 else 1008})
                return
            if (
                error.status_code == 401
                and scope.get("method") == "GET"
                and scope.get("path") in {"/ui", "/ui/"}
            ):
                response = RedirectResponse("/login", status_code=303)
            else:
                response = JSONResponse(
                    {"detail": error.detail}, status_code=error.status_code, headers=error.headers
                )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


LOGIN_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>灵境 AI 登录</title>
<style>body{font-family:system-ui;margin:10vh auto;padding:24px;max-width:420px;background:#f5f7fb}
form{background:white;padding:28px;border-radius:14px}label,input,button{display:block;width:100%;box-sizing:border-box}
label{margin:16px 0 6px}input,button{padding:12px;border:1px solid #cbd5e1;border-radius:6px}
button{margin-top:20px;background:#2563eb;color:white;cursor:pointer}#status{color:#b91c1c}</style></head>
<body><form id="login"><h1>灵境 AI 登录</h1><p>登录后使用图片分析与任务接口。</p>
<label for="username">用户名</label><input id="username" name="username" autocomplete="username" required maxlength="128">
<label for="password">密码</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="1024">
<button type="submit">登录</button><p id="status" role="status"></p></form>
<script>document.getElementById("login").addEventListener("submit",async(event)=>{
event.preventDefault();const status=document.getElementById("status");status.textContent="正在登录…";
try{const response=await fetch("/auth/token",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({username:document.getElementById("username").value,password:document.getElementById("password").value})});
if(response.ok){window.location.assign("/ui/");return;}
status.textContent=response.status===503?"管理员尚未配置登录，请检查服务配置。":"登录失败，请检查用户名和密码。";
}catch(error){status.textContent="服务连接失败，请稍后重试。";}});</script></body></html>"""


def configure_auth(app: FastAPI) -> None:
    """Install login routes and protection without changing AI endpoint functions."""
    if getattr(app.state, "lingjing_auth_configured", False):
        return
    app.state.lingjing_auth_configured = True

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page():
        return HTMLResponse(LOGIN_HTML, headers={"Cache-Control": "no-store"})

    @app.post("/auth/token")
    def login(body: LoginRequest, request: Request):
        if request.headers.get("origin"):
            _check_origin(request.scope)
        settings = _settings()
        rounds, salt, expected = _parse_hash(settings.password_hash)
        actual = hashlib.pbkdf2_hmac("sha256", body.password.encode(), salt, rounds)
        valid_password = hmac.compare_digest(actual, expected)
        valid_username = hmac.compare_digest(body.username.encode(), settings.username.encode())
        if not (valid_username and valid_password):
            raise _unauthorized()
        now = int(time.time())
        token = jwt.encode(
            {"sub": settings.username, "iat": now, "exp": now + TOKEN_TTL_SECONDS,
             "iss": JWT_ISSUER, "aud": JWT_AUDIENCE},
            settings.secret,
            algorithm="HS256",
        )
        response = JSONResponse(
            {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL_SECONDS},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
        response.set_cookie(
            COOKIE_NAME, token, max_age=TOKEN_TTL_SECONDS, httponly=True,
            secure=settings.cookie_secure, samesite="strict", path="/",
        )
        return response

    @app.get("/auth/me")
    def current_user(username: str = Depends(require_user)):
        return JSONResponse({"username": username}, headers={"Cache-Control": "no-store"})

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request):
        if request.cookies.get(COOKIE_NAME):
            _check_origin(request.scope)
        response = Response(status_code=204, headers={"Cache-Control": "no-store"})
        response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")
        return response

    app.add_middleware(AuthMiddleware)
    original_openapi = app.openapi

    def authenticated_openapi():
        schema = original_openapi()
        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes["BearerAuth"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        for path, operations in schema.get("paths", {}).items():
            if _protected_path(path) or path == "/auth/me":
                for method, operation in operations.items():
                    if method in {"get", "post", "put", "patch", "delete", "head", "options"}:
                        operation["security"] = [{"BearerAuth": []}]
        return schema

    app.openapi = authenticated_openapi
