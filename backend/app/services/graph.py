import asyncio
import logging
import re
import uuid
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

from app.services.generation_control import GenerationCancelled, is_generation_cancelled
from app.services.progress import (
    publish_batch_done,
    publish_error,
    publish_locked_var,
    publish_section_status,
    publish_thinking,
)

logger = logging.getLogger(__name__)

AGENT_ROLE_MAP = {
    "商务报价": "business_agent",
    "技术方案": "tech_agent",
    "实施计划": "implement_agent",
    "售后服务": "service_agent",
    "资质合规": "compliance_agent",
}


class SectionState(TypedDict):
    section_id: str
    title: str
    description: str
    agent_role: str
    content: str
    status: str


class BidState(TypedDict):
    project_id: str
    user_id: str
    task_id: str
    file_content: str
    outline: dict
    requirements: dict
    generated_sections: Annotated[dict, "section_id -> SectionState"]
    locked_vars: Annotated[dict, "var_name -> {value, source, timestamp}"]
    dependency_graph: Annotated[dict, "section_id -> [depends_on_ids]"]
    messages: Annotated[list, "event log"]
    check_report: dict
    current_batch: int
    error_sections: Annotated[list, "failed section ids"]


def _detect_cycles(sections: list[dict]) -> list[str] | None:
    """Detect circular dependencies. Returns cycle path or None."""
    dep_graph: dict[str, list[str]] = {}
    for s in sections:
        sid = s.get("id", str(uuid.uuid4()))
        dep_graph[sid] = s.get("dependencies", [])

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in dep_graph}
    parent = {}

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        for neighbor in dep_graph.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                # Found cycle, reconstruct path
                cycle = [neighbor, node]
                cur = node
                while cur != neighbor:
                    cur = parent.get(cur)
                    if cur is None:
                        break
                    cycle.append(cur)
                return list(reversed(cycle))
            if color[neighbor] == WHITE:
                parent[neighbor] = node
                result = dfs(neighbor)
                if result:
                    return result
        color[node] = BLACK
        return None

    for sid in dep_graph:
        if color[sid] == WHITE:
            result = dfs(sid)
            if result:
                return result
    return None


def _topological_sort(sections: list[dict]) -> list[list[str]]:
    """Sort sections into batches by dependency depth. Detects cycles."""
    ids = {s["id"] for s in sections}
    cycle = _detect_cycles(sections)
    cycle_edges: set[tuple[str, str]] = set()
    if cycle:
        logger.error("Circular dependency detected: %s", " -> ".join(cycle))
        cycle_edges = set(zip(cycle, cycle[1:]))
        logger.warning("Cycle broken in-memory; the stored outline is left untouched")

    dep_graph: dict[str, list[str]] = {}
    for s in sections:
        sid = s["id"]
        deps = [
            dep for dep in s.get("dependencies", [])
            if dep in ids and (sid, dep) not in cycle_edges
        ]
        dep_graph[sid] = deps

    batch_of: dict[str, int] = {}
    for _ in range(len(sections) + 1):
        changed = False
        for s in sections:
            sid = s["id"]
            if sid in batch_of:
                continue
            deps = dep_graph.get(sid, [])
            if not deps:
                if sid not in batch_of:
                    batch_of[sid] = 0
                    changed = True
            else:
                dep_batches = [batch_of.get(d) for d in deps if d in batch_of]
                if len(dep_batches) == len(deps):
                    batch_of[sid] = max(dep_batches) + 1
                    changed = True
        if not changed:
            break

    for s in sections:
        sid = s["id"]
        if sid not in batch_of:
            batch_of[sid] = 0

    max_batch = max(batch_of.values()) if batch_of else 0
    batches = []
    for b in range(max_batch + 1):
        batch = [sid for sid, level in batch_of.items() if level == b]
        if batch:
            batches.append(batch)
    return batches


async def _run_single_agent(
    state: BidState,
    section_id: str,
    section: dict,
    task_id: str,
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[str, dict, dict]:
    """Run a single writing agent for one section, with timeout and retries."""
    from app.services.agents.writer import run_writing_agent

    await publish_section_status(task_id, section_id, "writing")

    async def _call_writer() -> str:
        if semaphore is None:
            return await run_writing_agent(**kwargs)
        async with semaphore:
            return await run_writing_agent(**kwargs)

    kwargs = dict(
        agent_role=section["agent_role"],
        title=section["title"],
        description=section.get("description", ""),
        file_content=state["file_content"],
        outline=state["outline"],
        locked_vars=state["locked_vars"],
        requirements=state.get("requirements", {}),
        task_id=task_id,
        section_id=section_id,
        user_id=state["user_id"],
    )

    content: str | None = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            content = await asyncio.wait_for(_call_writer(), timeout=180)
            break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_error = exc
            logger.warning("Section %s attempt %s failed: %s", section_id, attempt + 1, exc)
            if attempt < 2:
                await publish_thinking(
                    task_id, section_id, f"{section['agent_role']}Agent",
                    f"生成失败，正在第 {attempt + 2} 次重试...",
                )
                await asyncio.sleep(2 ** attempt)

    if content is None:
        error = last_error or RuntimeError("写作 Agent 未返回内容")
        await publish_error(task_id, section_id, str(error))
        await publish_section_status(task_id, section_id, "failed")
        result_section = {
            "section_id": section_id,
            "title": section["title"],
            "description": section.get("description", ""),
            "agent_role": section["agent_role"],
            "content": f"【生成失败：{str(error)}，请人工填写】",
            "status": "failed",
        }
        return section_id, result_section, state.get("locked_vars", {})

    locked_vars = dict(state.get("locked_vars", {}))
    if section["agent_role"] == "商务报价":
        # Only lock an amount that is explicitly traced to a source document.
        sourced_price = re.search(
            r'<hl\b[^>]*source="([^"]+)"[^>]*>\s*([\d,]+\.?\d*\s*(?:万元|元|万))',
            content,
        )
        if sourced_price:
            source, value = sourced_price.group(1), sourced_price.group(2).strip()
            locked_vars["total_price"] = {"value": value, "source": source}
            await publish_locked_var(task_id, "total_price", value, source)

    await publish_section_status(task_id, section_id, "completed")
    result_section = {
        "section_id": section_id,
        "title": section["title"],
        "description": section.get("description", ""),
        "agent_role": section["agent_role"],
        "content": content,
        "status": "completed",
    }
    return section_id, result_section, locked_vars


def _build_graph() -> StateGraph:
    """Build the LangGraph StateGraph for multi-agent bid generation."""

    async def parse_node(state: BidState) -> dict:
        from app.services.agents.parser import run_parse_agent
        task_id = state["task_id"]
        if await is_generation_cancelled(task_id):
            raise GenerationCancelled()
        if state.get("requirements"):
            await publish_section_status(task_id, "parse", "completed")
            return {}
        await publish_section_status(task_id, "parse", "writing")
        requirements = await run_parse_agent(state["file_content"], task_id)
        await publish_section_status(task_id, "parse", "completed")
        return {"requirements": requirements}

    async def writing_batch_node(state: BidState) -> dict:
        task_id = state["task_id"]
        if await is_generation_cancelled(task_id):
            raise GenerationCancelled()
        outline = state["outline"]
        sections = outline.get("sections", [])
        batches = _topological_sort(sections)
        current_batch = state.get("current_batch", 0)

        if current_batch >= len(batches):
            return {}

        batch_section_ids = batches[current_batch]
        batch_sections = {s["id"]: s for s in sections if s["id"] in batch_section_ids}

        semaphore = asyncio.Semaphore(5)
        tasks = [
            _run_single_agent(state, sid, batch_sections[sid], task_id, semaphore)
            for sid in batch_section_ids
            if sid in batch_sections
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        generated = dict(state.get("generated_sections", {}))
        locked_vars = dict(state.get("locked_vars", {}))
        error_sections = list(state.get("error_sections", []))
        completed_ids = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                sid = batch_section_ids[i] if i < len(batch_section_ids) else "unknown"
                logger.error(f"Agent for section {sid} failed with exception: {result}", exc_info=result)
                await publish_error(task_id, sid, str(result))
                continue
            sid, section_data, new_locked = result
            generated[sid] = section_data
            locked_vars.update(new_locked)
            if section_data["status"] == "failed":
                error_sections.append(sid)
            else:
                completed_ids.append(sid)

        await publish_batch_done(task_id, current_batch, completed_ids)

        return {
            "generated_sections": generated,
            "locked_vars": locked_vars,
            "error_sections": error_sections,
            "current_batch": current_batch + 1,
        }

    async def should_continue_batch(state: BidState) -> str:
        outline = state["outline"]
        sections = outline.get("sections", [])
        batches = _topological_sort(sections)
        current_batch = state.get("current_batch", 0)
        if current_batch < len(batches):
            return "writing_batch"
        return "summary"

    async def summary_node(state: BidState) -> dict:
        from app.services.agents.summary import run_summary_agent
        task_id = state["task_id"]
        if await is_generation_cancelled(task_id):
            raise GenerationCancelled()
        await publish_section_status(task_id, "summary", "writing")
        merged = await run_summary_agent(
            generated_sections=state["generated_sections"],
            outline=state["outline"],
            task_id=task_id,
        )
        await publish_section_status(task_id, "summary", "completed")
        return {"generated_sections": merged}

    async def check_node(state: BidState) -> dict:
        from app.services.agents.checker import run_check_agent
        from app.services.rules import check_hard_rules
        task_id = state["task_id"]
        if await is_generation_cancelled(task_id):
            raise GenerationCancelled()
        await publish_section_status(task_id, "check", "writing")
        report = await run_check_agent(
            requirements=state.get("requirements", {}),
            generated_sections=state["generated_sections"],
            task_id=task_id,
        )
        rule_findings = check_hard_rules(state["generated_sections"])
        report["rule_findings"] = rule_findings
        if rule_findings:
            report.setdefault("failed", []).extend(rule_findings)
            if isinstance(report.get("score"), int):
                report["score"] = max(0, report["score"] - min(20, len(rule_findings) * 2))
        await publish_section_status(task_id, "check", "completed")
        messages = list(state.get("messages", []))
        messages.append({"type": "check_report", "content": report})
        return {"messages": messages, "check_report": report}

    graph = StateGraph(BidState)

    graph.add_node("parse", parse_node)
    graph.add_node("writing_batch", writing_batch_node)
    graph.add_node("summary", summary_node)
    graph.add_node("check", check_node)

    graph.set_entry_point("parse")
    graph.add_edge("parse", "writing_batch")
    graph.add_conditional_edges("writing_batch", should_continue_batch, {
        "writing_batch": "writing_batch",
        "summary": "summary",
    })
    graph.add_edge("summary", "check")
    graph.add_edge("check", END)

    return graph.compile()


async def run_generation(
    project_id: str,
    task_id: str,
    file_content: str,
    outline: dict,
    user_id: str,
    requirements: dict | None = None,
) -> dict:
    """Run the full multi-agent generation pipeline."""
    graph = _build_graph()

    raw_sections = outline.get("sections", [])
    sections = []
    for index, section in enumerate(raw_sections):
        if not isinstance(section, dict):
            continue
        normalized = dict(section)
        normalized.setdefault("id", f"s{index + 1}")
        sections.append(normalized)
    outline = {**outline, "sections": sections}

    dep_graph = {}
    for s in sections:
        dep_graph[s["id"]] = s.get("dependencies", [])

    initial_state: BidState = {
        "project_id": project_id,
        "user_id": user_id,
        "task_id": task_id,
        "file_content": file_content,
        "outline": outline,
        "requirements": requirements or {},
        "generated_sections": {},
        "locked_vars": {},
        "dependency_graph": dep_graph,
        "messages": [],
        "check_report": {},
        "current_batch": 0,
        "error_sections": [],
    }

    final_state = await graph.ainvoke(initial_state)
    return final_state
