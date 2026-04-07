"""기존 슬랙 채널 목록 조회 — name_taken 원인 확인"""
import json, urllib.request, re, sys

sys.stdout.reconfigure(encoding="utf-8")

with open("C:/MES/wta-agents/config/slack-token.txt", "r") as f:
    token = f.read().strip()

projects = [
    "[선제작] 포장기 #25-1 (교세라CN)",
    "연삭기핸들러",
    "쑤저우 신루이 프레스 #4~5",
    "메이써루이 프레스 #12~14",
    "한국야금 프레스 #40t-1",
    "몰디노 프레스 #1 (20t, 환봉)",
    "한국야금 CVD #4",
    "대구텍 PVD-UL #1 (개조)",
    "한국야금 PVD 로딩 #5,#6 (선제작)",
    "대구텍 검사기 F2 #1",
    "몰디노 PVD-L #1",
    "다인정공 F1 #1 딥러닝",
    "메이써루이 프레스 #11",
    "하이썽 프레스 핸들러 #10",
    "하이썽 프레스 핸들러 #9",
]


def to_slack_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r'[#\[\]()\s,~.]+', '-', n)
    n = re.sub(r'-+', '-', n)
    return n.strip('-')[:80]


target_names = {to_slack_name(p): p for p in projects}

# 전체 채널 목록 페이지 조회 (archived 포함)
all_channels = {}
cursor = ""
page = 0
while True:
    url = "https://slack.com/api/conversations.list?types=public_channel&limit=200&exclude_archived=false"
    if cursor:
        url += f"&cursor={cursor}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if not data.get("ok"):
        print(f"API error: {data.get('error')}")
        break
    for ch in data.get("channels", []):
        all_channels[ch["name"]] = {
            "id": ch["id"],
            "archived": ch.get("is_archived", False),
            "member_count": ch.get("num_members", 0),
        }
    meta = data.get("response_metadata", {})
    cursor = meta.get("next_cursor", "")
    page += 1
    if not cursor:
        break

print(f"Total channels in workspace: {len(all_channels)}\n")
print("=== Target channel status ===")
for target_name, orig in target_names.items():
    if target_name in all_channels:
        info = all_channels[target_name]
        archived = " [ARCHIVED]" if info["archived"] else ""
        print(f"EXISTS{archived}: #{target_name} (id={info['id']}, members={info['member_count']})")
        print(f"  original: {orig}")
    else:
        print(f"NOT FOUND: #{target_name}")
        print(f"  original: {orig}")
