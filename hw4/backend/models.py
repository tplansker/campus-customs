"""Structured types for the Campus Customs chatbot.

- API types: what the website sends to /api/chat and gets back.
- Agent types: ShopReply is the agent's typed output; ShopDeps is passed to every tool.
- Tool result types: compact product views the model sees (no images, no secrets).
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

# ---------- Product cards (shown in the chat panel) ----------


class StockLevel(BaseModel):
    size: str
    quantity: int


class ProductCard(BaseModel):
    """Same shape as the products stored in chat_messages.products_json, so old rows load too."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    image_url: str
    price: float
    inventory: list[StockLevel] = []
    total_stock: int = 0


# ---------- Chat API ----------


class PageContextIn(BaseModel):
    """Where the shopper is on the site when they send a message (sent by the browser).
    Untrusted: the backend only uses the ids, after checking them against the catalogue."""

    path: str = Field("/", max_length=200)
    product_id: str | None = Field(None, max_length=120)  # set on /products/{id}
    results_heading: str | None = Field(None, max_length=120)  # chat results shown on /products
    visible_product_ids: list[str] = Field(default_factory=list, max_length=12)  # first cards on screen


class GuestHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    page: PageContextIn | None = None
    # Only used for guests (nothing is stored for them). Logged-in history always comes from the database.
    history: list[GuestHistoryItem] = Field(default_factory=list, max_length=20)


class PageResultsOut(BaseModel):
    """Search matches for the website to show as product cards on the page (Products page)."""

    heading: str
    query: str
    products: list[ProductCard]


class ChatReply(BaseModel):
    reply: str
    products: list[ProductCard] = []  # a few highlights shown inside the chat bubble
    page_results: PageResultsOut | None = None  # full search results to render on the page


class ChatHistoryMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = []
    created_at: str


# ---------- Agent ----------


class PageResults(BaseModel):
    heading: str = Field(
        description='Short title for the results on the page, e.g. "Hoodies", "Navy crewnecks under $60".'
    )
    search_id: str = Field(description='The search_id returned by search_products, e.g. "s1".')


class ShopReply(BaseModel):
    """The agent's final answer. The backend turns product_ids into cards from the database,
    so prices, stock, and images always come from the catalogue, never from the model."""

    message: str = Field(
        description="Reply to the shopper in the Campus Customs voice. Short; Markdown bold and lists are OK."
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="product_id values (from tool results) to show as product cards, best match first. "
        "Empty when no products are relevant.",
    )
    page_results: PageResults | None = Field(
        None,
        description="Set when the shopper is browsing a type or group of items (e.g. 'what hoodies do you "
        "have?'), so the website shows every match from that search as product cards. "
        "Leave null for questions about one specific item.",
    )


class Customer(BaseModel):
    """The signed-in shopper, as the agent sees them. Never includes the password hash."""

    id: int
    first_name: str
    last_name: str
    email: str


class PageProduct(BaseModel):
    product_id: str
    name: str


class PageContext(BaseModel):
    """Server-checked version of PageContextIn: ids are verified and names come from the database."""

    path: str
    page_type: Literal["home", "products", "product_detail", "about", "login", "create_account", "other"]
    product: PageProduct | None = None  # the item on a product detail page
    results_heading: str | None = None
    visible_products: list[PageProduct] = []


@dataclass
class ShopDeps:
    customer: Customer | None  # None = guest
    page: PageContext | None = None
    # Prices returned by tools during this turn. The output validator rejects a reply that
    # quotes a dollar amount the agent didn't look up, so prices can't be invented.
    seen_prices: set[float] = field(default_factory=set)
    # Numbers the shopper typed this turn (e.g. a "$70" budget) may be repeated back.
    shopper_amounts: set[float] = field(default_factory=set)
    # search_id -> full ordered match list from search_products this turn (more than the model sees).
    searches: dict[str, "SearchRecord"] = field(default_factory=dict)

    @property
    def first_name(self) -> str:
        return self.customer.first_name if self.customer else "there"


@dataclass
class SearchRecord:
    description: str
    product_ids: list[str]


# ---------- Tool results ----------
# Compact, typed views of the database. Status fields are computed in the tool so the
# model never has to interpret raw numbers (e.g. it can't misread 0 as "available").

LOW_STOCK_THRESHOLD = 5  # 1-5 units left counts as low stock

StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]


class ProductSummary(BaseModel):
    """One search hit: enough to pick the right product and mention it."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    sizes_in_stock: list[str]
    total_stock: int


class SearchResults(BaseModel):
    """What search_products returns. `products` is the top `limit` matches; all `total_matches`
    are kept server-side under `search_id`, so the page can show them all."""

    search_id: str
    total_matches: int
    showing: int
    products: list[ProductSummary]


class ProductInfo(BaseModel):
    """Full description and price for one product (get_product_info)."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    price: float
    currency: Literal["USD"] = "USD"
    total_stock: int
    sizes_in_stock: list[str]
    sizes_out_of_stock: list[str]


class PriceInfo(BaseModel):
    """Price of one product (get_prices)."""

    product_id: str
    name: str
    price: float
    currency: Literal["USD"] = "USD"


class SizeStock(BaseModel):
    size: str
    quantity: int
    status: StockStatus


class StockCheck(BaseModel):
    """Stock for one product, by size (check_stock)."""

    product_id: str
    name: str
    total_stock: int
    sizes: list[SizeStock]
    sizes_in_stock: list[str]
    sizes_out_of_stock: list[str]
    requested_size: str | None = Field(
        None, description="The size the shopper asked about, normalised (e.g. 'large' -> 'L'), if any."
    )
    requested_size_status: StockStatus | Literal["not_offered"] | None = Field(
        None, description="'not_offered' means the shop doesn't make this size at all."
    )
    requested_size_quantity: int | None = None
    summary: str = Field(description="One plain sentence stating the stock facts; safe to paraphrase.")


class PastChatMatch(BaseModel):
    """One message from the customer's saved history (search_past_chats)."""

    created_at: str
    role: Literal["user", "assistant"]
    excerpt: str
    product_ids: list[str]
    product_names: list[str]


class RestockSignup(BaseModel):
    """Result of join_restock_waitlist / POST /api/restock."""

    product_id: str
    name: str
    size: str
    status: Literal["added", "already_on_list", "in_stock", "not_offered"]
    message: str


class RestockRequest(BaseModel):
    product_id: str
    name: str
    size: str
    requested_at: str
    back_in_stock: bool


class RestockIn(BaseModel):
    product_id: str = Field(max_length=120)
    size: str = Field(max_length=10)


class CatalogueOverview(BaseModel):
    garment_types: dict[str, int]
    price_min: float
    price_max: float
    sizes: list[str]
    product_count: int
