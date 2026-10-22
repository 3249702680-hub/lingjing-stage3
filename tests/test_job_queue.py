"""Queue access controls and redaction; live Redis/worker tests run in CI."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from rq.exceptions import NoSuchJobError
from rq.serializers import JSONSerializer

import job_queue
from security import require_user


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(job_queue.router)
        self.app.dependency_overrides[require_user] = lambda: "alice"
        self.client = TestClient(self.app)
        self.job_id = str(uuid4())
        self.fake_app = SimpleNamespace(
            _get_uploaded_image=Mock(),
            YoloPredictRequest=lambda **kw: SimpleNamespace(**kw),
            AnalyzeRequest=lambda **kw: SimpleNamespace(**kw),
            predict_yolo=Mock(return_value={"filename": "paper.jpg", "detections": []}),
            analyze=Mock(),
        )
        self.app_patch = patch.dict(sys.modules, {"app": self.fake_app})
        self.app_patch.start()
        self.addCleanup(self.app_patch.stop)
        self.addCleanup(self.client.close)

    def test_submission_checks_path_and_sets_owner_expiry(self):
        queue = Mock()
        queue.enqueue.return_value.id = self.job_id
        with patch.object(job_queue, "get_queue", return_value=queue):
            response = self.client.post("/jobs", json={"filename": "paper.jpg", "mode": "yolo"})
        self.assertEqual(response.status_code, 202)
        self.fake_app._get_uploaded_image.assert_called_once_with("paper.jpg")
        kwargs = queue.enqueue.call_args.kwargs
        self.assertEqual(kwargs["meta"], {"owner": "alice"})
        self.assertEqual(kwargs["result_ttl"], 3600)
        self.assertEqual(kwargs["failure_ttl"], 3600)
        self.assertEqual(queue.enqueue.call_args.args, (job_queue.run_analysis, "paper.jpg", "yolo"))

    def test_invalid_path_never_enqueues(self):
        self.fake_app._get_uploaded_image.side_effect = HTTPException(400, "Invalid filename")
        with patch.object(job_queue, "get_queue") as queue:
            response = self.client.post("/jobs", json={"filename": "../paper.jpg"})
        self.assertEqual(response.status_code, 400)
        queue.assert_not_called()

    def test_invalid_mode_is_rejected(self):
        with patch.object(job_queue, "get_queue") as queue:
            response = self.client.post("/jobs", json={"filename": "paper.jpg", "mode": "shell"})
        self.assertEqual(response.status_code, 422)
        queue.assert_not_called()

    def test_redis_failure_is_redacted(self):
        with patch.object(job_queue, "get_queue", side_effect=ConnectionError("password=secret")):
            response = self.client.post("/jobs", json={"filename": "paper.jpg"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_other_owner_cannot_read_result(self):
        job = Mock(id=self.job_id, meta={"owner": "bob"})
        with patch.object(job_queue.Job, "fetch", return_value=job):
            response = self.client.get(f"/jobs/{self.job_id}")
        self.assertEqual(response.status_code, 404)
        job.return_value.assert_not_called()

    def test_missing_or_expired_job_returns_404(self):
        with patch.object(job_queue.Job, "fetch", side_effect=NoSuchJobError):
            response = self.client.get(f"/jobs/{self.job_id}")
        self.assertEqual(response.status_code, 404)

    def test_rq_failure_does_not_expose_traceback(self):
        job = Mock(id=self.job_id, meta={"owner": "alice"}, exc_info="secret traceback")
        job.get_status.return_value = "failed"
        with patch.object(job_queue.Job, "fetch", return_value=job):
            response = self.client.get(f"/jobs/{self.job_id}")
        self.assertEqual(response.json()["status"], "failed")
        self.assertNotIn("secret", response.text)

    def test_http_business_failure_is_failed_not_success(self):
        self.fake_app.analyze.side_effect = HTTPException(503, "DASHSCOPE_API_KEY is not configured")
        payload = job_queue.run_analysis("paper.jpg", "analyze")
        job = Mock(id=self.job_id, meta={"owner": "alice"})
        job.get_status.return_value = "finished"
        job.return_value.return_value = payload
        with patch.object(job_queue.Job, "fetch", return_value=job):
            response = self.client.get(f"/jobs/{self.job_id}")
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["error"]["status_code"], 503)

    def test_worker_reuses_yolo_and_identifies_consumer(self):
        payload = job_queue.run_analysis("paper.jpg", "yolo")
        self.assertEqual(payload["status"], "finished")
        self.assertEqual(payload["result"]["filename"], "paper.jpg")
        self.assertTrue(payload["worker"]["hostname"])
        self.assertIsInstance(payload["worker"]["pid"], int)
        self.assertEqual(self.fake_app.predict_yolo.call_args.args[0].filename, "paper.jpg")

    def test_worker_exception_and_unknown_http_detail_are_redacted(self):
        for error in (RuntimeError("password=secret"), HTTPException(500, "password=secret")):
            self.fake_app.analyze.side_effect = error
            payload = job_queue.run_analysis("paper.jpg", "analyze")
            self.assertEqual(payload["status"], "failed")
            self.assertNotIn("secret", str(payload))

    def test_queue_uses_json_serialization(self):
        with patch.object(job_queue, "redis_connection"), patch.object(job_queue, "Queue") as queue:
            job_queue.get_queue()
        self.assertIs(queue.call_args.kwargs["serializer"], JSONSerializer)


if __name__ == "__main__":
    unittest.main()
