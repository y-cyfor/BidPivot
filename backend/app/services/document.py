"""Helpers to turn generated sections into editor-ready HTML."""

import html
import re

_HL_RE = re.compile(r"<hl\b([^>]*)>(.*?)</hl>", re.IGNORECASE | re.DOTALL)
_SOURCE_RE = re.compile(r"""source\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(text: str) -> str:
    return html.escape(_TAG_RE.sub("", text))


def _render_inline(text: str) -> str:
    """Convert ``<hl source="...">value</hl>`` into editor trace marks.

    Everything outside a trace block is escaped so LLM output cannot inject
    HTML into the editor.
    """
    parts: list[str] = []
    position = 0
    for match in _HL_RE.finditer(text):
        parts.append(html.escape(text[position:match.start()]))
        source_match = _SOURCE_RE.search(match.group(1))
        source = source_match.group(1) if source_match else ""
        inner = html.escape(_TAG_RE.sub("", match.group(2)))
        parts.append(
            f'<mark class="trace-mark" data-source="{html.escape(source, quote=True)}">{inner}</mark>'
        )
        position = match.end()
    parts.append(html.escape(text[position:]))
    return "".join(parts)


def sections_to_html(generated_sections: dict) -> str:
    """Deterministically render generated sections.

    Using section content (instead of the LLM-rewritten ``_merged`` entry)
    keeps every paragraph traceable back to its section.
    """
    parts: list[str] = []
    for key, section in generated_sections.items():
        if key.startswith("_") or not isinstance(section, dict):
            continue

        title = section.get("title") or ""
        if title:
            parts.append(f"<h2>{_clean_text(str(title))}</h2>")

        content = section.get("content") or ""
        for paragraph in str(content).split("\n"):
            text = paragraph.strip()
            if text:
                parts.append(f"<p>{_render_inline(text)}</p>")

    return "\n".join(parts)
