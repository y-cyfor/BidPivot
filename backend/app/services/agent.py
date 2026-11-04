import json

from app.services.llm_client import chat_completion

AGENT_ROLES = ["商务报价", "技术方案", "实施计划", "售后服务", "资质合规"]


def _normalize_outline(data: dict) -> dict:
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, list):
        return {"sections": []}

    normalized = []
    raw_deps_list: list[list] = []
    used_ids: set[str] = set()
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("id") or f"s{index + 1}")
        if section_id in used_ids:
            section_id = f"s{index + 1}"
        used_ids.add(section_id)
        role = section.get("agent_role")
        normalized.append({
            "id": section_id,
            "title": section.get("title") or f"第 {index + 1} 章",
            "description": section.get("description") or "",
            "agent_role": role if role in AGENT_ROLES else "技术方案",
            "dependencies": [],
        })
        raw_deps_list.append(section.get("dependencies") or [])

    valid_ids = {section["id"] for section in normalized}
    for section, raw_deps in zip(normalized, raw_deps_list):
        section["dependencies"] = [dep for dep in raw_deps if dep in valid_ids and dep != section["id"]]

    return {"sections": normalized}


async def generate_outline(
    file_content: str,
    industry_tags: list[str],
    requirements: dict | None = None,
) -> dict:
    """Generate a structured outline including ids and dependencies."""
    requirements_text = ""
    if requirements:
        requirements_text = "\n已解析的招标要求：\n" + json.dumps(requirements, ensure_ascii=False)[:3000]

    messages = [
        {
            "role": "system",
            "content": (
                "你是一名专业的标书分析师。请分析招标文件内容，生成结构化的标书大纲。\n"
                "输出JSON：{\"sections\":[{\"id\":\"s1\",\"title\":\"...\",\"description\":\"...\","
                "\"agent_role\":\"商务报价|技术方案|实施计划|售后服务|资质合规\","
                "\"dependencies\":[\"前置段落id\"]}]}。\n"
                "id 必须唯一且稳定；dependencies 只能引用其他段落的 id；无依赖则为空数组。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"招标文件内容：\n{file_content[:8000]}\n"
                f"{requirements_text}\n\n"
                f"行业标签：{', '.join(industry_tags)}\n\n请生成标书大纲JSON。"
            ),
        },
    ]
    response = await chat_completion(messages)
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            outline = _normalize_outline(json.loads(response[start:end]))
            if outline["sections"]:
                return outline
    except json.JSONDecodeError:
        pass

    return {
        "sections": [{
            "id": "s1",
            "title": "自动生成大纲",
            "description": response[:500],
            "agent_role": "技术方案",
            "dependencies": [],
        }]
    }
