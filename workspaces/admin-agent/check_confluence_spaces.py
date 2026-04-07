import sys, os, json, urllib.request, base64
from dotenv import load_dotenv
import psycopg2

load_dotenv("C:/MES/backend/.env")
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 55432)),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "postgres"),
}
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("SELECT config_data FROM api_systemconfig WHERE system_type = 'jira' LIMIT 1")
row = cur.fetchone()
conn.close()
cfg = row[0] if isinstance(row[0], dict) else json.loads(row[0])
email = cfg["email"]
token = cfg["api_token"]
domain = cfg.get("domain", cfg.get("jira_url", "wta-inc.atlassian.net")).replace("https://","").rstrip("/")

creds = base64.b64encode(f"{email}:{token}".encode()).decode()
headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}

def get(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        return e.code, {"error": e.reason, "body": body}

# Jira 기본 연결 확인
print("=== Jira API 연결 확인 ===")
s, d = get(f"https://{domain}/rest/api/3/myself")
print(f"상태: {s}")
if s == 200:
    print(f"계정: {d.get('emailAddress')} / {d.get('displayName')}")
else:
    print(d)

# Confluence v2 API 시도
print("\n=== Confluence v2 API 시도 ===")
s2, d2 = get(f"https://{domain}/wiki/api/v2/spaces?limit=10")
print(f"상태: {s2}")
if s2 == 200:
    for sp in d2.get("results", []):
        print(f"  {sp.get('key',''):20s} | {sp.get('name','')}")
else:
    print(d2.get("body","")[:400] or d2)

# Confluence v1 API 다른 엔드포인트 시도
print("\n=== Confluence v1 /space?limit=5 ===")
s3, d3 = get(f"https://{domain}/wiki/rest/api/space?limit=5")
print(f"상태: {s3}")
print(str(d3)[:400])
