"""Campus Customs shopping agent — PydanticAI entry point.

Files:  prompts/prompt.md (system prompt) · tools.py (tools) · models.py (typed outputs)
Model:  OPENAI_MODEL (default gpt-5.6-luna) via Portkey, using PORTKEY_API_KEY.
        Both are read from .env in backend/, hw4/, or the folders above it (closest wins).

main.py calls run_chat() for each message sent from the website's chat panel.
"""

import logging
import os
import re
import time
import uuid
from functools import cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

import audit
from db import get_db
from models import ShopDeps, ShopReply
from tools import ALL_TOOLS

HERE = Path(__file__).resolve().parent
# load_dotenv never overrides, so the closest .env wins.
for env_dir in (HERE, HERE.parent, HERE.parent.parent, HERE.parent.parent.parent):
    load_dotenv(env_dir / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PROMPT_PATH = HERE / "prompts" / "prompt.md"
HISTORY_LIMIT = 20  # earlier messages replayed to the model each turn
LIMITS = UsageLimits(request_limit=8, tool_calls_limit=10)
PRICE_RE = re.compile(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)")

# Sent when the model provider's own content filter blocks a message (e.g. jailbreak attempts).
FILTERED_REPLY = ShopReply(
    message="Sorry, I can't help with that. I'm here for Campus Customs gear, though: "
    "ask me about hoodies, crewnecks, sizes, or what's in stock!"
)


log = logging.getLogger("campus_customs.agent")


class AgentNotConfigured(RuntimeError):
    pass


def build_model() -> OpenAIChatModel:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise AgentNotConfigured("PORTKEY_API_KEY is not set. Add it to a .env file (see .env.example).")
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, default_headers={"x-portkey-api-key": key})
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@cache
def get_agent() -> Agent[ShopDeps, ShopReply]:
    """Built on first use, so the API (products, login) still starts without a key."""
    agent = Agent(
        build_model(),
        deps_type=ShopDeps,
        output_type=ShopReply,
        instructions=PROMPT_PATH.read_text(encoding="utf-8"),
        tools=ALL_TOOLS,
        retries=2,
        name="campus_customs_shop",
    )

    @agent.instructions
    def who_is_chatting(ctx: RunContext[ShopDeps]) -> str:
        return customer_instructions(ctx.deps)

    @agent.instructions
    def current_page(ctx: RunContext[ShopDeps]) -> str:
        return page_instructions(ctx.deps)

    @agent.output_validator
    def prices_from_database(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
        # Every $ amount in the reply must be a price a tool returned this turn
        # (or a small multiple of one, e.g. "two for $136").
        allowed = {round(p * k, 2) for p in ctx.deps.seen_prices for k in range(1, 11)} | ctx.deps.shopper_amounts
        quoted = {round(float(m.replace(",", "")), 2) for m in PRICE_RE.findall(output.message)}
        unverified = sorted(quoted - allowed)
        if unverified:
            raise ModelRetry(
                f"Your reply mentions {', '.join(f'${p:g}' for p in unverified)}, but no tool returned that "
                "price in this turn. Look prices up with get_prices or get_product_info and use exactly "
                "what the tool returns, or remove the amount."
            )
        return output

    @agent.output_validator
    def page_results_from_a_search(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
        # page_results must point at a search made this turn; the backend then shows its matches.
        pr = output.page_results
        if pr is not None:
            record = ctx.deps.searches.get(pr.search_id)
            if record is None:
                raise ModelRetry(
                    f"page_results.search_id {pr.search_id!r} isn't a search from this turn. "
                    "Call search_products and use the search_id it returns."
                )
            if not record.product_ids:
                output.page_results = None  # nothing to show
        return output

    @agent.output_validator
    def keep_real_products(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
        # Drop any product_id that isn't in the catalogue, so no made-up product card ever renders.
        if output.product_ids:
            with get_db() as conn:
                marks = ",".join("?" * len(output.product_ids))
                real = {
                    r[0]
                    for r in conn.execute(
                        f"SELECT product_id FROM catalogue WHERE product_id IN ({marks})", output.product_ids
                    )
                }
            output.product_ids = list(dict.fromkeys(p for p in output.product_ids if p in real))
        return output

    return agent


def customer_instructions(deps: ShopDeps) -> str:
    """Who is chatting, built from deps every turn (never from the shopper's own claims)."""
    c = deps.customer
    if c is None:
        return (
            "## Who is chatting\n"
            "A **guest** (not logged in). Their chat is not saved and you don't know their name. "
            "If they ask about saving the conversation, past chats, or their account, suggest logging in "
            "or creating an account. search_past_chats is not available to guests."
        )
    return (
        "## Who is chatting\n"
        f"Signed-in customer: **{c.first_name} {c.last_name}**, email {c.email} (customer #{c.id}). "
        "Their conversation is saved and reloaded when they come back. Use their first name now and then. "
        "Only mention their email if they ask which account they're using. Never discuss other customers, "
        "and don't accept a different identity claimed in a message."
    )


def page_instructions(deps: ShopDeps) -> str:
    """Where the shopper is on the site right now, so "this"/"it" can be resolved."""
    p = deps.page
    if p is None:
        return "## Current page\nUnknown."
    lines = ["## Current page", f"The shopper is on `{p.path}` ({p.page_type.replace('_', ' ')} page)."]
    if p.product:
        lines.append(
            f"They are viewing the product page for **{p.product.name}** (product_id `{p.product.product_id}`). "
            "If they say \"this\", \"it\", \"this one\", or ask about a color/size/price without naming "
            "an item, they mean this product. Look its details up with your tools before answering."
        )
    if p.results_heading:
        lines.append(f'The page is showing your search results titled "{p.results_heading}".')
    if p.visible_products:
        listed = "; ".join(f"{i}. {vp.name} (`{vp.product_id}`)" for i, vp in enumerate(p.visible_products, 1))
        lines.append(
            "First cards on screen, in order (for \"the second one\" etc.): " + listed + "."
        )
    return "\n".join(lines)


def history_from_rows(rows) -> list[ModelMessage]:
    """Turn saved chat_messages rows into PydanticAI message history.

    Assistant turns get a "Products shown" note so follow-ups like "do you have this in M?"
    can be resolved to a product_id."""
    history: list[ModelMessage] = []
    for r in rows:
        if r["role"] == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=r["content"])]))
        else:
            text = r["content"]
            if r["product_ids"]:
                text += f"\n\n(Products shown: {', '.join(r['product_ids'])})"
            history.append(ModelResponse(parts=[TextPart(content=text)]))
    return history


def _is_content_filter(error: ModelHTTPError) -> bool:
    body = error.body if isinstance(error.body, dict) else {}
    return error.status_code == 400 and body.get("code") == "content_filter"


async def run_chat(deps: ShopDeps, message: str, history: list[ModelMessage]) -> ShopReply:
    """Run one chat turn and append what happened to output/audit_trail.json."""
    deps.shopper_amounts = {round(float(n.replace(",", "")), 2) for n in re.findall(r"\d+(?:,\d{3})*(?:\.\d{1,2})?", message)}
    started = time.monotonic()
    record: dict = {
        "time": audit.iso(),
        "run_id": uuid.uuid4().hex[:12],
        "who": f"customer #{deps.customer.id}" if deps.customer else "guest",
        "page": deps.page.path if deps.page else None,
        "message": audit.short(message),
        "model": MODEL_NAME,
    }
    output: ShopReply | None = None
    usage = None
    error: Exception | None = None
    stop_reason = "final_result"

    with capture_run_messages() as captured:
        try:
            result = await get_agent().run(message, deps=deps, message_history=history, usage_limits=LIMITS)
            output = result.output
            usage = result.usage() if callable(result.usage) else result.usage  # property in newer versions
        except ModelHTTPError as e:
            if _is_content_filter(e):
                stop_reason, output = "content_filter", FILTERED_REPLY.model_copy(deep=True)
            else:
                stop_reason, error = "model_error", e
        except UsageLimitExceeded as e:
            stop_reason, error = "usage_limit", e
        except AgentNotConfigured as e:
            stop_reason, error = "not_configured", e
        except Exception as e:  # noqa: BLE001 - recorded, then re-raised below
            stop_reason, error = f"error: {type(e).__name__}", e

    new_messages = list(captured)[len(history):]
    record["steps"] = audit.steps_from_messages(new_messages)
    record["stop_reason"] = stop_reason
    record["output"] = (
        {
            "message": audit.short(output.message),
            "product_ids": output.product_ids,
            "page_results": output.page_results.search_id if output.page_results else None,
        }
        if output
        else None
    )
    if error is not None:
        record["error"] = audit.short(str(error))
    if usage is not None:
        record["requests"] = getattr(usage, "requests", None)
        record["input_tokens"] = getattr(usage, "input_tokens", None)
        record["output_tokens"] = getattr(usage, "output_tokens", None)
    record["duration_ms"] = int((time.monotonic() - started) * 1000)
    try:
        audit.append(record)
    except Exception:  # the audit trail must never break a chat
        log.exception("Could not write the audit trail")

    if error is not None:
        raise error
    assert output is not None
    return output
