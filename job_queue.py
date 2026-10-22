"""Authenticated job submission and result lookup using Redis and RQ."""

import os
import socket
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.serializers import JSONSerializer

from security import require_user


router = APIRouter(tags=["jobs"])
QUEUE_NAME = "analysis"
JOB_TIMEOUT = 360
RESULT_TTL = 3600
_SAFE_DETAILS = {
    "Invalid filename",
    "Invalid file path",
    "Uploaded image not found",
    "Uploaded file is not a readable image",
    "DASHSCOPE_API_KEY is not configured",
    "Qwen request timed out",
    "Qwen request failed; check the API key, quota, and network",
    "Analysis succeeded but saving the record failed",
}


class JobRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mode: Literal["yolo", "analyze"] = "analyze"


def redis_connection(*, worker: bool = False) -> Redis:
    # The worker's blocking dequeue must have a longer socket timeout than RQ's
    # default dequeue timeout. HTTP requests use a bounded, short timeout.
    return Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        socket_connect_timeout=5,
        socket_timeout=420 if worker else 5,
        health_check_interval=30,
    )


def get_queue() -> Queue:
    return Queue(
        QUEUE_NAME,
        connection=redis_connection(),
        serializer=JSONSerializer,
        default_timeout=JOB_TIMEOUT,
    )


def run_analysis(filename: str, mode: str) -> dict:
    """Executed by the separate RQ worker, using existing application functions."""
    worker = {"hostname": socket.gethostname(), "pid": os.getpid()}
    try:
        # Lazy import avoids app -> router -> app import cycles and performs
        # the existing filename/path checks again when the job is consumed.
        from app import AnalyzeRequest, YoloPredictRequest, analyze, predict_yolo

        if mode == "yolo":
            result = predict_yolo(YoloPredictRequest(filename=filename))
        elif mode == "analyze":
            result = analyze(AnalyzeRequest(filename=filename))
        else:
            raise HTTPException(status_code=400, detail="Unsupported analysis mode")
        return {"status": "finished", "result": result, "worker": worker}
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, str) else "Analysis failed"
        if detail not in _SAFE_DETAILS:
            detail = "Analysis failed"
        return {
            "status": "failed",
            "error": {"status_code": error.status_code, "detail": detail},
            "worker": worker,
        }
    except Exception:
        # Do not store/return exception text or tracebacks, which may contain
        # third-party responses, credentials, or database connection strings.
        return {
            "status": "failed",
            "error": {"status_code": 500, "detail": "Analysis failed"},
            "worker": worker,
        }


@router.post("/jobs", status_code=202)
def submit_job(request: JobRequest, owner: str = Depends(require_user)):
    from app import _get_uploaded_image

    _get_uploaded_image(request.filename)
    try:
        job = get_queue().enqueue(
            run_analysis,
            request.filename,
            request.mode,
            job_timeout=JOB_TIMEOUT,
            result_ttl=RESULT_TTL,
            ttl=RESULT_TTL,
            failure_ttl=RESULT_TTL,
            meta={"owner": owner},
            description="Garbage image analysis",
        )
    except RedisError:
        raise HTTPException(status_code=503, detail="Task queue is unavailable") from None
    return {"job_id": job.id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, owner: str = Depends(require_user)):
    try:
        UUID(job_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Job not found") from None

    try:
        job = Job.fetch(job_id, connection=redis_connection(), serializer=JSONSerializer)
        # Return the same response for nonexistent jobs and other users' jobs.
        if job.meta.get("owner") != owner:
            raise HTTPException(status_code=404, detail="Job not found")
        status = job.get_status(refresh=True)
        status = getattr(status, "value", status)
        if status == "finished":
            payload = job.return_value()
            if isinstance(payload, dict) and payload.get("status") in {"finished", "failed"}:
                return {"job_id": job.id, **payload}
            return {
                "job_id": job.id,
                "status": "failed",
                "error": {"status_code": 500, "detail": "Task result is unavailable"},
            }
        if status in {"failed", "stopped", "canceled"}:
            # Never return job.exc_info: an infrastructure failure can contain
            # a traceback or other information unsuitable for the client.
            return {
                "job_id": job.id,
                "status": "failed",
                "error": {"status_code": 500, "detail": "Task execution failed"},
            }
        return {"job_id": job.id, "status": status}
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except RedisError:
        raise HTTPException(status_code=503, detail="Task queue is unavailable") from None
