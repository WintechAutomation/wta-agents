"""Check parts_sale data."""
import asyncio, os

async def main():
    import asyncpg
    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)

    # Check if table exists
    exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='csagent' AND table_name='parts_sale')"
    )
    print(f"Table csagent.parts_sale exists: {exists}")

    if exists:
        total = await conn.fetchval("SELECT count(*) FROM csagent.parts_sale")
        print(f"Total rows: {total}")
        rows = await conn.fetch(
            "SELECT id, sale_no, customer_name, status, total, sale_date "
            "FROM csagent.parts_sale ORDER BY id LIMIT 10"
        )
        for r in rows:
            print(f"  id={r['id']} no={r['sale_no']} customer={r['customer_name']} "
                  f"status={r['status']} total={r['total']} date={r['sale_date']}")

        # Check items
        item_count = await conn.fetchval("SELECT count(*) FROM csagent.parts_sale_item")
        print(f"Total items: {item_count}")
    else:
        print("Table does not exist - checking for dummy data in other locations")

    await conn.close()

asyncio.run(main())
