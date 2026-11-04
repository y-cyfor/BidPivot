import json
import logging

from app.services.llm_client import chat_completion
from app.services.progress import publish_thinking

logger = logging.getLogger(__name__)


def _parse_report(response: str) -> dict:
    start = response.find("{")
    end = response.rfind("}") + 1
    if start == -1 or end <= start:
        return {
            "score": None,
            "passed": [],
            "failed": [],
            "missing": [],
            "summary": response[:500],
            "raw": response,
            "parse_error": "LLM 返回格式非标准 JSON",
        }

    try:
        data = json.loads(response[start:end])
    except json.JSONDecodeError:
        return {
            "score": None,
            "passed": [],
            "failed": [],
            "missing": [],
            "summary": response[:500],
            "raw": response,
            "parse_error": "JSON 解析失败",
        }

    score = data.get("score")
    try:
        score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        score = None

    return {
        "score": score,
        "passed": data.get("passed") or [],
        "failed": data.get("failed") or [],
        "missing": data.get("missing") or [],
        "summary": data.get("summary") or "",
        "raw": response,
    }


async def run_check_agent(
    requirements: dict,
    generated_sections: dict,
    task_id: str,
) -> dict:
    """Check generated content against requirements and return a structured report."""
    await publish_thinking(task_id, "check", "check_agent", "开始合规性检查...")

    sections_text = ""
    for sid, section in generated_sections.items():
        if sid.startswith("_"):
            continue
        sections_text += f"\n\n[{sid}] {section.get('title', '')}:\n{section.get('content', '')[:1000]}"

    messages = [
        {
            "role": "system",
            "content": (
                "你是一名标书合规检查专家。请逐条核对招标要求与生成内容的符合性。\n"
                "输出格式：\n"
                "1. 符合项列表\n"
                "2. 不符合项列表（含具体问题和建议修改）\n"
                "3. 缺失项列表（未覆盖的招标要求）\n"
                "4. 总体评分（0-100）\n"
                "输出JSON格式：{passed: [...], failed: [...], missing: [...], score: int, summary: str}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"招标要求：\n{json.dumps(requirements, ensure_ascii=False)[:3000]}\n\n"
                f"生成内容：\n{sections_text[:5000]}"
            ),
        },
    ]

    await publish_thinking(task_id, "check", "check_agent", "调用 LLM 进行合规性检查...")
    response = await chat_completion(messages)
    report = _parse_report(response)
    if report.get("parse_error"):
        logger.warning("Check report JSON parse failed for task %s", task_id)
    return report
