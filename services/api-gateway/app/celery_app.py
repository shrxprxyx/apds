from celery import Celery
from kombu import Queue

from app.core.config import settings

# ─── Celery App ─────────────────────────────────────────────────
# docker-compose.yml already launches four containers pointing at
# this exact module: `celery -A app.celery_app worker -Q <queue>`
# and `celery -A app.celery_app beat`. Nothing to change there —
# this file just needs to exist and define `celery_app`.
celery_app = Celery(
    "apds",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.analysis_tasks", "app.tasks.intel_tasks"],
)

# ─── Queues ──────────────────────────────────────────────────────
# Matches the three worker containers in docker-compose:
#   high_priority   -c 4  → real-time user-facing scans (extension, dashboard "scan now")
#   normal          -c 2  → bulk/batch scans, email plugin scans
#   background      -c 1  → nightly jobs (retraining, threat-intel refresh, once those exist)
celery_app.conf.task_queues = (
    Queue("high_priority"),
    Queue("normal"),
    Queue("background"),
)
celery_app.conf.task_default_queue = "normal"

# ─── General config ────────────────────────────────────────────
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # a stuck sub-service call shouldn't hang a worker forever
    task_time_limit=60,
    task_soft_time_limit=45,
)

# ─── Beat schedule ──────────────────────────────────────────────
# Empty for now — celery-beat container will just idle harmlessly.
# training-service (nightly retrain) and intel-service (15-min
# threat-feed refresh) will register their periodic tasks here
# once those services exist, per doc 8.2 and 6.4.
celery_app.conf.beat_schedule = {
    "refresh-threat-intel-feeds": {
        "task": "app.tasks.intel_tasks.trigger_intel_ingestion",
        "schedule": settings.INTEL_FEED_REFRESH_SECONDS,
        "options": {"queue": "background"},
    },
}