"""슬랙 채널 일괄 생성 — MES 프로젝트명 기반"""
import json, urllib.request, re, time, sys

# 출력 인코딩 강제 (Windows cp949 우회)
sys.stdout.reconfigure(encoding="utf-8")

# 토큰 로드
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


results = []
for proj in projects:
    ch_name = to_slack_name(proj)
    body = json.dumps({"name": ch_name}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/conversations.create",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("ok"):
            results.append(("OK", proj, ch_name, data["channel"]["id"]))
        else:
            err = data.get("error", "unknown")
            results.append(("FAIL", proj, ch_name, err))
    except Exception as e:
        results.append(("ERR", proj, ch_name, str(e)))
    time.sleep(0.5)

print("\n=== Slack Channel Creation Results ===")
ok_count = 0
for status, proj, ch, detail in results:
    mark = "[OK]" if status == "OK" else "[FAIL]"
    print(f"{mark} #{ch}")
    print(f"     original: {proj}")
    print(f"     detail:   {detail}")
    if status == "OK":
        ok_count += 1

print(f"\nDone: {ok_count}/{len(projects)} created")
