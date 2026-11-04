import json
import logging
import uuid

from app.services.llm_client import chat_completion
from app.services.progress import publish_content_token, publish_thinking, publish_tool_call

logger = logging.getLogger(__name__)

from app.services.agents.prompts import DEFAULT_AGENT_PROMPTS
from app.services.llm_client import chat_completion
from app.services.progress import publish_content_token, publish_thinking, publish_tool_call

logger = logging.getLogger(__name__)

AGENT_PROMPTS = DEFAULT_AGENT_PROMPTS
_prompt_cache: dict[str, str] = {}
MAX_KNOWLEDGE_CHARS = 6000


async def _get_system_prompt(role: str) -> str:
    """Load the prompt from the database, falling back to built-in defaults."""
    if role in _prompt_cache:
        return _prompt_cache[role]
    prompt = AGENT_PROMPTS.get(role, AGENT_PROMPTS["技术方案"])
    try:
        from sqlalchemy import select

        from app.database import async_session
        from app.models.agent_template import AgentTemplate

        async with async_session() as db:
            result = await db.execute(
                select(AgentTemplate).where(
                    AgentTemplate.role == role,
                    AgentTemplate.is_active.is_(True),
                )
            )
            template = result.scalar_one_or_none()
            if template and template.system_prompt.strip():
                prompt = template.system_prompt
    except Exception:
        logger.warning("Failed to load agent template for role %s", role, exc_info=True)
    _prompt_cache[role] = prompt
    return prompt


def clear_agent_prompt_cache() -> None:
    _prompt_cache.clear()


async def _retrieve_context(user_id: str, query: str, task_id: str, section_id: str) -> str:
    """Retrieve personal + global knowledge for the section.

    Returns formatted context, or an empty string when nothing relevant was
    found. Retrieval failures must not abort the section.
    """
    from app.database import async_session
    from app.services.knowledge import search_for_generation

    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        return ""

    try:
        async with async_session() as db:
            chunks = await search_for_generation(db, user_uuid, query, top_k=6)
    except Exception as exc:
        logger.warning("Knowledge retrieval failed for section %s: %s", section_id, exc)
        return ""

    if not chunks:
        return ""

    await publish_tool_call(
        task_id,
        section_id,
        "knowledge_search",
        {"query": query[:100]},
        f"命中 {len(chunks)} 条",
    )

    parts: list[str] = []
    total = 0
    for chunk in chunks:
        text = (chunk.get("chunk_text") or "").strip()
        if not text:
            continue
        source = chunk.get("document_title") or "知识库"
        piece = f"《{source}》\n{text[:800]}"
        if total + len(piece) > MAX_KNOWLEDGE_CHARS:
            break
        parts.append(piece)
        total += len(piece)
    return "\n\n---\n\n".join(parts)


async def run_writing_agent(
    agent_role: str,
    title: str,
    description: str,
    file_content: str,
    outline: dict,
    locked_vars: dict,
    requirements: dict,
    task_id: str,
    section_id: str,
    user_id: str,
) -> str:
    """Run a writing agent for a specific section."""
    system_prompt = await _get_system_prompt(agent_role)

    locked_context = ""
    if locked_vars:
        locked_items = [f"- {k}: {v['value']}（来源: {v['source']}）" for k, v in locked_vars.items()]
        locked_context = "\n已确定的共享变量：\n" + "\n".join(locked_items)

    outline_context = "\n".join([
        f"- [{s.get('id', '')}] {s.get('title', '')}: {s.get('description', '')}"
        for s in outline.get("sections", [])
    ])

    requirements_context = ""
    if requirements:
        requirements_context = (
            "\n招标要求摘要：\n"
            + json.dumps(requirements, ensure_ascii=False)[:1500]
        )

    await publish_thinking(task_id, section_id, f"{agent_role}Agent", f"开始撰写「{title}」，检索知识库...")
    knowledge_context = await _retrieve_context(
        user_id,
        f"{agent_role} {title} {description}"[:300],
        task_id,
        section_id,
    )
    if not knowledge_context:
        await publish_thinking(task_id, section_id, f"{agent_role}Agent", "未检索到相关知识库内容")

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"招标文件内容（摘要）：\n{file_content[:2000]}\n"
                f"{requirements_context}\n\n"
                f"标书大纲：\n{outline_context}\n\n"
                f"知识库检索结果（只能依据以下内容引用事实，未命中请标注【待人工填写】）：\n"
                f"{knowledge_context or '（未检索到相关内容）'}\n"
                f"{locked_context}\n\n"
                f"当前段落：{title}\n描述：{description}\n\n"
                f"请撰写该段落内容。直接输出正文，不要包含标题。"
            ),
        },
    ]

    await publish_thinking(task_id, section_id, f"{agent_role}Agent", "调用 LLM 生成内容...")
    content = await chat_completion(messages, max_tokens=2048)

    await publish_content_token(task_id, section_id, content)
    return content
