"""Deterministic rule checks that complement the LLM checker."""

import re

PLACEHOLDER = "【待人工填写】"
AMOUNT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:元|万元|万)")
HL_TAG_RE = re.compile(r"<hl\b([^>]*)>", re.IGNORECASE)
HL_BLOCK_RE = re.compile(r"<hl\b[^>]*>.*?</hl>", re.IGNORECASE | re.DOTALL)


def check_hard_rules(generated_sections: dict) -> list[dict]:
    findings: list[dict] = []

    for section_id, section in generated_sections.items():
        if section_id.startswith("_") or not isinstance(section, dict):
            continue
        content = str(section.get("content") or "")
        title = section.get("title") or section_id

        if not content.strip():
            findings.append({
                "type": "empty_section",
                "section_id": section_id,
                "point": f"段落「{title}」内容为空",
            })
            continue

        # Amounts outside <hl> and without a placeholder are untraceable.
        stripped = HL_BLOCK_RE.sub("", content)
        stripped = stripped.replace(PLACEHOLDER, "")
        for match in AMOUNT_RE.finditer(stripped):
            findings.append({
                "type": "untraced_amount",
                "section_id": section_id,
                "point": f"段落「{title}」存在未溯源金额：{match.group(0).strip()}",
            })

        for match in HL_TAG_RE.finditer(content):
            if "source=" not in match.group(1):
                findings.append({
                    "type": "missing_source",
                    "section_id": section_id,
                    "point": f"段落「{title}」存在缺少来源的溯源标记",
                })

        if len(findings) >= 50:
            break

    return findings[:50]
