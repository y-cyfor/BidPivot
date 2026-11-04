import base64
import io
import random
import string
import uuid

import redis.asyncio as redis
from PIL import Image, ImageDraw

from app.config import settings

CAPTCHA_PREFIX = "captcha:"
CAPTCHA_TTL = 120
CAPTCHA_RATE_PREFIX = "captcha_rate:"
CAPTCHA_RATE_LIMIT = 10  # Max 10 captchas per IP per minute
CAPTCHA_RATE_WINDOW = 60  # 60 seconds

_redis: redis.Redis | None = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL)
    return _redis


def generate_captcha_text(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


def generate_captcha_image(text: str) -> bytes:
    width, height = 120, 40
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    for _ in range(5):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200))

    for i, char in enumerate(text):
        x = 10 + i * 28
        y = random.randint(5, 15)
        draw.text((x, y), char, fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def check_captcha_rate_limit(ip_address: str) -> bool:
    """Check if IP has exceeded captcha rate limit. Returns True if allowed."""
    r = await _get_redis()
    key = f"{CAPTCHA_RATE_PREFIX}{ip_address}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, CAPTCHA_RATE_WINDOW)
    return count <= CAPTCHA_RATE_LIMIT


async def create_captcha(ip_address: str | None = None) -> tuple[str, str] | None:
    """Create a captcha. Returns None if rate limited."""
    if ip_address:
        if not await check_captcha_rate_limit(ip_address):
            return None

    captcha_id = str(uuid.uuid4())
    text = generate_captcha_text()
    image_bytes = generate_captcha_image(text)
    image_base64 = base64.b64encode(image_bytes).decode()

    r = await _get_redis()
    await r.set(f"{CAPTCHA_PREFIX}{captcha_id}", text, ex=CAPTCHA_TTL)

    return captcha_id, image_base64


async def verify_captcha(captcha_id: str, code: str) -> bool:
    r = await _get_redis()
    stored = await r.get(f"{CAPTCHA_PREFIX}{captcha_id}")
    await r.delete(f"{CAPTCHA_PREFIX}{captcha_id}")

    if stored is None:
        return False
    return stored.decode().lower() == code.lower()
