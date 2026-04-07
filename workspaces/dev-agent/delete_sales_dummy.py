"""Delete all dummy parts_sale data."""
import asyncio, os

async def main():
    import asyncpg
    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)

    items_deleted = await conn.execute("DELETE FROM csagent.parts_sale_item")
    sales_deleted = await conn.execute("DELETE FROM csagent.parts_sale")
    print(f"Deleted items: {items_deleted}")
    print(f"Deleted sales: {sales_deleted}")

    # Reset sequence
    await conn.execute("ALTER SEQUENCE csagent.parts_sale_id_seq RESTART WITH 1")
    await conn.execute("ALTER SEQUENCE csagent.parts_sale_item_id_seq RESTART WITH 1")
    print("Sequences reset to 1")

    # Verify
    remaining = await conn.fetchval("SELECT count(*) FROM csagent.parts_sale")
    print(f"Remaining sales: {remaining}")

    await conn.close()

asyncio.run(main())
