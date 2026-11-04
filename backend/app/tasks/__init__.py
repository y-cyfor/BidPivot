"""Celery task registry.

Import every task module here so ``celery -A app.celery_app worker``
registers the tasks before consuming messages.
"""

from app.tasks.generation import run_generation_task  # noqa: F401
