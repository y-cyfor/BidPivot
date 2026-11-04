from app.services.progress import publish_thinking


async def run_summary_agent(
    generated_sections: dict,
    outline: dict,
    task_id: str,
) -> dict:
    """Merge sections deterministically.

    The previous implementation asked the LLM to rewrite the whole document and
    truncated the input to 8000 characters, silently dropping chapters. A
    deterministic merge keeps every section and every citation intact.
    """
    await publish_thinking(task_id, "summary", "summary_agent", "开始汇总所有段落...")

    ordered_ids = [
        section.get("id")
        for section in outline.get("sections", [])
        if isinstance(section, dict) and section.get("id")
    ]
    ordered_ids += [
        sid for sid in generated_sections
        if not sid.startswith("_") and sid not in ordered_ids
    ]

    parts: list[str] = []
    for sid in ordered_ids:
        section = generated_sections.get(sid)
        if not isinstance(section, dict):
            continue
        title = section.get("title") or ""
        content = section.get("content") or ""
        parts.append(f"## {title}\n\n{content}".strip())

    merged_content = "\n\n".join(parts)
    result = dict(generated_sections)
    result["_merged"] = {
        "section_id": "_merged",
        "title": "完整文档",
        "content": merged_content,
        "agent_role": "summary",
        "status": "completed",
    }
    await publish_thinking(task_id, "summary", "summary_agent", "段落汇总完成")
    return result
