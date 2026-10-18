"""Campus Customs API.

Problem 3: serves the product catalogue, stock levels, and product images
from data/campus_customs.db.
Problem 4: account creation, login, and logout with a signed session cookie.
Problem 5: /api/chat sends shopper messages to the PydanticAI agent (agent.py).
Problem 9: login hardening (security.py, passwords.py) and the restock waitlist.
Deploy: uses Supabase Postgres when DATABASE_URL is set (see db.py), and serves the built
React app from frontend/dist, so the whole site runs as one Render web service.

Run from the backend folder:
    uvicorn main:app --reload --port 8000
"""

import json
import logging
import os
import re
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware

load_dotenv(Path(__file__).resolve().parent / ".env")

from agent import HISTORY_LIMIT, AgentNotConfigured, history_from_rows, run_chat  # noqa: E402
from db import DIALECT, IMAGES_DIR, Row, get_db, load_inventory, load_products, now_utc, product_from_row, size_key  # noqa: E402
from models import (  # noqa: E402
    ChatHistoryMessage,
    ChatReply,
    ChatRequest,
    Customer,
    PageContext,
    PageContextIn,
    PageProduct,
    PageResultsOut,
    ProductCard,
    RestockIn,
    RestockRequest,
    RestockSignup,
    ShopDeps,
)
from db import list_restock_requests  # noqa: E402
from tools import restock_signup  # noqa: E402
from passwords import DUMMY_HASH, hash_password, needs_rehash, password_problem, verify_password  # noqa: E402
from security import (  # noqa: E402
    SecurityMiddleware,
    check_login_allowed,
    check_signup_allowed,
    client_ip,
    record_attempt,
    redact_sensitive,
)

log = logging.getLogger("campus_customs")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    # Still runs without a .env, but everyone is logged out on each restart.
    print("WARNING: SESSION_SECRET is not set; using a temporary secret. See .env.example.")
    SESSION_SECRET = secrets.token_urlsafe(48)

app = FastAPI(title="Campus Customs API")

# The Vite dev server proxies /api and /media, so CORS is only needed if the
# frontend is opened directly against this port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Signed, HttpOnly cookie holding only the user's id. JavaScript can't read it,
# and it can't be forged without SESSION_SECRET. COOKIE_SECURE=true (HTTPS) when deployed.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="cc_session",
    max_age=7 * 24 * 60 * 60,
    same_site="lax",
    https_only=COOKIE_SECURE,
)

# Origin check (CSRF) + security headers. Added last, so it runs first.
app.add_middleware(SecurityMiddleware)

# Mount only the images folder so the .db file itself is never served.
IMAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*\.(jpg|jpeg|png|webp)$")


@app.get("/media/products/{file_name}", include_in_schema=False)
def product_image(file_name: str) -> Response:
    """Product photo: from the local data pack (data/products/) if present, otherwise from the
    product_images table (deployments without the data pack, e.g. Render). Only this folder is
    served, never the .db file."""
    if not IMAGE_NAME.match(file_name):
        raise HTTPException(404, "Not found")
    local = IMAGES_DIR / file_name
    if local.is_file():
        return FileResponse(local, headers={"Cache-Control": "public, max-age=86400"})
    with get_db() as conn:
        row = conn.execute(
            "SELECT content_type, data FROM product_images WHERE file_name = ?", (file_name,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Not found")
    return Response(content=bytes(row["data"]), media_type=row["content_type"],
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "database": DIALECT}


@app.get("/api/products")
def list_products() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        stock = load_inventory(conn, [r["product_id"] for r in rows])
    products = []
    for r in rows:
        inv = stock.get(r["product_id"], [])
        products.append(
            {
                **product_from_row(r),
                "total_stock": sum(s["quantity"] for s in inv),
                # used by the Products page "in stock in size" filter
                "sizes_in_stock": [s["size"] for s in inv if s["quantity"] > 0],
            }
        )
    return products


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        stock = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
        ).fetchall()

    inventory = sorted(
        ({"size": s["size"], "quantity": s["quantity"]} for s in stock),
        key=lambda s: size_key(s["size"]),
    )
    return {
        **product_from_row(row),
        "inventory": inventory,
        "total_stock": sum(s["quantity"] for s in inventory),
    }


# ---------- Accounts ----------


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def public_user(row: Row) -> dict:
    # Never include password_hash in anything sent to the browser (or, later, the model).
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "email": row["email"],
    }


def start_session(request: Request, user_id: int) -> None:
    # Clear first so a pre-login session can't carry over (session fixation).
    request.session.clear()
    request.session["user_id"] = user_id


def current_user(request: Request) -> Row | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    with get_db() as conn:
        return conn.execute(
            "SELECT id, first_name, last_name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterRequest, request: Request) -> dict:
    first = body.first_name.strip()
    last = body.last_name.strip()
    email = body.email.strip().lower()
    ip = client_ip(request)
    check_signup_allowed(ip)

    if not first or not last:
        raise HTTPException(400, "Please enter your first and last name.")
    if len(first) > 60 or len(last) > 60:
        raise HTTPException(400, "Names must be 60 characters or fewer.")
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(400, "Please enter a valid email address.")
    if problem := password_problem(body.password, email, first, last):
        raise HTTPException(400, problem)
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords don't match.")

    try:
        with get_db(write=True) as conn:
            new_id = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (f"{first} {last}", email, hash_password(body.password), first, last, now_utc()),
            ).fetchone()["id"]
            user = conn.execute(
                "SELECT id, first_name, last_name, email FROM users WHERE id = ?",
                (new_id,),
            ).fetchone()
    except IntegrityError:
        raise HTTPException(409, "An account with that email already exists.")

    record_attempt("register", email, ip, True)
    start_session(request, user["id"])
    return public_user(user)


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request) -> dict:
    email = body.email.strip().lower()[:254]
    ip = client_ip(request)
    check_login_allowed(email, ip)  # 429 after repeated failures (email or IP)

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, first_name, last_name, email, password_hash FROM users WHERE lower(email) = ?",
            (email,),
        ).fetchone()

    # Same work and same message whether the email or the password is wrong.
    valid = verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)
    record_attempt("login", email, ip, bool(row and valid))
    if not row or not valid:
        raise HTTPException(401, "Incorrect email or password.")

    if needs_rehash(row["password_hash"]):
        # Upgrade older/weaker hashes (e.g. seed users' 120k rounds) now that we have the password.
        with get_db(write=True) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), row["id"])
            )

    start_session(request, row["id"])
    return public_user(row)


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request) -> None:
    request.session.clear()


@app.get("/api/auth/me")
def me(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    return public_user(user)


# ---------- Chat ----------
# Logged-in customers: history lives in chat_messages (user_id -> users.id) and is reloaded
# from there on every turn and when the chat panel opens. Guests can chat too; nothing is
# stored for them, and the browser sends their recent turns with each message instead.

GUEST_HISTORY_LIMIT = 10

def require_user(request: Request) -> Row:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Please log in to see saved chats.")
    return user


def customer_from_row(user: Row) -> Customer:
    return Customer(
        id=user["id"],
        first_name=user["first_name"] or "Shopper",
        last_name=user["last_name"] or "",
        email=user["email"],
    )


def parse_products(products_json: str | None) -> list[ProductCard]:
    try:
        return [ProductCard.model_validate(p) for p in json.loads(products_json or "[]")]
    except (ValueError, TypeError):
        return []


def recent_messages(user_id: int, limit: int) -> list[Row]:
    # Always scoped to the session's user_id, never one sent by the browser.
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, products_json, created_at FROM chat_messages
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return rows[::-1]


PAGE_TYPES = {"/": "home", "/products": "products", "/about": "about", "/login": "login", "/create-account": "create_account"}


def resolve_page(page: PageContextIn | None) -> PageContext | None:
    """Turn the browser's page context into trusted facts: only ids that exist in the
    catalogue are kept, and names are read from the database (not from the browser)."""
    if page is None:
        return None
    path = page.path.split("?")[0].rstrip("/") or "/"
    page_type = PAGE_TYPES.get(path, "product_detail" if path.startswith("/products/") else "other")

    ids = ([page.product_id] if page.product_id else []) + page.visible_product_ids
    names: dict[str, str] = {}
    if ids:
        with get_db() as conn:
            marks = ",".join("?" * len(ids))
            names = dict(conn.execute(f"SELECT product_id, name FROM catalogue WHERE product_id IN ({marks})", ids).fetchall())

    product = None
    if page_type == "product_detail" and page.product_id in names:
        product = PageProduct(product_id=page.product_id, name=names[page.product_id])
    visible = [PageProduct(product_id=i, name=names[i]) for i in dict.fromkeys(page.visible_product_ids) if i in names]
    return PageContext(
        path=path,
        page_type=page_type,
        product=product,
        results_heading=page.results_heading if page_type == "products" else None,
        visible_products=visible,
    )


@app.get("/api/chat/history")
def chat_history(request: Request) -> list[ChatHistoryMessage]:
    user = require_user(request)
    return [
        ChatHistoryMessage(
            id=r["id"],
            role=r["role"],
            content=r["content"],
            products=parse_products(r["products_json"]),
            created_at=r["created_at"],
        )
        for r in recent_messages(user["id"], 50)
    ]


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> ChatReply:
    user = current_user(request)  # None = guest
    # Card numbers, SSNs, and passwords never reach the agent, the database, or the audit trail.
    message, redacted = redact_sensitive(body.message.strip())
    if not message:
        raise HTTPException(400, "Message is empty.")
    if redacted:
        log.info("Redacted %s from a chat message", ", ".join(redacted))

    if user is not None:
        history_rows = [
            {
                "role": r["role"],
                "content": r["content"],
                "product_ids": [p.product_id for p in parse_products(r["products_json"])],
            }
            for r in recent_messages(user["id"], HISTORY_LIMIT)
        ]
    else:
        history_rows = [
            {"role": h.role, "content": redact_sensitive(h.content)[0], "product_ids": []}
            for h in body.history[-GUEST_HISTORY_LIMIT:]
        ]

    deps = ShopDeps(
        customer=customer_from_row(user) if user is not None else None,
        page=resolve_page(body.page),
    )
    try:
        output = await run_chat(deps, message, history_from_rows(history_rows))
    except AgentNotConfigured as e:
        log.error("Chat unavailable: %s", e)
        raise HTTPException(503, "The shopping assistant isn't set up yet. Please try again later.")
    except Exception:
        log.exception("Agent run failed")
        raise HTTPException(502, "The shopping assistant ran into a problem. Please try again.")

    # Cards are built from the database, so prices, stock, and images are always real.
    products = [ProductCard.model_validate(p) for p in load_products(output.product_ids)]

    # Page results: every match of the search the agent pointed at (search_id), in search order.
    page_results = None
    if output.page_results and (record := deps.searches.get(output.page_results.search_id)):
        page_results = PageResultsOut(
            heading=output.page_results.heading,
            query=message,
            products=[ProductCard.model_validate(p) for p in load_products(record.product_ids)],
        )

    if user is not None:
        # Save highlights + page results together so history (and "Products shown" for
        # follow-ups) includes everything the shopper saw.
        saved = {p.product_id: p for p in products}
        for p in page_results.products if page_results else []:
            saved.setdefault(p.product_id, p)
        with get_db(write=True) as conn:
            ts = now_utc()
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, products_json, created_at) "
                "VALUES (?, 'user', ?, NULL, ?)",
                (user["id"], message, ts),
            )
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, products_json, created_at) "
                "VALUES (?, 'assistant', ?, ?, ?)",
                (user["id"], output.message, json.dumps([p.model_dump() for p in saved.values()]), ts),
            )

    return ChatReply(reply=output.message, products=products, page_results=page_results)


# ---------- Restock waitlist ----------


@app.post("/api/restock", status_code=201)
def restock(body: RestockIn, request: Request) -> RestockSignup:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Log in to get notified when this size is back.")
    try:
        return restock_signup(user["id"], user["email"], body.product_id, body.size)
    except ValueError:
        raise HTTPException(404, "Product not found.")


@app.get("/api/restock")
def my_restock(request: Request) -> list[RestockRequest]:
    user = require_user(request)
    return [RestockRequest(**r) for r in list_restock_requests(user["id"])]


# ---------- Visitor hit counter (Problem 10: retro footer) ----------

@app.post("/api/visits")
def count_visit() -> dict:
    """Called once per browser session by the footer's hit counter; returns the new total."""
    with get_db(write=True) as conn:
        (value,) = conn.execute(
            "UPDATE site_counter SET value = value + 1 WHERE name = 'visits' RETURNING value"
        ).fetchone()
    return {"visits": value}


@app.get("/api/visits")
def get_visits() -> dict:
    with get_db() as conn:
        (value,) = conn.execute("SELECT value FROM site_counter WHERE name = 'visits'").fetchone()
    return {"visits": value}


# ---------- Built front end (deploy) ----------
# In production FastAPI also serves the React build, so the site, API, and login cookie share one
# address. Any non-API path returns index.html and React Router shows the right page. Locally,
# the Vite dev server (port 5173) is used instead. Keep this last so API routes match first.

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "media/")):
            raise HTTPException(404, "Not found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)  # /assets/*.js, favicon.svg, …
        return FileResponse(FRONTEND_DIST / "index.html")
