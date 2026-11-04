import json

from app.services.llm_client import chat_completion
from app.services.progress import publish_thinking


async def run_parse_agent(file_content: str, task_id: str) -> dict:
    """Extract structured requirements from bid document."""
    await publish_thinking(task_id, "parse", "parse_agent", "正在分析招标文件，提取核心要求...")

    messages = [
        {
            "role": "system",
            "content": (
                "你是一名专业的标书分析师。请从招标文件中提取结构化要求。"
                "输出JSON格式，包含以下字段：\n"
                "- requirements: 招标要求列表（每项含 id, content, category）\n"
                "- scoring_criteria: 评分标准\n"
                "- format_requirements: 格式要求\n"
                "- key_constraints: 关键约束条件"
            ),
        },
        {
            "role": "user",
            "content": f"招标文件内容：\n{file_content[:8000]}",
        },
    ]

    await publish_thinking(task_id, "parse", "parse_agent", "调用 LLM 分析招标要求...")
    response = await chat_completion(messages)

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass

    return {"requirements": [], "scoring_criteria": response[:500], "format_requirements": "", "key_constraints": ""}
