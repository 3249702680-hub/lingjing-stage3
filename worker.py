"""Linux RQ consumer: run with ``python worker.py``."""

import socket

from rq import Queue, Worker
from rq.serializers import JSONSerializer

from job_queue import JOB_TIMEOUT, QUEUE_NAME, redis_connection


def main():
    connection = redis_connection(worker=True)
    queue = Queue(
        QUEUE_NAME,
        connection=connection,
        serializer=JSONSerializer,
        default_timeout=JOB_TIMEOUT,
    )
    worker = Worker(
        [queue],
        connection=connection,
        serializer=JSONSerializer,
        name=f"analysis-{socket.gethostname()}",
        log_job_description=False,
    )
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
