"""One-time copy of the shop data from data/campus_customs.db into Supabase (DATABASE_URL).

Run from backend/ after putting your Supabase Session pooler string in backend/.env as DATABASE_URL:

    .venv/bin/python copy_to_supabase.py

It creates every table in Supabase if missing (db.init_db), then copies:
  - catalogue (102 products) and inventory (612 size rows): the shop itself
  - users: the course's seed accounts (e.g. test@campuscustoms.yale.edu), so the graders' test
    login works on the live site. Test accounts made while building (…@example.test) are skipped.
  - product photos from data/products/ into the product_images table, so a deployment without the
    data pack (Render) can still show them. Safe to re-run: photos already stored are skipped.
Chat history, login attempts, restock requests, and the hit counter start fresh in Supabase.

Products, inventory, and users are copied only if Supabase has no products yet, so running it
twice can't duplicate anything.
"""

import sys

from sqlalchemy import create_engine, func, insert, select, text

import db


def main() -> int:
    if db.DIALECT != "postgresql":
        print("DATABASE_URL isn't set to a Postgres database. Put your Supabase string in backend/.env first.")
        return 1

    source = create_engine(db.SQLITE_URL)
    with source.connect() as src:
        products = [dict(r._mapping) for r in src.execute(select(db.catalogue).order_by(db.catalogue.c.product_id))]
        stock = [dict(r._mapping) for r in src.execute(select(db.inventory).order_by(db.inventory.c.id))]
        people = [
            dict(r._mapping)
            for r in src.execute(select(db.users).order_by(db.users.c.id))
            if not r._mapping["email"].endswith("@example.test")
        ]
    print(f"Read {len(products)} products, {len(stock)} inventory rows, {len(people)} seed users from SQLite")

    db.init_db()  # creates all tables in Supabase if missing
    copy_images()
    with db.engine.begin() as conn:
        existing = conn.execute(select(func.count()).select_from(db.catalogue)).scalar_one()
        if existing:
            print(f"Supabase already has {existing} products; catalogue, inventory, and users not copied again.")
            return 0
        conn.execute(insert(db.catalogue), products)
        conn.execute(insert(db.inventory), stock)
        if people:
            conn.execute(insert(db.users), people)
        # Rows kept their original ids, so move each id counter past them.
        for table in ("inventory", "users"):
            conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                )
            )

    with db.engine.connect() as conn:
        counts = {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one() for t in ("catalogue", "inventory", "users")}
    print("Supabase now has:", counts)
    print("Done. Start the backend with DATABASE_URL set and check /api/health says \"postgresql\".")
    return 0


def copy_images() -> None:
    """Store every photo in data/products/ in product_images (skips ones already there)."""
    files = sorted(p for p in db.IMAGES_DIR.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    with db.engine.begin() as conn:
        have = {r[0] for r in conn.execute(select(db.product_images.c.file_name))}
        new = [p for p in files if p.name not in have]
        types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        for p in new:
            conn.execute(
                insert(db.product_images),
                {"file_name": p.name, "content_type": types[p.suffix.lower()], "data": p.read_bytes()},
            )
    print(f"Photos: {len(new)} copied, {len(files) - len(new)} already in Supabase.")


if __name__ == "__main__":
    sys.exit(main())
