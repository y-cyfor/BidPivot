import asyncio
import json
import logging
import time

import httpx
from sqlalchemy import select

from app.database import async_session
from app.models.model_config import ModelConfig
from app.services.usage import record_usage
from app.utils.crypto import decrypt_api_key

logger = logging.getLogger(__name__)

# Cache for active LLM config
_llm_config_cache: dict | None = None
_llm_config_cached_at: float = 0.0
LLM_CONFIG_TTL_SECONDS = 60


def _resolve_api_key(stored: str | None) -> str:
    """Decrypt the stored key, tolerating legacy plaintext values."""
    if not stored:
        return ""
    try:
        return decrypt_api_key(stored)
    except Exception:
        logger.warning("Stored API key is not decryptable; treating it as plaintext")
        return stored


async def _get_active_llm_config() -> dict:
    """Get active LLM config from database. Returns dict with api_base, api_key, model_name, parameters."""
    global _llm_config_cache, _llm_config_cached_at
    if _llm_config_cache is not None and time.time() - _llm_config_cached_at < LLM_CONFIG_TTL_SECONDS:
        return _llm_config_cache

    async with async_session() as db:
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.type == "llm", ModelConfig.is_active == True)
        )
        config = result.scalar_one_or_none()

    if not config:
        raise RuntimeError(
            "未配置 LLM 模型。请在系统设置 → 模型配置中添加 LLM 配置。"
        )

    _llm_config_cache = {
        "api_base": config.api_base.rstrip("/"),
        "api_key": _resolve_api_key(config.api_key_encrypted),
        "model_name": config.model_name,
        "parameters": config.parameters or {},
    }
    _llm_config_cached_at = time.time()
    return _llm_config_cache


def clear_llm_config_cache():
    """Clear the cached config (call after updating config in admin)."""
    global _llm_config_cache, _llm_config_cached_at
    _llm_config_cache = None
    _llm_config_cached_at = 0.0


def _build_headers(api_key: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def chat_completion(messages: list[dict], model: str = "", temperature: float = 0.3, max_tokens: int = 4096) -> str:
    """Call OpenAI-compatible API using config from database."""
    config = await _get_active_llm_config()
    use_model = model or config["model_name"]
    use_temp = config["parameters"].get("temperature", temperature)
    use_max_tokens = config["parameters"].get("max_tokens", max_tokens)
    use_top_p = config["parameters"].get("top_p", 1.0)

    async with httpx.AsyncClient(timeout=120.0) as client:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await client.post(
                    f"{config['api_base']}/chat/completions",
                    json={
                        "model": use_model,
                        "messages": messages,
                        "temperature": use_temp,
                        "max_tokens": use_max_tokens,
                        "top_p": use_top_p,
                    },
                    headers=_build_headers(config["api_key"]),
                )
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"LLM server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
                usage = data.get("usage") or {}
                record_usage(
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                )
                return data["choices"][0]["message"]["content"]
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise last_error or RuntimeError("LLM 调用失败")


async def stream_chat_completion(
    messages: list[dict],
    model: str = "",
    temperature: float = 0.3,
    max_tokens: int = 4096,
):
    """Yield content deltas from an OpenAI-compatible streaming endpoint."""
    config = await _get_active_llm_config()
    use_model = model or config["model_name"]
    use_temp = config["parameters"].get("temperature", temperature)
    use_max_tokens = config["parameters"].get("max_tokens", max_tokens)
    use_top_p = config["parameters"].get("top_p", 1.0)

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            f"{config['api_base']}/chat/completions",
            json={
                "model": use_model,
                "messages": messages,
                "temperature": use_temp,
                "max_tokens": use_max_tokens,
                "top_p": use_top_p,
                "stream": True,
            },
            headers=_build_headers(config["api_key"]),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content


async def get_embedding(text: str, model: str = "") -> list[float]:
    """Get embedding vector for text using the configured embedding model."""
    # Try to get embedding config from database
    global _llm_config_cache
    emb_config = None
    async with async_session() as db:
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.type == "embedding", ModelConfig.is_active == True)
        )
        emb_config = result.scalar_one_or_none()

    if emb_config:
        api_base = emb_config.api_base.rstrip("/")
        api_key = _resolve_api_key(emb_config.api_key_encrypted)
        emb_model = model or emb_config.model_name
    else:
        # Fallback to LLM config
        llm = await _get_active_llm_config()
        api_base = llm["api_base"]
        api_key = llm["api_key"]
        emb_model = model or "bge-m3"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{api_base}/embeddings",
            json={"model": emb_model, "input": text},
            headers=_build_headers(api_key),
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


async def get_embeddings_batch(texts: list[str], model: str = "") -> list[list[float]]:
    """Get embeddings for multiple texts in a single API call."""
    global _llm_config_cache
    emb_config = None
    async with async_session() as db:
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.type == "embedding", ModelConfig.is_active == True)
        )
        emb_config = result.scalar_one_or_none()

    if emb_config:
        api_base = emb_config.api_base.rstrip("/")
        api_key = _resolve_api_key(emb_config.api_key_encrypted)
        emb_model = model or emb_config.model_name
    else:
        llm = await _get_active_llm_config()
        api_base = llm["api_base"]
        api_key = llm["api_key"]
        emb_model = model or "bge-m3"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{api_base}/embeddings",
            json={"model": emb_model, "input": texts},
            headers=_build_headers(api_key),
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]
