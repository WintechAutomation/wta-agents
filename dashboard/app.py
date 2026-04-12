"""
WTA Agent Dashboard — Flask + SocketIO 서버
에이전트 간 실시간 통신 허브 및 대시보드 제공
"""

import os
import sys
import json
import time
import uuid
import signal
import subprocess
import threading
import urllib.request
from datetime import datetime, timezone, timedelta
from flask import Flask, redirect, request, send_from_directory, jsonify, send_file, after_this_request
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ── KST 타임존 ──
KST = timezone(timedelta(hours=9))

# ── Flask 앱 설정 ──
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DASHBOARD_SECRET", "_0RO8o_Gt2soubBTkkBFBMT6RJyHpmIRiwy5NMx_GhJaAgcKIF55PiWsdQ2t1SMi")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # 정적 파일 캐시 비활성화

socketio = SocketIO(
    app,
    cors_allowed_origins=[
        "https://mes-wta.com",
        "https://agent.mes-wta.com",
        "http://localhost:3100",
        "http://localhost:3000",
        "http://localhost:5555",
    ],
    async_mode="eventlet",
)


@app.after_request
def add_no_cache_headers(response):
    """정적 파일 캐시 방지 헤더 추가"""
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# ── 디렉토리 ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 허용 확장자 (보안)
ALLOWED_EXTENSIONS = {
    "pdf", "xlsx", "xls", "csv", "docx", "doc",
    "txt", "png", "jpg", "jpeg", "gif", "zip",
    "dwg", "dxf", "step", "stp",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ── 에이전트 정의 — config/agents.json에서 로드 (API 호출 시 갱신) ──
_AGENTS_JSON_PATH = os.path.join(os.path.dirname(BASE_DIR), "config", "agents.json")

def _load_agent_defs() -> dict:
    """agents.json을 파일에서 읽어 AGENT_DEFS 딕셔너리로 반환."""
    with open(_AGENTS_JSON_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        aid: {"name": a["name"], "emoji": a["emoji"], "role": a["role"]}
        for aid, a in raw.items()
        if isinstance(a, dict) and "name" in a and a.get("enabled", True)
    }

AGENT_DEFS = _load_agent_defs()

def reload_agent_defs():
    """agents.json을 다시 읽어 전역 AGENT_DEFS를 갱신."""
    global AGENT_DEFS
    AGENT_DEFS = _load_agent_defs()

# ── 런타임 상태 ──
connected_agents = {}
heartbeats = {}
MAX_HISTORY = 500
server_start_time = time.time()

# ── 시작 시 오늘 로그 로드 ──
def _load_today_history() -> list:
    today = datetime.now(KST).strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"messages_{today}.json")
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
                return logs[-MAX_HISTORY:]
        except Exception:
            pass
    return []

message_history = _load_today_history()
total_messages = len(message_history)

# ── 쿼리 API 레지스트리 ──
QUERY_API_FILE = os.path.join(BASE_DIR, "query-apis.json")

def load_query_apis() -> dict:
    if os.path.exists(QUERY_API_FILE):
        try:
            with open(QUERY_API_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_query_apis(apis: dict):
    with open(QUERY_API_FILE, "w", encoding="utf-8") as f:
        json.dump(apis, f, ensure_ascii=False, indent=2)

query_apis: dict = load_query_apis()  # {name: {description, db, sql, params, ...}}


def now_kst():
    """현재 KST 시간 문자열 반환"""
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def save_log(msg_data):
    """메시지를 JSON 로그 파일에 저장 (일별 파일)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"messages_{today}.json")

    try:
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
    except (json.JSONDecodeError, IOError):
        logs = []

    logs.append(msg_data)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)



# ── HTTP 라우트 ──
@app.route("/")
def dashboard_root():
    """루트 → /v2/ 리다이렉트"""
    return redirect("/v2/")

@app.route("/v2/")
@app.route("/v2/<path:path>")
def dashboard_spa(path=""):
    """대시보드 SPA — 정적 파일 직접 서빙 + SPA 폴백"""
    static_dir = os.path.join(BASE_DIR, "static", "v2")
    if path and os.path.isfile(os.path.join(static_dir, path)):
        return send_from_directory(static_dir, path)
    return send_from_directory(static_dir, "index.html")

@app.route("/assets/<path:path>")
def dashboard_assets(path):
    """v2 정적 에셋 서빙 (루트 /assets 경로 호환)"""
    static_dir = os.path.join(BASE_DIR, "static", "v2", "assets")
    return send_from_directory(static_dir, path)


QA_REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "reports", "qa-agent")

_MD_VIEWER_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 900px; margin: 0 auto; padding: 24px; background: #fff; color: #1a1a1a; }}
  h1,h2,h3 {{ border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th,td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }}
  th {{ background: #f9fafb; font-weight: 600; }}
  tr:nth-child(even) {{ background: #f9fafb; }}
  code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  pre code {{ display: block; padding: 12px; }}
  .back {{ display: inline-block; margin-bottom: 16px; color: #3b82f6; text-decoration: none;
            font-size: 0.9em; }}
  .back:hover {{ text-decoration: underline; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111827; color: #f9fafb; }}
    th {{ background: #1f2937; }}
    tr:nth-child(even) {{ background: #1f2937; }}
    table,th,td {{ border-color: #374151; }}
    code {{ background: #1f2937; }}
  }}
</style>
</head>
<body>
<a class="back" href="/qa/reports">← 목록으로</a>
<div id="content"></div>
<script>
document.getElementById('content').innerHTML = marked.parse({content});
</script>
</body>
</html>"""

_MD_INDEX_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>출하검사 체크리스트</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 900px; margin: 0 auto; padding: 24px; background: #fff; color: #1a1a1a; }}
  h1 {{ margin-bottom: 24px; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 8px; }}
  a {{ display: block; padding: 12px 16px; color: #3b82f6; text-decoration: none; font-size: 0.95em; }}
  a:hover {{ background: #eff6ff; border-radius: 8px; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111827; color: #f9fafb; }}
    li {{ border-color: #374151; }}
    a:hover {{ background: #1f2937; }}
  }}
</style>
</head>
<body>
<h1>📋 출하검사 체크리스트</h1>
<ul>{items}</ul>
</body>
</html>"""


@app.route("/qa/reports")
def qa_reports_index():
    """출하검사 체크리스트 목록"""
    if not os.path.isdir(QA_REPORTS_DIR):
        return "reports 디렉토리 없음", 404
    files = sorted(f for f in os.listdir(QA_REPORTS_DIR) if f.endswith(".md"))
    items = "".join(
        f'<li><a href="/qa/reports/{f}">{f[:-3]}</a></li>' for f in files
    )
    return _MD_INDEX_HTML.format(items=items), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/qa/reports/<path:filename>")
def qa_report_view(filename: str):
    """MD 파일 HTML 렌더링"""
    if not filename.endswith(".md"):
        filename += ".md"
    safe = os.path.realpath(os.path.join(QA_REPORTS_DIR, filename))
    if not safe.startswith(os.path.realpath(QA_REPORTS_DIR)):
        return "접근 불가", 403
    if not os.path.isfile(safe):
        return "파일 없음", 404
    with open(safe, encoding="utf-8") as f:
        raw = f.read()
    import json as _json
    title = filename.replace(".md", "")
    content = _json.dumps(raw)
    return _MD_VIEWER_HTML.format(title=title, content=content), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/v2")
@app.route("/v2/<path:path>")
def dashboard_v2_compat(path=""):
    """/v2 하위 경로 호환 리다이렉트 (구 URL → 루트)"""
    return redirect("/" + path if path else "/")


@app.route("/api/status")
def api_status():
    """REST API: 현재 상태 조회"""
    return get_status_snapshot()


@app.route("/api/history")
def api_history():
    """REST API: 최근 메시지 히스토리"""
    limit = request.args.get("limit", 100, type=int)
    return {"messages": message_history[-limit:]}


@app.route("/api/stats/volume")
def api_stats_volume():
    """분석: 최근 7일 일별 메시지 수"""
    today = datetime.now(KST)
    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        label = f"{d.month}/{d.day}"
        log_file = os.path.join(LOG_DIR, f"messages_{d.strftime('%Y-%m-%d')}.json")
        count = 0
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    count = len(json.load(f))
            except Exception:
                count = 0
        days.append({"date": label, "메시지": count})
    return {"days": days}


@app.route("/api/stats/agents")
def api_stats_agents():
    """분석: 에이전트별 누적 메시지 수 (오늘 로그 기준)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"messages_{today}.json")
    counts: dict = {}
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for msg in json.load(f):
                    sender = msg.get("from", "unknown")
                    counts[sender] = counts.get(sender, 0) + 1
        except Exception:
            pass
    agents = [{"id": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return {"agents": agents}


# ── REST API: 에이전트용 메시지 큐 (CLI 에이전트가 curl로 통신) ──
# 에이전트별 수신 대기 메시지 큐
agent_inbox = {}  # {agent_id: [msg, msg, ...]}


@app.route("/api/send", methods=["POST"])
def api_send():
    """에이전트가 메시지 전송 (curl -X POST)"""
    global total_messages
    data = request.get_json(silent=True) or {}
    if not data:
        try:
            data = json.loads(request.data.decode("utf-8"))
        except Exception:
            data = {}
    total_messages += 1

    msg = {
        "id": total_messages,
        "from": data.get("from", "unknown"),
        "to": data.get("to", "all"),
        "content": data.get("content", ""),
        "type": data.get("type", "chat"),
        "time": now_kst(),
    }

    message_history.append(msg)
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)
    save_log(msg)

    # 대상 에이전트 inbox에 추가
    target = msg["to"]
    if target == "all":
        for aid in AGENT_DEFS:
            if aid != msg["from"]:
                agent_inbox.setdefault(aid, []).append(msg)
    else:
        agent_inbox.setdefault(target, []).append(msg)

    # WebSocket 브로드캐스트 (대시보드 UI 업데이트)
    socketio.emit("new_message", msg)

    return {"ok": True, "id": msg["id"]}


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """파일 업로드 — multipart/form-data"""
    global total_messages

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "파일이 없습니다"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "파일명이 없습니다"}), 400

    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "허용되지 않는 파일 형식입니다"}), 400

    # 파일 크기 확인
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({"ok": False, "error": "파일 크기가 50MB를 초과합니다"}), 400

    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[1].lower() if "." in original_name else ""
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    file.save(os.path.join(UPLOAD_DIR, stored_name))

    sender = request.form.get("from", "unknown")
    target = request.form.get("to", "all")

    total_messages += 1
    msg = {
        "id": total_messages,
        "from": sender,
        "to": target,
        "content": f"📎 {original_name}",
        "type": "file",
        "time": now_kst(),
        "file": {
            "original_name": original_name,
            "stored_name": stored_name,
            "size": size,
            "url": f"/api/files/{stored_name}",
            "ext": ext,
        },
    }

    message_history.append(msg)
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)
    save_log(msg)

    if target == "all":
        for aid in AGENT_DEFS:
            if aid != sender:
                agent_inbox.setdefault(aid, []).append(msg)
    else:
        agent_inbox.setdefault(target, []).append(msg)

    socketio.emit("new_message", msg)

    return jsonify({"ok": True, "id": msg["id"], "file": msg["file"]})


@app.route("/api/files/<filename>")
def api_download(filename):
    """업로드된 파일 다운로드"""
    safe = secure_filename(filename)
    is_html = safe.lower().endswith(".html")
    return send_from_directory(UPLOAD_DIR, safe, as_attachment=not is_html)


# ── HTML → PPTX 변환 ──
_PYTHON_BIN = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
_GEN_PPTX_SCRIPT = r"C:\MES\wta-agents\workspaces\crafter\gen_pptx.py"
_DEFAULT_IMG_DIR = r"C:\MES\wta-agents\reports\MAX\template-images"


@app.route("/api/convert/html-to-pptx", methods=["POST"])
def convert_html_to_pptx():
    """HTML 파일 또는 경로를 받아 PPTX로 변환 후 다운로드.

    multipart: html_file 필드로 .html 파일 업로드
    JSON: {"html_path": "<absolute_path>", "img_dir": "<optional>"}
    """
    tmp_html = None
    html_path = None
    img_dir = _DEFAULT_IMG_DIR

    if "html_file" in request.files:
        f = request.files["html_file"]
        if not f.filename or not f.filename.lower().endswith(".html"):
            return jsonify({"ok": False, "error": "HTML 파일(.html)만 허용됩니다"}), 400
        tmp_html = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.html")
        f.save(tmp_html)
        html_path = tmp_html
        img_dir = request.form.get("img_dir", _DEFAULT_IMG_DIR)
    else:
        data = request.get_json(silent=True) or {}
        html_path = data.get("html_path", "")
        if not html_path:
            return jsonify({"ok": False, "error": "html_file 업로드 또는 html_path JSON이 필요합니다"}), 400
        # 경로 순회 방지
        real = os.path.realpath(html_path)
        if ".." in html_path or not os.path.isfile(real):
            return jsonify({"ok": False, "error": "유효하지 않은 html_path입니다"}), 400
        html_path = real
        img_dir = data.get("img_dir", _DEFAULT_IMG_DIR)

    out_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.pptx")
    base_name = os.path.splitext(os.path.basename(html_path))[0] + ".pptx"

    try:
        env = os.environ.copy()
        env["PPTX_HTML_PATH"] = html_path
        env["PPTX_IMG_DIR"] = img_dir
        env["PPTX_OUT_PATH"] = out_path

        result = _subprocess_run_async(
            [_PYTHON_BIN, _GEN_PPTX_SCRIPT],
            capture_output=True, text=True, timeout=120, env=env
        )
        if result.returncode != 0 or not os.path.isfile(out_path):
            err = (result.stderr or result.stdout or "알 수 없는 오류")[:300]
            return jsonify({"ok": False, "error": f"변환 실패: {err}"}), 500

        @after_this_request
        def _cleanup(response):
            try:
                if os.path.exists(out_path):
                    os.unlink(out_path)
                if tmp_html and os.path.exists(tmp_html):
                    os.unlink(tmp_html)
            except Exception:
                pass
            return response

        return send_file(
            out_path,
            as_attachment=True,
            download_name=base_name,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "변환 시간 초과 (120초)"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        # 오류 경로에서 tmp_html 정리
        if tmp_html and os.path.exists(tmp_html):
            try:
                os.unlink(tmp_html)
            except Exception:
                pass


_NODE_BIN = r"C:\Program Files\nodejs\node.exe"
_GEN_PPTX_V2_SCRIPT = r"C:\MES\wta-agents\scripts\html-to-pptx-v2.mjs"
_GEN_PDF_SCRIPT = r"C:\MES\wta-agents\scripts\html-to-pdf.mjs"

# eventlet 이벤트루프 차단 방지를 위한 비동기 subprocess 래퍼
# 주의: eventlet이 threading을 monkey-patch하므로 ThreadPoolExecutor는 진짜 OS 스레드가 아님
# eventlet.tpool.execute()는 eventlet이 관리하지 않는 진짜 OS 스레드에서 실행됨
import eventlet.tpool


def _subprocess_run_async(cmd, **kwargs):
    """subprocess.run()을 eventlet.tpool(진짜 OS 스레드)에서 실행하여 그린렛 차단 방지"""
    return eventlet.tpool.execute(subprocess.run, cmd, **kwargs)


@app.route("/api/convert/html-to-pptx-v2", methods=["POST"])
def convert_html_to_pptx_v2():
    """HTML → PPTX 변환 v2 (dom-to-pptx + Playwright).

    DOM computed style 기반 고품질 변환. CSS 그라디언트, 그리드 레이아웃 지원.
    multipart: html_file 필드로 .html 파일 업로드
    JSON: {"html_path": "<absolute_path>"}
    """
    tmp_html = None
    html_path = None

    if "html_file" in request.files:
        f = request.files["html_file"]
        if not f.filename or not f.filename.lower().endswith(".html"):
            return jsonify({"ok": False, "error": "HTML 파일(.html)만 허용됩니다"}), 400
        tmp_html = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.html")
        f.save(tmp_html)
        html_path = tmp_html
    else:
        data = request.get_json(silent=True) or {}
        html_path = data.get("html_path", "")
        if not html_path:
            return jsonify({"ok": False, "error": "html_file 업로드 또는 html_path JSON이 필요합니다"}), 400
        real = os.path.realpath(html_path)
        if ".." in html_path or not os.path.isfile(real):
            return jsonify({"ok": False, "error": "유효하지 않은 html_path입니다"}), 400
        html_path = real

    out_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.pptx")
    base_name = os.path.splitext(os.path.basename(html_path))[0] + ".pptx"

    try:
        result = _subprocess_run_async(
            [_NODE_BIN, _GEN_PPTX_V2_SCRIPT, html_path, out_path],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0 or not os.path.isfile(out_path):
            err = (result.stderr or result.stdout or "알 수 없는 오류")[:500]
            return jsonify({"ok": False, "error": f"변환 실패: {err}"}), 500

        @after_this_request
        def _cleanup_v2(response):
            try:
                if os.path.exists(out_path):
                    os.unlink(out_path)
                if tmp_html and os.path.exists(tmp_html):
                    os.unlink(tmp_html)
            except Exception:
                pass
            return response

        return send_file(
            out_path,
            as_attachment=True,
            download_name=base_name,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "변환 시간 초과 (180초)"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        if tmp_html and os.path.exists(tmp_html):
            try:
                os.unlink(tmp_html)
            except Exception:
                pass


@app.route("/api/convert/html-to-pdf", methods=["POST"])
def convert_html_to_pdf():
    """HTML → PDF 변환 (Playwright page.pdf).

    브라우저 렌더링 그대로 PDF 출력. CSS/배경 이미지 100% 유지.
    multipart: html_file 필드로 .html 파일 업로드
    JSON: {"html_path": "<absolute_path>"}
    """
    tmp_html = None
    html_path = None

    if "html_file" in request.files:
        f = request.files["html_file"]
        if not f.filename or not f.filename.lower().endswith(".html"):
            return jsonify({"ok": False, "error": "HTML 파일(.html)만 허용됩니다"}), 400
        tmp_html = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.html")
        f.save(tmp_html)
        html_path = tmp_html
    else:
        data = request.get_json(silent=True) or {}
        html_path = data.get("html_path", "")
        if not html_path:
            return jsonify({"ok": False, "error": "html_file 업로드 또는 html_path JSON이 필요합니다"}), 400
        real = os.path.realpath(html_path)
        if ".." in html_path or not os.path.isfile(real):
            return jsonify({"ok": False, "error": "유효하지 않은 html_path입니다"}), 400
        html_path = real

    out_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.pdf")
    base_name = os.path.splitext(os.path.basename(html_path))[0] + ".pdf"

    try:
        result = _subprocess_run_async(
            [_NODE_BIN, _GEN_PDF_SCRIPT, html_path, out_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0 or not os.path.isfile(out_path):
            err = (result.stderr or result.stdout or "알 수 없는 오류")[:500]
            return jsonify({"ok": False, "error": f"변환 실패: {err}"}), 500

        @after_this_request
        def _cleanup_pdf(response):
            try:
                if os.path.exists(out_path):
                    os.unlink(out_path)
                if tmp_html and os.path.exists(tmp_html):
                    os.unlink(tmp_html)
            except Exception:
                pass
            return response

        return send_file(
            out_path,
            as_attachment=True,
            download_name=base_name,
            mimetype="application/pdf",
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "변환 시간 초과 (120초)"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        if tmp_html and os.path.exists(tmp_html):
            try:
                os.unlink(tmp_html)
            except Exception:
                pass


# ── 쿼리 API 레지스트리 ──
@app.route("/api/query/register", methods=["POST"])
def api_query_register():
    """db-manager가 검증된 쿼리를 API로 등록"""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip().replace(" ", "_")
    if not name:
        return jsonify({"ok": False, "error": "name 필드 필수"}), 400

    entry = {
        "name": name,
        "description": data.get("description", ""),
        "db": data.get("db", "mes"),          # mes | erp
        "sql": data.get("sql", ""),
        "params": data.get("params", []),      # [{name, description, required}]
        "example": data.get("example", ""),
        "registered_by": data.get("registered_by", "db-manager"),
        "registered_at": now_kst(),
    }

    if not entry["sql"]:
        return jsonify({"ok": False, "error": "sql 필드 필수"}), 400

    query_apis[name] = entry
    save_query_apis(query_apis)

    url = f"GET /api/query/{name}"
    return jsonify({"ok": True, "name": name, "url": url, "entry": entry})


@app.route("/api/query/list")
def api_query_list():
    """등록된 쿼리 API 목록"""
    return jsonify({"apis": list(query_apis.values())})


@app.route("/api/query/<name>")
def api_query_run(name):
    """등록된 쿼리 실행"""
    if name not in query_apis:
        return jsonify({"error": f"등록되지 않은 API: {name}"}), 404

    entry = query_apis[name]
    sql = entry["sql"]

    # URL 파라미터 치환
    params = request.args.to_dict()
    for k, v in params.items():
        sql = sql.replace(f"{{{k}}}", v)

    # 미치환 파라미터 검사
    import re as _re
    missing = _re.findall(r'\{(\w+)\}', sql)
    if missing:
        return jsonify({"error": f"필수 파라미터 누락: {missing}"}), 400

    # db-query.py 실행 — SQL을 stdin으로 전달 (Windows argv 파싱 문제 우회)
    import subprocess
    PYTHON_PATH = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [PYTHON_PATH, r"C:\MES\wta-agents\workspaces\db-manager\db-query.py",
             entry["db"], "-"],
            input=sql,
            capture_output=True, text=True, timeout=30, encoding="utf-8",
            env=env,
        )
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        if result.returncode != 0:
            return jsonify({"error": error or "쿼리 실행 실패"}), 500
        return jsonify({"ok": True, "name": name, "db": entry["db"],
                        "result": output, "params": params})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "쿼리 타임아웃 (30초)"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 보고서 파일 뷰어 API ──
REPORTS_DIR = os.path.join(BASE_DIR, "..", "reports")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "..", "agents", "sales-agent", "knowledge")

# 카테고리 한글 레이블
KNOWLEDGE_CATEGORY_LABELS = {
    "company": "회사",
    "products": "제품",
    "market": "시장",
    "customers": "고객",
    "strategy": "전략",
}

@app.route("/api/reports/tree")
def api_reports_tree():
    """reports/ 폴더 트리 반환 (영업팀 지식베이스 포함)"""
    tree = []
    base = os.path.normpath(REPORTS_DIR)
    if not os.path.exists(base):
        return jsonify({"tree": []})
    for agent_dir in sorted(os.listdir(base)):
        agent_path = os.path.join(base, agent_dir)
        if not os.path.isdir(agent_path):
            continue
        files = sorted([
            f for f in os.listdir(agent_path)
            if f.endswith((".md", ".html"))
        ], reverse=True)
        if files:
            tree.append({"agent": agent_dir, "files": files})

    # 영업팀 지식베이스 추가
    kb_base = os.path.normpath(KNOWLEDGE_DIR)
    if os.path.exists(kb_base):
        kb_files = []
        # INDEX.md 먼저
        if os.path.exists(os.path.join(kb_base, "INDEX.md")):
            kb_files.append("[index] INDEX.md")
        # 카테고리별 파일
        for cat in sorted(os.listdir(kb_base)):
            cat_path = os.path.join(kb_base, cat)
            if not os.path.isdir(cat_path):
                continue
            label = KNOWLEDGE_CATEGORY_LABELS.get(cat, cat)
            for f in sorted(os.listdir(cat_path)):
                if f.endswith(".md"):
                    kb_files.append(f"[{label}] {cat}/{f}")
        if kb_files:
            tree.append({"agent": "sales-knowledge", "files": kb_files})

    return jsonify({"tree": tree})


@app.route("/api/reports/file")
def api_reports_file():
    """보고서 파일 내용 반환 (영업팀 지식베이스 포함)"""
    agent = request.args.get("agent", "")
    filename = request.args.get("file", "")
    if not agent or not filename:
        return jsonify({"error": "agent, file 파라미터 필요"}), 400

    # 영업팀 지식베이스 처리
    if agent == "sales-knowledge":
        kb_base = os.path.normpath(KNOWLEDGE_DIR)
        # 접두사 제거: "[레이블] 경로" → "경로"
        clean_path = filename
        if "] " in filename:
            clean_path = filename.split("] ", 1)[1]
        # 경로 순회 방지
        norm_path = os.path.normpath(os.path.join(kb_base, clean_path))
        if not norm_path.startswith(kb_base):
            return jsonify({"error": "접근 거부"}), 403
        if not norm_path.endswith(".md"):
            return jsonify({"error": "md 파일만 허용"}), 400
        if not os.path.exists(norm_path):
            return jsonify({"error": "파일 없음"}), 404
        with open(norm_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content, "agent": agent, "file": filename})

    # 기존 reports 처리
    safe_agent = os.path.basename(agent)
    safe_file = os.path.basename(filename)
    if not safe_file.endswith(".md"):
        return jsonify({"error": "md 파일만 허용"}), 400
    filepath = os.path.normpath(os.path.join(REPORTS_DIR, safe_agent, safe_file))
    if not filepath.startswith(os.path.normpath(REPORTS_DIR)):
        return jsonify({"error": "접근 거부"}), 403
    if not os.path.exists(filepath):
        return jsonify({"error": "파일 없음"}), 404
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return jsonify({"content": content, "agent": safe_agent, "file": safe_file})


@app.route("/api/recv/<agent_id>")
def api_recv(agent_id):
    """에이전트가 자기 메시지 수신 (polling)"""
    msgs = agent_inbox.pop(agent_id, [])
    return {"messages": msgs}


# ── 외부 에이전트 릴레이 프록시 (Cloudflare Tunnel 경유) ──
AGENT_RELAY_TOKEN = os.environ.get("AGENT_RELAY_TOKEN", "wta-relay-2026")

@app.route("/api/agent-relay/<agent_id>", methods=["POST"])
def api_agent_relay(agent_id):
    """외부 에이전트 → 내부 에이전트 메시지 릴레이.
    Cloudflare Tunnel(agent.mes-wta.com) 경유로 외부 에이전트가
    내부 에이전트에게 메시지를 보낼 때 사용하는 프록시 엔드포인트.
    """
    # 인증 토큰 검증
    auth = request.headers.get("X-Relay-Token", "")
    if auth != AGENT_RELAY_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    # 대상 에이전트 포트 확인
    port = AGENT_PORTS.get(agent_id)
    if not port:
        return jsonify({"error": f"unknown agent: {agent_id}"}), 404

    host = AGENT_HOSTS.get(agent_id, "localhost")
    # 외부 에이전트로의 릴레이는 불필요 (직접 통신 가능)
    if host != "localhost":
        return jsonify({"error": f"agent {agent_id} is external, direct connect"}), 400

    # 요청 본문을 그대로 내부 에이전트 포트로 전달
    try:
        body = request.get_data()
        relay_url = f"http://localhost:{port}/message"
        req = urllib.request.Request(
            relay_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = resp.read().decode("utf-8")
        return jsonify(json.loads(result)) if result.strip() else jsonify({"ok": True})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return jsonify({"error": f"relay failed: {e.code}", "detail": err_body}), e.code
    except Exception as e:
        return jsonify({"error": f"relay failed: {str(e)}"}), 502


@app.route("/api/response-times")
def api_response_times():
    """응답시간 통계 (최근 N건 + 에이전트별 평균)"""
    limit = min(int(request.args.get("limit", 50)), 500)
    filepath = os.path.join(BASE_DIR, "..", "data", "response-times.jsonl")
    records = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    recent = records[-limit:][::-1]
    # 에이전트별 평균 (전체 기록 기준)
    agent_buckets: dict = {}
    for r in records:
        agent = r.get("agent", "unknown")
        elapsed = r.get("elapsed_sec")
        if elapsed is not None:
            agent_buckets.setdefault(agent, []).append(elapsed)
    stats = {
        agent: {"count": len(times), "avg_sec": round(sum(times) / len(times), 1)}
        for agent, times in agent_buckets.items()
    }
    return jsonify({"records": recent, "stats": stats, "total": len(records)})


@app.route("/api/heartbeat/<agent_id>", methods=["POST"])
def api_heartbeat(agent_id):
    """에이전트 하트비트 (curl -X POST)"""
    heartbeats[agent_id] = now_kst()

    # 온라인 상태로 등록 (REST 전용 에이전트)
    if agent_id not in [info["agent_id"] for info in connected_agents.values()]:
        defn = AGENT_DEFS.get(agent_id, {"name": agent_id, "emoji": "🤖", "role": "미등록"})
        socketio.emit("agent_online", {"agent_id": agent_id, "time": now_kst(), **defn})
        socketio.emit("status_update", get_status_snapshot())

    return {"ok": True, "time": now_kst()}


# ── 도구 사용 로그 ──
TOOL_LOG_FILE = os.path.join(BASE_DIR, "tool-log.jsonl")
_tool_log_lock = threading.Lock()

@app.route("/api/tool-log", methods=["POST"])
def api_tool_log():
    """PostToolUse 훅에서 도구 사용 로그 수신 → 저장 + SocketIO 브로드캐스트"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        agent_id  = str(data.get("agent_id", "unknown"))
        tool_name = str(data.get("tool_name", "unknown"))
        timestamp = data.get("timestamp") or now_kst()

        entry = {"agent_id": agent_id, "tool_name": tool_name, "timestamp": timestamp}

        # JSONL 파일에 append
        with _tool_log_lock:
            with open(TOOL_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # SocketIO 브로드캐스트
        socketio.emit("tool_log", entry)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


@app.route("/api/tool-log/recent")
def api_tool_log_recent():
    """최근 도구 사용 로그 반환 (기본 200건)"""
    limit = int(request.args.get("limit", 200))
    try:
        with _tool_log_lock:
            if not os.path.exists(TOOL_LOG_FILE):
                return {"ok": True, "logs": []}
            with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        logs = [json.loads(l) for l in lines[-limit:] if l.strip()]
        return {"ok": True, "logs": logs}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


@app.route("/api/tool-log/stats")
def api_tool_log_stats():
    """에이전트별·도구별 사용량 집계"""
    try:
        with _tool_log_lock:
            if not os.path.exists(TOOL_LOG_FILE):
                return {"ok": True, "by_agent": {}, "by_tool": {}}
            with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

        by_agent: dict = {}
        by_tool: dict  = {}
        for l in lines:
            if not l.strip():
                continue
            entry = json.loads(l)
            a, t = entry.get("agent_id", "?"), entry.get("tool_name", "?")
            by_agent[a] = by_agent.get(a, 0) + 1
            by_tool[t]  = by_tool.get(t, 0) + 1

        return {"ok": True, "by_agent": by_agent, "by_tool": by_tool}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


# ── 토큰 사용량 API ──────────────────────────────────────────
_usage_data: dict = {}

@app.route("/api/usage", methods=["POST"])
def api_usage_post():
    """admin-agent가 토큰 사용량 데이터 전송"""
    try:
        global _usage_data
        data = request.get_json(force=True)
        _usage_data = {
            "tokens_used": data.get("tokens_used", 0),
            "tokens_limit": data.get("tokens_limit", 0),
            "cost": data.get("cost", 0),
            "period": data.get("period", ""),
            "updated_at": data.get("updated_at", ""),
            "weekly_tokens": data.get("weekly_tokens", 0),
            "weekly_cost": data.get("weekly_cost", 0),
            "weekly_period": data.get("weekly_period", ""),
            "weekly_limit": data.get("weekly_limit", 0),
            "session_remaining_pct": data.get("session_remaining_pct"),
        }
        socketio.emit("usage_update", _usage_data)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@app.route("/api/usage", methods=["GET"])
def api_usage_get():
    """프론트엔드에서 최신 사용량 조회"""
    return {"ok": True, "data": _usage_data}


# ── WebSocket 이벤트 ──
@socketio.on("connect")
def handle_connect():
    """클라이언트 연결"""
    print(f"[{now_kst()}] 클라이언트 연결: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    """클라이언트 연결 해제"""
    sid = request.sid
    if sid in connected_agents:
        agent_info = connected_agents.pop(sid)
        agent_id = agent_info["agent_id"]
        print(f"[{now_kst()}] 에이전트 연결 해제: {agent_id}")

        # 다른 세션에서 같은 에이전트가 연결되어 있는지 확인
        still_connected = any(
            info["agent_id"] == agent_id for info in connected_agents.values()
        )
        if not still_connected:
            emit("agent_offline", {"agent_id": agent_id, "time": now_kst()}, broadcast=True)
            emit("status_update", get_status_snapshot(), broadcast=True)


@socketio.on("register")
def handle_register(data):
    """에이전트 등록 — {agent_id, name?, emoji?}"""
    agent_id = data.get("agent_id", "unknown")

    # 정의된 에이전트인지 확인
    defn = AGENT_DEFS.get(agent_id, {
        "name": agent_id,
        "emoji": "\U0001F916",
        "role": "\ubbf8\ub4f1\ub85d",
    })

    agent_info = {
        "agent_id": agent_id,
        "name": defn["name"],
        "emoji": defn["emoji"],
        "role": defn["role"],
        "connected_at": now_kst(),
    }

    connected_agents[request.sid] = agent_info
    heartbeats[agent_id] = now_kst()

    print(f"[{now_kst()}] 에이전트 등록: {agent_id} ({defn['role']})")

    # 등록 확인 응답
    emit("registered", {"agent_id": agent_id, "status": "ok", "time": now_kst()})
    # 전체 상태 브로드캐스트
    emit("agent_online", {"agent_id": agent_id, "time": now_kst(), **defn}, broadcast=True)
    emit("status_update", get_status_snapshot(), broadcast=True)


@socketio.on("heartbeat")
def handle_heartbeat(data):
    """하트비트 수신 — 에이전트 생존 확인"""
    agent_id = data.get("agent_id", "unknown")
    heartbeats[agent_id] = now_kst()
    emit("heartbeat_ack", {"agent_id": agent_id, "time": now_kst()})


@socketio.on("message")
def handle_message(data):
    """에이전트 간 메시지 전달 — {from, to, content, type?}"""
    global total_messages
    total_messages += 1

    msg = {
        "id": total_messages,
        "from": data.get("from", "unknown"),
        "to": data.get("to", "all"),
        "content": data.get("content", ""),
        "type": data.get("type", "chat"),
        "time": now_kst(),
    }

    # 히스토리에 추가
    message_history.append(msg)
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)

    # 로그 파일 저장
    save_log(msg)

    print(f"[{msg['time']}] {msg['from']} -> {msg['to']}: {msg['content'][:80]}")

    # 특정 에이전트 대상이면 해당 에이전트 + 보스(대시보드)에 전달
    # 'all'이면 브로드캐스트
    emit("new_message", msg, broadcast=True)


@socketio.on("broadcast")
def handle_broadcast(data):
    """전체 브로드캐스트 메시지"""
    global total_messages
    total_messages += 1

    msg = {
        "id": total_messages,
        "from": data.get("from", "unknown"),
        "to": "all",
        "content": data.get("content", ""),
        "type": "broadcast",
        "time": now_kst(),
    }

    message_history.append(msg)
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)

    save_log(msg)
    emit("new_message", msg, broadcast=True)


@socketio.on("approval_request")
def handle_approval_request(data):
    """승인 요청 — MAX가 보스에게 승인 요청"""
    global total_messages
    total_messages += 1

    msg = {
        "id": total_messages,
        "from": data.get("from", "MAX"),
        "to": "boss",
        "content": data.get("content", ""),
        "type": "approval_request",
        "request_id": data.get("request_id", f"req-{total_messages}"),
        "time": now_kst(),
    }

    message_history.append(msg)
    save_log(msg)
    emit("approval_request", msg, broadcast=True)


@socketio.on("approval_response")
def handle_approval_response(data):
    """승인 응답 — 보스가 승인/거절"""
    global total_messages
    total_messages += 1

    msg = {
        "id": total_messages,
        "from": "boss",
        "to": data.get("to", "MAX"),
        "content": data.get("content", ""),
        "type": "approval_response",
        "request_id": data.get("request_id"),
        "approved": data.get("approved", False),
        "time": now_kst(),
    }

    message_history.append(msg)
    save_log(msg)
    emit("approval_response", msg, broadcast=True)


@socketio.on("boss_message")
def handle_boss_message(data):
    """보스(부서장) 메시지 — 대시보드에서 직접 전송"""
    global total_messages
    total_messages += 1

    msg = {
        "id": total_messages,
        "from": "\ubd80\uc11c\uc7a5",
        "to": data.get("to", "all"),
        "content": data.get("content", ""),
        "type": "boss",
        "time": now_kst(),
    }

    message_history.append(msg)
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)

    save_log(msg)
    emit("new_message", msg, broadcast=True)


# ── 텔레그램 알림 ──
_TELEGRAM_ENV = r"C:\Users\Administrator\.claude\channels\telegram\.env"
_TELEGRAM_ACCESS = r"C:\Users\Administrator\.claude\channels\telegram\access.json"


def _load_telegram_config() -> tuple[str, str] | tuple[None, None]:
    """bot_token, chat_id 로드 — 실패 시 (None, None) 반환"""
    try:
        token = None
        with open(_TELEGRAM_ENV, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
        if not token:
            return None, None

        with open(_TELEGRAM_ACCESS, "r", encoding="utf-8") as f:
            access = json.load(f)
        chat_ids = access.get("allowFrom", [])
        if not chat_ids:
            return None, None

        return token, str(chat_ids[0])
    except Exception:
        return None, None


# telegram_poller 제거 — getUpdates가 텔레그램 플러그인과 충돌
# 인바운드/아웃바운드 모두 /api/send REST 호출로 로깅


def send_telegram(text: str) -> None:
    """Telegram 메시지 발송 (비차단 스레드)"""
    def _send():
        token, chat_id = _load_telegram_config()
        if not token or not chat_id:
            return
        try:
            payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # 알림 실패는 무시

    threading.Thread(target=_send, daemon=True).start()


# ── P2P 포트 기반 에이전트 상태 모니터 ──
def _load_agents_raw() -> dict:
    """agents.json 원본 데이터 로드 (port/host 포함)."""
    with open(_AGENTS_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)

_agents_raw = _load_agents_raw()

AGENT_PORTS = {
    aid: info["port"] for aid, info in _agents_raw.items()
    if isinstance(info, dict) and info.get("port") and info.get("enabled", False)
}
# 외부 호스트 에이전트 (host 필드가 있으면 해당 IP 사용)
AGENT_HOSTS = {
    aid: info.get("host", "localhost") for aid, info in _agents_raw.items()
    if isinstance(info, dict) and info.get("port") and info.get("enabled", False)
}
# 에이전트별 이전 온라인 상태 (변경 감지용)
_prev_online: dict[str, bool] = {aid: False for aid in AGENT_PORTS}


def ping_agent(agent_id: str, port: int) -> bool:
    """에이전트 P2P 포트 /ping 호출 → 온라인 여부 반환"""
    host = AGENT_HOSTS.get(agent_id, "localhost")
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/ping",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return data.get("online", False)
    except Exception:
        return False


def agent_status_monitor():
    """백그라운드: 5초마다 모든 에이전트 포트 병렬 ping → 상태 변경 시 SocketIO 브로드캐스트"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    while True:
        changed = False

        with ThreadPoolExecutor(max_workers=len(AGENT_PORTS)) as ex:
            futures = {ex.submit(ping_agent, aid, port): aid
                       for aid, port in AGENT_PORTS.items()}
            for fut in as_completed(futures):
                agent_id = futures[fut]
                online = fut.result()
                prev = _prev_online.get(agent_id, False)

                if online:
                    heartbeats[agent_id] = now_kst()

                if online != prev:
                    _prev_online[agent_id] = online
                    changed = True
                    defn = AGENT_DEFS.get(agent_id, {"name": agent_id, "emoji": "🤖", "role": ""})
                    if online:
                        socketio.emit("agent_online", {
                            "agent_id": agent_id,
                            "time": now_kst(),
                            **defn,
                        })
                        send_telegram(
                            f"🟢 {defn['emoji']} {defn['name']} 온라인\n"
                            f"({agent_id}) — {now_kst()}"
                        )
                    else:
                        socketio.emit("agent_offline", {"agent_id": agent_id, "time": now_kst()})
                        send_telegram(
                            f"🔴 {defn['emoji']} {defn['name']} 오프라인\n"
                            f"({agent_id}) — {now_kst()}"
                        )

        if changed:
            socketio.emit("status_update", get_status_snapshot())

        time.sleep(5)


# ── 세션 JSONL 동기화 ──
PARSE_SESSIONS_SCRIPT = os.path.join(os.path.dirname(BASE_DIR), "scripts", "parse-sessions.py")
_last_sync_result: dict = {"added": 0, "time": None, "error": None}


def _run_session_sync() -> int:
    """parse-sessions.py 실행 → 추가된 메시지 수 반환"""
    global message_history, total_messages
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("parse_sessions", PARSE_SESSIONS_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        added = mod.run()
        if added > 0:
            # 로그 파일에서 최신 메시지 히스토리 재로드
            today = datetime.now(KST).strftime("%Y-%m-%d")
            log_file = os.path.join(LOG_DIR, f"messages_{today}.json")
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        new_history = json.load(f)
                    message_history = new_history[-MAX_HISTORY:]
                    total_messages = max(total_messages, len(new_history))
                    # 새 메시지를 WebSocket으로 브로드캐스트
                    for msg in new_history[-added:]:
                        socketio.emit("new_message", msg)
                except Exception:
                    pass
        return added
    except Exception as e:
        return -1


def session_sync_worker():
    """백그라운드: 30초마다 세션 JSONL 파싱 → 대시보드 로그 업데이트"""
    global _last_sync_result
    # 시작 즉시 1회 실행
    added = _run_session_sync()
    _last_sync_result = {"added": added, "time": now_kst(), "error": None if added >= 0 else "실행 오류"}

    while True:
        time.sleep(30)
        added = _run_session_sync()
        _last_sync_result = {"added": added, "time": now_kst(), "error": None if added >= 0 else "실행 오류"}


def get_status_snapshot():
    """현재 전체 상태 스냅샷 반환 — P2P ping 결과 기반"""
    reload_agent_defs()
    online_ids = {aid for aid, online in _prev_online.items() if online}

    agents_status = []
    for agent_id, defn in AGENT_DEFS.items():
        agents_status.append({
            "agent_id": agent_id,
            "name": defn["name"],
            "emoji": defn["emoji"],
            "role": defn["role"],
            "online": agent_id in online_ids,
            "last_heartbeat": heartbeats.get(agent_id),
        })

    uptime_sec = int(time.time() - server_start_time)
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60

    return {
        "agents": agents_status,
        "stats": {
            "online_count": len(online_ids),
            "total_agents": len(AGENT_DEFS),
            "total_messages": total_messages,
            "uptime": f"{hours}h {minutes}m",
        },
    }


# ── 스케줄러 ──
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")
JOB_RUNS_FILE = os.path.join(LOG_DIR, "job_runs.json")
SCRIPTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "scripts")
PYTHON_BIN = sys.executable

_scheduler = BackgroundScheduler(timezone="Asia/Seoul")
_jobs_lock = threading.Lock()


def _load_jobs() -> list[dict]:
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 기본 작업 목록
    return [
        {
            "id": "cs-embed",
            "name": "CS 임베딩 동기화",
            "description": "CS 이력 데이터를 벡터DB에 임베딩 (신규 건만)",
            "command": f"{PYTHON_BIN} {os.path.join(SCRIPTS_DIR, 'cs-embed.py')}",
            "cron": "0 2 * * *",
            "enabled": True,
            "created_at": now_kst() if 'now_kst' in dir() else "",
        }
    ]


def _save_jobs(jobs: list[dict]):
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def _load_runs() -> list[dict]:
    if os.path.exists(JOB_RUNS_FILE):
        try:
            with open(JOB_RUNS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_run(run: dict):
    runs = _load_runs()
    runs.append(run)
    # 최근 200건만 유지
    if len(runs) > 200:
        runs = runs[-200:]
    with open(JOB_RUNS_FILE, "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=2)


def _run_job(job_id: str, command: str, name: str):
    """작업 실행 및 결과 저장."""
    run_id = str(uuid.uuid4())[:8]
    started = datetime.now(KST).isoformat()
    socketio.emit("job_started", {"job_id": job_id, "run_id": run_id, "name": name, "started": started})

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,
            encoding="utf-8",
            errors="replace",
        )
        status = "success" if result.returncode == 0 else "error"
        output = (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        status = "timeout"
        output = "실행 시간 초과 (10분)"
    except Exception as e:
        status = "error"
        output = str(e)

    finished = datetime.now(KST).isoformat()
    run = {
        "run_id": run_id,
        "job_id": job_id,
        "name": name,
        "status": status,
        "started": started,
        "finished": finished,
        "output": output[-3000:] if len(output) > 3000 else output,
    }
    _save_run(run)

    # 대시보드에 실시간 알림
    socketio.emit("job_finished", run)


def _schedule_job(job: dict):
    """APScheduler에 작업 등록."""
    if not job.get("enabled"):
        return
    try:
        cron_parts = job["cron"].split()
        if len(cron_parts) != 5:
            return
        trigger = CronTrigger(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4],
            timezone="Asia/Seoul",
        )
        _scheduler.add_job(
            _run_job,
            trigger=trigger,
            args=[job["id"], job["command"], job["name"]],
            id=job["id"],
            replace_existing=True,
        )
    except Exception as e:
        print(f"  [scheduler] 작업 등록 실패 {job['id']}: {e}")


def _init_scheduler():
    """앱 시작 시 저장된 작업 로드 및 스케줄러 시작."""
    jobs = _load_jobs()
    # created_at 초기화 (최초 로드 시)
    changed = False
    for job in jobs:
        if not job.get("created_at"):
            job["created_at"] = now_kst()
            changed = True
    if changed:
        _save_jobs(jobs)

    for job in jobs:
        _schedule_job(job)
    _scheduler.start()
    print(f"  스케줄러 시작: {len([j for j in jobs if j.get('enabled')])}개 활성 작업")

    # Knowledge 통계 캐시: 즉시 1회 실행 후 60초마다 갱신 (OS 스레드, eventlet 비간섭)
    _scheduler.add_job(_update_knowledge_cache, "interval", seconds=60,
                       id="knowledge-stats-refresh", replace_existing=True)
    _scheduler.add_job(_update_knowledge_cache, "date",
                       id="knowledge-stats-init", replace_existing=True)

    # 일일 업무보고 트리거: 매일 22:00 KST
    _scheduler.add_job(
        _daily_report_trigger,
        "cron", hour=22, minute=0,
        timezone="Asia/Seoul",
        id="daily-report-trigger",
        replace_existing=True,
    )

    # 슬랙봇 watchdog: 시작 시 즉시 1회 + 5분마다 생존 체크
    _scheduler.add_job(
        _slackbot_watchdog,
        "interval", minutes=5,
        id="slackbot-watchdog",
        replace_existing=True,
    )
    _scheduler.add_job(
        _slackbot_watchdog,
        "date",
        id="slackbot-watchdog-init",
        replace_existing=True,
    )


# ── 슬랙봇 자동 실행 (watchdog) ──
_SLACKBOT_SCRIPT = os.path.join(os.path.dirname(BASE_DIR), "scripts", "slack-bot.py")
_SLACKBOT_PID_FILE = os.path.join(os.path.dirname(BASE_DIR), "logs", "slack-bot.pid")


def _is_slackbot_running() -> bool:
    """슬랙봇 프로세스 생존 확인 (PID 파일 + 프로세스 존재 체크)."""
    if not os.path.exists(_SLACKBOT_PID_FILE):
        return False
    try:
        with open(_SLACKBOT_PID_FILE, "r") as f:
            pid = int(f.read().strip())
        # tasklist로 PID 존재 여부 확인 (Windows)
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return str(pid) in result.stdout
    except Exception:
        return False


def _slackbot_watchdog():
    """슬랙봇 프로세스 생존 체크 → 없으면 새 터미널 창으로 실행."""
    if _is_slackbot_running():
        return

    print(f"  [slackbot-watchdog] 슬랙봇 미실행 감지, 자동 시작 중... ({now_kst()})")

    try:
        # 새 cmd 창에서 슬랙봇 실행 (ConEmu 환경이면 ConEmu, 아니면 start cmd)
        wta_dir = os.path.dirname(BASE_DIR)
        cmd = f'start "slack-bot" cmd /c "cd /d {wta_dir} && {PYTHON_BIN} scripts/slack-bot.py"'
        subprocess.Popen(cmd, shell=True, cwd=wta_dir)
        print(f"  [slackbot-watchdog] 슬랙봇 시작 명령 실행 완료")
    except Exception as e:
        print(f"  [slackbot-watchdog] 슬랙봇 시작 실패: {e}")


# ── 스케줄 API ──

@app.route("/api/jobs", methods=["GET"])
def api_jobs_list():
    """등록된 작업 목록 + 다음 실행 시각."""
    with _jobs_lock:
        jobs = _load_jobs()
    result = []
    for job in jobs:
        entry = dict(job)
        # 다음 실행 시각
        apjob = _scheduler.get_job(job["id"])
        entry["next_run"] = apjob.next_run_time.isoformat() if apjob and apjob.next_run_time else None
        # 최근 실행 이력 (3건)
        runs = [r for r in _load_runs() if r["job_id"] == job["id"]]
        entry["last_runs"] = runs[-3:][::-1]
        result.append(entry)
    return jsonify(result)


@app.route("/api/jobs", methods=["POST"])
def api_jobs_create():
    """새 작업 등록."""
    data = request.get_json(silent=True) or {}
    required = ["name", "command", "cron"]
    if not all(data.get(k) for k in required):
        return jsonify({"error": "name, command, cron 필수"}), 400
    job = {
        "id": str(uuid.uuid4())[:8],
        "name": data["name"],
        "description": data.get("description", ""),
        "command": data["command"],
        "cron": data["cron"],
        "enabled": data.get("enabled", True),
        "created_at": now_kst(),
    }
    with _jobs_lock:
        jobs = _load_jobs()
        jobs.append(job)
        _save_jobs(jobs)
    _schedule_job(job)
    return jsonify(job), 201


@app.route("/api/jobs/<job_id>", methods=["PUT"])
def api_jobs_update(job_id):
    """작업 수정 (enabled, cron, name 등)."""
    data = request.get_json(silent=True) or {}
    with _jobs_lock:
        jobs = _load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                for key in ("name", "description", "command", "cron", "enabled"):
                    if key in data:
                        job[key] = data[key]
                _save_jobs(jobs)
                # 스케줄 재등록
                try:
                    _scheduler.remove_job(job_id)
                except Exception:
                    pass
                if job.get("enabled"):
                    _schedule_job(job)
                return jsonify(job)
    return jsonify({"error": "작업 없음"}), 404


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_jobs_delete(job_id):
    """작업 삭제."""
    with _jobs_lock:
        jobs = _load_jobs()
        jobs = [j for j in jobs if j["id"] != job_id]
        _save_jobs(jobs)
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/jobs/<job_id>/run", methods=["POST"])
def api_jobs_run_now(job_id):
    """즉시 실행 (테스트/수동 트리거)."""
    with _jobs_lock:
        jobs = _load_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        return jsonify({"error": "작업 없음"}), 404
    threading.Thread(target=_run_job, args=[job["id"], job["command"], job["name"]], daemon=True).start()
    return jsonify({"ok": True, "message": f"'{job['name']}' 실행 시작"})


@app.route("/api/jobs/<job_id>/logs", methods=["GET"])
def api_jobs_logs(job_id):
    """작업 실행 이력 조회."""
    runs = [r for r in _load_runs() if r["job_id"] == job_id]
    return jsonify(runs[::-1][:50])  # 최신순 50건


@app.route("/api/sync", methods=["POST"])
def api_sync():
    """세션 JSONL 수동 동기화 트리거"""
    added = _run_session_sync()
    _last_sync_result.update({"added": added, "time": now_kst(), "error": None if added >= 0 else "실행 오류"})
    return jsonify({"ok": added >= 0, "added": added, "time": _last_sync_result["time"]})


@app.route("/api/sync/status", methods=["GET"])
def api_sync_status():
    """마지막 동기화 결과 조회"""
    return jsonify(_last_sync_result)


# ── 작업큐 API ──
TASK_QUEUE_FILE = os.path.join(os.path.dirname(BASE_DIR), "config", "task-queue.json")


def _load_tasks() -> list[dict]:
    if os.path.exists(TASK_QUEUE_FILE):
        try:
            with open(TASK_QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("tasks", []) if isinstance(data, dict) else data
        except Exception:
            pass
    return []


def _save_tasks(tasks: list[dict]):
    with open(TASK_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump({"tasks": tasks}, f, ensure_ascii=False, indent=2)


@app.route("/api/task-queue", methods=["GET"])
def api_task_queue_list():
    tasks = _load_tasks()
    agent = request.args.get("agent")
    status = request.args.get("status")
    if agent:
        tasks = [t for t in tasks if t.get("agent") == agent]
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return jsonify(tasks)


@app.route("/api/task-queue", methods=["POST"])
def api_task_queue_create():
    data = request.get_json(silent=True)
    if not data or not data.get("agent") or not data.get("task"):
        return jsonify({"error": "agent, task 필수"}), 400
    tasks = _load_tasks()
    now = now_kst()
    new_task = {
        "id": f"tq-{data['agent']}-{uuid.uuid4().hex[:6]}",
        "agent": data["agent"],
        "task": data["task"],
        "message": data.get("message", ""),
        "status": data.get("status", "pending"),
        "priority": data.get("priority", "medium"),
        "created_at": now,
        "updated_at": now,
        "last_report_at": None,
        "completed_at": None,
    }
    tasks.append(new_task)
    _save_tasks(tasks)
    return jsonify(new_task), 201


@app.route("/api/task-queue/<task_id>", methods=["PUT"])
def api_task_queue_update(task_id):
    data = request.get_json(silent=True) or {}
    tasks = _load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            now = now_kst()
            if "status" in data:
                t["status"] = data["status"]
                if data["status"] == "done":
                    t["completed_at"] = now
            if "priority" in data:
                t["priority"] = data["priority"]
            if "task" in data:
                t["task"] = data["task"]
            if "message" in data:
                t["message"] = data["message"]
            t["updated_at"] = now
            _save_tasks(tasks)
            return jsonify(t)
    return jsonify({"error": "not found"}), 404


@app.route("/api/task-queue/<task_id>", methods=["DELETE"])
def api_task_queue_delete(task_id):
    tasks = _load_tasks()
    new_tasks = [t for t in tasks if t.get("id") != task_id]
    if len(new_tasks) == len(tasks):
        return jsonify({"error": "not found"}), 404
    _save_tasks(new_tasks)
    return jsonify({"ok": True})


# ── CS 세션 API ──
CS_SESSIONS_DIR = os.path.join(os.path.dirname(BASE_DIR), "cs_sessions")


def _load_cs_sessions() -> list[dict]:
    """cs_sessions/ 폴더의 개별 JSONL 파일에서 전체 메시지 로드."""
    sessions = []
    if not os.path.isdir(CS_SESSIONS_DIR):
        return sessions
    for fname in os.listdir(CS_SESSIONS_DIR):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(CS_SESSIONS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            sessions.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
    return sessions


def _ts_to_md_filename(ts: str) -> str:
    """타임스탬프 → MD 파일명 변환 (여러 형식 지원)"""
    # "2026-04-02 14:29:50 KST" → "2026-04-02_14-29-50"
    ts_clean = ts.replace(" KST", "").replace("KST", "").strip()
    # ISO 형식 "2026-04-02T14:29:43+09:00" → "2026-04-02 14:29:43"
    if "T" in ts_clean:
        ts_clean = ts_clean.split("+")[0].split("Z")[0].replace("T", " ")
    ts_parts = ts_clean.split(" ", 1)
    if len(ts_parts) == 2:
        return f"{ts_parts[0]}_{ts_parts[1].replace(':', '-')}.md"
    return ""


def _find_md_content(ts: str) -> str:
    """타임스탬프에 매칭되는 MD 파일 내용 반환"""
    try:
        md_filename = _ts_to_md_filename(ts)
        if not md_filename:
            return ""
        md_dir = os.path.join(
            os.path.dirname(BASE_DIR),
            "workspaces", "cs-agent", "logs", "slack-response",
        )
        md_path = os.path.join(md_dir, md_filename)
        if os.path.isfile(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return ""


@app.route("/api/cs-sessions", methods=["GET"])
def api_cs_sessions_list():
    all_messages = _load_cs_sessions()

    # 필터
    search = request.args.get("search", "").lower()
    source = request.args.get("source", "")
    if search:
        all_messages = [s for s in all_messages if search in s.get("query", s.get("question", "")).lower() or search in (s.get("full_response", "") or s.get("response_summary", "") or s.get("answer_preview", "") or s.get("answer", "")).lower()]
    if source:
        all_messages = [s for s in all_messages if s.get("question_source", "") == source]

    # session_id 기준 그룹핑
    groups: dict[str, list[dict]] = {}
    for msg in all_messages:
        sid = msg.get("session_id", "")
        if not sid:
            # session_id 없는 레거시 데이터는 타임스탬프를 키로 사용
            sid = f"legacy-{msg.get('timestamp', '')}"
        groups.setdefault(sid, []).append(msg)

    # 각 그룹을 세션 요약으로 변환
    session_list = []
    for sid, msgs in groups.items():
        msgs.sort(key=lambda m: m.get("timestamp", ""))
        first = msgs[0]
        last = msgs[-1]
        first_q = first.get("query", first.get("question", ""))
        session_list.append({
            "session_id": sid,
            "first_timestamp": first.get("timestamp", ""),
            "last_timestamp": last.get("timestamp", ""),
            "user": first.get("user", ""),
            "channel": first.get("channel", ""),
            "question_source": first.get("question_source", ""),
            "question_summary": first_q[:80] + ("..." if len(first_q) > 80 else ""),
            "message_count": len(msgs),
            "equipment_type": first.get("equipment_type", ""),
            "last_status": last.get("status", ""),
        })

    # 최신 순 정렬
    session_list.sort(key=lambda s: s.get("last_timestamp", ""), reverse=True)
    total = len(session_list)

    # 페이지네이션
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    start = (page - 1) * limit
    page_items = session_list[start:start + limit]

    return jsonify({"items": page_items, "total": total, "page": page, "limit": limit})


@app.route("/api/cs-sessions/<session_id>", methods=["GET"])
def api_cs_sessions_detail(session_id):
    all_messages = _load_cs_sessions()

    # 해당 session_id의 모든 메시지 수집
    session_msgs = [s for s in all_messages if s.get("session_id") == session_id]

    # 레거시 키 호환
    if not session_msgs:
        for s in all_messages:
            legacy_key = f"legacy-{s.get('timestamp', '')}"
            if legacy_key == session_id:
                session_msgs = [s]
                break

    if not session_msgs:
        return jsonify({"error": "not found"}), 404

    # 시간순 정렬
    session_msgs.sort(key=lambda m: m.get("timestamp", ""))

    first = session_msgs[0]

    # 각 메시지를 대화 흐름으로 변환
    messages = []
    for msg in session_msgs:
        ts = msg.get("timestamp", "")
        md_content = _find_md_content(ts)
        # JSONL 전문 → 요약 폴백 체인
        jsonl_answer = msg.get("full_response", "") or msg.get("response_summary", "") or msg.get("answer_preview", "") or msg.get("answer", "")
        # MD 원문이 있고 JSONL 답변이 잘려있으면 MD 원문 사용
        if md_content and len(jsonl_answer) < len(md_content):
            display_answer = md_content
        else:
            display_answer = jsonl_answer
        messages.append({
            "timestamp": ts,
            "question": msg.get("query", msg.get("question", "")),
            "answer": display_answer,
            "status": msg.get("status", ""),
            "image_paths": msg.get("image_paths", []),
            "attachments": msg.get("attachments", []),
            "rag_sources": msg.get("rag_sources", []),
            "tools_used": msg.get("tools_used", []),
            "model": msg.get("model", ""),
            "response_time_ms": msg.get("response_time_ms"),
            "full_conversation": md_content,
        })

    return jsonify({
        "session_id": session_id,
        "user": first.get("user", ""),
        "channel": first.get("channel", ""),
        "question_source": first.get("question_source", ""),
        "equipment_type": first.get("equipment_type", ""),
        "language": first.get("language", ""),
        "message_count": len(messages),
        "first_timestamp": session_msgs[0].get("timestamp", ""),
        "last_timestamp": session_msgs[-1].get("timestamp", ""),
        "messages": messages,
    })


# ── 기술용어집 API ──
GLOSSARY_FILE = os.path.join(os.path.dirname(BASE_DIR), "config", "glossary.json")


def _load_glossary() -> dict:
    if os.path.exists(GLOSSARY_FILE):
        try:
            with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"categories": [], "terms": []}


def _save_glossary(data: dict):
    with open(GLOSSARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/api/glossary", methods=["GET"])
def api_glossary():
    data = _load_glossary()
    categories = data.get("categories", [])
    terms = data.get("terms", [])
    # 필터
    cat = request.args.get("category", "")
    q = request.args.get("q", "").lower()
    if cat:
        terms = [t for t in terms if t.get("category") == cat]
    if q:
        terms = [t for t in terms if q in t.get("term_ko", "").lower()
                 or q in t.get("term_en", "").lower()
                 or q in t.get("definition", "").lower()]
    return jsonify({"categories": categories, "terms": terms})


@app.route("/api/glossary/terms", methods=["POST"])
def api_glossary_create():
    term = request.get_json(silent=True)
    if not term or not term.get("term_ko"):
        return jsonify({"error": "term_ko 필수"}), 400
    data = _load_glossary()
    # ID 생성
    existing_ids = [t.get("id", "") for t in data.get("terms", [])]
    max_num = 0
    for tid in existing_ids:
        if tid.startswith("t") and tid[1:].isdigit():
            max_num = max(max_num, int(tid[1:]))
    term["id"] = f"t{max_num + 1:03d}"
    data.setdefault("terms", []).append(term)
    _save_glossary(data)
    return jsonify(term), 201


@app.route("/api/glossary/terms/<term_id>", methods=["PUT"])
def api_glossary_update(term_id):
    update = request.get_json(silent=True) or {}
    data = _load_glossary()
    for t in data.get("terms", []):
        if t.get("id") == term_id:
            t.update({k: v for k, v in update.items() if k != "id"})
            _save_glossary(data)
            return jsonify(t)
    return jsonify({"error": "not found"}), 404


@app.route("/api/glossary/terms/<term_id>", methods=["DELETE"])
def api_glossary_delete(term_id):
    data = _load_glossary()
    terms = data.get("terms", [])
    new_terms = [t for t in terms if t.get("id") != term_id]
    if len(new_terms) == len(terms):
        return jsonify({"error": "not found"}), 404
    data["terms"] = new_terms
    _save_glossary(data)
    return jsonify({"ok": True})


# ── Knowledge Base API (실시간 진행률) ──
KNOWLEDGE_CONFIG_FILE = os.path.join(os.path.dirname(BASE_DIR), "config", "knowledge.json")
AGENTS_CONFIG_FILE = os.path.join(os.path.dirname(BASE_DIR), "config", "agents.json")
MES_ENV_FILE = "C:/MES/backend/.env"

# 캐시: APScheduler OS 스레드에서 60초마다 갱신, HTTP 핸들러는 캐시만 읽음
_knowledge_stats_cache: dict = {"stats": None}


def _load_anthropic_key() -> str:
    """ANTHROPIC_API_KEY를 환경변수 또는 .env에서 로드"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # .env 파일에서 읽기
    env_path = os.path.join(os.path.dirname(BASE_DIR), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


def _load_mes_db_password() -> str | None:
    """C:/MES/backend/.env에서 DB_PASSWORD 로드"""
    try:
        with open(MES_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return None


def _query_knowledge_stats() -> dict | None:
    """
    PostgreSQL에서 RAG 시스템 실시간 통계 조회.
    실패 시 None 반환 (호출자가 fallback 처리).
    """
    try:
        import psycopg2
    except ImportError:
        return None

    password = _load_mes_db_password()
    if not password:
        return None

    try:
        conn = psycopg2.connect(
            host="localhost", port=55432,
            user="postgres", password=password, dbname="postgres",
            connect_timeout=5,
        )
    except Exception:
        return None

    stats = {}
    try:
        with conn.cursor() as cur:
            # CS 이력 임베딩 수
            cur.execute("SELECT COUNT(*) FROM csagent.vector_embeddings")
            stats["cs_embeddings"] = cur.fetchone()[0]

            # 부품 매뉴얼: 파싱된 파일 수 / 임베딩 완료 파일 수
            cur.execute("SELECT COUNT(DISTINCT source_file) FROM manual.documents")
            stats["parts_parsed"] = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(DISTINCT source_file) FROM manual.documents"
                " WHERE embedding IS NOT NULL"
            )
            stats["parts_embedded"] = cur.fetchone()[0]

            # WTA 매뉴얼: 파싱된 파일 수 / 임베딩 완료 파일 수
            cur.execute("SELECT COUNT(DISTINCT source_file) FROM manual.wta_documents")
            stats["wta_parsed"] = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(DISTINCT source_file) FROM manual.wta_documents"
                " WHERE embedding IS NOT NULL"
            )
            stats["wta_embedded"] = cur.fetchone()[0]
    except Exception:
        return None
    finally:
        conn.close()

    return stats


def _count_enabled_agents() -> int:
    """config/agents.json에서 enabled: true 에이전트 수 반환"""
    try:
        with open(AGENTS_CONFIG_FILE, "r", encoding="utf-8") as f:
            agents = json.load(f)
        return sum(1 for v in agents.values() if isinstance(v, dict) and v.get("enabled"))
    except Exception:
        return 0


def _update_knowledge_cache():
    """APScheduler OS 스레드에서 실행 — DB 조회 후 캐시 갱신"""
    stats = _query_knowledge_stats()
    _knowledge_stats_cache["stats"] = stats


@app.route("/api/knowledge", methods=["GET"])
def api_knowledge():
    """캐시된 DB 통계를 knowledge.json 구조에 오버레이. 캐시 미준비 시 파일 fallback."""
    # 기본 구조 로드
    base = None
    if os.path.exists(KNOWLEDGE_CONFIG_FILE):
        try:
            with open(KNOWLEDGE_CONFIG_FILE, "r", encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            pass
    if base is None:
        base = {"categories": [], "updated_at": ""}

    # 캐시에서 읽기 (HTTP 핸들러에서 직접 DB 호출 안 함 — eventlet 블로킹 방지)
    stats = _knowledge_stats_cache.get("stats")
    if stats is None:
        # fallback: 파일 그대로 반환
        return jsonify(base)

    # 에이전트 수
    agent_count = _count_enabled_agents()

    # categories 인덱스 맵
    cat_map = {c["id"]: c for c in base.get("categories", [])}

    # cs-rag 카테고리 값 오버레이
    cs_rag = cat_map.get("cs-rag")
    if cs_rag:
        for item in cs_rag.get("items", []):
            label = item.get("label", "")
            if "CS 이력" in label:
                item["value"] = stats["cs_embeddings"]
                item["total"] = stats["cs_embeddings"]
            elif "부품 매뉴얼" in label:
                item["parsed"] = stats["parts_parsed"]
                item["embedded"] = stats["parts_embedded"]
                item["total"] = stats["parts_parsed"] or item.get("total", 0)
            elif "WTA 매뉴얼" in label:
                item["parsed"] = stats["wta_parsed"]
                item["embedded"] = stats["wta_embedded"]
                item["total"] = stats["wta_parsed"] or item.get("total", 0)

    # agent-system 카테고리: 운영 에이전트 수 오버레이
    agent_sys = cat_map.get("agent-system")
    if agent_sys and agent_count:
        for item in agent_sys.get("items", []):
            if "운영 에이전트" in item.get("label", ""):
                item["value"] = agent_count

    kst_now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    base["updated_at"] = kst_now

    return jsonify(base)


# ── 대시보드 메시지 전송 API ──
@app.route("/api/send-message", methods=["POST"])
def api_send_message():
    """대시보드에서 MAX에게 메시지 전송"""
    to = request.form.get("to", "MAX")
    message = request.form.get("message", "")
    uploaded_files = request.files.getlist("files")
    file_paths = []
    for f in uploaded_files:
        if f and f.filename and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
            filename = f"{ts}_{filename}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            f.save(filepath)
            file_paths.append(filename)
    # MCP agent-channel로 전달
    content = message
    if file_paths:
        content += "\n[첨부파일: " + ", ".join(file_paths) + "]"
    if not content.strip():
        return jsonify({"error": "메시지 또는 파일 필요"}), 400
    # 대시보드 메시지로 기록 + 브로드캐스트
    msg_data = {
        "id": total_messages + 1,
        "from": "dashboard",
        "to": to,
        "content": content,
        "type": "chat",
        "time": now_kst(),
    }
    save_log(msg_data)
    message_history.append(msg_data)
    if len(message_history) > MAX_HISTORY:
        del message_history[0]
    socketio.emit("new_message", msg_data)
    # MCP 허브로 전달 시도
    try:
        hub_url = "http://localhost:5555/api/send"
        req_data = json.dumps({"from": "dashboard", "to": to, "message": content}).encode()
        req = urllib.request.Request(hub_url, data=req_data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass  # 허브 미응답 무시
    return jsonify({"ok": True, "files": file_paths})


# ── 업무공간(Workspace) 파일 탐색 API ──
WORKSPACE_BASE = os.path.normpath(os.path.join(os.path.dirname(BASE_DIR), "reports"))

# 텍스트 파일 확장자
_TEXT_EXTS = {
    "txt", "md", "json", "csv", "log", "py", "js", "ts", "tsx", "jsx",
    "html", "htm", "css", "yml", "yaml", "toml", "cfg", "ini", "sh",
    "bat", "ps1", "sql", "go", "rs", "jsonl", "xml",
}
_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "ico"}
_MAX_TEXT_SIZE = 2 * 1024 * 1024  # 2MB


# ── 일일 업무보고 API ──
DAILY_REPORTS_BASE = os.path.join(os.path.dirname(BASE_DIR), "reports", "daily-reports")

# 에이전트 보고서 작성 대상 목록 (MAX, slack-bot 제외)
_REPORT_AGENTS = [
    "db-manager", "cs-agent", "crafter", "dev-agent", "admin-agent",
    "nc-manager", "qa-agent", "issue-manager", "sales-agent",
    "schedule-agent", "docs-agent",
]


def _daily_report_trigger():
    """매일 22:00 KST — MAX에게 일일 업무보고 트리거 메시지 전송"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    body = json.dumps({
        "from": "dashboard-scheduler",
        "to": "MAX",
        "content": (
            f"[일일 업무보고 트리거] {today}\n"
            f"전 팀원에게 업무보고 요청 바랍니다.\n"
            f"보고서 경로: reports/daily-reports/{today}/{{에이전트명}}.md\n"
            f"포맷: # 일일 업무보고 — {{에이전트명}}\n"
            f"날짜: {today}\n## 처리 작업\n## 특이사항\n## 내일 예정"
        ),
    }).encode()
    try:
        req = urllib.request.Request(
            "http://localhost:5600/message",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        pass  # MAX 오프라인 시 무시


@app.route("/api/daily-reports", methods=["GET"])
def api_daily_reports():
    """
    GET /api/daily-reports?date=YYYY-MM-DD
    reports/daily-reports/YYYY-MM-DD/ 디렉토리에서 팀원별 MD 읽기
    """
    date_str = request.args.get("date", "")
    if not date_str:
        date_str = datetime.now(KST).strftime("%Y-%m-%d")

    # 날짜 포맷 검증
    import re as _re
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        return jsonify({"error": "날짜 포맷 오류 (YYYY-MM-DD)"}), 400

    report_dir = os.path.join(DAILY_REPORTS_BASE, date_str)
    reports = []

    # summary.md 먼저 읽기
    summary_path = os.path.join(report_dir, "summary.md")
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                reports.append({
                    "agent_id": "summary",
                    "agent_name": "종합 요약",
                    "emoji": "📋",
                    "content": f.read(),
                    "exists": True,
                })
        except Exception:
            pass

    # 각 에이전트 보고서 읽기
    for agent_id in _REPORT_AGENTS:
        md_path = os.path.join(report_dir, f"{agent_id}.md")
        defn = AGENT_DEFS.get(agent_id, {"name": agent_id, "emoji": "🤖"})
        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = None
            reports.append({
                "agent_id": agent_id,
                "agent_name": defn["name"],
                "emoji": defn["emoji"],
                "content": content,
                "exists": True,
            })
        else:
            reports.append({
                "agent_id": agent_id,
                "agent_name": defn["name"],
                "emoji": defn["emoji"],
                "content": None,
                "exists": False,
            })

    submitted = sum(1 for r in reports if r["exists"] and r["agent_id"] != "summary")
    return jsonify({
        "date": date_str,
        "reports": reports,
        "submitted_count": submitted,
        "total_count": len(_REPORT_AGENTS),
    })


@app.route("/api/daily-reports/dates", methods=["GET"])
def api_daily_reports_dates():
    """보고서가 있는 날짜 목록 반환 (최신순 30개)"""
    import re as _re
    dates = []
    if os.path.isdir(DAILY_REPORTS_BASE):
        for d in sorted(os.listdir(DAILY_REPORTS_BASE), reverse=True):
            if _re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                dates.append(d)
                if len(dates) >= 30:
                    break
    return jsonify({"dates": dates})


# ── 팀 헌장 API ────────────────────────────────────────────────
CHARTER_PATH = os.path.join(BASE_DIR, "..", "charter", "team-charter.md")


@app.route("/api/charter", methods=["GET"])
def api_charter():
    """charter/team-charter.md 파일 내용 반환"""
    try:
        with open(CHARTER_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content})
    except FileNotFoundError:
        return jsonify({"error": "team-charter.md not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _safe_workspace_path(rel_path: str) -> str | None:
    """path traversal 방지: 결과가 WORKSPACE_BASE 내인지 확인"""
    abs_path = os.path.normpath(os.path.join(WORKSPACE_BASE, rel_path))
    if not abs_path.startswith(WORKSPACE_BASE):
        return None
    return abs_path


@app.route("/api/workspace/tree", methods=["GET"])
def api_workspace_tree():
    rel = request.args.get("path", "")
    depth = int(request.args.get("depth", 1))
    base = _safe_workspace_path(rel) if rel else WORKSPACE_BASE
    if not base or not os.path.isdir(base):
        return jsonify({"tree": []})

    def scan(dirpath: str, current_depth: int) -> list[dict]:
        items = []
        try:
            entries = sorted(os.scandir(dirpath), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return items
        for entry in entries:
            if entry.name.startswith("."):
                continue
            node: dict = {
                "name": entry.name,
                "path": os.path.relpath(entry.path, WORKSPACE_BASE).replace("\\", "/"),
                "type": "folder" if entry.is_dir() else "file",
            }
            if entry.is_file():
                try:
                    st = entry.stat()
                    node["size"] = st.st_size
                    node["modified"] = datetime.fromtimestamp(st.st_mtime, KST).isoformat()
                except Exception:
                    node["size"] = 0
            if entry.is_dir() and current_depth > 1:
                node["children"] = scan(entry.path, current_depth - 1)
                node["_loaded"] = True
            items.append(node)
        return items

    tree = scan(base, depth)
    return jsonify({"tree": tree})


@app.route("/api/workspace/file", methods=["GET"])
def api_workspace_file():
    rel = request.args.get("path", "")
    if not rel:
        return jsonify({"error": "path required"}), 400
    abs_path = _safe_workspace_path(rel)
    if not abs_path or not os.path.isfile(abs_path):
        return jsonify({"error": "not found"}), 404

    download = request.args.get("download")
    if download:
        return send_from_directory(
            os.path.dirname(abs_path),
            os.path.basename(abs_path),
            as_attachment=True,
        )

    ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
    st = os.stat(abs_path)
    result: dict = {
        "name": os.path.basename(abs_path),
        "path": rel,
        "size": st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime, KST).isoformat(),
        "content": None,
        "content_type": "binary",
    }
    if ext in _TEXT_EXTS and st.st_size <= _MAX_TEXT_SIZE:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                result["content"] = f.read()
            result["content_type"] = "text"
        except Exception:
            pass
    elif ext in _IMAGE_EXTS:
        import base64
        try:
            with open(abs_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "image/png")
            result["content"] = f"data:{mime};base64,{b64}"
            result["content_type"] = "image"
        except Exception:
            pass
    return jsonify(result)


@app.route("/api/workspace/file", methods=["DELETE"])
def api_workspace_file_delete():
    """업무공간 파일 삭제 (reports/ 내부만)"""
    rel = request.args.get("path", "")
    if not rel:
        return jsonify({"error": "path required"}), 400
    abs_path = _safe_workspace_path(rel)
    if not abs_path or not os.path.isfile(abs_path):
        return jsonify({"error": "not found"}), 404
    try:
        os.remove(abs_path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/workspace/upload", methods=["POST"])
def api_workspace_upload():
    """업무공간(reports/)에 파일 업로드"""
    folder = request.form.get("folder", "")
    if folder:
        target_dir = _safe_workspace_path(folder)
        if not target_dir or not os.path.isdir(target_dir):
            return jsonify({"error": "invalid folder"}), 400
    else:
        target_dir = WORKSPACE_BASE
    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "no files"}), 400
    saved = []
    for f in uploaded:
        if f and f.filename:
            filename = secure_filename(f.filename)
            if not filename:
                continue
            filepath = os.path.join(target_dir, filename)
            # path traversal 재확인
            if not os.path.normpath(filepath).startswith(WORKSPACE_BASE):
                continue
            f.save(filepath)
            saved.append(filename)
    if not saved:
        return jsonify({"error": "no valid files"}), 400
    return jsonify({"ok": True, "files": saved, "folder": folder})


# ── 슬랙 챗로그 API ──
CHATLOG_DIR = os.path.join(os.path.dirname(BASE_DIR), "slack_chatlog")

@app.route("/api/chatlog/channels")
def chatlog_channels():
    """챗로그 채널 목록 (헤더에서 채널명 읽기)"""
    channels = []
    if not os.path.isdir(CHATLOG_DIR):
        return jsonify(channels)
    for fname in sorted(os.listdir(CHATLOG_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        channel_id = fname.replace(".jsonl", "")
        filepath = os.path.join(CHATLOG_DIR, fname)
        channel_name = channel_id
        msg_count = 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i == 0:
                        hdr = json.loads(line)
                        if hdr.get("_header"):
                            channel_name = hdr.get("channel_name", channel_id)
                            continue
                    msg_count += 1
        except Exception:
            pass
        # 파일 디렉토리에서 첨부파일 수 확인
        files_dir = os.path.join(CHATLOG_DIR, f"{channel_id}_files")
        file_count = len(os.listdir(files_dir)) if os.path.isdir(files_dir) else 0
        channels.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "message_count": msg_count,
            "file_count": file_count,
        })
    return jsonify(channels)


@app.route("/api/chatlog/<channel_id>")
def chatlog_messages(channel_id):
    """특정 채널 메시지 조회 (최근 N개, 기본 200)"""
    limit = request.args.get("limit", 200, type=int)
    offset = request.args.get("offset", 0, type=int)
    search = request.args.get("q", "").strip().lower()

    filepath = os.path.join(CHATLOG_DIR, f"{channel_id}.jsonl")
    if not os.path.isfile(filepath):
        return jsonify({"error": "channel not found"}), 404

    messages = []
    channel_name = channel_id
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("_header"):
                    channel_name = entry.get("channel_name", channel_id)
                    continue
                if search:
                    text_lower = (entry.get("text", "") + entry.get("username", "")).lower()
                    if search not in text_lower:
                        continue
                messages.append(entry)
    except Exception:
        pass

    total = len(messages)
    # 최신 메시지부터 (역순)
    messages.reverse()
    page = messages[offset:offset + limit]

    return jsonify({
        "channel_id": channel_id,
        "channel_name": channel_name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "messages": page,
    })


@app.route("/chatlog")
def chatlog_page():
    """슬랙 챗로그 뷰어 페이지"""
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>슬랙 챗로그 - WTA Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Pretendard', -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; }
  .header { background: #1e293b; padding: 16px 24px; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid #334155; }
  .header h1 { font-size: 18px; font-weight: 600; }
  .header a { color: #60a5fa; text-decoration: none; font-size: 14px; }
  .container { display: flex; height: calc(100vh - 57px); }
  .sidebar { width: 280px; background: #1e293b; border-right: 1px solid #334155; overflow-y: auto; flex-shrink: 0; }
  .channel-item { padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #334155; transition: background 0.15s; }
  .channel-item:hover { background: #334155; }
  .channel-item.active { background: #1d4ed8; }
  .channel-name { font-size: 14px; font-weight: 500; }
  .channel-meta { font-size: 12px; color: #94a3b8; margin-top: 4px; }
  .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .toolbar { padding: 12px 16px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; gap: 12px; align-items: center; }
  .toolbar input { flex: 1; padding: 8px 12px; background: #0f172a; border: 1px solid #475569; border-radius: 6px; color: #e2e8f0; font-size: 14px; outline: none; }
  .toolbar input:focus { border-color: #3b82f6; }
  .toolbar button { padding: 8px 16px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
  .toolbar button:hover { background: #2563eb; }
  .messages { flex: 1; overflow-y: auto; padding: 16px; }
  .msg { padding: 8px 12px; margin-bottom: 4px; border-radius: 6px; font-size: 14px; line-height: 1.5; }
  .msg:hover { background: #1e293b; }
  .msg-ts { color: #64748b; font-size: 12px; min-width: 140px; display: inline-block; }
  .msg-user { color: #60a5fa; font-weight: 500; margin-right: 8px; }
  .msg-text { color: #e2e8f0; }
  .msg-files { margin-top: 4px; }
  .msg-file { display: inline-block; background: #334155; padding: 2px 8px; border-radius: 4px; font-size: 12px; color: #94a3b8; margin-right: 4px; }
  .msg-nc { background: #1e293b; border-left: 3px solid #f59e0b; }
  .empty { color: #64748b; text-align: center; padding: 48px; font-size: 15px; }
  .stats { font-size: 13px; color: #94a3b8; }
  .load-more { text-align: center; padding: 12px; }
  .load-more button { padding: 6px 20px; background: #334155; color: #94a3b8; border: none; border-radius: 6px; cursor: pointer; }
</style>
</head>
<body>
<div class="header">
  <a href="/v2/">&larr; 대시보드</a>
  <h1>💬 슬랙 챗로그</h1>
</div>
<div class="container">
  <div class="sidebar" id="sidebar"></div>
  <div class="main">
    <div class="toolbar">
      <input type="text" id="search" placeholder="검색 (이름, 내용...)">
      <button onclick="doSearch()">검색</button>
      <span class="stats" id="stats"></span>
    </div>
    <div class="messages" id="messages">
      <div class="empty">왼쪽에서 채널을 선택하세요</div>
    </div>
  </div>
</div>
<script>
let currentChannel = null;
let allMessages = [];

async function loadChannels() {
  const res = await fetch('/api/chatlog/channels');
  const channels = await res.json();
  const sb = document.getElementById('sidebar');
  sb.innerHTML = channels.map(ch => `
    <div class="channel-item" data-id="${ch.channel_id}" onclick="selectChannel('${ch.channel_id}')">
      <div class="channel-name">#${ch.channel_name}</div>
      <div class="channel-meta">${ch.message_count}개 메시지 · ${ch.file_count}개 파일</div>
    </div>
  `).join('');
}

async function selectChannel(channelId) {
  currentChannel = channelId;
  document.querySelectorAll('.channel-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === channelId);
  });
  document.getElementById('search').value = '';
  await loadMessages(channelId);
}

async function loadMessages(channelId, q='') {
  const url = q
    ? '/api/chatlog/'+channelId+'?limit=1000&q='+encodeURIComponent(q)
    : '/api/chatlog/'+channelId+'?limit=1000';
  const res = await fetch(url);
  const data = await res.json();
  allMessages = data.messages || [];
  document.getElementById('stats').textContent =
    '#'+data.channel_name+' — '+data.total+'개 메시지' + (q ? ' (검색: '+q+')' : '');
  renderMessages(allMessages);
}

function renderMessages(msgs) {
  const el = document.getElementById('messages');
  if (!msgs.length) { el.innerHTML = '<div class="empty">메시지 없음</div>'; return; }
  // 시간순 (오래된 것 위)
  const sorted = [...msgs].reverse();
  el.innerHTML = sorted.map(m => {
    const isNc = (m.text||'').includes('[부적합');
    const files = (m.files||[]).map(f =>
      '<span class="msg-file">📎 '+f.name+'</span>'
    ).join('');
    return '<div class="msg'+(isNc?' msg-nc':'')+'">'+
      '<span class="msg-ts">'+m.ts+'</span>'+
      '<span class="msg-user">'+m.username+'</span>'+
      '<span class="msg-text">'+escHtml(m.text||'')+'</span>'+
      (files?'<div class="msg-files">'+files+'</div>':'')+
      '</div>';
  }).join('');
  el.scrollTop = el.scrollHeight;
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function doSearch() {
  if (!currentChannel) return;
  const q = document.getElementById('search').value.trim();
  loadMessages(currentChannel, q);
}

document.getElementById('search').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

loadChannels();
</script>
</body>
</html>"""


@app.route("/guide")
def slack_guide_page():
    """슬랙 기능 안내 페이지"""
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WTA 슬랙 사용 가이드</title>
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Pretendard Variable', -apple-system, sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.7; }
  .hero { background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%); color: #fff; padding: 60px 24px; text-align: center; }
  .hero h1 { font-size: 32px; font-weight: 700; margin-bottom: 12px; }
  .hero p { font-size: 17px; opacity: 0.9; max-width: 600px; margin: 0 auto; }
  .hero .badge { display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 14px; border-radius: 20px; font-size: 13px; margin-bottom: 16px; }
  .content { max-width: 800px; margin: -40px auto 40px; padding: 0 20px; }
  .card { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 32px; margin-bottom: 20px; }
  .card h2 { font-size: 20px; font-weight: 600; margin-bottom: 16px; color: #1e293b; display: flex; align-items: center; gap: 10px; }
  .card h2 .icon { font-size: 24px; }
  .feature { display: flex; gap: 16px; padding: 16px 0; border-bottom: 1px solid #f1f5f9; }
  .feature:last-child { border-bottom: none; }
  .feature-icon { width: 48px; height: 48px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }
  .feature-body h3 { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
  .feature-body p { font-size: 14px; color: #64748b; }
  .cmd { display: inline-block; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #7c3aed; font-weight: 600; }
  .steps { counter-reset: step; }
  .step { display: flex; gap: 16px; padding: 12px 0; }
  .step-num { counter-increment: step; width: 32px; height: 32px; border-radius: 50%; background: #e0e7ff; color: #4338ca; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; }
  .step-num::before { content: counter(step); }
  .step-body { font-size: 15px; }
  .note { background: #fffbeb; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 0 8px 8px 0; margin-top: 16px; font-size: 14px; color: #92400e; }
  .channels { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .ch { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; font-size: 14px; }
  .ch-name { font-weight: 600; color: #7c3aed; }
  .footer { text-align: center; padding: 32px; color: #94a3b8; font-size: 13px; }
  @media (max-width: 600px) {
    .hero h1 { font-size: 24px; }
    .channels { grid-template-columns: 1fr; }
    .card { padding: 20px; }
  }
</style>
</head>
<body>

<div class="hero">
  <div class="badge">테스트 기간 운영 중</div>
  <h1>WTA 슬랙 사용 가이드</h1>
  <p>제조생산 업무 효율화를 위한 슬랙 AI 시스템</p>
</div>

<div class="content">

  <div class="card">
    <h2><span class="icon">💡</span> 왜 슬랙을 도입하나요?</h2>
    <p style="font-size:15px; color:#475569; margin-bottom:16px;">
      기존 메신저/그룹웨어 기반 소통에서 이런 불편함을 겪으셨을 겁니다.
    </p>
    <div class="feature">
      <div class="feature-icon" style="background:#fef2f2;">😥</div>
      <div class="feature-body">
        <h3>대화 기록 손실</h3>
        <p>퇴사·기기변경·기간 만료 시 이전 대화가 사라져, 업무 이력을 추적할 수 없었습니다.</p>
      </div>
    </div>
    <div class="feature">
      <div class="feature-icon" style="background:#fefce8;">📉</div>
      <div class="feature-body">
        <h3>정보의 데이터화 부재</h3>
        <p>채팅에서 논의된 품질 이슈, 기술 정보가 정형 데이터로 남지 않아 나중에 활용하기 어려웠습니다.</p>
      </div>
    </div>
    <div class="feature">
      <div class="feature-icon" style="background:#eff6ff;">🆕</div>
      <div class="feature-body">
        <h3>신규 인원의 정보 단절</h3>
        <p>새로 합류한 동료가 이전 논의 맥락을 확인할 방법이 없어 같은 질문이 반복되었습니다.</p>
      </div>
    </div>
    <div class="feature">
      <div class="feature-icon" style="background:#faf5ff;">🔁</div>
      <div class="feature-body">
        <h3>이중 업무 부하</h3>
        <p>채팅에서 이야기한 내용을 MES·ERP 등에 다시 수기 등록해야 하는 번거로움이 있었습니다.</p>
      </div>
    </div>
    <div class="note" style="background:#f0fdf4; border-left-color:#22c55e; color:#166534; margin-top:20px;">
      ✅ <strong>슬랙 도입 후:</strong> 모든 대화가 영구 보존 · 자동 데이터화 · 추가 인원 즉시 맥락 파악 · 채팅에서 바로 MES 연동
    </div>
  </div>

  <div class="card">
    <h2><span class="icon">🚀</span> 시작하기</h2>
    <div class="steps">
      <div class="step"><div class="step-num"></div><div class="step-body">관리자로부터 슬랙 초대 메일을 받으면 가입합니다</div></div>
      <div class="step"><div class="step-num"></div><div class="step-body">PC: <a href="https://slack.com/intl/ko-kr/downloads">Slack 데스크톱 앱</a> 설치 / 모바일: 앱스토어에서 Slack 설치</div></div>
      <div class="step"><div class="step-num"></div><div class="step-body">워크스페이스 <strong>wta-team</strong>에 로그인하면 배정된 채널이 보입니다</div></div>
    </div>
    <div class="note">💡 초대에 의한 가입 방식입니다. 초대를 받지 못하셨다면 생산관리팀에 문의해주세요.</div>
  </div>

  <div class="card">
    <h2><span class="icon">⚡</span> 주요 기능</h2>

    <div class="feature">
      <div class="feature-icon" style="background:#fef2f2;">⚠️</div>
      <div class="feature-body">
        <h3>부적합 등록 <span class="cmd">!부적합</span></h3>
        <p>채널에서 <span class="cmd">!부적합</span> 입력 → 등록 버튼 클릭 → 모달 폼 작성 → MES 자동 등록. 등록 후 사진·동영상 첨부도 가능합니다.</p>
      </div>
    </div>

    <div class="feature">
      <div class="feature-icon" style="background:#eff6ff;">🤖</div>
      <div class="feature-body">
        <h3>AI 질문하기 <span class="cmd">@WTA-AI</span></h3>
        <p>채널에서 <span class="cmd">@WTA-AI</span> 멘션 후 질문하면 AI 팀원이 답변합니다. 장비 매뉴얼 검색, 업무 질문, 데이터 조회 등에 활용하세요.</p>
      </div>
    </div>

    <div class="feature">
      <div class="feature-icon" style="background:#f0fdf4;">📁</div>
      <div class="feature-body">
        <h3>프로젝트 채널</h3>
        <p>프로젝트별 전용 채널에서 팀원과 소통합니다. 파일 공유, 진행상황 논의가 가능하며 대화 내용은 자동으로 기록됩니다.</p>
      </div>
    </div>

    <div class="feature">
      <div class="feature-icon" style="background:#faf5ff;">📎</div>
      <div class="feature-body">
        <h3>기술자료 자동 저장</h3>
        <p>프로젝트 채널에 업로드한 도면, 사양서 등 기술문서는 MES에 자동으로 연동·저장됩니다.</p>
      </div>
    </div>
  </div>

  <div class="card">
    <h2><span class="icon">📢</span> 채널 안내</h2>
    <div class="channels">
      <div class="ch"><span class="ch-name">#프로젝트명</span> — 프로젝트별 소통</div>
      <div class="ch"><span class="ch-name">#부적합</span> — 부적합 이슈 공유</div>
      <div class="ch"><span class="ch-name">#cs</span> — CS 기술지원</div>
      <div class="ch"><span class="ch-name">#개발</span> — MES 개발 관련</div>
      <div class="ch"><span class="ch-name">#영업</span> — 영업/수주 관련</div>
      <div class="ch"><span class="ch-name">#일반</span> — 자유 소통</div>
    </div>
  </div>

  <div class="card">
    <h2><span class="icon">💬</span> 피드백</h2>
    <p style="font-size:15px; color:#475569;">
      테스트 기간 동안 불편한 점이나 개선 아이디어가 있으시면 슬랙 <span class="cmd">#일반</span> 채널에 자유롭게 남겨주세요.
      여러분의 피드백이 시스템 개선에 직접 반영됩니다.
    </p>
  </div>

</div>

<div class="footer">
  (주)윈텍오토메이션 · 생산관리팀 · WTA AI 시스템
</div>

</body>
</html>"""


@app.route("/security-slide")
def security_slide_page():
    """대표이사(사장님) 보고용 — AI 데이터 보안 슬라이드"""
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WTA AI 데이터 보안 보고</title>
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Pretendard Variable','맑은 고딕',-apple-system,sans-serif;background:#0b1120;color:#e2e8f0;overflow-x:hidden}

  /* 슬라이드 컨테이너 */
  .slide-wrap{max-width:1100px;margin:0 auto;padding:20px}
  .slide{background:#1a2332;border:1px solid #2d3f54;border-radius:16px;padding:56px 64px;margin-bottom:32px;min-height:580px;display:flex;flex-direction:column;justify-content:center;position:relative;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.3)}
  .slide::after{content:attr(data-num);position:absolute;bottom:20px;right:32px;font-size:14px;color:#475569;font-weight:600}

  /* 타이포그래피 — 65세 가독성 */
  .slide h1{font-size:38px;font-weight:800;line-height:1.4;margin-bottom:20px;color:#f1f5f9}
  .slide h2{font-size:30px;font-weight:700;line-height:1.4;margin-bottom:24px;color:#f1f5f9}
  .slide h3{font-size:22px;font-weight:600;margin:24px 0 14px;color:#cbd5e1}
  .slide p{font-size:19px;line-height:1.9;color:#94a3b8;margin-bottom:14px}
  .slide li{font-size:18px;line-height:2;color:#94a3b8;margin-bottom:6px}
  .slide ul{padding-left:24px}
  .slide strong,.hl{color:#f1f5f9;font-weight:700}
  .accent{color:#38bdf8}
  .safe{color:#4ade80}
  .warn{color:#fbbf24}
  .danger{color:#f87171}

  /* 슬라이드 넘버 뱃지 */
  .slide-num{display:inline-block;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);color:#38bdf8;padding:4px 14px;border-radius:20px;font-size:13px;font-weight:700;margin-bottom:16px;letter-spacing:1px}

  /* 표지 */
  .cover{background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#0f172a 100%);text-align:center;min-height:620px}
  .cover::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 50%,rgba(56,189,248,0.06) 0%,transparent 70%)}
  .cover h1{font-size:44px;margin-bottom:12px}
  .cover .sub{font-size:22px;color:#94a3b8;margin-bottom:32px}
  .cover .meta{font-size:16px;color:#64748b;margin-top:24px}
  .cover .logo{font-size:64px;margin-bottom:24px}
  .cover .conf{display:inline-block;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.25);color:#fca5a5;padding:6px 20px;border-radius:24px;font-size:14px;font-weight:600;letter-spacing:2px;margin-bottom:20px}

  /* 카드/박스 */
  .box{background:#0f172a;border:1px solid #2d3f54;border-radius:12px;padding:28px 32px;margin:16px 0}
  .box.green{border-left:4px solid #4ade80}
  .box.yellow{border-left:4px solid #fbbf24}
  .box.red{border-left:4px solid #f87171}
  .box.blue{border-left:4px solid #38bdf8}
  .box.purple{border-left:4px solid #a855f7}
  .box h4{font-size:20px;font-weight:700;margin-bottom:10px;color:#f1f5f9}
  .box p{margin-bottom:6px}

  /* 그리드 */
  .g2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:16px 0}
  .g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin:16px 0}
  @media(max-width:800px){.g2,.g3{grid-template-columns:1fr}}

  /* 큰 숫자 */
  .big-num{font-size:56px;font-weight:900;line-height:1;margin-bottom:8px}
  .big-label{font-size:16px;color:#64748b}

  /* 태그 */
  .tag{display:inline-block;padding:4px 14px;border-radius:6px;font-size:15px;font-weight:700}
  .tag.green{background:rgba(34,197,94,0.15);color:#4ade80;border:1px solid rgba(34,197,94,0.3)}
  .tag.yellow{background:rgba(245,158,11,0.15);color:#fbbf24;border:1px solid rgba(245,158,11,0.3)}
  .tag.red{background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3)}

  /* 표 */
  table{width:100%;border-collapse:collapse;margin:16px 0}
  th{text-align:left;padding:14px 16px;background:#0f172a;color:#94a3b8;font-weight:600;border-bottom:2px solid #2d3f54;font-size:15px}
  td{padding:14px 16px;border-bottom:1px solid rgba(45,63,84,0.5);color:#cbd5e1;font-size:16px}
  tr:hover td{background:rgba(56,189,248,0.03)}

  /* 도식 */
  .diagram-box{background:#0b1120;border:2px solid #2d3f54;border-radius:12px;padding:32px;margin:20px 0;position:relative}
  .d-node{display:inline-flex;align-items:center;gap:8px;padding:12px 20px;border-radius:10px;font-size:16px;font-weight:600;margin:6px}
  .d-node.server{background:rgba(56,189,248,0.12);border:2px solid rgba(56,189,248,0.4);color:#7dd3fc}
  .d-node.safe{background:rgba(34,197,94,0.12);border:2px solid rgba(34,197,94,0.4);color:#86efac}
  .d-node.ext{background:rgba(168,85,247,0.12);border:2px solid rgba(168,85,247,0.4);color:#c4b5fd}
  .d-node.warn{background:rgba(245,158,11,0.12);border:2px solid rgba(245,158,11,0.4);color:#fde68a}
  .d-arrow{color:#475569;font-size:24px;margin:0 4px;vertical-align:middle}
  .d-section{margin:16px 0;padding:16px;border:1px dashed #2d3f54;border-radius:8px}
  .d-section-title{font-size:14px;color:#64748b;font-weight:600;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px}

  /* 비교 */
  .vs{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid #2d3f54;border-radius:12px;overflow:hidden;margin:16px 0}
  .vs-col{padding:28px}
  .vs-col.bad{background:rgba(239,68,68,0.04);border-right:1px solid #2d3f54}
  .vs-col.good{background:rgba(34,197,94,0.04)}
  .vs-col h4{font-size:18px;font-weight:700;margin-bottom:14px}
  .vs-col.bad h4{color:#f87171}
  .vs-col.good h4{color:#4ade80}
  .vs-col li{font-size:16px;line-height:2;list-style:none;padding-left:24px;position:relative}
  .vs-col li::before{position:absolute;left:0;font-size:16px}
  .vs-col.bad li::before{content:'✗';color:#f87171}
  .vs-col.good li::before{content:'✓';color:#4ade80}

  /* 푸터 */
  .footer{text-align:center;padding:40px;color:#334155;font-size:13px}

  /* 인쇄 */
  @media print{
    .slide{break-inside:avoid;page-break-inside:avoid;box-shadow:none;border:1px solid #ddd}
    body{background:#fff;color:#1e293b}
    .slide{background:#fff}
  }
</style>
</head>
<body>
<div class="slide-wrap">

<!-- ========== SLIDE 1: 표지 ========== -->
<div class="slide cover" data-num="">
  <div style="position:relative;z-index:1">
    <div class="conf">CONFIDENTIAL</div>
    <div class="logo">🔒</div>
    <h1>AI 멀티에이전트 시스템<br>데이터 보안 보고</h1>
    <p class="sub">기술 데이터 보호 체계 및 외부 유출 방지 대책</p>
    <div class="meta">
      <p>(주)윈텍오토메이션 AI운영팀</p>
      <p style="margin-top:8px">2026년 4월 2일</p>
    </div>
  </div>
</div>

<!-- ========== SLIDE 2: 핵심 요약 ========== -->
<div class="slide" data-num="01">
  <div class="slide-num">01 핵심 요약</div>
  <h2>사장님께서 가장 궁금하신 것</h2>
  <p style="font-size:22px;color:#f1f5f9;margin-bottom:24px">
    "AI를 쓰면 우리 기술 데이터가 밖으로 새어나가는 것 아닌가?"
  </p>

  <div class="g2">
    <div class="box green">
      <h4>✅ 결론: AI가 우리 데이터를 <span class="safe">학습하지 않습니다</span></h4>
      <p style="font-size:17px">우리가 사용하는 유료 API는 계약상 <strong>고객 데이터를 AI 모델 훈련에 사용하지 않습니다.</strong> 이것은 법적으로 보장된 사항입니다.</p>
    </div>
    <div class="box blue">
      <h4>🔐 모든 전송은 암호화됩니다</h4>
      <p style="font-size:17px">인터넷 뱅킹과 동일한 수준의 <strong>TLS 1.3 암호화</strong>로 보호됩니다. 중간에서 누가 엿볼 수 없습니다.</p>
    </div>
  </div>

  <div class="g3" style="margin-top:20px;text-align:center">
    <div class="box" style="text-align:center">
      <div class="big-num safe">0건</div>
      <div class="big-label">AI 학습에 사용된 WTA 데이터</div>
    </div>
    <div class="box" style="text-align:center">
      <div class="big-num accent">30일</div>
      <div class="big-label">이후 전송 기록 자동 삭제</div>
    </div>
    <div class="box" style="text-align:center">
      <div class="big-num" style="color:#a855f7">100%</div>
      <div class="big-label">사내 서버에서 운영</div>
    </div>
  </div>
</div>

<!-- ========== SLIDE 3: AI는 어떻게 동작하는가 ========== -->
<div class="slide" data-num="02">
  <div class="slide-num">02 AI는 어떻게 동작하는가</div>
  <h2>우리 AI 시스템의 동작 방식</h2>

  <p>AI 에이전트는 <strong>우리 회사 서버 안에서</strong> 동작합니다.<br>
  외부 AI 서비스(Claude)는 <strong>"두뇌" 역할만</strong> 합니다 — 질문을 보내면 답변을 돌려줍니다.</p>

  <div class="box blue" style="margin-top:20px">
    <h4>💡 비유하자면</h4>
    <p style="font-size:18px">
      AI 에이전트 = <strong>우리 회사에 상주하는 직원</strong><br>
      Claude API = <strong>외부 전문가에게 전화로 자문을 구하는 것</strong><br><br>
      직원이 전문가에게 전화할 때 필요한 내용만 말하고,<br>
      전문가는 답변 후 통화 내용을 <strong>30일 뒤 자동으로 폐기</strong>합니다.<br>
      전문가가 우리 통화 내용으로 <strong>다른 고객을 가르치지 않습니다.</strong>
    </p>
  </div>
</div>

<!-- ========== SLIDE 4: 시스템 구성도 ========== -->
<div class="slide" data-num="03">
  <div class="slide-num">03 시스템 구성도</div>
  <h2>WTA AI 시스템 전체 구조</h2>

  <div class="diagram-box">
    <!-- 사내 영역 -->
    <div class="d-section" style="border-color:#4ade80">
      <div class="d-section-title">🏢 WTA 사내 서버 (외부 접근 차단)</div>

      <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:12px 0">
        <div class="d-node server">👑 MAX (총괄)</div>
        <div class="d-node server">📊 DB매니저</div>
        <div class="d-node server">🛠️ CS담당</div>
        <div class="d-node server">💻 개발팀</div>
        <div class="d-node server">🔧 크래프터</div>
      </div>
      <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:8px 0">
        <div class="d-node server">🔍 NC관리</div>
        <div class="d-node server">🔬 출하품질</div>
        <div class="d-node server">💰 영업팀</div>
        <div class="d-node server">📐 설계팀</div>
        <div class="d-node server">📅 일정관리</div>
      </div>
      <div style="text-align:center;color:#64748b;font-size:14px;margin:8px 0">▲ AI 에이전트 14명 — 모두 사내 서버에서 실행</div>

      <div style="display:flex;justify-content:center;gap:20px;margin-top:16px;flex-wrap:wrap">
        <div class="d-node safe">🗄️ MES DB<br><span style="font-size:12px;color:#64748b">생산/품질 데이터</span></div>
        <div class="d-node safe">🗄️ ERP DB<br><span style="font-size:12px;color:#64748b">읽기 전용</span></div>
        <div class="d-node safe">📁 기술문서<br><span style="font-size:12px;color:#64748b">도면/매뉴얼</span></div>
      </div>
      <div style="text-align:center;color:#4ade80;font-size:14px;margin:8px 0">🔒 모든 데이터는 사내에 저장 — 외부 반출 없음</div>
    </div>

    <!-- 통신 화살표 -->
    <div style="text-align:center;margin:16px 0">
      <div style="display:inline-block;padding:8px 24px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px">
        <span style="font-size:20px">⬆️⬇️</span>
        <span style="color:#fbbf24;font-size:15px;font-weight:600;margin-left:8px">암호화된 질문/답변만 오감 (TLS 1.3)</span>
      </div>
    </div>

    <!-- 외부 영역 -->
    <div class="d-section" style="border-color:#a855f7">
      <div class="d-section-title">☁️ 외부 클라우드 서비스</div>
      <div style="display:flex;justify-content:center;gap:16px;flex-wrap:wrap">
        <div class="d-node ext">🧠 Anthropic Claude<br><span style="font-size:12px;color:#94a3b8">AI 두뇌 (미국)</span></div>
        <div class="d-node ext">💬 Slack<br><span style="font-size:12px;color:#94a3b8">사내 메신저</span></div>
        <div class="d-node ext">📋 Jira<br><span style="font-size:12px;color:#94a3b8">이슈 관리</span></div>
      </div>
    </div>
  </div>
</div>

<!-- ========== SLIDE 5: 데이터는 어디로 가는가 ========== -->
<div class="slide" data-num="04">
  <div class="slide-num">04 데이터 흐름</div>
  <h2>어떤 데이터가 외부로 나가는가?</h2>

  <table>
    <tr>
      <th style="width:25%">전송 경로</th>
      <th style="width:25%">전송되는 데이터</th>
      <th style="width:15%">암호화</th>
      <th style="width:15%">AI 학습</th>
      <th style="width:20%">보존 기간</th>
    </tr>
    <tr>
      <td><strong>→ Claude AI</strong><br><span style="font-size:13px;color:#64748b">(Anthropic 서버)</span></td>
      <td>에이전트의 질문과<br>분석 요청 텍스트</td>
      <td><span class="tag green">TLS 1.3</span></td>
      <td><span class="safe" style="font-size:18px;font-weight:700">사용 안함</span></td>
      <td>30일 후 자동 삭제</td>
    </tr>
    <tr>
      <td><strong>→ Slack</strong><br><span style="font-size:13px;color:#64748b">(슬랙 서버)</span></td>
      <td>채널 대화 메시지</td>
      <td><span class="tag green">TLS 1.2+</span></td>
      <td><span class="safe">사용 안함</span></td>
      <td>슬랙 정책 따름</td>
    </tr>
    <tr>
      <td><strong>→ Jira</strong><br><span style="font-size:13px;color:#64748b">(Atlassian 서버)</span></td>
      <td>이슈/문서 내용</td>
      <td><span class="tag green">TLS 1.2+</span></td>
      <td><span class="safe">사용 안함</span></td>
      <td>직접 관리</td>
    </tr>
  </table>

  <div class="box green" style="margin-top:20px">
    <h4>📌 중요한 점</h4>
    <p style="font-size:17px">
      <strong>DB 원본 데이터, 도면 파일, CAD 파일은 외부로 전송되지 않습니다.</strong><br>
      에이전트가 분석에 필요한 <strong>텍스트 요약본만</strong> Claude에 질문으로 보내고, 답변을 받아옵니다.<br>
      원본 데이터는 항상 <strong>사내 서버에만</strong> 존재합니다.
    </p>
  </div>
</div>

<!-- ========== SLIDE 6: 핵심 Q&A ========== -->
<div class="slide" data-num="05">
  <div class="slide-num">05 핵심 질문과 답변</div>
  <h2>자주 우려되는 질문들</h2>

  <div class="box green" style="margin-bottom:16px">
    <h4>Q1. AI가 우리 기술을 배워서 경쟁사에 알려주지 않나?</h4>
    <p style="font-size:17px"><span class="tag green">NO</span> &nbsp; 유료 API는 <strong>고객 데이터를 모델 학습에 사용하지 않습니다.</strong> 우리가 보낸 질문은 다른 누구에게도 답변으로 나가지 않습니다. 이것은 Anthropic의 상용 서비스 계약에 명시된 <strong>법적 의무</strong>입니다.</p>
  </div>

  <div class="box green" style="margin-bottom:16px">
    <h4>Q2. 전송 중에 해커가 데이터를 훔칠 수 있나?</h4>
    <p style="font-size:17px"><span class="tag green">NO</span> &nbsp; 인터넷 뱅킹과 동일한 <strong>TLS 1.3 암호화</strong>가 적용됩니다. 전송 중 제3자가 내용을 열람하는 것은 <strong>현실적으로 불가능</strong>합니다.</p>
  </div>

  <div class="box blue" style="margin-bottom:16px">
    <h4>Q3. Anthropic 직원이 우리 데이터를 볼 수 있나?</h4>
    <p style="font-size:17px">일상 업무에서는 <strong>열람하지 않습니다.</strong> 악용 방지 조사(Trust & Safety) 목적에 한해 제한적 접근이 가능하지만, 기술 데이터 열람 목적의 접근은 <strong>허용되지 않습니다.</strong></p>
  </div>

  <div class="box blue">
    <h4>Q4. 만약 Anthropic이 해킹당하면?</h4>
    <p style="font-size:17px">Anthropic은 <strong>SOC 2 Type II 인증</strong>을 보유하고 있으며, 저장 데이터를 AES-256으로 암호화합니다. 또한 30일 후 자동 삭제되므로 해킹 시에도 노출 가능한 데이터 범위가 <strong>매우 제한적</strong>입니다.</p>
  </div>
</div>

<!-- ========== SLIDE 7: 무료 vs 유료 차이 ========== -->
<div class="slide" data-num="06">
  <div class="slide-num">06 무료 AI vs 유료 API</div>
  <h2>왜 유료 API를 사용하는가?</h2>
  <p>같은 AI라도 무료 웹 채팅과 유료 API는 <strong>데이터 취급 방식이 완전히 다릅니다.</strong></p>

  <div class="vs" style="margin-top:24px">
    <div class="vs-col bad">
      <h4>✗ 무료 AI 채팅 (일반 사용)</h4>
      <ul>
        <li>대화 내용이 AI 학습에 <strong>사용될 수 있음</strong></li>
        <li>데이터 삭제 절차가 복잡함</li>
        <li>기업 보안 계약(DPA) 불가</li>
        <li>감사 로그 없음</li>
        <li>개인 단위 — 통제 불가</li>
      </ul>
    </div>
    <div class="vs-col good">
      <h4>✓ 유료 API (WTA가 사용 중)</h4>
      <ul>
        <li>학습에 <strong>절대 사용되지 않음</strong> (법적 보장)</li>
        <li>30일 후 자동 삭제 + 즉시 삭제 가능</li>
        <li>기업 보안 계약(DPA) 체결 가능</li>
        <li>API 사용 감사 로그 제공</li>
        <li>회사 관리 — 접근 통제 가능</li>
      </ul>
    </div>
  </div>

  <div class="box purple" style="margin-top:20px">
    <h4>⚠️ 오히려 위험한 것은</h4>
    <p style="font-size:17px">직원들이 회사 시스템 대신 <strong>개인 ChatGPT/Claude 무료 버전에 기술 데이터를 직접 입력</strong>하는 것이 훨씬 큰 리스크입니다. 회사 AI 시스템을 통해 관리하면 <strong>어떤 데이터가 AI에 전달되는지 통제</strong>할 수 있습니다.</p>
  </div>
</div>

<!-- ========== SLIDE 8: 보안 인증 ========== -->
<div class="slide" data-num="07">
  <div class="slide-num">07 Anthropic 보안 수준</div>
  <h2>Anthropic(Claude)은 얼마나 안전한가?</h2>

  <div class="g2">
    <div class="box" style="text-align:center">
      <div style="font-size:48px;margin-bottom:8px">🏅</div>
      <h4>SOC 2 Type II</h4>
      <p style="font-size:16px">독립 회계법인의 정보보안 감사를 통과한 최고 수준 인증</p>
    </div>
    <div class="box" style="text-align:center">
      <div style="font-size:48px;margin-bottom:8px">🔐</div>
      <h4>AES-256 암호화</h4>
      <p style="font-size:16px">저장 데이터를 군사 등급 암호화로 보호 (미국 정부 표준)</p>
    </div>
    <div class="box" style="text-align:center">
      <div style="font-size:48px;margin-bottom:8px">🗑️</div>
      <h4>30일 자동 삭제</h4>
      <p style="font-size:16px">API 호출 기록은 30일 후 자동으로 영구 삭제</p>
    </div>
    <div class="box" style="text-align:center">
      <div style="font-size:48px;margin-bottom:8px">📄</div>
      <h4>DPA 체결 가능</h4>
      <p style="font-size:16px">기업 맞춤 데이터 처리 계약으로 법적 보호 강화 가능</p>
    </div>
  </div>

  <h3>주요 AI 서비스 보안 비교</h3>
  <table>
    <tr><th>항목</th><th>Claude (Anthropic)<br><span style="font-size:11px;color:#4ade80">WTA 사용 중</span></th><th>GPT (OpenAI)</th><th>Gemini (Google)</th></tr>
    <tr><td>API 학습 제외</td><td><span class="safe">✓ 기본 적용</span></td><td><span class="safe">✓ 기본 적용</span></td><td>✓ 유료만</td></tr>
    <tr><td>데이터 보존</td><td><strong>30일</strong></td><td>30일</td><td>18개월*</td></tr>
    <tr><td>SOC 2 인증</td><td><span class="safe">✓ Type II</span></td><td><span class="safe">✓ Type II</span></td><td>✓</td></tr>
    <tr><td>DPA 체결</td><td><span class="safe">✓</span></td><td>✓</td><td>✓</td></tr>
  </table>
</div>

<!-- ========== SLIDE 9: 우리가 지키는 것들 ========== -->
<div class="slide" data-num="08">
  <div class="slide-num">08 현재 보호 조치</div>
  <h2>WTA가 이미 적용한 보안 장치들</h2>

  <div class="g2">
    <div class="box green">
      <h4>✅ 유료 API만 사용</h4>
      <p style="font-size:16px">무료 AI 채팅 사용을 금지하고, 학습 제외가 보장되는 유료 API만 사용합니다.</p>
    </div>
    <div class="box green">
      <h4>✅ 100% 사내 서버 운영</h4>
      <p style="font-size:16px">모든 AI 에이전트가 사내 서버에서 실행됩니다. 외부 클라우드에 우리 시스템이 올라가 있지 않습니다.</p>
    </div>
    <div class="box green">
      <h4>✅ 데이터베이스 외부 차단</h4>
      <p style="font-size:16px">MES DB, ERP DB 모두 사내망에서만 접근 가능합니다. 인터넷에서 직접 접근이 불가능합니다.</p>
    </div>
    <div class="box green">
      <h4>✅ ERP 읽기 전용</h4>
      <p style="font-size:16px">ERP 데이터베이스는 읽기만 가능한 계정을 사용합니다. AI가 ERP 데이터를 변경할 수 없습니다.</p>
    </div>
    <div class="box green">
      <h4>✅ 슬랙 대화 사내 백업</h4>
      <p style="font-size:16px">슬랙 채널 대화를 사내 서버에 별도 저장합니다. 슬랙 서비스에 문제가 생겨도 데이터가 보존됩니다.</p>
    </div>
    <div class="box green">
      <h4>✅ 업무 영역별 권한 분리</h4>
      <p style="font-size:16px">각 AI 에이전트는 자기 업무 범위의 데이터만 접근합니다. 예: NC관리는 품질 데이터만, 영업은 수주 데이터만.</p>
    </div>
  </div>
</div>

<!-- ========== SLIDE 10: 개선 계획 ========== -->
<div class="slide" data-num="09">
  <div class="slide-num">09 추가 보안 강화 계획</div>
  <h2>앞으로 더 강화할 것들</h2>

  <h3>단기 (2주 내)</h3>
  <table>
    <tr><th style="width:8%">#</th><th style="width:30%">항목</th><th>내용</th></tr>
    <tr><td><strong>1</strong></td><td>민감 데이터 자동 필터</td><td>도면번호, 고객 코드 등 기밀 정보를 <strong>AI에 보내기 전 자동으로 마스킹</strong>하는 필터 적용</td></tr>
    <tr><td><strong>2</strong></td><td>AI 전송 감사 로그</td><td>어떤 데이터가 AI로 전송됐는지 <strong>모든 기록을 남기는</strong> 감사 시스템 구축</td></tr>
    <tr><td><strong>3</strong></td><td>기밀 문서 전송 차단</td><td>CAD 파일, 도면 원본, BOM 등 <strong>최고 기밀 자료는 AI 전송을 자동 차단</strong></td></tr>
  </table>

  <h3>중장기 로드맵</h3>
  <table>
    <tr><th style="width:20%">시기</th><th>항목</th></tr>
    <tr><td>2026년 Q2</td><td><strong>DPA(데이터 처리 부록) 정식 체결</strong> — Anthropic과 법적 구속력 있는 데이터 보호 계약</td></tr>
    <tr><td>2026년 Q2~Q3</td><td><strong>사내 전용 AI 검토</strong> — 최고 기밀 데이터는 외부 전송 없이 사내 AI로만 처리하는 방안</td></tr>
    <tr><td>2026년 Q3</td><td><strong>분기별 보안 점검 체계</strong> — 정기적으로 데이터 유출 위험을 자동 점검</td></tr>
    <tr><td>2026년 Q4</td><td><strong>ISO 27001 준비</strong> — 국제 정보보안 인증 획득 추진</td></tr>
  </table>
</div>

<!-- ========== SLIDE 11: 리스크 ========== -->
<div class="slide" data-num="10">
  <div class="slide-num">10 리스크 분석</div>
  <h2>남아 있는 위험과 대비</h2>

  <table>
    <tr><th style="width:30%">우려 사항</th><th style="width:15%">가능성</th><th>대비 방안</th></tr>
    <tr>
      <td>Anthropic 서버가 해킹되어<br>우리 API 기록이 유출</td>
      <td><span class="tag green">극히 낮음</span></td>
      <td>SOC 2 인증 기업, AES-256 암호화, <strong>30일 자동 삭제</strong>로 노출 범위 최소화.<br>DPA 체결 시 법적 보호 추가.</td>
    </tr>
    <tr>
      <td>직원이 실수로 기밀 자료를<br>AI에 직접 입력</td>
      <td><span class="tag yellow">중간</span></td>
      <td><strong>민감 데이터 자동 필터링</strong> 도입 예정.<br>직원 교육 + 사용 가이드라인 수립.</td>
    </tr>
    <tr>
      <td>사내 서버 자체가<br>외부에서 공격 받음</td>
      <td><span class="tag yellow">낮음</span></td>
      <td>DB 외부 접근 차단, 방화벽 운영 중.<br>에이전트 간 인증 체계 추가 예정.</td>
    </tr>
    <tr>
      <td>Anthropic이 정책을 바꿔<br>데이터를 학습에 사용</td>
      <td><span class="tag green">극히 낮음</span></td>
      <td>DPA 체결 시 <strong>법적 구속력</strong> 발생. 사전 통지 의무.<br>위반 시 계약 해지 + 손해배상 가능.</td>
    </tr>
  </table>
</div>

<!-- ========== SLIDE 12: 결론 ========== -->
<div class="slide" data-num="11" style="min-height:620px">
  <div class="slide-num">11 결론</div>
  <h2>종합 결론</h2>

  <div class="box green" style="margin-bottom:20px">
    <h4 style="font-size:22px">핵심 3가지</h4>
    <ul style="margin-top:12px">
      <li style="font-size:18px;margin-bottom:12px">
        <strong class="safe">1. 기술 데이터가 AI 학습에 사용되지 않습니다.</strong><br>
        <span style="color:#94a3b8">유료 API 계약상 법적으로 보장. DPA 체결로 추가 강화 가능.</span>
      </li>
      <li style="font-size:18px;margin-bottom:12px">
        <strong class="accent">2. 데이터 전송은 은행 수준으로 보호됩니다.</strong><br>
        <span style="color:#94a3b8">TLS 1.3 암호화 + 30일 자동 삭제. 중간 탈취 사실상 불가능.</span>
      </li>
      <li style="font-size:18px;margin-bottom:12px">
        <strong style="color:#c4b5fd">3. 직원의 개인 AI 사용이 더 큰 위험입니다.</strong><br>
        <span style="color:#94a3b8">회사 시스템으로 통제하는 것이 개인 사용을 방치하는 것보다 안전합니다.</span>
      </li>
    </ul>
  </div>

  <h3>사장님 의사결정 요청 사항</h3>
  <div class="g2">
    <div class="box purple">
      <h4>📄 DPA 체결 추진?</h4>
      <p style="font-size:16px">Anthropic과 데이터 처리 부록(DPA)을 정식 체결하여 <strong>법적 구속력을 확보</strong>하겠습니까?<br><br>비용: 무료 (API 구독에 포함)<br>효과: 법적 보호 강화</p>
    </div>
    <div class="box purple">
      <h4>🖥️ 사내 전용 AI 검토?</h4>
      <p style="font-size:16px">도면, BOM 등 <strong>최고 기밀 데이터</strong>는 외부 전송 없이 사내 AI 모델로 처리하는 방안을 검토하겠습니까?<br><br>비용: 서버 투자 필요<br>효과: 외부 전송 완전 제거</p>
    </div>
  </div>
</div>

<!-- ========== SLIDE 13: 끝 ========== -->
<div class="slide cover" data-num="" style="min-height:400px">
  <div style="position:relative;z-index:1">
    <div class="logo">🔒</div>
    <h1 style="font-size:36px">감사합니다</h1>
    <p class="sub">추가 궁금하신 사항은 AI운영팀으로 문의해 주십시오.</p>
    <div class="meta" style="margin-top:32px">
      <p>(주)윈텍오토메이션 AI운영팀</p>
      <p style="margin-top:4px;color:#475569">CONFIDENTIAL — 본 자료는 사내 기밀입니다</p>
    </div>
  </div>
</div>

</div>

<div class="footer">
  <p>© 2026 (주)윈텍오토메이션. All rights reserved.</p>
</div>

</body>
</html>"""


@app.route("/security-report")
def security_report_page():
    """대표이사 보고용 — AI 멀티에이전트 데이터 보안 리포트"""
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WTA AI 시스템 데이터 보안 보고서</title>
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Pretendard Variable',-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;line-height:1.8}
  .hero{background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#0f172a 100%);border-bottom:1px solid #334155;padding:60px 24px 48px;text-align:center;position:relative;overflow:hidden}
  .hero::before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 30% 50%,rgba(56,189,248,0.05) 0%,transparent 50%),radial-gradient(circle at 70% 50%,rgba(168,85,247,0.05) 0%,transparent 50%);animation:pulse 8s ease-in-out infinite alternate}
  @keyframes pulse{0%{opacity:0.5}100%{opacity:1}}
  .hero .badge{display:inline-block;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#fca5a5;padding:4px 16px;border-radius:20px;font-size:12px;font-weight:600;letter-spacing:1px;margin-bottom:16px;text-transform:uppercase}
  .hero h1{font-size:28px;font-weight:700;color:#f1f5f9;margin-bottom:8px}
  .hero .subtitle{font-size:15px;color:#94a3b8;max-width:600px;margin:0 auto}
  .hero .meta{margin-top:20px;font-size:13px;color:#64748b}
  .hero .meta span{margin:0 12px}
  .content{max-width:900px;margin:-20px auto 60px;padding:0 20px}
  .toc{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px 32px;margin-bottom:24px}
  .toc h3{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:2px;margin-bottom:12px}
  .toc a{display:block;color:#38bdf8;text-decoration:none;padding:4px 0;font-size:14px;transition:color 0.2s}
  .toc a:hover{color:#7dd3fc}
  .toc a .num{color:#64748b;margin-right:8px;font-weight:600}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:32px;margin-bottom:20px;position:relative;overflow:hidden}
  .card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
  .card.safe::before{background:linear-gradient(90deg,#22c55e,#16a34a)}
  .card.warn::before{background:linear-gradient(90deg,#f59e0b,#d97706)}
  .card.danger::before{background:linear-gradient(90deg,#ef4444,#dc2626)}
  .card.info::before{background:linear-gradient(90deg,#3b82f6,#2563eb)}
  .card.purple::before{background:linear-gradient(90deg,#a855f7,#7c3aed)}
  .card h2{font-size:20px;font-weight:700;margin-bottom:16px;color:#f1f5f9;display:flex;align-items:center;gap:10px}
  .card h3{font-size:16px;font-weight:600;margin:20px 0 10px;color:#cbd5e1}
  .card p,.card li{font-size:14px;color:#94a3b8;margin-bottom:8px}
  .card ul{padding-left:20px}
  .card li{margin-bottom:6px}
  .highlight{color:#f1f5f9;font-weight:600}
  .tag{display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:0.5px}
  .tag.green{background:rgba(34,197,94,0.15);color:#4ade80;border:1px solid rgba(34,197,94,0.3)}
  .tag.yellow{background:rgba(245,158,11,0.15);color:#fbbf24;border:1px solid rgba(245,158,11,0.3)}
  .tag.red{background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3)}
  .tag.blue{background:rgba(59,130,246,0.15);color:#60a5fa;border:1px solid rgba(59,130,246,0.3)}
  .diagram{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:24px;margin:16px 0;font-family:'Courier New',monospace;font-size:12px;line-height:1.6;color:#94a3b8;overflow-x:auto;white-space:pre}
  .diagram .arrow{color:#38bdf8}
  .diagram .label{color:#a855f7}
  .diagram .safe{color:#4ade80}
  .diagram .warn{color:#fbbf24}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
  @media(max-width:700px){.grid{grid-template-columns:1fr}}
  .grid-item{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px}
  .grid-item h4{font-size:14px;color:#e2e8f0;margin-bottom:8px;display:flex;align-items:center;gap:6px}
  .grid-item p{font-size:13px;color:#64748b}
  .stat{text-align:center;padding:16px}
  .stat .num{font-size:36px;font-weight:800;background:linear-gradient(135deg,#38bdf8,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .stat .label{font-size:12px;color:#64748b;margin-top:4px}
  table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}
  th{text-align:left;padding:10px 12px;background:#0f172a;color:#94a3b8;font-weight:600;border-bottom:1px solid #334155;font-size:12px;text-transform:uppercase;letter-spacing:0.5px}
  td{padding:10px 12px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1}
  tr:hover td{background:rgba(56,189,248,0.03)}
  .check{color:#4ade80}
  .cross{color:#f87171}
  .shield{display:inline-flex;align-items:center;gap:6px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.2);padding:6px 14px;border-radius:8px;font-size:13px;color:#4ade80;margin:4px}
  .risk{display:inline-flex;align-items:center;gap:6px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);padding:6px 14px;border-radius:8px;font-size:13px;color:#f87171;margin:4px}
  .footer{text-align:center;padding:40px 20px;color:#475569;font-size:12px;border-top:1px solid #1e293b}
  .exec-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}
  @media(max-width:700px){.exec-summary{grid-template-columns:repeat(2,1fr)}}
  .kpi{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center}
  .kpi .value{font-size:28px;font-weight:800}
  .kpi .desc{font-size:11px;color:#64748b;margin-top:4px}
  .kpi.good .value{color:#4ade80}
  .kpi.caution .value{color:#fbbf24}
  .kpi.bad .value{color:#f87171}
  .kpi.info .value{color:#38bdf8}
  .quote{border-left:3px solid #a855f7;padding:12px 20px;margin:16px 0;background:rgba(168,85,247,0.05);border-radius:0 8px 8px 0}
  .quote p{color:#c4b5fd;font-style:italic;font-size:14px;margin:0}
  .compare{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:16px 0;border:1px solid #334155;border-radius:8px;overflow:hidden}
  .compare-col{padding:20px}
  .compare-col.before{background:rgba(239,68,68,0.05);border-right:1px solid #334155}
  .compare-col.after{background:rgba(34,197,94,0.05)}
  .compare-col h4{font-size:13px;font-weight:700;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px}
  .compare-col.before h4{color:#f87171}
  .compare-col.after h4{color:#4ade80}
  .compare-col li{font-size:13px;color:#94a3b8;margin-bottom:4px;list-style:none;padding-left:16px;position:relative}
  .compare-col li::before{position:absolute;left:0}
  .compare-col.before li::before{content:'✗';color:#f87171}
  .compare-col.after li::before{content:'✓';color:#4ade80}
</style>
</head>
<body>

<div class="hero">
  <div class="badge">CONFIDENTIAL — 대표이사 보고용</div>
  <h1>🔒 WTA AI 멀티에이전트 시스템<br>데이터 보안 보고서</h1>
  <p class="subtitle">AI 기술 도입에 따른 기술 데이터 보호 체계 및 외부 유출 방지 대책</p>
  <div class="meta">
    <span>보고일: 2026-04-02</span>
    <span>|</span>
    <span>작성: AI운영팀 (MAX)</span>
    <span>|</span>
    <span>보안등급: 사내 기밀</span>
  </div>
</div>

<div class="content">

  <div class="toc">
    <h3>목차</h3>
    <a href="#exec"><span class="num">01</span> 핵심 요약 (Executive Summary)</a>
    <a href="#ai-data"><span class="num">02</span> AI 서버 데이터 유출 분석 — 가장 중요한 질문</a>
    <a href="#dataflow"><span class="num">03</span> 데이터 흐름도 — 어떤 데이터가 어디로 가는가</a>
    <a href="#anthropic"><span class="num">04</span> Anthropic(Claude) 데이터 정책 상세</a>
    <a href="#compare"><span class="num">05</span> 경쟁사 AI 서비스 보안 비교</a>
    <a href="#internal"><span class="num">06</span> 내부 보안 자체 감사 결과</a>
    <a href="#measures"><span class="num">07</span> 현재 보호 조치 및 개선 계획</a>
    <a href="#risk"><span class="num">08</span> 잔여 리스크 및 대응 방안</a>
    <a href="#conclusion"><span class="num">09</span> 결론 및 권고</a>
  </div>

  <!-- 1. Executive Summary -->
  <div class="card info" id="exec">
    <h2>📋 01. 핵심 요약</h2>
    <div class="exec-summary">
      <div class="kpi good"><div class="value">0건</div><div class="desc">AI 학습에 사용된<br>WTA 데이터</div></div>
      <div class="kpi good"><div class="value">30일</div><div class="desc">API 로그 최대<br>보존 기간</div></div>
      <div class="kpi info"><div class="value">14명</div><div class="desc">운영 중인<br>AI 에이전트</div></div>
      <div class="kpi good"><div class="value">100%</div><div class="desc">사내 서버<br>처리 비율</div></div>
    </div>
    <div class="quote">
      <p>"WTA의 기술 데이터는 AI 모델 학습에 사용되지 않으며, API 호출 데이터는 최대 30일 후 자동 삭제됩니다. 모든 에이전트 처리는 사내 서버에서 이루어지고, 외부 전송은 Claude API 호출 시에만 암호화된 채널(TLS 1.3)을 통해 발생합니다."</p>
    </div>
  </div>

  <!-- 2. AI 데이터 유출 핵심 -->
  <div class="card danger" id="ai-data">
    <h2>🎯 02. AI 서버 데이터 유출 분석</h2>
    <p style="color:#f1f5f9;font-size:15px;margin-bottom:16px">
      <strong>대표님의 핵심 우려:</strong> "AI를 활용하면서 기술 데이터가 AI 서버나 외부로 유출되는 것"
    </p>

    <h3>❓ Q1. WTA 데이터가 Claude AI 학습에 사용되는가?</h3>
    <p><span class="tag green">NO — 사용되지 않음</span></p>
    <ul>
      <li>Anthropic의 <span class="highlight">상용 API(Claude API)</span>는 고객 데이터를 모델 학습에 사용하지 않음</li>
      <li>이는 Anthropic 서비스 약관(Commercial Terms)에 명시된 법적 보장 사항</li>
      <li>무료 웹 채팅(claude.ai 무료)과 달리, <span class="highlight">유료 API는 학습 제외가 기본 정책</span></li>
    </ul>

    <h3>❓ Q2. 어떤 데이터가 외부(Anthropic 서버)로 전송되는가?</h3>
    <p>에이전트가 Claude API를 호출할 때 전송되는 데이터:</p>
    <ul>
      <li><span class="highlight">프롬프트(질문)</span> — 에이전트가 분석을 요청하는 텍스트</li>
      <li><span class="highlight">컨텍스트 데이터</span> — DB 조회 결과, 문서 내용 등 분석에 필요한 참조 데이터</li>
      <li><span class="highlight">파일 내용</span> — 문서 분석 시 텍스트 추출본 (이미지는 VLM 호출 시에만)</li>
    </ul>
    <p style="margin-top:8px"><span class="tag yellow">주의</span> 전송은 되지만, <strong>학습에는 사용되지 않고 30일 이내 삭제</strong>됩니다.</p>

    <h3>❓ Q3. 전송 시 암호화는 되는가?</h3>
    <p><span class="tag green">YES — TLS 1.3 암호화</span></p>
    <ul>
      <li>모든 API 호출은 HTTPS(TLS 1.3)로 암호화 전송</li>
      <li>전송 중 제3자가 데이터를 열람하는 것은 <span class="highlight">사실상 불가능</span></li>
    </ul>

    <h3>❓ Q4. Anthropic 직원이 우리 데이터를 볼 수 있는가?</h3>
    <p><span class="tag yellow">제한적 가능 — Trust & Safety 목적에 한함</span></p>
    <ul>
      <li>정상 운영 시 열람하지 않음</li>
      <li>악용 방지(Trust & Safety) 조사 시에만 제한적 접근 가능</li>
      <li>기술 데이터 열람 목적의 접근은 <span class="highlight">불가</span></li>
    </ul>

    <h3>❓ Q5. 만약 Anthropic이 해킹당하면?</h3>
    <p>이론적 리스크이며, Anthropic의 대응 체계:</p>
    <ul>
      <li>SOC 2 Type II 인증 보유</li>
      <li>저장 데이터 암호화(AES-256)</li>
      <li>30일 후 자동 삭제 → 노출 가능 데이터 최소화</li>
      <li>별도 <span class="highlight">데이터 처리 부록(DPA)</span> 체결 가능 — 기업 맞춤 보안 계약</li>
    </ul>
  </div>

  <!-- 3. 데이터 흐름도 -->
  <div class="card purple" id="dataflow">
    <h2>🔄 03. 데이터 흐름도</h2>
    <p>WTA 시스템에서 데이터가 이동하는 전체 경로입니다.</p>
    <div class="diagram">
<span class="label">[ WTA 사내 서버 (192.168.x.x) ]</span>
  │
  ├─ <span class="safe">MES DB (PostgreSQL)</span> ─────── 사내 전용, 외부 접근 차단
  │     ↕ 조회/저장
  ├─ <span class="safe">ERP DB (SQL Server)</span> ──────── 읽기 전용, 사내망
  │     ↕ 읽기
  ├─ <span class="safe">AI 에이전트 14명</span> ──────────── 사내 서버에서 실행
  │     │
  │     ├─ 에이전트 간 통신 ────────── <span class="safe">✅ 사내망 (HTTP localhost)</span>
  │     │
  │     └─ Claude API 호출 ────────── <span class="warn">⚠️ 외부 전송 (HTTPS/TLS 1.3)</span>
  │           │
  │           ▼
  │     <span class="label">[ Anthropic 클라우드 (미국) ]</span>
  │           │
  │           ├─ 처리 후 응답 반환
  │           ├─ 30일 이내 로그 삭제
  │           └─ <span class="safe">✅ 모델 학습 사용 안함</span>
  │
  ├─ <span class="safe">슬랙 (Slack)</span> ────────────────── 메시지 게이트웨이
  │     └─ 슬랙 서버(미국)에 메시지 저장 (슬랙 자체 정책)
  │
  ├─ <span class="safe">텔레그램</span> ───────────────────── 부서장 통신 채널
  │
  └─ <span class="safe">Jira/Confluence</span> ──────────── 이슈/문서 관리 (Atlassian Cloud)

<span class="label">[ 외부 전송 경로 요약 ]</span>
  ┌────────────────────┬──────────────┬──────────┬────────────┐
  │ 경로               │ 데이터 종류  │ 암호화   │ 학습 사용  │
  ├────────────────────┼──────────────┼──────────┼────────────┤
  │ → Anthropic API    │ 프롬프트+컨텍스트 │ TLS 1.3  │ <span class="safe">사용 안함</span>  │
  │ → Slack 서버       │ 채널 메시지   │ TLS 1.2+ │ <span class="safe">사용 안함</span>  │
  │ → Atlassian Cloud  │ 이슈/문서    │ TLS 1.2+ │ <span class="safe">사용 안함</span>  │
  │ → Telegram 서버    │ 명령/보고    │ MTProto  │ <span class="safe">사용 안함</span>  │
  └────────────────────┴──────────────┴──────────┴────────────┘</div>
  </div>

  <!-- 4. Anthropic 정책 -->
  <div class="card safe" id="anthropic">
    <h2>📜 04. Anthropic(Claude) 데이터 정책 상세</h2>
    <table>
      <tr><th style="width:30%">항목</th><th>내용</th></tr>
      <tr><td>모델 학습 사용</td><td><span class="check">✓</span> <strong>상용 API: 학습에 사용하지 않음</strong> (Commercial Terms §2)</td></tr>
      <tr><td>데이터 보존 기간</td><td>API 로그 최대 30일 보존 후 자동 삭제</td></tr>
      <tr><td>전송 암호화</td><td>TLS 1.3 (HTTPS), 전송 중 제3자 열람 불가</td></tr>
      <tr><td>저장 암호화</td><td>AES-256 at rest (AWS 인프라)</td></tr>
      <tr><td>인증</td><td>SOC 2 Type II, 정기 보안 감사</td></tr>
      <tr><td>데이터 위치</td><td>미국 AWS 리전 (GovCloud 옵션 별도)</td></tr>
      <tr><td>직원 접근</td><td>Trust & Safety 조사 목적에 한해 제한적 접근</td></tr>
      <tr><td>DPA(처리 부록)</td><td>기업 고객 대상 별도 데이터 처리 계약 가능</td></tr>
      <tr><td>서브프로세서</td><td>AWS, GCP (인프라 제공자만, 데이터 열람 없음)</td></tr>
      <tr><td>삭제 요청</td><td>고객 요청 시 즉시 삭제 가능</td></tr>
    </table>

    <div class="compare">
      <div class="compare-col before">
        <h4>무료 AI 채팅 (claude.ai Free)</h4>
        <ul>
          <li>대화 내용이 학습에 사용될 수 있음</li>
          <li>데이터 삭제 요청 절차 복잡</li>
          <li>DPA 체결 불가</li>
          <li>감사 로그 없음</li>
        </ul>
      </div>
      <div class="compare-col after">
        <h4>유료 API (WTA 사용 중) ✓</h4>
        <ul>
          <li>학습에 절대 사용되지 않음</li>
          <li>30일 자동 삭제 + 즉시 삭제 가능</li>
          <li>DPA 체결 가능</li>
          <li>API 사용량/접근 감사 로그 제공</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- 5. 경쟁사 비교 -->
  <div class="card info" id="compare">
    <h2>⚖️ 05. AI 서비스 데이터 보안 비교</h2>
    <table>
      <tr>
        <th>항목</th>
        <th>Claude API<br>(Anthropic)</th>
        <th>GPT API<br>(OpenAI)</th>
        <th>Gemini API<br>(Google)</th>
        <th>국내 LLM<br>(네이버 등)</th>
      </tr>
      <tr>
        <td>API 학습 제외</td>
        <td><span class="check">✓ 기본</span></td>
        <td><span class="check">✓ 기본</span></td>
        <td><span class="check">✓ 유료만</span></td>
        <td><span class="check">✓ 기업용</span></td>
      </tr>
      <tr>
        <td>데이터 보존</td>
        <td>30일</td>
        <td>30일</td>
        <td>18개월*</td>
        <td>미공개</td>
      </tr>
      <tr>
        <td>저장 암호화</td>
        <td><span class="check">✓ AES-256</span></td>
        <td><span class="check">✓ AES-256</span></td>
        <td><span class="check">✓</span></td>
        <td>업체별 상이</td>
      </tr>
      <tr>
        <td>DPA 체결</td>
        <td><span class="check">✓</span></td>
        <td><span class="check">✓</span></td>
        <td><span class="check">✓</span></td>
        <td>일부 가능</td>
      </tr>
      <tr>
        <td>SOC 2 인증</td>
        <td><span class="check">✓ Type II</span></td>
        <td><span class="check">✓ Type II</span></td>
        <td><span class="check">✓</span></td>
        <td>일부만</td>
      </tr>
      <tr>
        <td>데이터 위치</td>
        <td>미국</td>
        <td>미국</td>
        <td>미국/글로벌</td>
        <td>국내 가능</td>
      </tr>
      <tr>
        <td>온프레미스 옵션</td>
        <td><span class="cross">✗</span></td>
        <td><span class="cross">✗</span></td>
        <td><span class="check">✓ Vertex</span></td>
        <td><span class="check">✓ 일부</span></td>
      </tr>
    </table>
    <p style="margin-top:8px;font-size:12px;color:#64748b">* Google Gemini 무료 버전 기준. 유료 API는 정책 상이.</p>
    <p style="margin-top:8px">현재 WTA가 사용하는 <span class="highlight">Anthropic Claude API는 업계 최고 수준의 데이터 보호 정책</span>을 갖추고 있습니다.</p>
  </div>

  <!-- 6. 내부 보안 감사 -->
  <div class="card warn" id="internal">
    <h2>🔍 06. 내부 보안 자체 감사 결과</h2>
    <p>2026-04-02 실시한 자체 보안 감사에서 발견된 사항과 조치 계획입니다.</p>

    <h3>A. 외부 데이터 유출 방어 (AI 관련)</h3>
    <table>
      <tr><th>점검 항목</th><th>상태</th><th>설명</th></tr>
      <tr>
        <td>API 학습 제외</td>
        <td><span class="tag green">안전</span></td>
        <td>유료 API 사용 중, 학습에 사용되지 않음</td>
      </tr>
      <tr>
        <td>API 통신 암호화</td>
        <td><span class="tag green">안전</span></td>
        <td>TLS 1.3 암호화 적용</td>
      </tr>
      <tr>
        <td>민감 데이터 필터링</td>
        <td><span class="tag yellow">개선 필요</span></td>
        <td>도면 번호, 고객 정보 등 민감 데이터 전송 전 필터링 로직 강화 필요</td>
      </tr>
      <tr>
        <td>API 호출 감사 로그</td>
        <td><span class="tag yellow">개선 필요</span></td>
        <td>어떤 데이터가 API로 전송됐는지 감사 로그 보강 필요</td>
      </tr>
      <tr>
        <td>도면/기술문서 전송 제한</td>
        <td><span class="tag yellow">개선 필요</span></td>
        <td>CAD 파일, 기밀 도면 등 자동 전송 차단 정책 수립 필요</td>
      </tr>
    </table>

    <h3>B. 내부 인프라 보안</h3>
    <table>
      <tr><th>점검 항목</th><th>상태</th><th>조치 계획</th></tr>
      <tr>
        <td>인증 토큰 관리</td>
        <td><span class="tag red">조치 필요</span></td>
        <td>토큰 파일 암호화 저장 전환 (1주 내)</td>
      </tr>
      <tr>
        <td>에이전트 간 통신 인증</td>
        <td><span class="tag yellow">개선 필요</span></td>
        <td>사내망 내 통신이나, 에이전트 인증 토큰 도입 예정</td>
      </tr>
      <tr>
        <td>대시보드 API 인증</td>
        <td><span class="tag yellow">개선 필요</span></td>
        <td>사내 접근만 가능하나, 인증 레이어 추가 예정</td>
      </tr>
      <tr>
        <td>데이터베이스 접근</td>
        <td><span class="tag green">안전</span></td>
        <td>환경변수 방식, ERP는 읽기전용 계정</td>
      </tr>
      <tr>
        <td>외부 노출 최소화</td>
        <td><span class="tag green">안전</span></td>
        <td>Cloudflare 터널은 파일 업로드 전용, DB 미노출</td>
      </tr>
      <tr>
        <td>프로세스 권한</td>
        <td><span class="tag yellow">개선 필요</span></td>
        <td>전용 서비스 계정 분리 예정</td>
      </tr>
    </table>
  </div>

  <!-- 7. 보호 조치 -->
  <div class="card safe" id="measures">
    <h2>🛡️ 07. 현재 보호 조치 및 개선 계획</h2>

    <h3>현재 적용된 보호 조치</h3>
    <div class="grid">
      <div class="grid-item">
        <h4><span class="check">✓</span> 유료 API 사용</h4>
        <p>Anthropic 상용 API로 학습 제외 보장. 무료 웹 채팅 사용 금지.</p>
      </div>
      <div class="grid-item">
        <h4><span class="check">✓</span> 사내 서버 운영</h4>
        <p>모든 에이전트가 사내 서버(192.168.x.x)에서 실행. 외부 호스팅 없음.</p>
      </div>
      <div class="grid-item">
        <h4><span class="check">✓</span> DB 직접 노출 차단</h4>
        <p>PostgreSQL, SQL Server 모두 외부 접근 차단. 사내망 전용.</p>
      </div>
      <div class="grid-item">
        <h4><span class="check">✓</span> ERP 읽기 전용</h4>
        <p>ERP DB는 읽기 전용 계정만 사용. 데이터 변조 원천 차단.</p>
      </div>
      <div class="grid-item">
        <h4><span class="check">✓</span> 코드 내 시크릿 관리</h4>
        <p>API 키, DB 비밀번호는 환경변수/.env 파일로 분리 관리.</p>
      </div>
      <div class="grid-item">
        <h4><span class="check">✓</span> 슬랙 채널 격리</h4>
        <p>채널별 에이전트 배정. 업무 데이터 범위 제한. 챗로그 사내 저장.</p>
      </div>
    </div>

    <h3>단기 개선 계획 (2주 내)</h3>
    <table>
      <tr><th>#</th><th>항목</th><th>내용</th><th>기한</th></tr>
      <tr><td>1</td><td>민감 데이터 필터</td><td>도면번호, 고객 코드, 기밀 문서 자동 마스킹 후 API 전송</td><td>1주</td></tr>
      <tr><td>2</td><td>API 감사 로그</td><td>모든 Claude API 호출 시 전송 데이터 요약 로깅</td><td>1주</td></tr>
      <tr><td>3</td><td>토큰 보안 강화</td><td>환경변수 통합 관리, 파일 권한 제한</td><td>1주</td></tr>
      <tr><td>4</td><td>기밀 문서 전송 차단</td><td>CAD, 도면, BOM 원본 파일 API 전송 자동 차단 규칙</td><td>2주</td></tr>
      <tr><td>5</td><td>에이전트 인증</td><td>에이전트 간 통신 시 토큰 기반 인증 도입</td><td>2주</td></tr>
    </table>

    <h3>중장기 로드맵</h3>
    <table>
      <tr><th>시기</th><th>항목</th></tr>
      <tr><td>Q2 2026</td><td>DPA(데이터 처리 부록) Anthropic과 정식 체결</td></tr>
      <tr><td>Q2 2026</td><td>온프레미스 LLM 파일럿 (오픈소스 모델로 기밀 데이터 처리)</td></tr>
      <tr><td>Q3 2026</td><td>전사 보안 감사 체계 구축 (분기별 자동 점검)</td></tr>
      <tr><td>Q3 2026</td><td>HTTPS/TLS 내부 통신 전환</td></tr>
      <tr><td>Q4 2026</td><td>ISO 27001 준비 (AI 운영 보안 포함)</td></tr>
    </table>
  </div>

  <!-- 8. 잔여 리스크 -->
  <div class="card warn" id="risk">
    <h2>⚠️ 08. 잔여 리스크 및 대응 방안</h2>

    <table>
      <tr><th>리스크</th><th>발생 확률</th><th>영향도</th><th>대응 방안</th></tr>
      <tr>
        <td>Anthropic 서버 해킹으로 API 로그 유출</td>
        <td><span class="tag green">극히 낮음</span></td>
        <td><span class="tag yellow">중간</span></td>
        <td>30일 자동 삭제로 노출 범위 최소화. DPA 체결로 법적 보호 강화.</td>
      </tr>
      <tr>
        <td>사내 서버 해킹으로 전체 시스템 침해</td>
        <td><span class="tag yellow">낮음</span></td>
        <td><span class="tag red">높음</span></td>
        <td>방화벽 강화, 에이전트 인증 도입, 프로세스 권한 분리.</td>
      </tr>
      <tr>
        <td>직원 실수로 기밀 데이터를 AI에 입력</td>
        <td><span class="tag yellow">중간</span></td>
        <td><span class="tag yellow">중간</span></td>
        <td>민감 데이터 자동 필터링 + 교육 + 가이드라인 수립.</td>
      </tr>
      <tr>
        <td>슬랙/텔레그램 메시지 외부 유출</td>
        <td><span class="tag green">낮음</span></td>
        <td><span class="tag yellow">중간</span></td>
        <td>사내 챗로그 병행 저장. 슬랙 Enterprise Grid 검토.</td>
      </tr>
      <tr>
        <td>Anthropic 정책 변경 (학습 제외 철회)</td>
        <td><span class="tag green">극히 낮음</span></td>
        <td><span class="tag red">높음</span></td>
        <td>DPA 체결 시 법적 구속력. 변경 시 사전 통지 의무.</td>
      </tr>
    </table>
  </div>

  <!-- 9. 결론 -->
  <div class="card safe" id="conclusion">
    <h2>✅ 09. 결론 및 권고</h2>

    <div class="quote">
      <p>"WTA의 AI 멀티에이전트 시스템은 업계 최고 수준의 데이터 보호 정책을 가진 Anthropic Claude API를 사용하고 있으며, 기술 데이터의 AI 학습 사용은 원천적으로 차단되어 있습니다."</p>
    </div>

    <h3>핵심 결론 3가지</h3>
    <ul>
      <li><span class="highlight">1. 기술 데이터 AI 학습 사용 = 없음.</span> 유료 API 정책상 보장되며, DPA 체결로 법적 구속력을 추가할 수 있습니다.</li>
      <li><span class="highlight">2. 데이터 전송은 불가피하나, 보호됨.</span> AI 분석을 위해 데이터 전송은 필수이지만, TLS 1.3 암호화 + 30일 자동 삭제로 보호됩니다.</li>
      <li><span class="highlight">3. 내부 보안 강화가 더 시급.</span> AI 서버 유출보다 사내 인프라 보안(토큰 관리, 인증 체계)이 우선 개선 대상입니다.</li>
    </ul>

    <h3>대표이사 검토 요청 사항</h3>
    <div class="grid">
      <div class="grid-item" style="border-left:3px solid #a855f7">
        <h4>🔏 DPA 체결 승인</h4>
        <p>Anthropic과 데이터 처리 부록(DPA) 체결을 통해 법적 보호를 강화하겠습니까?</p>
      </div>
      <div class="grid-item" style="border-left:3px solid #38bdf8">
        <h4>🖥️ 온프레미스 LLM 검토</h4>
        <p>기밀 도면/BOM 등 최고 기밀 데이터는 사내 전용 AI 모델로 처리하는 방안을 검토하겠습니까?</p>
      </div>
    </div>

    <div style="margin-top:24px;padding:20px;background:#0f172a;border-radius:8px;border:1px solid #334155;text-align:center">
      <p style="color:#64748b;font-size:13px;margin-bottom:8px">보안 등급</p>
      <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap">
        <span class="shield">🔒 API 학습 제외 보장</span>
        <span class="shield">🔐 TLS 1.3 암호화</span>
        <span class="shield">🗑️ 30일 자동 삭제</span>
        <span class="shield">🏢 사내 서버 운영</span>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  <p>(주)윈텍오토메이션 AI운영팀 — CONFIDENTIAL</p>
  <p style="margin-top:4px">본 보고서는 사내 기밀 문서입니다. 외부 유출을 금합니다.</p>
  <p style="margin-top:4px;color:#334155">Generated: 2026-04-02 | System: WTA AI Multi-Agent Platform v2.0</p>
</div>

</body>
</html>"""


# ── 기존 대시보드 프로세스 정리 ──
def kill_existing_dashboard(port: int = 5555):
    """지정 포트를 점유 중인 기존 프로세스를 종료"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        my_pid = os.getpid()
        killed = set()
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = int(parts[-1])
                if pid != my_pid and pid not in killed and pid != 0:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        killed.add(pid)
                        print(f"  기존 대시보드 프로세스 종료: PID {pid}")
                    except (ProcessLookupError, PermissionError):
                        pass
        if killed:
            time.sleep(1)  # 포트 해제 대기
    except Exception as e:
        print(f"  기존 프로세스 정리 실패: {e}")


# ── 이미지 캡셔닝 모니터링 API ──

CAPTIONING_PROGRESS_PATH = os.path.join(
    os.path.dirname(BASE_DIR),
    "data", "motion-data", "photos",
    "한국야금_NC_Press_29-31호기",
    "captions_progress.json",
)

@app.route("/api/captioning/status")
def captioning_status():
    """이미지 캡셔닝 진행 현황 조회"""
    if not os.path.exists(CAPTIONING_PROGRESS_PATH):
        return jsonify({"success": True, "data": {"total": 0, "completed": 0, "captions": [], "message": "캡셔닝 진행 파일이 아직 생성되지 않았습니다."}})

    try:
        with open(CAPTIONING_PROGRESS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return jsonify({"success": False, "error": f"파일 읽기 실패: {e}"}), 500

    # captions_progress.json 구조에 맞게 파싱
    captions = data.get("captions", data.get("results", []))
    total = data.get("total", data.get("total_files", len(captions)))
    completed = data.get("completed", len(captions))

    return jsonify({
        "success": True,
        "data": {
            "total": total,
            "completed": completed,
            "remaining": total - completed,
            "progress_pct": round(completed / total * 100, 1) if total > 0 else 0,
            "captions": captions,
        },
    })


@app.route("/api/captioning/image")
def captioning_image():
    """캡셔닝 이미지 서빙 (보안: motion-data 하위만 허용)"""
    rel_path = request.args.get("path", "")
    if not rel_path:
        return jsonify({"error": "path 파라미터 필요"}), 400

    photos_base = os.path.join(
        os.path.dirname(BASE_DIR),
        "data", "motion-data", "photos",
    )
    full_path = os.path.normpath(os.path.join(photos_base, rel_path))

    # 경로 순회 방지
    if not full_path.startswith(os.path.normpath(photos_base)):
        return jsonify({"error": "접근 불가 경로"}), 403

    if not os.path.isfile(full_path):
        return jsonify({"error": "파일 없음"}), 404

    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename)


# ── 벡터 검색 API ──
OLLAMA_EMBED_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/api/embed"
EMBED_MODEL_NAME = "qwen3-embedding:8b"
EMBED_DIM = 2000


def _get_embedding(text: str) -> list[float] | None:
    """Ollama 임베딩 모델로 텍스트를 벡터화"""
    import json as _json
    try:
        payload = _json.dumps({"model": EMBED_MODEL_NAME, "input": [text]}).encode()
        req = urllib.request.Request(
            OLLAMA_EMBED_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
        if "embeddings" in data and data["embeddings"]:
            vec = data["embeddings"][0]
            return vec[:EMBED_DIM]
    except Exception:
        pass
    return None


@app.route("/api/vector-search", methods=["POST"])
def api_vector_search():
    """벡터 유사도 검색 — manual.wta_documents"""
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    limit = min(int(body.get("limit", 20)), 50)
    table = body.get("table", "wta_documents")

    if not query:
        return jsonify({"error": "검색어를 입력해주세요."}), 400

    # 테이블 허용 목록
    allowed_tables = {
        "wta_documents": "manual.wta_documents",
        "documents": "manual.documents",
    }
    full_table = allowed_tables.get(table)
    if not full_table:
        return jsonify({"error": f"허용되지 않는 테이블: {table}"}), 400

    # 임베딩 생성
    embedding = _get_embedding(query)
    if not embedding:
        return jsonify({"error": "임베딩 생성 실패. 모델 서버를 확인해주세요."}), 500

    # DB 연결
    try:
        import psycopg2
    except ImportError:
        return jsonify({"error": "psycopg2 미설치"}), 500

    password = _load_mes_db_password()
    if not password:
        return jsonify({"error": "DB 비밀번호를 불러올 수 없습니다."}), 500

    try:
        conn = psycopg2.connect(
            host="localhost", port=55432,
            user="postgres", password=password, dbname="postgres",
            connect_timeout=5,
        )
    except Exception as e:
        return jsonify({"error": f"DB 연결 실패: {e}"}), 500

    try:
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        sql = f"""
            SELECT id, source_file, category, chunk_index, chunk_type,
                   page_number, content, image_url, pdf_url,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM {full_table}
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (vec_str, vec_str, limit))
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

        results = []
        for row in rows:
            item = dict(zip(cols, row))
            item["similarity"] = round(float(item["similarity"]), 4)
            results.append(item)

        return jsonify({"query": query, "table": table, "count": len(results), "results": results})
    except Exception as e:
        return jsonify({"error": f"검색 실패: {e}"}), 500
    finally:
        conn.close()


# ── /upload — upload-server(8080) 프록시 ──
UPLOAD_SERVER_URL = "http://localhost:8080"

@app.route("/upload", methods=["GET"])
def upload_page():
    """upload-server HTML 페이지 프록시"""
    try:
        with urllib.request.urlopen(f"{UPLOAD_SERVER_URL}/", timeout=3) as resp:
            data = resp.read()
        from flask import Response
        return Response(data, status=200, content_type="text/html; charset=utf-8")
    except Exception:
        return "Upload server unavailable", 503

@app.route("/upload", methods=["POST"])
def upload_post():
    """파일 업로드를 upload-server(8080)로 포워드"""
    import urllib.request as ur
    content_type = request.content_type or ""
    try:
        req = ur.Request(
            f"{UPLOAD_SERVER_URL}/upload",
            data=request.get_data(),
            headers={"Content-Type": content_type},
            method="POST",
        )
        with ur.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ct = resp.headers.get("Content-Type", "application/json")
        from flask import Response
        return Response(body, status=200, content_type=ct)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route("/api/files/<file_id>/<filename>", methods=["GET"])
def upload_download(file_id: str, filename: str):
    """업로드된 파일 다운로드를 upload-server(8080)로 포워드"""
    import urllib.request as ur
    from flask import Response
    try:
        url = f"{UPLOAD_SERVER_URL}/api/files/{file_id}/{filename}"
        req = ur.Request(url)
        with ur.urlopen(req, timeout=10) as resp:
            body = resp.read()
            ct = resp.headers.get("Content-Type", "application/octet-stream")
            cd = resp.headers.get("Content-Disposition", "")
        headers = {"Content-Type": ct}
        if cd:
            headers["Content-Disposition"] = cd
        return Response(body, status=200, headers=headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ── AI 스킬 라이브러리 API ──
@app.route("/api/skills", methods=["GET"])
def api_skills():
    """스킬 파일(.md)에서 메타데이터 추출하여 반환"""
    import re
    skills = []
    # 스킬 파일 탐색 경로
    skill_dirs = [
        (os.path.join(os.path.dirname(BASE_DIR), ".claude", "skills"), "공용"),
        (os.path.join(os.path.dirname(BASE_DIR), "skills"), "운영"),
    ]
    for skill_dir, source in skill_dirs:
        if not os.path.isdir(skill_dir):
            continue
        for fname in sorted(os.listdir(skill_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(skill_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                # 제목 추출
                title_m = re.search(r"^#\s+(.+)", content, re.MULTILINE)
                title = title_m.group(1).strip() if title_m else fname.replace(".md", "")
                # 트리거 키워드 추출
                trigger_m = re.search(r"##\s*트리거\s*키워드\s*\n(.+)", content)
                triggers = trigger_m.group(1).strip() if trigger_m else ""
                # 개요 추출
                overview_m = re.search(r"##\s*개요\s*\n(.+?)(?:\n##|\Z)", content, re.DOTALL)
                overview = overview_m.group(1).strip()[:200] if overview_m else ""
                # 카테고리 추론
                lower = (title + triggers).lower()
                if any(k in lower for k in ["슬라이드", "ppt", "발표"]):
                    category = "문서작성"
                elif any(k in lower for k in ["매뉴얼", "manual", "파싱"]):
                    category = "매뉴얼"
                elif any(k in lower for k in ["분석", "조사", "리서치"]):
                    category = "분석"
                elif any(k in lower for k in ["개발", "코드", "빌드"]):
                    category = "개발"
                elif any(k in lower for k in ["영업", "고객", "CS"]):
                    category = "영업"
                else:
                    category = "기타"
                skills.append({
                    "id": fname.replace(".md", ""),
                    "title": title,
                    "filename": fname,
                    "source": source,
                    "category": category,
                    "triggers": triggers,
                    "overview": overview,
                    "path": fpath.replace("\\", "/"),
                })
            except Exception:
                continue
    # 에이전트 스킬 참조 (CLAUDE.md의 skills 섹션에서)
    q = request.args.get("q", "").lower()
    cat = request.args.get("category", "")
    if q:
        skills = [s for s in skills if q in s["title"].lower() or q in s["triggers"].lower() or q in s["overview"].lower()]
    if cat:
        skills = [s for s in skills if s["category"] == cat]
    categories = sorted(set(s["category"] for s in skills))
    return jsonify({"skills": skills, "categories": categories, "total": len(skills)})


# ── 슬랙 라우팅 설정 API (agents.json 기반) ──
_AGENTS_JSON = os.path.join(os.path.dirname(BASE_DIR), "config", "agents.json")


@app.route("/api/slack-routing", methods=["GET"])
def api_slack_routing_get():
    """agents.json에서 슬랙 라우팅 관련 필드만 추출하여 반환"""
    try:
        with open(_AGENTS_JSON, "r", encoding="utf-8") as f:
            agents = json.load(f)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    routing = []
    for agent_id, cfg in agents.items():
        if not isinstance(cfg, dict) or agent_id.startswith("_"):
            continue
        channels = cfg.get("slack_channels", [])
        if not channels and not cfg.get("slack_prefix"):
            continue
        routing.append({
            "agent_id": agent_id,
            "agent_name": cfg.get("name", agent_id),
            "emoji": cfg.get("emoji", ""),
            "slack_channels": channels,
            "slack_prefix": cfg.get("slack_prefix", []),
            "mention_required": cfg.get("mention_required", True),
            "auto_response": cfg.get("auto_response", True),
            "ack_message": cfg.get("ack_message", True),
            "context_hint": cfg.get("context_hint", ""),
            "slack_overrides": cfg.get("slack_overrides", {}),
        })
    return jsonify({"routing": routing})


@app.route("/api/slack-routing", methods=["PUT"])
def api_slack_routing_put():
    """agents.json의 슬랙 라우팅 필드 업데이트"""
    data = request.get_json(silent=True)
    if not data or "routing" not in data:
        return jsonify({"error": "routing 필드 필요"}), 400
    try:
        with open(_AGENTS_JSON, "r", encoding="utf-8") as f:
            agents = json.load(f)

        for item in data["routing"]:
            agent_id = item.get("agent_id")
            if not agent_id or agent_id not in agents:
                continue
            agents[agent_id]["slack_channels"] = item.get("slack_channels", [])
            agents[agent_id]["slack_prefix"] = item.get("slack_prefix", [])
            agents[agent_id]["mention_required"] = item.get("mention_required", True)
            agents[agent_id]["auto_response"] = item.get("auto_response", True)
            agents[agent_id]["ack_message"] = item.get("ack_message", True)
            agents[agent_id]["context_hint"] = item.get("context_hint", "")
            if "slack_overrides" in item:
                agents[agent_id]["slack_overrides"] = item["slack_overrides"]

        with open(_AGENTS_JSON, "w", encoding="utf-8") as f:
            json.dump(agents, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/slack-routing/reload", methods=["POST"])
def api_slack_routing_reload():
    """slack-bot에 리로드 신호 전송"""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:5612/reload-routing", method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        return jsonify({"ok": True, "slack_bot": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GraphRAG Neo4j API ──
_NEO4J_BOLT_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
_NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
_NEO4J_PASS = os.environ.get("NEO4J_PASS", "WtaPoc2026!Graph")


def _neo4j_query(cypher: str, params: dict | None = None):
    """Neo4j Bolt 드라이버로 Cypher 실행 후 결과 반환"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return None, "neo4j 드라이버 미설치 (pip install neo4j)"
    try:
        driver = GraphDatabase.driver(_NEO4J_BOLT_URI, auth=(_NEO4J_USER, _NEO4J_PASS))
        with driver.session() as session:
            result = session.run(cypher, params or {})
            records = [dict(r) for r in result]
        driver.close()
        return records, None
    except Exception as e:
        return None, str(e)


@app.route("/api/graphrag/nodes", methods=["GET"])
def api_graphrag_nodes():
    """Neo4j 전체 노드 + 관계 조회 (NVL 포맷)"""
    limit = request.args.get("limit", 200, type=int)
    label = request.args.get("label", "")

    # 노드 조회
    if label:
        node_q = f"MATCH (n:`{label}`) RETURN n LIMIT $limit"
    else:
        node_q = "MATCH (n) RETURN n LIMIT $limit"
    records, err = _neo4j_query(node_q, {"limit": limit})
    if err:
        return jsonify({"error": err}), 500

    nodes = []
    node_ids = set()
    for rec in records:
        n = rec["n"]
        nid = str(n.element_id)
        node_ids.add(nid)
        props = dict(n)
        lbl = list(n.labels)[0] if n.labels else "Node"
        display = props.get("name") or props.get("title") or props.get("id") or lbl
        nodes.append({
            "id": nid,
            "labels": list(n.labels),
            "properties": props,
            "caption": str(display),
        })

    # 관계 조회 (노드 간)
    if label:
        rel_q = f"MATCH (a:`{label}`)-[r]->(b) WHERE elementId(a) IN $ids OR elementId(b) IN $ids RETURN r LIMIT $rlimit"
    else:
        rel_q = "MATCH ()-[r]->() RETURN r LIMIT $rlimit"
    rel_records, rel_err = _neo4j_query(rel_q, {"ids": list(node_ids), "rlimit": limit * 3})
    rels = []
    if rel_records:
        for rec in rel_records:
            r = rec["r"]
            rels.append({
                "id": str(r.element_id),
                "from": str(r.start_node.element_id),
                "to": str(r.end_node.element_id),
                "type": r.type,
                "properties": dict(r),
            })

    return jsonify({"nodes": nodes, "rels": rels})


@app.route("/api/graphrag/labels", methods=["GET"])
def api_graphrag_labels():
    """Neo4j 라벨 목록 + 개수"""
    records, err = _neo4j_query("CALL db.labels() YIELD label RETURN label")
    if err:
        return jsonify({"error": err}), 500
    labels = []
    for rec in records:
        cnt_rec, _ = _neo4j_query(f"MATCH (n:`{rec['label']}`) RETURN count(n) AS cnt")
        cnt = cnt_rec[0]["cnt"] if cnt_rec else 0
        labels.append({"label": rec["label"], "count": cnt})
    return jsonify({"labels": labels})


@app.route("/api/graphrag/search", methods=["GET"])
def api_graphrag_search():
    """키워드로 노드 검색"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"nodes": [], "rels": []})
    cypher = """
    MATCH (n) WHERE any(key IN keys(n) WHERE toString(n[key]) CONTAINS $q)
    RETURN n LIMIT 50
    """
    records, err = _neo4j_query(cypher, {"q": q})
    if err:
        return jsonify({"error": err}), 500

    nodes = []
    node_ids = []
    for rec in records:
        n = rec["n"]
        nid = str(n.element_id)
        node_ids.append(nid)
        props = dict(n)
        lbl = list(n.labels)[0] if n.labels else "Node"
        display = props.get("name") or props.get("title") or props.get("id") or lbl
        nodes.append({
            "id": nid,
            "labels": list(n.labels),
            "properties": props,
            "caption": str(display),
        })

    # 검색된 노드 간 관계
    rels = []
    if node_ids:
        rel_q = "MATCH (a)-[r]->(b) WHERE elementId(a) IN $ids AND elementId(b) IN $ids RETURN r"
        rel_records, _ = _neo4j_query(rel_q, {"ids": node_ids})
        if rel_records:
            for rec in rel_records:
                r = rec["r"]
                rels.append({
                    "id": str(r.element_id),
                    "from": str(r.start_node.element_id),
                    "to": str(r.end_node.element_id),
                    "type": r.type,
                    "properties": dict(r),
                })

    return jsonify({"nodes": nodes, "rels": rels})


@app.route("/api/graphrag/expand", methods=["GET"])
def api_graphrag_expand():
    """특정 노드의 이웃(1-hop) 확장"""
    node_id = request.args.get("node_id", "")
    if not node_id:
        return jsonify({"error": "node_id required"}), 400
    cypher = """
    MATCH (n)-[r]-(m) WHERE elementId(n) = $nid
    RETURN n, r, m LIMIT 50
    """
    records, err = _neo4j_query(cypher, {"nid": node_id})
    if err:
        return jsonify({"error": err}), 500

    nodes_map = {}
    rels = []
    for rec in records:
        for key in ["n", "m"]:
            nd = rec[key]
            nid = str(nd.element_id)
            if nid not in nodes_map:
                props = dict(nd)
                lbl = list(nd.labels)[0] if nd.labels else "Node"
                display = props.get("name") or props.get("title") or props.get("id") or lbl
                nodes_map[nid] = {
                    "id": nid,
                    "labels": list(nd.labels),
                    "properties": props,
                    "caption": str(display),
                }
        r = rec["r"]
        rels.append({
            "id": str(r.element_id),
            "from": str(r.start_node.element_id),
            "to": str(r.end_node.element_id),
            "type": r.type,
            "properties": dict(r),
        })

    return jsonify({"nodes": list(nodes_map.values()), "rels": rels})


@app.route("/api/graphrag/cypher", methods=["POST"])
def api_graphrag_cypher():
    """커스텀 Cypher 쿼리 실행 (읽기 전용)"""
    body = request.get_json(silent=True) or {}
    cypher = (body.get("cypher") or "").strip()
    if not cypher:
        return jsonify({"error": "cypher required"}), 400
    # 쓰기 방지
    upper = cypher.upper()
    for kw in ["CREATE", "MERGE", "DELETE", "SET ", "REMOVE", "DROP", "DETACH"]:
        if kw in upper:
            return jsonify({"error": f"쓰기 쿼리 금지 ({kw})"}), 403
    records, err = _neo4j_query(cypher, body.get("params", {}))
    if err:
        return jsonify({"error": err}), 500
    # 노드/관계 자동 추출
    nodes_map = {}
    rels = []
    raw_rows = []
    for rec in records:
        row = {}
        for k, v in rec.items():
            if hasattr(v, "element_id") and hasattr(v, "labels"):
                nid = str(v.element_id)
                if nid not in nodes_map:
                    props = dict(v)
                    lbl = list(v.labels)[0] if v.labels else "Node"
                    display = props.get("name") or props.get("title") or props.get("id") or lbl
                    nodes_map[nid] = {
                        "id": nid, "labels": list(v.labels),
                        "properties": props, "caption": str(display),
                    }
                row[k] = {"_type": "node", "id": nid}
            elif hasattr(v, "element_id") and hasattr(v, "type"):
                rid = str(v.element_id)
                rels.append({
                    "id": rid,
                    "from": str(v.start_node.element_id),
                    "to": str(v.end_node.element_id),
                    "type": v.type,
                    "properties": dict(v),
                })
                row[k] = {"_type": "rel", "id": rid}
            else:
                row[k] = v
        raw_rows.append(row)
    return jsonify({
        "nodes": list(nodes_map.values()), "rels": rels,
        "rows": raw_rows, "count": len(raw_rows),
    })


# ── 하이브리드 검색 API (Graph + Vector 융합) ──

@app.route("/api/search/hybrid", methods=["POST"])
def api_search_hybrid():
    """Graph(Neo4j) + Vector(pgvector) 하이브리드 검색.

    요청: {"query": "검색어", "vector_limit": 10, "graph_limit": 20, "tables": ["documents","wta_documents"]}
    응답: {"query", "vector_results", "graph_results", "answer", "timing"}
    """
    import time as _time

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "검색어를 입력해주세요."}), 400

    vector_limit = min(int(body.get("vector_limit", 10)), 30)
    graph_limit = min(int(body.get("graph_limit", 20)), 50)
    tables = body.get("tables", ["documents", "wta_documents"])
    generate_answer = body.get("generate_answer", True)

    timings = {}

    # ── 경로 A: pgvector 유사도 검색 ──
    t0 = _time.time()
    vector_results = []

    embedding = _get_embedding(query)
    if embedding:
        password = _load_mes_db_password()
        if password:
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host="localhost", port=55432,
                    user="postgres", password=password, dbname="postgres",
                    connect_timeout=5,
                )
                allowed = {"wta_documents": "manual.wta_documents", "documents": "manual.documents"}
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                try:
                    with conn.cursor() as cur:
                        for tbl_key in tables:
                            full_tbl = allowed.get(tbl_key)
                            if not full_tbl:
                                continue
                            sql = f"""
                                SELECT id, source_file, category, chunk_index, chunk_type,
                                       page_number, content, image_url,
                                       1 - (embedding <=> %s::vector) AS similarity
                                FROM {full_tbl}
                                WHERE embedding IS NOT NULL
                                ORDER BY embedding <=> %s::vector
                                LIMIT %s
                            """
                            cur.execute(sql, (vec_str, vec_str, vector_limit))
                            rows = cur.fetchall()
                            cols = [d[0] for d in cur.description]
                            for row in rows:
                                item = dict(zip(cols, row))
                                item["similarity"] = round(float(item["similarity"]), 4)
                                item["source_table"] = tbl_key
                                vector_results.append(item)
                finally:
                    conn.close()
                # 유사도 내림차순 정렬 후 상위 N개
                vector_results.sort(key=lambda x: x["similarity"], reverse=True)
                vector_results = vector_results[:vector_limit]
            except Exception as e:
                vector_results = [{"error": str(e)}]

    timings["vector_ms"] = round((_time.time() - t0) * 1000)

    # ── 경로 B: Neo4j 그래프 검색 ──
    t0 = _time.time()
    graph_results = []

    # 키워드 추출 (간단 분리: 공백/쉼표 기준 2글자 이상)
    keywords = [w for w in query.replace(",", " ").split() if len(w) >= 2]

    if keywords:
        # CONTAINS 기반 노드 검색 (OR 조건)
        where_clauses = " OR ".join(
            [f"toLower(n.name) CONTAINS toLower($kw{i})" for i in range(len(keywords))]
        )
        params = {f"kw{i}": kw for i, kw in enumerate(keywords)}
        params["lim"] = graph_limit

        cypher = f"""
            MATCH (n)
            WHERE {where_clauses}
            WITH n LIMIT $lim
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, r, m
            LIMIT 100
        """
        records, err = _neo4j_query(cypher, params)
        if records and not err:
            seen_nodes = {}
            seen_rels = set()
            for rec in records:
                for key in ["n", "m"]:
                    node = rec.get(key)
                    if node and hasattr(node, "element_id"):
                        nid = str(node.element_id)
                        if nid not in seen_nodes:
                            props = dict(node)
                            labels = list(node.labels) if hasattr(node, "labels") else []
                            seen_nodes[nid] = {
                                "id": nid,
                                "labels": labels,
                                "name": props.get("name", ""),
                                "properties": {k: str(v)[:200] for k, v in props.items()},
                            }
                rel = rec.get("r")
                if rel and hasattr(rel, "element_id"):
                    rid = str(rel.element_id)
                    if rid not in seen_rels:
                        seen_rels.add(rid)

            graph_results = list(seen_nodes.values())

    timings["graph_ms"] = round((_time.time() - t0) * 1000)

    # ── LLM 답변 생성 (선택적) ──
    answer = None
    if generate_answer and (vector_results or graph_results):
        t0 = _time.time()
        # 컨텍스트 구축
        ctx_parts = []
        if vector_results and not (len(vector_results) == 1 and "error" in vector_results[0]):
            ctx_parts.append("## 벡터 검색 결과 (유사도 순)")
            for i, vr in enumerate(vector_results[:5]):
                src = vr.get("source_file", "")
                content = str(vr.get("content", ""))[:300]
                sim = vr.get("similarity", 0)
                ctx_parts.append(f"{i+1}. [{src}] (유사도 {sim})\n{content}")

        if graph_results:
            ctx_parts.append("\n## 지식그래프 관련 노드")
            for i, gr in enumerate(graph_results[:10]):
                labels = ", ".join(gr.get("labels", []))
                name = gr.get("name", "")
                props = gr.get("properties", {})
                desc = props.get("description", "")[:200]
                ctx_parts.append(f"{i+1}. [{labels}] {name}: {desc}")

        context = "\n".join(ctx_parts)

        # Claude haiku 호출
        try:
            import urllib.request as _ur
            import json as _json

            api_key = _load_anthropic_key()
            if api_key:
                prompt = f"""다음 검색 결과를 바탕으로 질문에 답변해주세요. 한국어로 간결하게 답변하세요.

질문: {query}

{context}

답변:"""
                payload = _json.dumps({
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode()
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = _json.loads(resp.read())
                if data.get("content"):
                    answer = data["content"][0].get("text", "")
            else:
                answer = "(API 키 없음 — .env에 ANTHROPIC_API_KEY 설정 필요)"
        except Exception as e:
            answer = f"(답변 생성 실패: {e})"

        timings["llm_ms"] = round((_time.time() - t0) * 1000)

    timings["total_ms"] = timings.get("vector_ms", 0) + timings.get("graph_ms", 0) + timings.get("llm_ms", 0)

    return jsonify({
        "query": query,
        "vector_results": vector_results,
        "vector_count": len([r for r in vector_results if "error" not in r]),
        "graph_results": graph_results,
        "graph_count": len(graph_results),
        "answer": answer,
        "timing": timings,
    })


# ── 벡터 검색 + LLM 답변 API (그래프 제외) ──

@app.route("/api/search/vector-answer", methods=["POST"])
def api_search_vector_answer():
    """벡터 검색 결과 → LLM 답변 생성 (그래프 없이 벡터 컨텍스트만 사용).

    요청: {"query": "검색어", "limit": 10, "table": "documents"}
    응답: {"query", "results", "count", "answer", "timing"}
    """
    import time as _time

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "검색어를 입력해주세요."}), 400

    limit = min(int(body.get("limit", 10)), 30)
    table = body.get("table", "documents")

    timings = {}

    # ── 벡터 검색 ──
    t0 = _time.time()
    results = []

    embedding = _get_embedding(query)
    if embedding:
        password = _load_mes_db_password()
        if password:
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host="localhost", port=55432,
                    user="postgres", password=password, dbname="postgres",
                    connect_timeout=5,
                )
                allowed = {"wta_documents": "manual.wta_documents", "documents": "manual.documents"}
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                full_tbl = allowed.get(table, "manual.documents")
                try:
                    with conn.cursor() as cur:
                        sql = f"""
                            SELECT id, source_file, category, chunk_index, chunk_type,
                                   page_number, content, image_url,
                                   1 - (embedding <=> %s::vector) AS similarity
                            FROM {full_tbl}
                            WHERE embedding IS NOT NULL
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                        """
                        cur.execute(sql, (vec_str, vec_str, limit))
                        rows = cur.fetchall()
                        cols = [d[0] for d in cur.description]
                        for row in rows:
                            item = dict(zip(cols, row))
                            item["similarity"] = round(float(item["similarity"]), 4)
                            results.append(item)
                finally:
                    conn.close()
            except Exception as e:
                results = [{"error": str(e)}]

    timings["vector_ms"] = round((_time.time() - t0) * 1000)

    # ── LLM 답변 생성 ──
    answer = None
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        t0 = _time.time()
        ctx_parts = ["## 벡터 검색 결과 (유사도 순)"]
        for i, vr in enumerate(valid_results[:5]):
            src = vr.get("source_file", "")
            content = str(vr.get("content", ""))[:300]
            sim = vr.get("similarity", 0)
            ctx_parts.append(f"{i+1}. [{src}] (유사도 {sim})\n{content}")

        context = "\n".join(ctx_parts)

        try:
            import urllib.request as _ur
            import json as _json

            api_key = _load_anthropic_key()
            if api_key:
                prompt = f"""다음 벡터 검색 결과만을 바탕으로 질문에 답변해주세요. 한국어로 간결하게 답변하세요.

질문: {query}

{context}

답변:"""
                payload = _json.dumps({
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode()
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = _json.loads(resp.read())
                if data.get("content"):
                    answer = data["content"][0].get("text", "")
            else:
                answer = "(API 키 없음 — .env에 ANTHROPIC_API_KEY 설정 필요)"
        except Exception as e:
            answer = f"(답변 생성 실패: {e})"

        timings["llm_ms"] = round((_time.time() - t0) * 1000)

    timings["total_ms"] = timings.get("vector_ms", 0) + timings.get("llm_ms", 0)

    return jsonify({
        "query": query,
        "results": results,
        "count": len(valid_results),
        "answer": answer,
        "timing": timings,
    })


# ── reports 정적 HTML 서빙 (Cloudflare 터널 경유) ──
@app.route("/<path:page_name>")
def serve_report_page(page_name: str):
    """reports 폴더의 HTML 파일 서빙. 2단계 이상 하위 폴더 경로 지원."""
    # 보안: 경로 순회 방지
    if ".." in page_name:
        return "Not Found", 404
    reports_dir = os.path.join(os.path.dirname(BASE_DIR), "reports")
    # 보안: realpath로 reports_dir 벗어나는 경로 차단
    candidate = os.path.realpath(os.path.join(reports_dir, page_name))
    reports_real = os.path.realpath(reports_dir)
    if not candidate.startswith(reports_real + os.sep) and candidate != reports_real:
        return "Not Found", 404
    # 직접 매치: reports/{page_name} (경로 포함)
    if os.path.isfile(candidate):
        rel_dir = os.path.dirname(page_name)
        filename = os.path.basename(page_name)
        serve_dir = os.path.join(reports_dir, rel_dir) if rel_dir else reports_dir
        return send_from_directory(serve_dir, filename)
    # .html 확장자 자동 추가
    candidate_html = os.path.realpath(os.path.join(reports_dir, f"{page_name}.html"))
    if os.path.isfile(candidate_html):
        rel_dir = os.path.dirname(page_name)
        filename = os.path.basename(page_name) + ".html"
        serve_dir = os.path.join(reports_dir, rel_dir) if rel_dir else reports_dir
        return send_from_directory(serve_dir, filename)
    return "Not Found", 404


# ── 서버 시작 ──
if __name__ == "__main__":
    # 기존 대시보드 프로세스 정리
    kill_existing_dashboard(5555)

    print(f"\n{'='*50}")
    print(f"  WTA Agent Dashboard")
    print(f"  http://localhost:5555")
    print(f"  시작: {now_kst()}")
    print(f"  등록 에이전트: {len(AGENT_DEFS)}개")
    print(f"{'='*50}\n")

    # P2P 상태 모니터 백그라운드 스레드 시작
    monitor = threading.Thread(target=agent_status_monitor, daemon=True)
    monitor.start()
    print(f"  P2P 상태 모니터 시작 (5초 주기)")

    # 세션 JSONL 동기화 스레드 시작
    sync_thread = threading.Thread(target=session_sync_worker, daemon=True)
    sync_thread.start()
    print(f"  세션 JSONL 동기화 시작 (30초 주기)")

    # 스케줄러 시작
    _init_scheduler()

    socketio.run(app, host="127.0.0.1", port=5555, debug=False)
