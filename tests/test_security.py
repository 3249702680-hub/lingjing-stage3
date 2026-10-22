"""Authentication regression tests use generated temporary credentials only."""
import os
import secrets
import time
import unittest
from unittest.mock import patch

import jwt
from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from security import (
    COOKIE_NAME, JWT_AUDIENCE, JWT_ISSUER, TOKEN_TTL_SECONDS,
    configure_auth, hash_password, require_user,
)


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(18)
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        self.secret = secrets.token_urlsafe(48)
        self.environment = patch.dict(os.environ, {
            "AUTH_USERNAME": "ci-user",
            "AUTH_PASSWORD_HASH": self.password_hash,
            "JWT_SECRET": self.secret,
            "AUTH_COOKIE_SECURE": "false",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        app = FastAPI()
        configure_auth(app)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.get("/ui/")
        def ui():
            return {"page": "test"}

        @app.post("/upload")
        def upload(request: Request):
            return {"username": require_user(request)}

        @app.get("/jobs/job-id")
        def job(request: Request):
            return {"username": require_user(request)}

        @app.websocket("/ui/ws")
        async def websocket(websocket: WebSocket):
            await websocket.accept()
            await websocket.send_text(websocket.scope["state"]["auth_user"])
            await websocket.close()

        self.app = app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def login(self, **overrides):
        body = {"username": "ci-user", "password": self.password, **overrides}
        return self.client.post("/auth/token", json=body)

    def token(self, **overrides):
        now = int(time.time())
        claims = {"sub": "ci-user", "iat": now, "exp": now + 900,
                  "iss": JWT_ISSUER, "aud": JWT_AUDIENCE, **overrides}
        return jwt.encode(claims, self.secret, algorithm="HS256")

    def test_valid_login_and_bearer_identity(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["expires_in"], TOKEN_TTL_SECONDS)
        self.assertEqual(body["token_type"], "bearer")
        self.assertEqual(response.headers["cache-control"], "no-store")
        identity = self.client.get("/auth/me", headers={"Authorization": "Bearer " + body["access_token"]})
        self.assertEqual(identity.json(), {"username": "ci-user"})
        cookie = response.headers["set-cookie"]
        for expected in ("HttpOnly", "SameSite=strict", "Max-Age=900"):
            self.assertIn(expected, cookie)

    def test_wrong_credentials_are_rejected(self):
        self.assertEqual(self.login(password="incorrect").status_code, 401)
        self.assertEqual(self.login(username="unknown").status_code, 401)

    def test_missing_settings_fail_closed(self):
        os.environ.pop("JWT_SECRET")
        self.assertEqual(self.login().status_code, 503)
        self.assertEqual(self.client.post("/upload").status_code, 503)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_short_secret_and_malformed_hash_fail_closed(self):
        os.environ["JWT_SECRET"] = "short"
        self.assertEqual(self.login().status_code, 503)
        os.environ["JWT_SECRET"] = self.secret
        os.environ["AUTH_PASSWORD_HASH"] = "not-a-password-hash"
        self.assertEqual(self.login().status_code, 503)

    def test_anonymous_api_and_gradio_subroutes_are_protected(self):
        for path in (
            "/upload", "/predict/yolo", "/predict/qwen", "/analyze", "/jobs",
            "/jobs/job-id", "/ui/gradio_api/upload", "/ui/gradio_api/stream/event",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 401)
        response = self.client.get("/ui/", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")

    def test_login_page_and_docs_remain_public(self):
        for path in ("/login", "/docs", "/openapi.json", "/health"):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_invalid_expired_and_wrong_subject_tokens(self):
        tokens = [
            "not-a-jwt", self.token(exp=int(time.time()) - 1),
            self.token(sub="different-user"), self.token(iat=int(time.time()) + 3600),
            self.token(iss="untrusted"), self.token(aud="untrusted"),
        ]
        for token in tokens:
            with self.subTest(token_case=tokens.index(token)):
                response = self.client.get("/auth/me", headers={"Authorization": "Bearer " + token})
                self.assertEqual(response.status_code, 401)
                self.assertNotIn(token, response.text)

    def test_signature_algorithm_and_required_claims(self):
        claims = {"sub": "ci-user", "iat": int(time.time()), "exp": int(time.time()) + 900,
                  "iss": JWT_ISSUER, "aud": JWT_AUDIENCE}
        tokens = [
            jwt.encode(claims, secrets.token_urlsafe(48), algorithm="HS256"),
            jwt.encode(claims, self.secret, algorithm="HS384"),
        ]
        for field in tuple(claims):
            incomplete = {key: value for key, value in claims.items() if key != field}
            tokens.append(jwt.encode(incomplete, self.secret, algorithm="HS256"))
        for token in tokens:
            self.assertEqual(self.client.post("/upload", headers={"Authorization": "Bearer " + token}).status_code, 401)

    def test_cookie_write_requires_same_origin(self):
        self.login()
        self.assertEqual(self.client.get("/ui/").status_code, 200)
        self.assertEqual(self.client.post("/upload").status_code, 403)
        self.assertEqual(self.client.post("/upload", headers={"Origin": "https://other.invalid"}).status_code, 403)
        response = self.client.post("/upload", headers={"Origin": "http://testserver"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "ci-user"})

    def test_bearer_write_does_not_require_cookies(self):
        response = self.client.post("/upload", headers={"Authorization": "Bearer " + self.token()})
        self.assertEqual(response.status_code, 200)

    def test_invalid_authorization_does_not_fall_back_to_valid_cookie(self):
        self.login()
        response = self.client.get("/auth/me", headers={"Authorization": "Basic bad"})
        self.assertEqual(response.status_code, 401)

    def test_cross_origin_login_is_rejected(self):
        response = self.client.post(
            "/auth/token", json={"username": "ci-user", "password": self.password},
            headers={"Origin": "https://other.invalid"},
        )
        self.assertEqual(response.status_code, 403)

    def test_logout_clears_cookie_and_blocks_cross_origin(self):
        self.login()
        self.assertEqual(self.client.post("/auth/logout", headers={"Origin": "https://other.invalid"}).status_code, 403)
        self.assertEqual(self.client.post("/auth/logout", headers={"Origin": "http://testserver"}).status_code, 204)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_secure_cookie_setting(self):
        os.environ["AUTH_COOKIE_SECURE"] = "true"
        self.assertIn("Secure", self.login().headers["set-cookie"])

    def test_websocket_requires_authentication(self):
        with self.assertRaises(WebSocketDisconnect) as caught:
            with self.client.websocket_connect("/ui/ws"):
                pass
        self.assertEqual(caught.exception.code, 1008)
        with self.client.websocket_connect("/ui/ws", headers={"Authorization": "Bearer " + self.token()}) as socket:
            self.assertEqual(socket.receive_text(), "ci-user")

    def test_cookie_websocket_origin_is_checked(self):
        self.login()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/ui/ws", headers={"Origin": "https://other.invalid"}):
                pass
        with self.client.websocket_connect("/ui/ws", headers={"Origin": "http://testserver"}) as socket:
            self.assertEqual(socket.receive_text(), "ci-user")

    def test_openapi_exposes_bearer_authorization(self):
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(schema["components"]["securitySchemes"]["BearerAuth"]["scheme"], "bearer")
        self.assertEqual(schema["paths"]["/upload"]["post"]["security"], [{"BearerAuth": []}])
        self.assertNotIn("security", schema["paths"]["/auth/token"]["post"])

    def test_password_hash_has_unique_salt(self):
        self.assertNotEqual(hash_password(self.password), self.password_hash)
        self.assertNotIn(self.password, self.password_hash)


if __name__ == "__main__":
    unittest.main()
