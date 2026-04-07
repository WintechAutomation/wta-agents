"""Add delivery_terms and payment_terms columns to csagent.quotes."""
import asyncio, os

async def main():
    import asyncpg
    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)

    # 칼럼 존재 여부 확인 후 추가
    for col in ("delivery_terms", "payment_terms"):
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='csagent' AND table_name='quotes' AND column_name=$1)",
            col,
        )
        if not exists:
            await conn.execute(
                f"ALTER TABLE csagent.quotes ADD COLUMN {col} VARCHAR(200)"
            )
            print(f"Added column: {col}")
        else:
            print(f"Column already exists: {col}")

    await conn.close()

asyncio.run(main())
