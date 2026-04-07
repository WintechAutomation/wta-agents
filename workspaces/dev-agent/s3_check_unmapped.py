"""Check how many S3 files are NOT mapped in DB."""
import asyncio
import json
import os

import asyncpg
import boto3

BUCKET = "cs-setupimage"
REGION = "ap-northeast-2"
PREFIX = "cs-attachments/"
BASE_URL = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/"


async def main():
    s3 = boto3.client("s3", region_name=REGION)
    paginator = s3.get_paginator("list_objects_v2")

    cs_files: dict[int, list[str]] = {}
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            if len(parts) < 4:
                continue
            try:
                cs_id = int(parts[1])
            except ValueError:
                continue
            url = BASE_URL + key
            cs_files.setdefault(cs_id, []).append(url)

    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)

    unmapped_count = 0
    mapped_count = 0
    missing_cs = 0
    already_mapped_cs = 0

    for cs_id, urls in sorted(cs_files.items()):
        row = await conn.fetchrow(
            "SELECT attachment_urls, result_attachment_urls FROM csagent.cs_history WHERE id = $1",
            cs_id,
        )
        if not row:
            missing_cs += 1
            unmapped_count += len(urls)
            continue

        existing_symptom = json.loads(row["attachment_urls"]) if row["attachment_urls"] else []
        existing_result = json.loads(row["result_attachment_urls"]) if row["result_attachment_urls"] else []
        existing_urls = {e.get("url") for e in existing_symptom + existing_result}

        new_urls = [u for u in urls if u not in existing_urls]
        if new_urls:
            unmapped_count += len(new_urls)
        else:
            already_mapped_cs += 1
        mapped_count += len(urls) - len(new_urls)

    await conn.close()

    print(f"S3 CS IDs: {len(cs_files)}")
    print(f"Already fully mapped: {already_mapped_cs}")
    print(f"CS not in DB: {missing_cs}")
    print(f"Files already mapped: {mapped_count}")
    print(f"Files NOT mapped: {unmapped_count}")


if __name__ == "__main__":
    asyncio.run(main())
