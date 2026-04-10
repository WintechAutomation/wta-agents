"""MAD111T 재고감안 10년치 JSON 추출"""
import urllib.request
import json
import os

FROM_DT = "2016-01-01"
TO_DT   = "2026-04-10"
OUTPUT  = r"C:\MES\wta-agents\reports\김근형\MAD111T_재고감안_10년.json"
API_BASE = "http://localhost:8100"

def get_token():
    env = {}
    with open("C:/MES/backend/.env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v
    data = json.dumps({
        "username": env["MES_SERVICE_USERNAME"],
        "password": env["MES_SERVICE_PASSWORD"],
    }).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    r = urllib.request.urlopen(req, timeout=10)
    return json.loads(r.read().decode("utf-8"))["data"]["access"]

def export(token):
    url = f"{API_BASE}/api/erp/purchase/mad111t/export?fr_dt={FROM_DT}&to_dt={TO_DT}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    r = urllib.request.urlopen(req, timeout=300)
    d = json.loads(r.read().decode("utf-8"))
    return d.get("data", d)

if __name__ == "__main__":
    print(f"MAD111T export ({FROM_DT} ~ {TO_DT})")
    token = get_token()
    print("로그인 성공, 조회 중...")
    result = export(token)
    count = result.get("count", len(result.get("items", [])))
    print(f"조회 완료: {count:,}건")

    output = {"items": result.get("items", []), "total": count}
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {OUTPUT}")
