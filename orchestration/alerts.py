from __future__ import annotations

import json
from urllib import request


def send_webhook(url: str | None, payload: dict, *, timeout: float = 5.0) -> bool:
    if not url:
        return False
    body = json.dumps(payload).encode("utf-8")
    webhook_request = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(webhook_request, timeout=timeout) as response:
        return 200 <= response.status < 300
