import json
import re

from app.services.llm_client import chat_completion, stream_chat_completion

BLOCK_RE = re.compile(r"<(p|h[1-4]|li)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
WHOLE_DOC_LIMIT = 12000


def _block_text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _select_blocks(current_html: str, instruction: str, selected_text: str | None):
    matches = list(BLOCK_RE.finditer(current_html))
    if not matches:
        return matches, set()

    terms = set(re.findall(r"[\u4e00-\u9fa5]{2,}|[A-Za-z0-9]+", instruction))
    scored: list[tuple[int, int]] = []
    for index, match in enumerate(matches):
        text = _block_text(match.group(0))
        score = sum(1 for term in terms if term in text)
        if selected_text and selected_text.strip() and selected_text.strip() in text:
            score += 10
        scored.append((score, index))

    chosen = {index for score, index in sorted(scored, reverse=True)[:4] if score > 0}
    if not chosen and scored:
        chosen = {scored[0][1]}

    expanded = set(chosen)
    for index in chosen:
        if index - 1 >= 0:
            expanded.add(index - 1)
        if index + 1 < len(matches):
            expanded.add(index + 1)
    return matches, expanded


def _extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _apply_replacements(current_html: str, matches, response: str) -> str:
    data = _extract_json(response)
    replacements = data.get("replacements") if data else None
    if not isinstance(replacements, list):
        raise ValueError("未解析到段落修改结果")

    applied = 0
    for item in sorted(replacements, key=lambda entry: int(entry.get("index", -1)), reverse=True):
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        new_html = item.get("html")
        if not isinstance(new_html, str) or not (0 <= index < len(matches)):
            continue
        match = matches[index]
        current_html = current_html[:match.start()] + new_html + current_html[match.end():]
        applied += 1

    if applied == 0:
        raise ValueError("未定位到需要修改的段落")
    return current_html


def _history_text(conversation_history: list) -> str:
    if not conversation_history:
        return ""
    return "".join(
        f"{message['role']}: {message['content']}\n"
        for message in conversation_history[-6:]
    )


async def stream_conversation_modification(
    instruction: str,
    current_html: str,
    selected_text: str | None,
    conversation_history: list,
):
    """Yield ``("token", text)`` chunks and a final ``("content", html)``.

    Short documents are rewritten as a whole with real streaming. Long
    documents are handled block-by-block so the model never has to return the
    entire document and the unmentioned chapters are preserved verbatim.
    """
    history_text = _history_text(conversation_history)
    context = f"用户选中的文字：\n{selected_text}\n\n" if selected_text else ""

    if len(current_html) <= WHOLE_DOC_LIMIT:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名标书编辑助手。用户会给你修改指令，你需要根据指令修改标书内容。\n"
                    "规则：\n"
                    "1. 只修改与指令相关的部分，保持其他内容不变\n"
                    "2. 如果涉及数字/价格修改，使用【待人工填写】标记\n"
                    "3. 保持文档格式和结构\n"
                    "4. 直接输出修改后的完整HTML内容，不要添加解释"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"对话历史：\n{history_text}\n\n"
                    f"{context}"
                    f"当前文档内容：\n{current_html}\n\n"
                    f"修改指令：{instruction}"
                ),
            },
        ]
        accumulated = ""
        async for token in stream_chat_completion(messages, max_tokens=8192):
            accumulated += token
            yield "token", token
        yield "content", accumulated
        return

    matches, selected_indexes = _select_blocks(current_html, instruction, selected_text)
    if not matches or not selected_indexes:
        raise ValueError("无法定位需要修改的段落，请选中文字后重试")

    blocks_context = "\n\n".join(
        f"[{index}] {matches[index].group(0)[:2000]}"
        for index in sorted(selected_indexes)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是一名标书编辑助手。只修改用户指定的段落，其他段落必须保持不变。\n"
                "输出严格的 JSON：{\"replacements\":[{\"index\":段落编号,\"html\":\"修改后的HTML片段\"}]}。\n"
                "禁止输出 JSON 以外的任何文字；涉及价格/数字时使用【待人工填写】。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"对话历史：\n{history_text}\n\n"
                f"{context}"
                f"候选段落：\n{blocks_context}\n\n"
                f"修改指令：{instruction}\n"
                "请只返回需要修改的段落。"
            ),
        },
    ]
    response = await chat_completion(messages, max_tokens=4096)
    yield "content", _apply_replacements(current_html, matches, response)
