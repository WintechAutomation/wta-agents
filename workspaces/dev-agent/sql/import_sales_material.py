#!/usr/bin/env python3
"""판매자재관리 CSV → csagent.sales_material_master 임포트 (EC2에서 실행).

데이터 파일: /tmp/sales_material.csv (scp로 업로드)
장비모델 매칭: csagent.equipment_models.model_name <-> CSV 장비모델구분
"""

import csv
import json
import os
import sys
from io import StringIO

import asyncio
import asyncpg


async def get_conn():
    return await asyncpg.connect(
        host="127.0.0.1", port=55432,
        user="postgres",
        password=os.environ.get("PGPASSWORD", ""),
        database="postgres",
    )

CSV_PATH = "/tmp/sales_material.csv"


async def main() -> int:
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    conn = await get_conn()

    model_rows = await conn.fetch("SELECT id, model_name FROM csagent.equipment_models")
    model_map = {r["model_name"]: r["id"] for r in model_rows}

    inserted = 0
    matched = 0
    unmatched: dict[str, int] = {}
    errors: list[str] = []

    for row in rows:
        try:
            legacy_id_raw = (row.get("*ID") or "").strip()
            legacy_id = int(legacy_id_raw) if legacy_id_raw.isdigit() else None
            status = (row.get("상태") or "대기").strip()
            erp_cd = (row.get("ERP 품목코드") or "").strip() or None
            item_nm = (row.get("품명") or "").strip()
            if not item_nm:
                continue
            sale_model = (row.get("판매형번") or "").strip() or None
            unit_price_raw = (row.get("단가") or "").strip().replace(",", "")
            try:
                unit_price = float(unit_price_raw) if unit_price_raw else None
            except ValueError:
                unit_price = None
            remark = (row.get("비고") or "").strip() or None
            maker = (row.get("제조사") or "").strip() or None
            equip_name = (row.get("장비모델구분") or "").strip()
            image_fn = (row.get("제품이미지") or "").strip() or None
            drawing_fn = (row.get("도면(dwg)") or "").strip() or None
            sop_fn = (row.get("조립SOP & 점검표") or "").strip() or None
            created_by = (row.get("등록자") or "").strip() or None
            updated_by = (row.get("수정자") or "").strip() or None

            equipment_model_id = model_map.get(equip_name) if equip_name else None
            if equip_name:
                if equipment_model_id:
                    matched += 1
                else:
                    unmatched[equip_name] = unmatched.get(equip_name, 0) + 1

            result = await conn.execute(
                """INSERT INTO csagent.sales_material_master
                   (legacy_id, status, material_type, erp_item_cd, item_nm, sale_model,
                    unit_price, remark, maker, equipment_model_id,
                    image_filenames, drawing_filenames, sop_filenames,
                    created_by, updated_by)
                   VALUES ($1,$2,'일반',$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                   ON CONFLICT (legacy_id) DO NOTHING""",
                legacy_id, status, erp_cd, item_nm, sale_model, unit_price, remark,
                maker, equipment_model_id, image_fn, drawing_fn, sop_fn,
                created_by, updated_by,
            )
            if "INSERT 0 1" in result:
                inserted += 1
        except Exception as e:
            errors.append(f"legacy_id={row.get('*ID')}: {e}")
            continue

    await conn.close()

    summary = {
        "total_rows": len(rows),
        "inserted": inserted,
        "matched_equipment": matched,
        "unmatched_equipment": unmatched,
        "errors": errors[:20],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
