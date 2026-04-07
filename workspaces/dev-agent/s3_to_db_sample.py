"""S3 CS attachments -> DB mapping script (sample 5 CS IDs)."""
import asyncio
import json
import os

import asyncpg
import boto3

BUCKET = "cs-setupimage"
REGION = "ap-northeast-2"
PREFIX = "cs-attachments/"
BASE_URL = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/"

# content_type by extension
EXT_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".pdf": "application/pdf", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

def guess_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return EXT_MAP.get(ext, "application/octet-stream")


async def main():
    # S3 list
    s3 = boto3.client("s3", region_name=REGION)
    paginator = s3.get_paginator("list_objects_v2")

    # group by cs_id
    cs_files: dict[int, list[dict]] = {}
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            # cs-attachments/{cs_id}/{type}/{filename}
            if len(parts) < 4:
                continue
            try:
                cs_id = int(parts[1])
            except ValueError:
                continue
            attach_type = parts[2]  # symptom or result
            filename = parts[3]
            cs_files.setdefault(cs_id, []).append({
                "cs_id": cs_id,
                "type": attach_type,
                "key": key,
                "filename": filename,
                "size": obj["Size"],
                "content_type": guess_content_type(filename),
                "url": BASE_URL + key,
            })

    print(f"S3 total CS IDs: {len(cs_files)}, total files: {sum(len(v) for v in cs_files.values())}")

    # DB connect
    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)

    # sample: first 5 CS IDs
    sample_ids = sorted(cs_files.keys())[:5]
    print(f"Sample CS IDs: {sample_ids}")

    for cs_id in sample_ids:
        files = cs_files[cs_id]

        # check cs_history exists
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM csagent.cs_history WHERE id = $1)", cs_id
        )
        if not exists:
            print(f"  CS {cs_id}: NOT FOUND in DB, skip")
            continue

        # get current attachments
        row = await conn.fetchrow(
            "SELECT attachment_urls, result_attachment_urls FROM csagent.cs_history WHERE id = $1",
            cs_id,
        )
        existing_symptom = json.loads(row["attachment_urls"]) if row["attachment_urls"] else []
        existing_result = json.loads(row["result_attachment_urls"]) if row["result_attachment_urls"] else []
        existing_urls = {e.get("url") for e in existing_symptom + existing_result}

        symptom_add = []
        result_add = []

        for f in files:
            if f["url"] in existing_urls:
                continue  # skip duplicates
            entry = {
                "url": f["url"],
                "filename": f["filename"],
                "file_size": f["size"],
                "content_type": f["content_type"],
            }
            if f["type"] == "result":
                result_add.append(entry)
            else:
                symptom_add.append(entry)

        # update DB
        if symptom_add:
            new_symptom = existing_symptom + symptom_add
            await conn.execute(
                "UPDATE csagent.cs_history SET attachment_urls = $1::jsonb WHERE id = $2",
                json.dumps(new_symptom), cs_id,
            )

        if result_add:
            new_result = existing_result + result_add
            await conn.execute(
                "UPDATE csagent.cs_history SET result_attachment_urls = $1::jsonb WHERE id = $2",
                json.dumps(new_result), cs_id,
            )

        print(f"  CS {cs_id}: +{len(symptom_add)} symptom, +{len(result_add)} result (existing: {len(existing_urls)})")

    await conn.close()
    print("Done. Check cs-wta.com CS history pages for these IDs.")


if __name__ == "__main__":
    asyncio.run(main())
