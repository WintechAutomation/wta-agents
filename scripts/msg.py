"""에이전트 통신 헬퍼 — 대시보드 REST API 호출"""
import sys
import json
import urllib.request

BASE = "http://localhost:5555/api"

def send(from_agent, to_agent, content):
    """메시지 전송"""
    data = json.dumps({"from": from_agent, "to": to_agent, "content": content}).encode()
    req = urllib.request.Request(f"{BASE}/send", data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def recv(agent_id):
    """메시지 수신"""
    resp = urllib.request.urlopen(f"{BASE}/recv/{agent_id}")
    return json.loads(resp.read())

def heartbeat(agent_id):
    """하트비트"""
    req = urllib.request.Request(f"{BASE}/heartbeat/{agent_id}", method="POST")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "send" and len(sys.argv) >= 5:
        print(json.dumps(send(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))))
    elif cmd == "recv" and len(sys.argv) >= 3:
        result = recv(sys.argv[2])
        for m in result.get("messages", []):
            print(f"[{m['time']}] {m['from']}: {m['content']}")
        if not result.get("messages"):
            print("(수신 메시지 없음)")
    elif cmd == "heartbeat" and len(sys.argv) >= 3:
        print(json.dumps(heartbeat(sys.argv[2])))
    else:
        print("사용법:")
        print("  python msg.py send <from> <to> <content>")
        print("  python msg.py recv <agent_id>")
        print("  python msg.py heartbeat <agent_id>")
