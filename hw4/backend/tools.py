"""Tools the Campus Customs agent can call. All are read-only lookups in campus_customs.db.

Find:   search_products, catalogue_overview
Facts:  get_product_info (description + price), get_prices (price only, several products),
        check_stock (quantity by size, with in/low/out-of-stock status)

Every tool that returns a price records it in ctx.deps.seen_prices, so agent.py can reject
a reply that quotes a price the agent never looked up.
"""

import json
import re

from pydantic_ai import ModelRetry, RunContext

from db import SIZE_ORDER, add_restock_request, get_db, list_restock_requests, load_inventory, size_key
from models import (
    LOW_STOCK_THRESHOLD,
    CatalogueOverview,
    PastChatMatch,
    PriceInfo,
    ProductInfo,
    ProductSummary,
    RestockRequest,
    RestockSignup,
    SearchRecord,
    SearchResults,
    ShopDeps,
    SizeStock,
    StockCheck,
    StockStatus,
)

STOP_WORDS = {
    "a", "an", "and", "any", "do", "for", "have", "i", "in", "is", "me", "my", "of",
    "on", "or", "show", "some", "the", "to", "with", "you", "yale", "want", "looking",
}

# Weight of a query word found in each field.
FIELD_WEIGHTS = {"name": 3, "garment_type": 3, "search_tags": 2, "colors": 2, "description": 1}

# garment_type filter word -> spellings used in the catalogue's garment_type and names
GARMENT_SYNONYMS = {
    "hoodie": ["hoodie", "hooded", "hood"],
    "hood": ["hoodie", "hooded", "hood"],
    "tee": ["t-shirt", "t shirt", "tee"],
    "t": ["t-shirt", "t shirt", "tee"],
    "shirt": ["t-shirt", "t shirt", "tee", "performance shirt"],  # not "sweatshirt"
    "zip": ["zip"],
    "quarter": ["quarter-zip", "1 4 zip", "1/4 zip"],
    "crewneck": ["crewneck", "crew neck", "crew-neck"],
    "crew": ["crewneck", "crew neck", "crew-neck"],
    "fleece": ["fleece"],
    "jacket": ["jacket"],
    "sweatshirt": ["sweatshirt", "hoodie", "crewneck"],
}

MAX_PAGE_RESULTS = 48  # most matches kept per search for the page

# Shopper wording -> size code used in the inventory table.
SIZE_ALIASES = {
    "xs": "XS", "extra small": "XS", "x-small": "XS", "xsmall": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "extra large": "XL", "x-large": "XL", "xlarge": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "double xl": "XXL",
}


# ---------- helpers ----------


def _words(text: str) -> list[str]:
    words = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP_WORDS or len(w) < 2:
            continue
        # crude plural handling: hoodies -> hoodie, shirts -> shirt
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    return words


def normalize_size(size: str) -> str:
    """'large' -> 'L', '2XL' -> 'XXL'. Unrecognised sizes come back upper-cased (e.g. '3XL')."""
    key = re.sub(r"\s+", " ", size.strip().lower())
    return SIZE_ALIASES.get(key, key.upper())


def stock_status(quantity: int) -> StockStatus:
    if quantity <= 0:
        return "out_of_stock"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


def _load_product(conn, product_id: str):
    row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    if row is None:
        raise ModelRetry(
            f"No product with id {product_id!r}. Call search_products to find the right product_id."
        )
    return row


def _remember_price(ctx: RunContext[ShopDeps] | None, price: float) -> None:
    if ctx is not None:
        ctx.deps.seen_prices.add(round(price, 2))


def _summary(row, inventory: list[dict]) -> ProductSummary:
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        sizes_in_stock=[s["size"] for s in inventory if s["quantity"] > 0],
        total_stock=sum(s["quantity"] for s in inventory),
    )


# ---------- find ----------


def search_products(
    ctx: RunContext[ShopDeps],
    query: str = "",
    garment_type: str | None = None,
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    in_stock_only: bool = True,
    limit: int = 8,
) -> SearchResults:
    """Search the Campus Customs catalogue to find products and their product_id.
    Use this first whenever the shopper names or describes a product, or browses a type of item.

    Returns the top `limit` matches plus `total_matches` and a `search_id`. Every match (not just
    the ones shown to you) is kept under `search_id`: put it in `page_results` to show all of
    them as product cards on the website.

    Args:
        query: Free-text keywords, e.g. "bulldog hoodie", "Saybrook", "hockey", "gift for dad".
        garment_type: Optional filter such as "hoodie", "crewneck", "t-shirt", "1/4 zip", "fleece".
        color: Optional color filter, e.g. "navy", "gray", "pink".
        size: Optional size (XS, S, M, L, XL, XXL, or words like "large") for browsing, e.g.
            "hoodies in XL": only products with that size in stock are returned. Don't use it when
            the shopper names a specific product; search by name, then call check_stock with the size.
        max_price: Optional maximum price in USD.
        in_stock_only: Leave True for browsing. Set False to include sold-out items; then `size`
            does not hide anything either.
        limit: Maximum number of results (1-12).
    """
    limit = max(1, min(limit, 12))
    size = normalize_size(size) if size else None
    if size and size not in SIZE_ORDER:
        raise ModelRetry(f"Unknown size {size!r}. Use one of {SIZE_ORDER}.")

    words = _words(query)
    type_words = _words((garment_type or "").lower().replace("1/4", "quarter"))
    color_lc = color.lower().strip() if color else None

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
        stock = load_inventory(conn, [r["product_id"] for r in rows])

    scored: list[tuple[int, ProductSummary]] = []
    for r in rows:
        if max_price is not None and r["price"] > max_price:
            continue
        gt = r["garment_type"].lower()
        name_lc = r["name"].lower()
        if type_words and not all(
            any(v in gt or v in name_lc for v in GARMENT_SYNONYMS.get(w, [w])) for w in type_words
        ):
            continue
        colors = [c.lower() for c in json.loads(r["colors"])]
        if color_lc and not any(color_lc in c for c in colors):
            continue
        inv = stock.get(r["product_id"], [])
        if in_stock_only:
            if sum(s["quantity"] for s in inv) == 0:
                continue
            if size and not any(s["size"] == size and s["quantity"] > 0 for s in inv):
                continue

        score = 0
        if words:
            fields = {
                "name": r["name"].lower(),
                "garment_type": gt,
                "search_tags": " ".join(json.loads(r["search_tags"])).lower(),
                "colors": " ".join(colors),
                "description": r["description"].lower(),
            }
            score = sum(FIELD_WEIGHTS[f] for w in words for f, text in fields.items() if w in text)
            if score == 0:
                continue
        scored.append((score, _summary(r, inv)))

    scored.sort(key=lambda s: (-s[0], s[1].name))
    matches = [s for _, s in scored]
    shown = matches[:limit]
    for r in shown:
        _remember_price(ctx, r.price)

    search_id = "none"
    if ctx is not None:
        search_id = f"s{len(ctx.deps.searches) + 1}"
        filters = ", ".join(
            f"{k}={v!r}"
            for k, v in dict(query=query, garment_type=garment_type, color=color, size=size, max_price=max_price).items()
            if v
        )
        ctx.deps.searches[search_id] = SearchRecord(
            description=filters or "all products",
            product_ids=[m.product_id for m in matches[:MAX_PAGE_RESULTS]],
        )
    return SearchResults(search_id=search_id, total_matches=len(matches), showing=len(shown), products=shown)


def catalogue_overview(ctx: RunContext[ShopDeps]) -> CatalogueOverview:
    """Overview of what the shop carries: garment types with product counts, price range, and sizes.
    Use for broad questions like "what do you sell?"."""
    with get_db() as conn:
        types = conn.execute(
            "SELECT garment_type, COUNT(*) AS n FROM catalogue GROUP BY garment_type ORDER BY n DESC"
        ).fetchall()
        lo, hi, n = conn.execute("SELECT MIN(price), MAX(price), COUNT(*) FROM catalogue").fetchone()
        sizes = [r[0] for r in conn.execute("SELECT DISTINCT size FROM inventory").fetchall()]

    _remember_price(ctx, lo)
    _remember_price(ctx, hi)
    return CatalogueOverview(
        garment_types={t["garment_type"]: t["n"] for t in types},
        price_min=lo,
        price_max=hi,
        sizes=sorted(sizes, key=size_key),
        product_count=n,
    )


# ---------- facts: description, price, stock ----------


def get_product_info(ctx: RunContext[ShopDeps], product_id: str) -> ProductInfo:
    """Get the database description, colors, and price of one product, plus which sizes are
    in or out of stock. Use when the shopper asks what an item is like or how much it costs.

    Args:
        product_id: The product_id from search_products or from "Products shown" in an earlier reply.
    """
    with get_db() as conn:
        row = _load_product(conn, product_id)
        inv = load_inventory(conn, [product_id])[product_id]

    _remember_price(ctx, row["price"])
    return ProductInfo(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        colors=json.loads(row["colors"]),
        price=row["price"],
        total_stock=sum(s["quantity"] for s in inv),
        sizes_in_stock=[s["size"] for s in inv if s["quantity"] > 0],
        sizes_out_of_stock=[s["size"] for s in inv if s["quantity"] <= 0],
    )


def get_prices(ctx: RunContext[ShopDeps], product_ids: list[str]) -> list[PriceInfo]:
    """Look up the current price of one or more products (for "how much is…" or "which is cheaper?").
    Always use a tool for prices; never quote a price from memory or an earlier message.

    Args:
        product_ids: 1-10 product_id values.
    """
    ids = list(dict.fromkeys(product_ids))[:10]
    if not ids:
        raise ModelRetry("Pass at least one product_id.")
    with get_db() as conn:
        marks = ",".join("?" * len(ids))
        rows = {
            r["product_id"]: r
            for r in conn.execute(
                f"SELECT product_id, name, price FROM catalogue WHERE product_id IN ({marks})", ids
            )
        }
    missing = [i for i in ids if i not in rows]
    if missing:
        raise ModelRetry(f"Unknown product_id(s) {missing}. Call search_products to find the right ids.")

    for r in rows.values():
        _remember_price(ctx, r["price"])
    return [PriceInfo(product_id=i, name=rows[i]["name"], price=rows[i]["price"]) for i in ids]


def check_stock(ctx: RunContext[ShopDeps], product_id: str, size: str | None = None) -> StockCheck:
    """Check how many of a product are in stock, size by size. Use for any availability,
    "is it in my size?", or "how many are left?" question. Pass `size` when the shopper names one.

    Args:
        product_id: The product_id from search_products or from "Products shown" in an earlier reply.
        size: Optional size the shopper asked about: XS, S, M, L, XL, XXL, or words like "large".
    """
    with get_db() as conn:
        row = _load_product(conn, product_id)
        inv = load_inventory(conn, [product_id])[product_id]

    sizes = [SizeStock(size=s["size"], quantity=s["quantity"], status=stock_status(s["quantity"])) for s in inv]
    in_stock = [s.size for s in sizes if s.quantity > 0]
    out_of_stock = [s.size for s in sizes if s.quantity <= 0]
    total = sum(s.quantity for s in sizes)
    name = row["name"]

    requested = normalize_size(size) if size else None
    status = qty = None
    if requested:
        match = next((s for s in sizes if s.size == requested), None)
        if match is None:
            status = "not_offered"
            summary = f"{name} is not made in size {requested}; sizes offered are {', '.join(s.size for s in sizes)}."
        else:
            status, qty = match.status, match.quantity
            if status == "out_of_stock":
                others = ", ".join(in_stock) or "none"
                summary = f"{name} is OUT OF STOCK in {requested}. In stock: {others}."
            elif status == "low_stock":
                summary = f"{name} is in stock in {requested}, but only {qty} left."
            else:
                summary = f"{name} is in stock in {requested} ({qty} available)."
    elif total == 0:
        summary = f"{name} is sold out in every size."
    else:
        summary = (
            f"{name}: {total} in stock. In stock: {', '.join(in_stock)}."
            + (f" Out of stock: {', '.join(out_of_stock)}." if out_of_stock else "")
        )

    return StockCheck(
        product_id=product_id,
        name=name,
        total_stock=total,
        sizes=sizes,
        sizes_in_stock=in_stock,
        sizes_out_of_stock=out_of_stock,
        requested_size=requested,
        requested_size_status=status,
        requested_size_quantity=qty,
        summary=summary,
    )


# ---------- customer memory ----------


def search_past_chats(ctx: RunContext[ShopDeps], query: str, limit: int = 5) -> list[PastChatMatch]:
    """Search this signed-in customer's own saved chat history (older than what you can see),
    e.g. "the hoodie you showed me last week". Returns matching past messages, newest first,
    with the products shown at the time. Only works for logged-in customers.

    Args:
        query: Keywords to look for, e.g. "hoodie", "Saybrook", "gift for dad".
        limit: Maximum matches (1-10).
    """
    if ctx.deps.customer is None:
        raise ModelRetry("The shopper is a guest, so there is no saved history. Suggest logging in instead.")
    words = _words(query)
    if not words:
        raise ModelRetry("Give one or more keywords to search for.")
    limit = max(1, min(limit, 10))

    with get_db() as conn:
        # Scoped by the session's customer id from deps, never by anything the model or shopper supplies.
        rows = conn.execute(
            "SELECT id, role, content, products_json, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 500",
            (ctx.deps.customer.id,),
        ).fetchall()

    matches = []
    for r in rows:
        products = json.loads(r["products_json"] or "[]")
        names = " ".join(p.get("name", "") for p in products).lower()
        text = r["content"].lower() + " " + names
        if all(w in text for w in words):
            matches.append(
                PastChatMatch(
                    created_at=r["created_at"],
                    role=r["role"],
                    excerpt=r["content"][:300],
                    product_ids=[p["product_id"] for p in products if "product_id" in p][:6],
                    product_names=[p.get("name", "") for p in products][:6],
                )
            )
        if len(matches) >= limit:
            break
    return matches


# ---------- restock waitlist ----------

RESTOCK_MESSAGES = {
    "added": "Added to the restock list for {size} under {email}. The shop uses this list when it restocks.",
    "already_on_list": "Already on the restock list for {size}.",
    "in_stock": "{size} is in stock right now ({qty} available), so no waitlist is needed.",
    "not_offered": "This item isn't made in {size}.",
}


def restock_signup(user_id: int, email: str, product_id: str, size: str) -> RestockSignup:
    """Shared by the agent tool and POST /api/restock."""
    size = normalize_size(size)
    status, info = add_restock_request(user_id, product_id, size)
    if status == "unknown_product":
        raise ValueError(f"No product with id {product_id!r}")
    return RestockSignup(
        product_id=product_id,
        name=info["name"],
        size=size,
        status=status,
        message=RESTOCK_MESSAGES[status].format(size=size, email=email, qty=info.get("quantity")),
    )


def join_restock_waitlist(ctx: RunContext[ShopDeps], product_id: str, size: str) -> RestockSignup:
    """Add the signed-in customer to the "notify me when it's back" list for a SOLD-OUT size.
    Only call this after the customer says yes to being notified. Guests must log in first.

    Args:
        product_id: The product's id.
        size: The sold-out size (XS, S, M, L, XL, XXL or words like "large").
    """
    c = ctx.deps.customer
    if c is None:
        raise ModelRetry("The shopper is a guest. Tell them to log in so you can add them to the restock list.")
    try:
        return restock_signup(c.id, c.email, product_id, size)
    except ValueError:
        raise ModelRetry(f"No product with id {product_id!r}. Call search_products to find the right id.")


def my_restock_requests(ctx: RunContext[ShopDeps]) -> list[RestockRequest]:
    """List the signed-in customer's open restock requests, and whether each is back in stock."""
    if ctx.deps.customer is None:
        raise ModelRetry("The shopper is a guest, so they have no restock requests. Suggest logging in.")
    return [RestockRequest(**r) for r in list_restock_requests(ctx.deps.customer.id)]


ALL_TOOLS = [
    search_products,
    catalogue_overview,
    get_product_info,
    get_prices,
    check_stock,
    search_past_chats,
    join_restock_waitlist,
    my_restock_requests,
]
