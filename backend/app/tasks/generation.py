import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.celery_app import celery_app
from app.database import async_session, engine
from app.models.generation_log import GenerationLog
from app.models.project import Project
from app.models.token_usage import TokenUsage
from app.services.usage import get_usage, start_usage
from app.services.generation_control import (
    GenerationCancelled,
    clear_generation_cancel,
    release_generation_lock,
)
from app.services.progress import (
    close_redis,
    publish_error,
    publish_generation_cancelled,
    publish_generation_complete,
    publish_generation_failed,
)


@celery_app.task(bind=True, name="app.tasks.run_generation")
def run_generation_task(self, project_id: str, task_id: str, file_content: str, outline: dict):
    """Celery task to run multi-agent generation."""

    async def _run():
        from app.services.graph import run_generation

        try:
            async with async_session() as db:
                result = await db.execute(select(Project).where(Project.id == project_id))
                project = result.scalar_one_or_none()
                if not project:
                    return

                log = GenerationLog(
                    project_id=project_id,
                    user_id=project.user_id,
                    task_id=task_id,
                    status="running",
                )
                db.add(log)

                project.status = "generating"
                await db.commit()

                try:
                    start_usage()
                    final_state = await run_generation(
                        project_id=project_id,
                        task_id=task_id,
                        file_content=file_content,
                        outline=outline,
                        user_id=str(project.user_id),
                        requirements=project.requirements_json or {},
                    )

                    generated = final_state.get("generated_sections", {})
                    report = final_state.get("check_report") or {}
                    failed_sections = list(final_state.get("error_sections") or [])
                    section_count = len([key for key in generated if not key.startswith("_")])

                    from app.services.document import sections_to_html

                    if section_count == 0 or len(failed_sections) >= section_count:
                        status = "failed"
                    elif failed_sections:
                        status = "partial"
                    else:
                        status = "completed"

                    project.full_document_json = generated
                    project.content_json = generated
                    project.content_html = sections_to_html(generated)
                    project.check_report = report
                    project.status = status
                    project.generation_task_id = None

                    log.status = status
                    log.end_time = datetime.now(timezone.utc)
                    log.final_score = report.get("score")
                    log.agents_used = list(set(
                        s.get("agent_role", "") for s in generated.values() if isinstance(s, dict)
                    ))
                    await db.commit()

                    # Publish only after the transaction is committed so clients
                    # that reload on the event see the final document.
                    if status == "failed":
                        await publish_generation_failed(task_id, "所有段落均生成失败，请查看日志")
                    else:
                        await publish_generation_complete(task_id, section_count, failed_sections)

                except GenerationCancelled:
                    project.status = "cancelled"
                    project.generation_task_id = None
                    log.status = "cancelled"
                    log.end_time = datetime.now(timezone.utc)
                    await db.commit()
                    await publish_generation_cancelled(task_id)

                except Exception as e:
                    project.status = "failed"
                    project.generation_task_id = None
                    log.status = "failed"
                    log.end_time = datetime.now(timezone.utc)
                    await db.commit()
                    await publish_error(task_id, "system", str(e))
                    await publish_generation_failed(task_id, str(e))

                try:
                    usage = get_usage()
                    if usage["total"] > 0:
                        db.add(TokenUsage(
                            user_id=project.user_id,
                            project_id=project.id,
                            session_id=task_id,
                            input_tokens=usage["input"],
                            output_tokens=usage["output"],
                            total_tokens=usage["total"],
                        ))
                        await db.commit()
                except Exception:
                    await db.rollback()
        finally:
            # Each Celery invocation runs in its own event loop. Pooled asyncpg
            # connections and the Redis client are bound to that loop, so they
            # must be released before asyncio.run() closes it.
            await clear_generation_cancel(task_id)
            await release_generation_lock(project_id)
            await engine.dispose()
            await close_redis()

    asyncio.run(_run())
