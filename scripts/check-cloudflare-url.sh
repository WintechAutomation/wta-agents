#!/bin/bash
# PreToolUse hook: telegram/slack reply with local file paths -> block, require Cloudflare URL
# Blocks if reply text contains local file paths not converted to agent.mes-wta.com

INPUT=$(cat)

# Extract text field using python (jq not available)
TEXT=$("C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('tool_input',{}).get('text','') or d.get('tool_input',{}).get('message',''))
except:
    print('')
" <<< "$INPUT")

if [ -z "$TEXT" ]; then
  exit 0
fi

HAS_LOCAL=false

# Check C:\ or C:/ paths
if echo "$TEXT" | grep -qiE '(C:\\\\|C:/)' ; then
  if ! echo "$TEXT" | grep -qi 'agent\.mes-wta\.com'; then
    HAS_LOCAL=true
  fi
fi

# Check /reports/xxx.html style without Cloudflare URL
if echo "$TEXT" | grep -qiE '/reports/[^ ]*\.(html|pdf|xlsx|png|jpg)' ; then
  if ! echo "$TEXT" | grep -qi 'agent\.mes-wta\.com'; then
    HAS_LOCAL=true
  fi
fi

# Check file:// protocol
if echo "$TEXT" | grep -qi 'file://' ; then
  HAS_LOCAL=true
fi

if [ "$HAS_LOCAL" = true ]; then
  cat <<'HOOK_JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "BLOCK: Reply contains local file path. Copy file to C:/MES/wta-agents/dashboard/uploads/ first, then use https://agent.mes-wta.com/uploads/<filename> in the message. Local paths are not accessible to users outside this server.",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Local file path detected in reply. Must convert to Cloudflare URL (agent.mes-wta.com/uploads/...)"
  }
}
HOOK_JSON
  exit 0
fi

exit 0
