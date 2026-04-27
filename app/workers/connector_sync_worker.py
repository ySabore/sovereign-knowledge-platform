from __future__ import annotations

import logging
import time

from app.config import settings
from app.database import SessionLocal
from app.services.sync_orchestrator import claim_next_connector_sync_job, run_connector_sync_job

logger = logging.getLogger(__name__)


def run_forever() -> None:
    poll_seconds = float(settings.connector_sync_worker_poll_seconds)
    max_jobs = int(settings.connector_sync_worker_max_jobs_per_tick)
    logger.info(
        "connector sync worker started: poll_seconds=%s max_jobs_per_tick=%s",
        poll_seconds,
        max_jobs,
    )
    while True:
        processed = 0
        for _ in range(max_jobs):
            db = SessionLocal()
            try:
                job = claim_next_connector_sync_job(db)
                if job is None:
                    break
                logger.info("processing connector sync job: job_id=%s connector_id=%s", job.id, job.connector_id)
                run_connector_sync_job(db, job.id, claimed=True)
                processed += 1
            except Exception:
                logger.exception("connector sync worker tick failed")
            finally:
                db.close()
        if processed == 0:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()

