"""
PostToolUse 훅 — Edit/Write 시 MAX에게 파일 수정 보고
사용법: python notify-max-edit.py {agent_id}
stdin: Claude Code 훅 JSON (tool_name, tool_input 포함)
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

agent_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"

try:
    raw = sys.stdin.read()
    hook_input = json.loads(raw) if raw.strip() else {}
except Exception:
    sys.exit(0)

tool_name = hook_input.get("tool_name", "")
if tool_name not in ("Edit", "Write"):
    sys.exit(0)

tool_input = hook_input.get("tool_input", {})
file_path = tool_input.get("file_path", "(알 수 없음)")

# 경로 단축 (C:\MES\wta-agents\ 이하만 표시)
display_path = file_path.replace("C:\\MES\\wta-agents\\", "").replace("C:/MES/wta-agents/", "")

message = f"[{agent_id}] {tool_name}: {display_path}"

payload = json.dumps({"to": "MAX", "message": message}).encode()
req = urllib.request.Request(
    "http://localhost:5600/send",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=3):
        pass
except Exception:
    pass  # MAX 오프라인 시 무시
