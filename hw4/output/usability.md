# Campus Customs: Usability Improvements (Problem 9)

Four improvements are built and running: two on the front end and two on the agent and backend. Each section says **what was added**, **why it helps** Campus Customs shoppers or the business, **where to see it** in the running app, and what was **verified**.

| # | Area | Improvement | Quickest place to see it |
|---|---|---|---|
| 1 | Front end | Yale Blue look and the **Handsome Dan** bulldog assistant ("Boola Boola!") | Any page: logo, footer, chat button (bottom right) |
| 2 | Front end | **Find products faster**: search, categories, "in stock in size", price sort; chat starter questions | `/products` |
| 3 | Backend | **Login security hardening** | `/login`, `/create-account` |
| 4 | Agent + backend | **"Notify me when it's back"** restock waitlist | Sold-out size on a product page, e.g. `/products/ice-hockey-left-chest-hoodie` |

Run: `uvicorn main:app --reload --port 8000` in `backend/`, and `npm run dev` in `frontend/`, then open http://localhost:5173.

---

## 1. Yale Blue look + Handsome Dan the bulldog

### What was added
- **Traditional Yale colors.** The black-and-pink theme was replaced by Yale Blue `#00356B` on white, with Yale's medium blue `#286DC0` for hover and cool grays for borders. Every color is a CSS variable in `frontend/src/index.css` (`--accent`, `--accent-hover`, `--accent-soft`, …), so the palette is defined in one place.
- **Classic typography.** Headings use the serif *Libre Baskerville*, which echoes Yale's printed style; body text uses *Inter* (both from Google Fonts).
- **Handsome Dan.** An original bulldog illustration (`frontend/src/components/Bulldog.tsx`: wide head, rose ears, jowls, underbite; no real photos or Yale marks) appears:
  - in the **site logo**, next to "Campus Customs" with the tagline **BOOLA BOOLA!**;
  - as the **browser-tab icon** (`public/favicon.svg`);
  - as the **chat button** (white button with a blue ring) and the **chat header avatar**;
  - on the **404 page** ("Ruff! Page not found … Handsome Dan sniffed everywhere").
- **The assistant is Handsome Dan.** The chat header reads "Handsome Dan · Campus Customs assistant", it greets shoppers with *"Woof, hi Test! I'm Handsome Dan, the Campus Customs bulldog … Boola Boola!"*, and the system prompt (`backend/prompts/prompt.md`) gives the agent that persona, with an occasional "Boola Boola!" (not every message).
- **"Boola Boola!"** also appears in the home hero line and in the new Yale Blue footer.

### Why it helps
- **Trust and fit:** shoppers are buying Yale apparel; a site in Yale Blue with Yale's mascot looks like an official campus shop, not a generic template, which makes people more comfortable buying.
- **A friendlier assistant:** a named mascot makes the chat feel approachable and memorable, so more shoppers try it. It answers stock and size questions that would otherwise end in a lost sale.
- **Readability:** dark text on white with Yale Blue accents gives strong contrast, and product photos (mostly on white backgrounds) blend in instead of floating on black.

### Where to see it
Every page (logo, footer, chat button); open the chat for the Handsome Dan header and greeting; visit any bad URL (e.g. `/nope`) for the bulldog 404.

### Verified
Home, Products, product detail, chat panel, and 404 checked in the browser at desktop and phone width (375px). The logo stays on one line, and there's no sideways scrolling on phones. In chat, Handsome Dan answered "What colors does this come in?" with *"…navy blue and white. Boola Boola!"*.

> Note: the course style guide's default is black and pink; this change was explicitly requested for Problem 9.

---

## 2. Find products faster

### What was added
On the **Products page** (`frontend/src/pages/Products.tsx`):
- **Search box**: matches words across name, garment type, description, colors, and tags ("saybrook", "navy hockey", "bulldog").
- **Category buttons** with live counts: All 102 · Hoodies 27 · Crewnecks 29 · T-shirts 25 · Quarter-zips 11 · Fleece & jackets 8.
- **"In stock in" size filter** (XS–XXL): hides products that are sold out in your size. To support it, `GET /api/products` now returns `sizes_in_stock` for each product.
- **Sort**: Name (A–Z), Price low → high, Price high → low.
- **Result bar**: "20 of 102 products in stock in L", a **Clear filters** link, and a helpful empty state ("No products match those filters. Try another size or category, or ask Handsome Dan").
- **Shareable filters**: the view is saved in the URL, e.g. `/products?cat=hoodies&size=L&sort=price-desc`, so it can be bookmarked or sent to a friend.

In the **chat panel** (`ChatWidget.tsx`):
- **One-tap starter questions** for new conversations: "What hoodies do you have?", "Gift ideas for a Yale dad", "T-shirts under $35". On a product page they become questions about that item: "Is this in stock in my size?", "What colors does this come in?", "Show me similar items".

### Why it helps
- **Shoppers:** going from "navy hoodie in L" to a short list takes seconds instead of scrolling 102 cards. The size filter stops people from falling for items they can't buy, and price sort helps budget shoppers.
- **Business:** fewer visitors leave because they can't find something, and shared filtered links bring friends straight to relevant products. Starter questions show new visitors what Handsome Dan can do, which drives chat use.

### Where to see it
`/products` (filters panel above the grid). Open the chat on Home (general starters) or on any product page (item starters).

### Verified
Hoodies + in stock in **L** + price high → low showed **20 of 102** (the database also has 20 hoodies with L in stock), Brooks Brothers and Champion Full Zip ($88) first. The Sailor Bulldog and Fencing hoodies, both sold out in L, were correctly hidden. `?q=saybrook` gave the 3 Saybrook items; `?q=zzzz` showed the empty state. Clicking the "What colors does this come in?" starter on the Ice Hockey hoodie page got a correct answer.

**Bug found and fixed:** changing category, then size, then sort quickly dropped earlier filters (React Router's params were one render behind). Filter updates now build on the live URL.

---

## 3. Login security hardening

### What was added
| Protection | Details | Code |
|---|---|---|
| **Stronger password hashing** | New hashes use **PBKDF2-SHA256 with 600,000 rounds** (current OWASP guidance; was 120,000). The round count is stored in the hash (`pbkdf2_sha256$600000$salt$hash`), so it can be raised later. | `backend/passwords.py` |
| **Automatic upgrade of old hashes** | When a seed user (old 120k format) logs in successfully, the password is re-hashed at 600k. Nobody has to reset their password. | `main.py` `login()`, `needs_rehash()` |
| **Brute-force lockout** | **5 failed logins for one email in 15 minutes** → that email gets `429` with a `Retry-After` header: *"Too many failed login attempts for this account. Please wait about N minutes."* **20 failures from one IP** → that IP is throttled. Unknown emails are locked too, so lockouts don't reveal which accounts exist. A successful login clears that email's failures. | `backend/security.py` |
| **Sign-up throttle** | At most 5 new accounts per IP per hour (slows bots creating fake accounts). | `security.py` |
| **Login audit log** | New table `login_attempts (kind, email, ip, success, created_at)` records every login and sign-up attempt, for lockouts and for investigating suspicious activity. | `security.py` |
| **Stronger password rules** | At least **10 characters** (was 8), max 128; blocks the most common passwords plus shop-specific guesses ("boolaboola1", "bulldogs", "yale1701"…); rejects repetitive passwords ("aaaaaaaaaaaa"); can't contain your name or email. Clear messages tell shoppers what to fix, and the sign-up page shows the rule. | `passwords.py`, `CreateAccount.tsx` |
| **Cross-site request (CSRF) protection** | POST, PUT, PATCH, and DELETE requests from another website's `Origin` are rejected with `403`, on top of the `SameSite=Lax` cookie. | `SecurityMiddleware` |
| **Security headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (no clickjacking), `Referrer-Policy`, `Permissions-Policy`, and `Cache-Control: no-store` on all `/api/` responses (account and chat data are never cached). | `SecurityMiddleware` |
| **HTTPS cookie switch** | `COOKIE_SECURE=true` in `.env` makes the session cookie HTTPS-only for deployment. | `main.py` |

Still in place from Problem 4: salted hashes, constant-time comparison, the same error for a wrong password or an unknown email, the dummy-hash timing defence, a signed HttpOnly session cookie, and session reset at login.

### Why it helps
- **Shoppers:** their account (name, email, chat history, restock list) is much harder to break into, even with a guessed or reused password. A password guesser gets 5 tries, not unlimited.
- **Business:** a breach of customer accounts would hurt Campus Customs' reputation. The audit log gives the shop a record if something looks wrong, and the sign-up throttle keeps fake accounts out of the customer list.

### Where to see it
- `/create-account`: hint "At least 10 characters. Avoid common passwords and don't use your name or email."; try `password123` → "That password is too common…".
- `/login`: 6 wrong passwords for the same email → "Too many failed login attempts for this account. Please wait about 15 minutes and try again."

### Verified
| Check | Result |
|---|---|
| Seed user logs in with the old 120k hash | Works; stored hash now starts `pbkdf2_sha256$600000$`; logging in again works |
| 6 wrong passwords for a fake email | Tries 1–5 → `401`; try 6 → `429`, `Retry-After: 899` |
| Same email in the browser login form | Red message: "Too many failed login attempts … wait about 7 minutes" |
| `short12` / `password123` / `aaaaaaaaaaaa` / `bulldogtest99` (name Bull Dogtest) / `boolaboola1` | Each rejected with its own clear reason |
| POST with `Origin: https://evil.example` | `403 Request blocked: unexpected origin.` (real site origin → `200`) |
| Response headers | nosniff, DENY, referrer-policy, permissions-policy, no-store present |
| `login_attempts` table | Records each attempt with kind, email, IP, success, time |

---

## 4. "Notify me when it's back" restock waitlist

### What was added
- **New table** `restock_requests (user_id, product_id, size, created_at, notified_at)` with `UNIQUE(user_id, product_id, size)`, so no duplicates (`backend/db.py`).
- **Two new agent tools** (`backend/tools.py`):
  - `join_restock_waitlist(product_id, size)`: adds the signed-in customer to the list for a **sold-out** size. If the size is actually in stock it says so instead; if the shop doesn't make that size it says that. Guests are told to log in.
  - `my_restock_requests()`: lists the customer's open requests and whether each is back in stock.
- **Prompt rules** (`backend/prompts/prompt.md`): when the shopper's size is sold out, Handsome Dan **offers** the restock list, adds them **only after they say yes**, and says plainly what happened. It doesn't promise a date or an automatic email (no email sending is built yet).
- **API**: `POST /api/restock {product_id, size}` and `GET /api/restock` (logged-in only, scoped to the session user).
- **Product page button**: every sold-out size box shows **Notify me**. After a click it shows **✓ You're on the list**. Guests see **Log in to get notified**.
- **Demand report for the shop** (one query):

  ```sql
  SELECT c.name, r.size, COUNT(*) AS shoppers_waiting
  FROM restock_requests r JOIN catalogue c USING (product_id)
  WHERE r.notified_at IS NULL
  GROUP BY r.product_id, r.size ORDER BY shoppers_waiting DESC;
  ```

### Why it helps
- **Shoppers:** a sold-out size is no longer a dead end; there's a clear next step, in the chat or with one click on the product page.
- **Business:** the shop gets a ranked list of **exactly which products and sizes customers want**, with their emails, to guide reorders and reach waiting buyers when stock arrives. `notified_at` is ready for marking people as contacted.

### Where to see it
Log in, open `/products/ice-hockey-left-chest-hoodie` (sold out in M, L, XL) and click **Notify me**. Or ask Handsome Dan "is it in large?" on that page and answer "yes".

### Verified
| Check | Result |
|---|---|
| Product page, logged in: **Notify me** on M | Became "✓ You're on the list"; row saved |
| Chat on the same page: "is it in large?" | *"Sorry, … sold out in L. It's currently in stock in XS, S, and XXL. Want me to put you on the restock list for L?"* |
| "yes please add me" | *"You're on the restock list for L of the Ice Hockey Left Chest Hoodie, Test. It's saved with your account email…"*; row saved |
| "what restock requests do I have?" | Listed the open request(s), "not back in stock yet" |
| API: sold-out L / in-stock M / L again | `added` / `in_stock (15 available)` / `already_on_list` |
| Guest | Product page shows "Log in to get notified"; `POST /api/restock` → `401` |
| Demand report query | Lists each product and size with the number of shoppers waiting |

---

## Files changed (Problem 9)

- **Front end:** `src/index.css` (Yale palette, filters, chat starters, Notify me), `index.html` (fonts), `public/favicon.svg`, `src/components/Bulldog.tsx` (new), `NavBar.tsx`, `ChatWidget.tsx`, `pages/Products.tsx`, `pages/ProductDetail.tsx`, `pages/CreateAccount.tsx`, `pages/NotFound.tsx`, `pages/Home.tsx`, `App.tsx`, `api.ts`
- **Backend:** `passwords.py` (rewritten), `security.py` (new), `db.py` (restock table and helpers), `tools.py` (2 tools), `models.py`, `main.py` (auth hardening, middleware, restock API, `sizes_in_stock`), `prompts/prompt.md` (Handsome Dan persona, restock rules)
- **Database (created automatically on startup):** tables `login_attempts`, `restock_requests`; indexes on both
