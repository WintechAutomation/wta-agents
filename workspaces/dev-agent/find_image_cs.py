"""Find CS IDs with image attachments."""
import asyncio, json, os

async def main():
    import asyncpg
    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(
        "SELECT id, attachment_urls FROM csagent.cs_history "
        "WHERE attachment_urls IS NOT NULL "
        "AND attachment_urls != '[]'::jsonb "
        "AND attachment_urls::text LIKE '%image%' "
        "ORDER BY jsonb_array_length(attachment_urls) DESC "
        "LIMIT 5"
    )
    for r in rows:
        attachments = json.loads(r["attachment_urls"])
        imgs = [a for a in attachments if "image" in a.get("content_type", "")]
        print(f"CS ID: {r['id']} -- images: {len(imgs)}, total: {len(attachments)}")
        for a in imgs[:2]:
            print(f"  {a['filename']}")
    await conn.close()

asyncio.run(main())
