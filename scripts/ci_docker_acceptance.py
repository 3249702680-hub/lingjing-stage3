"""Accept an already-built Compose image; no real Qwen/SQL credentials are used."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--expected-class", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = os.environ.get("COMPOSE_PROJECT_NAME", "ci")
    env = dict(os.environ)
    env.update(DASHSCOPE_API_KEY="", SQLSERVER_AUTH="sql", SQLSERVER_HOST="not-configured",
               SQLSERVER_USERNAME="", SQLSERVER_PASSWORD="", SQLSERVER_PORT="1433")
    compose = ["docker", "compose", "-p", project, "-f", "docker-compose.yml"]
    evidence = {"ok": False, "project": project, "commit": os.environ.get("GITHUB_SHA"), "checks": [],
                "not_verified": ["Real Qwen upstream inference", "Real SQL Server connection/writes",
                                 "Complete /analyze persistence and browser interaction"]}
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def command(arguments, timeout=120):
        result = subprocess.run(arguments, env=env, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f"Docker command exited {result.returncode}: {result.stderr[-6000:]}")
        return result.stdout.strip()

    def check(name, passed, **details):
        evidence["checks"].append({"name": name, "ok": bool(passed), **details})
        if not passed:
            raise AssertionError(name)

    def request(path, payload=None, content_type="application/json", timeout=120):
        headers = {"Content-Type": content_type} if payload is not None else {}
        req = urllib.request.Request(args.base_url.rstrip("/") + path, data=payload, headers=headers)
        try:
            with http.open(req, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def ready():
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                status, body = request("/health", timeout=3)
                if status == 200 and json.loads(body) == {"status": "ok"}:
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError("HTTP /health did not become available")

    def container():
        cid = command(compose + ["ps", "-q", "app"])
        if not re.fullmatch(r"[0-9a-f]{12,64}", cid):
            raise AssertionError("Expected exactly one running app container")
        mounts = json.loads(command(["docker", "inspect", "--format", "{{json .Mounts}}", cid]))
        upload = next((m for m in mounts if m["Destination"] == "/app/uploads"), {})
        check("uploads_is_named_volume", upload.get("Type") == "volume" and bool(upload.get("Name")), mount=upload)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            state = command(["docker", "inspect", "--format",
                             "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", cid])
            if state == "running|healthy":
                return cid, upload["Name"]
            if state.split("|")[0] != "running":
                break
            time.sleep(2)
        raise AssertionError("Docker HEALTHCHECK did not report running|healthy: " + state)

    def predict(name, payload):
        status, raw = request("/predict/yolo", payload)
        result = json.loads(raw)
        detections = result.get("detections") if isinstance(result, dict) else None
        valid = status == 200 and isinstance(detections, list) and bool(detections)
        numeric = lambda n: isinstance(n, (float, int)) and not isinstance(n, bool) and math.isfinite(n)
        for detection in detections if valid else []:
            box = detection.get("bbox", []) if isinstance(detection, dict) else []
            confidence = detection.get("confidence") if isinstance(detection, dict) else None
            valid = valid and isinstance(detection.get("class_name"), str) and bool(detection["class_name"])
            valid = valid and numeric(confidence) and 0 <= confidence <= 1
            valid = valid and isinstance(box, list) and len(box) == 4 and all(numeric(n) for n in box)
            valid = valid and 0 <= box[0] < box[2] and 0 <= box[1] < box[3]
        valid = valid and any(d["class_name"] == args.expected_class and d["confidence"] >= 0.25 for d in detections)
        check(name, valid, status=status, result=result)

    try:
        check("compose_project_name", bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project)))
        fixture = args.image.read_bytes()
        check("real_jpeg_fixture", fixture.startswith(b"\xff\xd8\xff") and fixture.endswith(b"\xff\xd9"))
        expected_hash = hashlib.sha256(fixture).hexdigest()
        evidence["fixture"] = {"name": args.image.name, "sha256": expected_hash, "expected_class": args.expected_class}
        inventory_code = ("from pathlib import Path; import json,os; "
                          "assert not os.getenv('DASHSCOPE_API_KEY'); assert not os.getenv('SQLSERVER_PASSWORD'); "
                          "print(json.dumps(sorted(str(p.relative_to('/app')) for p in Path('/app').rglob('*') if p.is_file())))")
        files = json.loads(command(["docker", "run", "--rm", "--entrypoint", "python", "lingjing-stage3:day4", "-c", inventory_code]))
        allowed = {"app.py", "web_ui.py", "database.py", "requirements.txt", "services/__init__.py",
                   "services/yolo_service.py", "services/qwen_service.py", "weights/garbage_detect.pt"}
        check("image_contains_only_allowed_project_files", set(files) == allowed, files=files)
        command(compose + ["up", "-d", "--no-build", "nginx"], timeout=180)
        ready()
        original_id, volume = container()
        ports = json.loads(command(["docker", "inspect", "--format", "{{json .HostConfig.PortBindings}}", original_id]))
        check("app_port_not_published", not ports, port_bindings=ports)
        command(compose + ["exec", "-T", "nginx", "nginx", "-t"])
        check("nginx_configuration", True)
        with http.open(args.base_url + "/health", timeout=10) as response:
            check("http_reaches_nginx", "nginx" in response.headers.get("Server", "").lower(), server=response.headers.get("Server"))
        nginx_id = command(compose + ["ps", "-q", "nginx"])
        for path in ("/health", "/docs", "/ui/"):
            status, body = request(path)
            check("http_" + path, status == 200, status=status, response_bytes=len(body))
        probe = ("import os,json,cv2,pyodbc,torch,torchvision; "
                 "assert not os.getenv('DASHSCOPE_API_KEY'); assert not os.getenv('SQLSERVER_USERNAME'); "
                 "assert not os.getenv('SQLSERVER_PASSWORD'); "
                 "print(json.dumps(dict(uid=os.getuid(),torch=str(torch.__version__),torchvision=str(torchvision.__version__),"
                 "cuda=torch.version.cuda,opencv=cv2.__version__,drivers=pyodbc.drivers())))")
        runtime = json.loads(command(compose + ["exec", "-T", "app", "python", "-c", probe]))
        check("nonroot_cpu_torch_odbc", runtime["uid"] != 0 and runtime["cuda"] is None
              and runtime["torch"] == "2.14.1+cpu" and runtime["torchvision"] == "0.29.1+cpu"
              and "ODBC Driver 18 for SQL Server" in runtime["drivers"], runtime=runtime)
        filename = "ci_paper_" + uuid.uuid4().hex + ".jpg"
        boundary = "CiDockerAcceptance" + uuid.uuid4().hex
        upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                  'Content-Type: image/jpeg\r\n\r\n').encode() + fixture + f"\r\n--{boundary}--\r\n".encode()
        status, body = request("/upload", upload, "multipart/form-data; boundary=" + boundary)
        check("upload", status == 200 and json.loads(body).get("filename") == filename, status=status, filename=filename)
        payload = json.dumps({"filename": filename}).encode()
        predict("yolo_before_recreate", payload)
        for route in ("/predict/qwen", "/analyze"):
            status, body = request(route, payload)
            response = json.loads(body)
            check(route + "_missing_key_guard", status == 503 and "DASHSCOPE_API_KEY" in response.get("detail", ""),
                  status=status, response=response, real_qwen_verified=False)
        ui_probe = ("from gradio_client import Client,handle_file; import json,sys; "
                    "client=Client('http://nginx/ui/',verbose=False); "
                    "result=client.predict(handle_file('/app/uploads/'+sys.argv[1]),api_name='/analyze_upload'); "
                    "assert result[0] and result[1]; "
                    "assert any(d['class_name']=='paper' for d in result[2]['detections']); "
                    "assert 'API Key' in result[3]; "
                    "print(json.dumps(dict(original_image=bool(result[0]),annotated_image=bool(result[1]),"
                    "detections=result[2],qwen_guard=result[3]),ensure_ascii=False))")
        ui_output = command(compose + ["exec", "-T", "app", "python", "-c", ui_probe, filename], timeout=120)
        ui_result = json.loads(ui_output.splitlines()[-1])
        check("gradio_upload_and_streaming_via_nginx", True, result=ui_result, real_qwen_verified=False)
        guard = ("from database import engine; from sqlalchemy.exc import SQLAlchemyError\n"
                 "try:\n engine.connect()\nexcept SQLAlchemyError as error:\n"
                 " assert 'SQLSERVER_USERNAME' in str(error); print('Missing SQL credentials rejected before connecting')\n"
                 "else:\n raise AssertionError('Unexpected database connection')")
        command(compose + ["exec", "-T", "app", "python", "-c", guard])
        check("database_missing_credentials_guard", True, real_database_verified=False)
        command(compose + ["up", "-d", "--force-recreate", "--no-build", "app"], timeout=180)
        ready()
        recreated_id, recreated_volume = container()
        check("nginx_survives_app_recreation", nginx_id == command(compose + ["ps", "-q", "nginx"]))
        check("recreated_container_same_volume", original_id != recreated_id and volume == recreated_volume,
              old_container=original_id, new_container=recreated_id, volume=volume)
        hash_code = "from pathlib import Path; import hashlib,sys; print(hashlib.sha256((Path('/app/uploads')/sys.argv[1]).read_bytes()).hexdigest())"
        actual_hash = command(compose + ["exec", "-T", "app", "python", "-c", hash_code, filename])
        check("uploaded_bytes_survive_recreate", actual_hash == expected_hash, sha256=actual_hash)
        predict("yolo_after_recreate", payload)
        evidence["image_id"] = command(["docker", "inspect", "--format", "{{.Image}}", recreated_id])
        evidence["ok"] = True
    except Exception as error:
        evidence["error"] = type(error).__name__ + ": " + str(error)
    finally:
        try:
            evidence["container_logs"] = command(compose + ["logs", "--no-color", "--tail", "200", "app", "nginx"])
        except Exception as error:
            evidence["log_collection_error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": evidence["ok"], "evidence": str(args.output)}))
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
