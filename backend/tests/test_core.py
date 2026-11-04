from datetime import timedelta

import pytest
from jose import JWTError

from app.api.v1.export import _content_disposition
from app.services.agent import _normalize_outline
from app.services.document import sections_to_html
from app.services.graph import _topological_sort
from app.services.knowledge import _split_text
from app.services.rules import check_hard_rules
from app.utils.security import create_access_token, create_refresh_token, decode_access_token


def test_content_disposition_is_latin1_safe():
    header = _content_disposition("我的标书.docx")
    header.encode("latin-1")  # must not raise
    assert "filename*=UTF-8''" in header
    assert header.startswith("attachment;")


def test_outline_normalization_ids_and_dependencies():
    outline = _normalize_outline({
        "sections": [
            {"title": "报价", "agent_role": "商务报价", "dependencies": ["s2"]},
            {"id": "s2", "title": "技术", "dependencies": ["missing", "s2"]},
        ]
    })
    assert [section["id"] for section in outline["sections"]] == ["s1", "s2"]
    assert outline["sections"][0]["dependencies"] == ["s2"]
    assert outline["sections"][1]["dependencies"] == []


def test_split_text_keeps_heading_boundaries():
    text = "# 第一章\n内容一\n\n## 第二章\n" + "长" * 900
    chunks = _split_text(text, chunk_size=200, overlap=20)
    assert len(chunks) >= 2
    assert chunks[0].startswith("# 第一章")


def test_hard_rules_flags_untraced_amount_and_source():
    findings = check_hard_rules({
        "s1": {"title": "报价", "content": "总价 12000 元，<hl>3000 元</hl>"}
    })
    types = {finding["type"] for finding in findings}
    assert "untraced_amount" in types
    assert "missing_source" in types


def test_hard_rules_accepts_traced_amount():
    findings = check_hard_rules({
        "s1": {"title": "报价", "content": '<hl source="价格表">12000 元</hl>'}
    })
    assert not any(finding["type"] == "untraced_amount" for finding in findings)
    assert not any(finding["type"] == "missing_source" for finding in findings)


def test_topological_sort_does_not_mutate_outline():
    sections = [
        {"id": "s1", "dependencies": ["s2"]},
        {"id": "s2", "dependencies": ["s1"]},
    ]
    _topological_sort(sections)
    assert sections[0]["dependencies"] == ["s2"]


def test_sections_to_html_renders_trace_marks():
    html = sections_to_html({
        "s1": {"title": "报价", "content": '<hl source="价格表">12000 元</hl>'}
    })
    assert '<mark class="trace-mark" data-source="价格表">12000 元</mark>' in html
    assert "<hl" not in html


def test_token_type_and_expiry():
    access = create_access_token("user-id")
    refresh = create_refresh_token("user-id")
    assert decode_access_token(access)["type"] == "access"
    assert decode_access_token(refresh)["type"] == "refresh"

    expired = create_access_token("user-id", expires_delta=timedelta(seconds=-5))
    with pytest.raises(JWTError):
        decode_access_token(expired)
