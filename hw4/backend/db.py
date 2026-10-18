"""Database access shared by the API (main.py), agent tools (tools.py), and security.py.

Locally: the SQLite file data/campus_customs.db.
Deployed: Supabase Postgres. Set DATABASE_URL to its Session pooler connection string, e.g.
    postgresql://postgres.<project>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

Code uses one small API for both:
    with get_db() as conn:                 # read
        rows = conn.execute("SELECT … WHERE id = ?", (1,)).fetchall()
        rows[0]["name"], rows[0][0]        # by column name or position
    with get_db(write=True) as conn:       # one transaction, committed on success
        conn.execute("INSERT … RETURNING id", (...)).fetchone()

SQL must be portable between SQLite and Postgres: use ON CONFLICT … DO NOTHING (not INSERT OR
IGNORE), RETURNING id (not lastrowid), and pass created_at from Python (now_utc()).
"""

import json
import os
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    Float,
    LargeBinary,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)

HERE = Path(__file__).resolve().parent
# backend/.env, hw4/.env, then the folders above (e.g. a course-wide .env). Never overrides;
# the closest .env wins.
for _env in (HERE / ".env", HERE.parent / ".env", HERE.parent.parent / ".env", HERE.parent.parent.parent / ".env"):
    load_dotenv(_env)

DATA_DIR = Path(os.getenv("CAMPUS_DATA_DIR", HERE.parent / "data"))
DB_PATH = DATA_DIR / "campus_customs.db"
IMAGES_DIR = DATA_DIR / "products"
SQLITE_URL = f"sqlite:///{DB_PATH}"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def _normalize_url(url: str) -> str:
    """Accept Supabase's string as-is ("postgresql://…" / "postgres://…") and use psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


DATABASE_URL = _normalize_url(os.getenv("DATABASE_URL", "").strip() or SQLITE_URL)
if os.getenv("RENDER") and DATABASE_URL == SQLITE_URL:
    # On Render the disk is wiped on restart and the .db file isn't deployed: fail loudly
    # instead of starting with an empty shop.
    raise RuntimeError("DATABASE_URL is not set. Add your Supabase connection string in Render's environment.")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    # Supabase's transaction pooler (port 6543) can't handle prepared statements; turning them
    # off makes either pooler string work.
    connect_args={"prepare_threshold": None} if DATABASE_URL.startswith("postgresql") else {},
)
DIALECT = engine.dialect.name  # "sqlite" or "postgresql"


def now_utc() -> str:
    """Timestamps are stored as UTC text 'YYYY-MM-DD HH:MM:SS' in both databases."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------- Schema (created if missing; the SQLite file already has the first four) ----------

metadata = MetaData()

catalogue = Table(
    "catalogue", metadata,
    Column("product_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("garment_type", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("colors", Text, nullable=False),  # JSON array
    Column("search_tags", Text, nullable=False),  # JSON array
    Column("image_file_path", Text, nullable=False),
    Column("price", Float, nullable=False),
)
inventory = Table(
    "inventory", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("product_id", Text, ForeignKey("catalogue.product_id"), nullable=False),
    Column("size", Text, nullable=False),
    Column("quantity", Integer, nullable=False),
    UniqueConstraint("product_id", "size"),
)
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False),
    Column("email", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("first_name", Text),
    Column("last_name", Text),
)
chat_messages = Table(
    "chat_messages", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("products_json", Text),
    Column("created_at", Text, nullable=False),
    Index("idx_chat_messages_user", "user_id", "id"),
)
login_attempts = Table(
    "login_attempts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", Text, nullable=False),  # 'login' | 'register'
    Column("email", Text, nullable=False),
    Column("ip", Text, nullable=False),
    Column("success", Integer, nullable=False),
    Column("created_at", Text, nullable=False),
    Index("idx_login_attempts_email", "email", "created_at"),
    Index("idx_login_attempts_ip", "ip", "created_at"),
)
restock_requests = Table(
    "restock_requests", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("product_id", Text, ForeignKey("catalogue.product_id"), nullable=False),
    Column("size", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("notified_at", Text),
    UniqueConstraint("user_id", "product_id", "size"),
    Index("idx_restock_product", "product_id", "size"),
)
# Product photos for deployments without the local data pack (e.g. Render). Filled once by
# copy_to_supabase.py; main.py serves data/products/<file> when present, else these bytes.
product_images = Table(
    "product_images", metadata,
    Column("file_name", Text, primary_key=True),
    Column("content_type", Text, nullable=False),
    Column("data", LargeBinary, nullable=False),
)
site_counter = Table(
    "site_counter", metadata,
    Column("name", Text, primary_key=True),
    Column("value", Integer, nullable=False),
)


# ---------- Small connection wrapper: "?" placeholders, rows by name or index ----------


class Row(tuple):
    """A result row usable as row["column"] or row[0] (and unpacked like a tuple)."""

    _keys: dict[str, int]

    def __new__(cls, values: Sequence[Any], keys: dict[str, int]):
        row = super().__new__(cls, values)
        row._keys = keys
        return row

    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, str):
            return tuple.__getitem__(self, self._keys[key])
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._keys)


class Result:
    def __init__(self, result):
        self._result = result
        self.rowcount = result.rowcount
        self._keys = {k: i for i, k in enumerate(result.keys())} if result.returns_rows else {}

    def _wrap(self, r) -> Row:
        return Row(tuple(r), self._keys)

    def fetchone(self) -> Row | None:
        r = self._result.fetchone()
        return self._wrap(r) if r is not None else None

    def fetchall(self) -> list[Row]:
        return [self._wrap(r) for r in self._result.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


_QMARK = re.compile(r"\?")


class Conn:
    def __init__(self, sa_conn):
        self._c = sa_conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Result:
        params = list(params)
        counter = iter(range(len(params)))
        named = _QMARK.sub(lambda _m: f":p{next(counter)}", sql)
        return Result(self._c.execute(text(named), {f"p{i}": v for i, v in enumerate(params)}))


@contextmanager
def get_db(write: bool = False) -> Iterator[Conn]:
    """Reads use a plain connection; writes run in one transaction (commit or roll back)."""
    if write:
        with engine.begin() as c:
            yield Conn(c)
    else:
        with engine.connect() as c:
            yield Conn(c)


def init_db() -> None:
    """Create any missing tables/indexes and the hit-counter row. Safe to run every start."""
    metadata.create_all(engine, checkfirst=True)
    with get_db(write=True) as conn:
        conn.execute(
            "INSERT INTO site_counter (name, value) VALUES ('visits', 0) ON CONFLICT (name) DO NOTHING"
        )


init_db()


# ---------- Shared product helpers ----------


def size_key(size: str) -> int:
    return SIZE_ORDER.index(size) if size in SIZE_ORDER else len(SIZE_ORDER)


def product_from_row(row) -> dict:
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"]),
        "search_tags": json.loads(row["search_tags"]),
        "image_url": f"/media/{row['image_file_path']}",
        "price": row["price"],
    }


def load_inventory(conn: Conn, product_ids: list[str]) -> dict[str, list[dict]]:
    """product_id -> [{size, quantity}, ...] in XS..XXL order."""
    if not product_ids:
        return {}
    marks = ",".join("?" * len(product_ids))
    rows = conn.execute(
        f"SELECT product_id, size, quantity FROM inventory WHERE product_id IN ({marks})",
        product_ids,
    ).fetchall()
    stock: dict[str, list[dict]] = {pid: [] for pid in product_ids}
    for r in rows:
        stock.setdefault(r["product_id"], []).append({"size": r["size"], "quantity": r["quantity"]})
    for sizes in stock.values():
        sizes.sort(key=lambda s: size_key(s["size"]))
    return stock


def load_products(product_ids: list[str]) -> list[dict]:
    """Full product dicts (with inventory and total_stock) in the order given; unknown ids are skipped."""
    if not product_ids:
        return []
    with get_db() as conn:
        marks = ",".join("?" * len(product_ids))
        rows = conn.execute(f"SELECT * FROM catalogue WHERE product_id IN ({marks})", product_ids).fetchall()
        stock = load_inventory(conn, [r["product_id"] for r in rows])
    by_id = {r["product_id"]: r for r in rows}
    products = []
    for pid in product_ids:
        if pid in by_id:
            inv = stock.get(pid, [])
            products.append(
                {**product_from_row(by_id[pid]), "inventory": inv, "total_stock": sum(s["quantity"] for s in inv)}
            )
    return products


# ---------- Restock waitlist (Problem 9) ----------


def add_restock_request(user_id: int, product_id: str, size: str) -> tuple[str, dict]:
    """Put a customer on the waitlist for one sold-out size.

    Returns (status, info): status is 'added', 'already_on_list', 'in_stock', 'not_offered',
    or 'unknown_product'; info has the product name and current quantity."""
    with get_db(write=True) as conn:
        row = conn.execute("SELECT name FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return "unknown_product", {}
        stock = conn.execute(
            "SELECT quantity FROM inventory WHERE product_id = ? AND size = ?", (product_id, size)
        ).fetchone()
        info = {"name": row["name"], "quantity": stock["quantity"] if stock else None}
        if stock is None:
            return "not_offered", info
        if stock["quantity"] > 0:
            return "in_stock", info
        inserted = conn.execute(
            "INSERT INTO restock_requests (user_id, product_id, size, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, product_id, size) DO NOTHING RETURNING id",
            (user_id, product_id, size, now_utc()),
        ).fetchone()
        return ("added" if inserted else "already_on_list"), info


def list_restock_requests(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT r.product_id, c.name, r.size, r.created_at, i.quantity
            FROM restock_requests r
            JOIN catalogue c ON c.product_id = r.product_id
            LEFT JOIN inventory i ON i.product_id = r.product_id AND i.size = r.size
            WHERE r.user_id = ? AND r.notified_at IS NULL
            ORDER BY r.id DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {"product_id": r["product_id"], "name": r["name"], "size": r["size"],
         "requested_at": r["created_at"], "back_in_stock": (r["quantity"] or 0) > 0}
        for r in rows
    ]
