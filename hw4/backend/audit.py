"""Append-only audit trail of agent loop activity: output/audit_trail.json.

One record per chat turn (agent run):
    {
      "time": "2026-10-18T01:02:03Z", "run_id": "…", "who": "customer #1" | "guest",
      "page": "/products/…", "message": "first 200 chars of the shopper's message",
      "model": "gpt-5.6-luna",
      "steps": [ {"time", "tool", "args" (short), "result" (short)}, … ],
      "stop_reason": "final_result" | "content_filter" | "usage_limit" | "model_error" | "not_configured",
      "output": {"message": "first 200 chars", "product_ids": […], "page_results": "s1" | null},
      "requests": 3, "input_tokens": …, "output_tokens": …, "duration_ms": …
    }

The file is a JSON array that is never rewritten: each new record replaces only the closing "]"
with ",<record>]", so earlier records are untouched (append-only) and the file stays valid JSON.
It is never wiped between runs. A lock stops two chats from writing at the same moment.
Emails and passwords are never logged; customers appear as "customer #<id>".
"""

import fcntl
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

AUDIT_PATH = Path(os.getenv("AUDIT_PATH", Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"))
SHORT = 200  # max characters for args/results/messages in a record

_lock = threading.Lock()


def iso(ts: datetime | None = None) -> str:
    return (ts or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short(value: Any, limit: int = SHORT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summarize_result(content: Any) -> str:
    """A one-line description of a tool's return value."""
    if isinstance(content, list):
        if content and isinstance(content[0], BaseModel):
            names = ", ".join(
                (getattr(c, "name", "") or getattr(c, "product_id", ""))
                + (f" ${c.price:.2f}" if isinstance(getattr(c, "price", None), (int, float)) else "")
                for c in content[:3]
            )
            return short(f"{len(content)} item(s): {names}{' …' if len(content) > 3 else ''}")
        return short(f"{len(content)} item(s)")
    if isinstance(content, BaseModel):
        kind = type(content).__name__
        d = content.model_dump()
        if kind == "SearchResults":
            top = ", ".join(p["product_id"] for p in d["products"][:3])
            return short(f"{d['search_id']}: {d['total_matches']} matches (showing {d['showing']}): {top}")
        if kind == "StockCheck":
            return short(d["summary"])
        if kind == "ProductInfo":
            return short(f"{d['name']}: ${d['price']:.2f}, in stock {d['sizes_in_stock']}")
        if kind == "RestockSignup":
            return short(f"{d['status']}: {d['name']} {d['size']}")
        if kind == "CatalogueOverview":
            return short(f"{d['product_count']} products, ${d['price_min']:.0f}-${d['price_max']:.0f}")
        return short(f"{kind}: {json.dumps(d, default=str)}")
    return short(content)


def append(record: dict) -> None:
    """Append one record to the JSON array without rewriting earlier records."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(record, ensure_ascii=False, indent=2)
    data = "\n".join("  " + line for line in data.splitlines())
    with _lock:
        AUDIT_PATH.touch(exist_ok=True)
        with open(AUDIT_PATH, "r+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size == 0:
                    f.write(("[\n" + data + "\n]\n").encode())
                    return
                # Find the closing "]" (skipping trailing whitespace) and write over just that.
                pos = size
                while pos > 0:
                    f.seek(pos - 1)
                    ch = f.read(1)
                    if ch not in b" \n\r\t":
                        break
                    pos -= 1
                if ch != b"]":
                    raise ValueError(f"{AUDIT_PATH} doesn't end with ']'; refusing to modify it.")
                f.seek(pos - 1)
                f.truncate()
                f.write((",\n" + data + "\n]\n").encode())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def steps_from_messages(messages) -> list[dict]:
    """Tool calls in this run with their results, in order (the output tool included)."""
    from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart

    steps: list[dict] = []
    by_id: dict[str, dict] = {}
    for m in messages:
        stamp = iso(getattr(m, "timestamp", None))
        for part in m.parts:
            if isinstance(m, ModelResponse) and isinstance(part, ToolCallPart):
                step = {"time": stamp, "tool": part.tool_name, "args": short(part.args_as_dict()), "result": None}
                steps.append(step)
                by_id[part.tool_call_id] = step
            elif isinstance(part, ToolReturnPart) and part.tool_call_id in by_id:
                by_id[part.tool_call_id]["result"] = summarize_result(part.content)
            elif isinstance(part, RetryPromptPart) and part.tool_call_id in by_id:
                err = part.content if isinstance(part.content, str) else json.dumps(part.content, default=str)
                by_id[part.tool_call_id]["result"] = short("RETRY: " + err)
    return steps
