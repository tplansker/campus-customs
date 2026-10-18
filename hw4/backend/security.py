"""Login and request hardening (Problem 9).

- login_attempts table: audit log of every login/sign-up attempt, used for lockouts.
- Lockouts: too many failed logins for one email, or from one IP, return 429 for a while.
- Origin check: state-changing requests from another website are rejected (CSRF defence,
  on top of the SameSite=Lax session cookie).
- Security headers on every response.
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from db import get_db, now_utc

WINDOW = timedelta(minutes=15)
MAX_FAILS_PER_EMAIL = 5  # then that email is locked for the rest of the window
MAX_FAILS_PER_IP = 20  # stops one machine from trying many different emails
MAX_SIGNUPS_PER_IP = 5  # per hour, to slow down fake-account creation
SIGNUP_WINDOW = timedelta(hours=1)

ALLOWED_ORIGINS = {
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
}
# Render sets the service's public URL automatically (e.g. https://campus-customs.onrender.com).
if os.getenv("RENDER_EXTERNAL_URL"):
    ALLOWED_ORIGINS.add(os.environ["RENDER_EXTERNAL_URL"].rstrip("/"))

# The login_attempts table is defined in db.py (created at startup if missing).


def client_ip(request: Request) -> str:
    # On Render, uvicorn runs with --proxy-headers so this is the shopper's real IP
    # (from X-Forwarded-For), not the proxy's; otherwise every visitor would share one IP.
    return request.client.host if request.client else "unknown"


def _since(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%d %H:%M:%S")


def _retry_after(oldest: str, window: timedelta) -> int:
    started = datetime.strptime(oldest, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return max(60, int((started + window - datetime.now(timezone.utc)).total_seconds()))


def _too_many(seconds: int, what: str) -> HTTPException:
    minutes = max(1, round(seconds / 60))
    return HTTPException(
        429,
        f"Too many {what}. Please wait about {minutes} minute{'s' if minutes != 1 else ''} and try again.",
        headers={"Retry-After": str(seconds)},
    )


def check_login_allowed(email: str, ip: str) -> None:
    """Raise 429 if this email or IP has too many recent failed logins.
    Applies to unknown emails too, so lockouts don't reveal which accounts exist."""
    since = _since(WINDOW)
    with get_db() as conn:
        by_email = conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM login_attempts "
            "WHERE kind='login' AND success=0 AND email=? AND created_at >= ?",
            (email, since),
        ).fetchone()
        by_ip = conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM login_attempts "
            "WHERE kind='login' AND success=0 AND ip=? AND created_at >= ?",
            (ip, since),
        ).fetchone()
    if by_email[0] >= MAX_FAILS_PER_EMAIL:
        raise _too_many(_retry_after(by_email[1], WINDOW), "failed login attempts for this account")
    if by_ip[0] >= MAX_FAILS_PER_IP:
        raise _too_many(_retry_after(by_ip[1], WINDOW), "failed login attempts from this device")


def check_signup_allowed(ip: str) -> None:
    with get_db() as conn:
        n, oldest = conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM login_attempts "
            "WHERE kind='register' AND success=1 AND ip=? AND created_at >= ?",
            (ip, _since(SIGNUP_WINDOW)),
        ).fetchone()
    if n >= MAX_SIGNUPS_PER_IP:
        raise _too_many(_retry_after(oldest, SIGNUP_WINDOW), "new accounts from this device")


def record_attempt(kind: str, email: str, ip: str, success: bool) -> None:
    with get_db(write=True) as conn:
        conn.execute(
            "INSERT INTO login_attempts (kind, email, ip, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (kind, email[:254], ip, int(success), now_utc()),
        )
        if kind == "login" and success:
            # A successful login clears earlier failures for that email.
            conn.execute(
                "DELETE FROM login_attempts WHERE kind='login' AND success=0 AND email=?", (email,)
            )


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Browsers always send Origin on cross-site POSTs. Reject ones from other websites.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin not in ALLOWED_ORIGINS:
                return JSONResponse({"detail": "Request blocked: unexpected origin."}, status_code=403)

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")  # never cache account/chat data
        return response


# ---------- Sensitive-data redaction for chat (Problem 12) ----------
# Shoppers sometimes paste things that should never be stored or sent to an AI model.
# Chat messages are cleaned in main.py BEFORE they reach the agent, the database, or the
# audit trail. The agent sees the placeholder and reminds the shopper not to share it.

import re as _re

_CARD = _re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_SSN = _re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_PASSWORD = _re.compile(r"(?i)\b(password|passcode|pwd)\b(\s*(?:is|:|=)\s*)(\S+)")


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact_sensitive(text: str) -> tuple[str, list[str]]:
    """Replace card numbers (Luhn-valid), SSNs, and 'password is …' values. Returns (clean text, kinds found)."""
    found: list[str] = []

    def card(m: _re.Match) -> str:
        digits = _re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found.append("card number")
            return "[card number removed]"
        return m.group(0)

    text = _CARD.sub(card, text)
    if _SSN.search(text):
        found.append("SSN")
        text = _SSN.sub("[SSN removed]", text)
    if _PASSWORD.search(text):
        found.append("password")
        text = _PASSWORD.sub(lambda m: f"{m.group(1)}{m.group(2)}[password removed]", text)
    return text, found
