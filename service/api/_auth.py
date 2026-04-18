from __future__ import annotations
import os
from typing import Optional

from fastapi import Header, HTTPException


async def verify_taskpilot_secret(x_taskpilot_secret: Optional[str] = Header(default=None)) -> None:
    """Reject requests that don't carry the correct X-TaskPilot-Secret header.

    If TASKPILOT_SECRET is not set in the environment the check is skipped so
    that local / test deployments without a secret still work.  In production
    you should always set the env var.
    """
    expected = os.environ.get("TASKPILOT_SECRET")
    if expected and x_taskpilot_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-TaskPilot-Secret")
