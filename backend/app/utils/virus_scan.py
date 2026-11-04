"""Minimal ClamAV INSTREAM client.

Scanning is opt-in: when ``CLAMAV_HOST`` is not configured the function is a
no-op, so local development does not require a running ClamAV daemon.
"""

import logging
import socket

from app.config import settings

logger = logging.getLogger(__name__)


def scan_bytes(data: bytes) -> None:
    endpoint = settings.CLAMAV_HOST
    if not endpoint:
        return

    host, _, port_text = endpoint.partition(":")
    port = int(port_text or "3310")

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.sendall(b"zINSTREAM\0")
        for start in range(0, len(data), 64 * 1024):
            chunk = data[start:start + 64 * 1024]
            sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
        sock.sendall((0).to_bytes(4, "big"))
        response = sock.recv(4096).decode("utf-8", errors="ignore")

    if "FOUND" in response:
        raise ValueError("文件安全扫描未通过")
    if "ERROR" in response:
        logger.warning("ClamAV returned an error: %s", response.strip())
        raise ValueError("文件安全扫描失败，请稍后重试")
