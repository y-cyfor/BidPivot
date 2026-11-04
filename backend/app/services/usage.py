"""Per-task token accounting via a ContextVar."""

from contextvars import ContextVar

_usage: ContextVar[dict | None] = ContextVar("token_usage", default=None)


def start_usage() -> None:
    _usage.set({"input": 0, "output": 0, "total": 0})


def record_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
    usage = _usage.get()
    if usage is None:
        return
    usage["input"] += int(prompt_tokens or 0)
    usage["output"] += int(completion_tokens or 0)
    usage["total"] += int(total_tokens or 0)


def get_usage() -> dict:
    usage = _usage.get()
    return dict(usage) if usage else {"input": 0, "output": 0, "total": 0}
