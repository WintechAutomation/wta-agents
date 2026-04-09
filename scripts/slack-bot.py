"""
WTA 슬랙 봇 — P2P 직접 통신 방식
- 슬랙 채널 메시지 수신 (Socket Mode) → 채널별 에이전트 포트로 직접 HTTP POST
- 에이전트 메시지 수신 (포트 5612 HTTP 서버) → 슬랙 채널로 직접 발신
- 대시보드 폴링 없음
- 부적합 채널 메시지 → LLM 파싱 → 슬랙 확인 요청 → 확인 시 MES API 자동 등록
- 파일 첨부 시 NC 등록 후 /api/quality/nonconformance/upload 업로드
"""
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ── 로깅 ──
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── 슬랙 챗로그 (채널별/날짜별 JSONL) ──
CHATLOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "slack_chatlog")
os.makedirs(CHATLOG_DIR, exist_ok=True)
_chatlog_lock = threading.Lock()

KST_TZ = timezone(timedelta(hours=9))

def _log_chat(channel_id: str, channel_name: str, user_id: str, username: str, text: str, files: list | None = None):
    """채널ID 기반 단일 JSONL 파일에 메시지 누적 기록 (slack_chatlog/{채널ID}.jsonl)
    파일 첫 줄에 채널 메타정보(이름) 헤더를 기록하고, 이름 변경 시 자동 업데이트.
    첨부파일은 slack_chatlog/{채널ID}_files/ 에 원본 저장."""
    try:
        now = datetime.now(KST_TZ)
        filepath = os.path.join(CHATLOG_DIR, f"{channel_id}.jsonl")
        # 파일이 새로 생성되거나 채널명 변경 시 헤더 업데이트
        header = {"_header": True, "channel_id": channel_id, "channel_name": channel_name}
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if first_line:
                try:
                    old_header = json.loads(first_line)
                    if old_header.get("_header") and old_header.get("channel_name") != channel_name:
                        with open(filepath, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        lines[0] = json.dumps(header, ensure_ascii=False) + "\n"
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.writelines(lines)
                except (json.JSONDecodeError, KeyError):
                    pass
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json.dumps(header, ensure_ascii=False) + "\n")
        # 첨부파일 원본 저장
        saved_files = []
        if files:
            files_dir = os.path.join(CHATLOG_DIR, f"{channel_id}_files")
            os.makedirs(files_dir, exist_ok=True)
            for fi in files:
                fname = fi.get("name", "unknown")
                ftype = fi.get("filetype", "")
                url = fi.get("url_private") or fi.get("url_private_download", "")
                saved_path = None
                if url:
                    try:
                        ts_prefix = now.strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{ts_prefix}_{fname}"
                        dest = os.path.join(files_dir, safe_name)
                        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {BOT_TOKEN}"})
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            with open(dest, "wb") as out:
                                out.write(resp.read())
                        saved_path = dest
                    except Exception:
                        pass
                saved_files.append({"name": fname, "type": ftype, "saved_path": saved_path})
        entry = {
            "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "username": username,
            "text": text,
        }
        if saved_files:
            entry["files"] = saved_files
        with _chatlog_lock:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 챗로그 실패가 봇 동작을 방해하면 안 됨

# ── 슬랙 파일 다운로드 (범용) ──
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "slack")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _download_slack_files(files: list, channel_name: str, username: str) -> list[dict]:
    """슬랙 파일을 uploads/slack/{채널명}/{날짜}/ 경로에 다운로드.
    반환: [{name, filetype, size, local_path}, ...]"""
    if not files:
        return []
    now = datetime.now(KST_TZ)
    date_str = now.strftime("%Y-%m-%d")
    dest_dir = os.path.join(UPLOAD_DIR, channel_name, date_str)
    os.makedirs(dest_dir, exist_ok=True)

    results = []
    for fi in files:
        fname = fi.get("name", "unknown")
        ftype = fi.get("filetype", "")
        fsize = fi.get("size", 0)
        url = fi.get("url_private") or fi.get("url_private_download", "")
        if not url:
            log.warning(f"[파일다운] URL 없음: {fname}")
            continue
        try:
            ts_prefix = now.strftime("%H%M%S")
            safe_name = f"{ts_prefix}_{fname}"
            dest = os.path.join(dest_dir, safe_name)
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {BOT_TOKEN}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(dest, "wb") as out:
                    out.write(resp.read())
            results.append({
                "name": fname,
                "filetype": ftype,
                "size": fsize,
                "local_path": dest,
            })
            log.info(f"[파일다운] 저장 완료: {fname} ({fsize}B) → {dest}")
        except Exception as e:
            log.error(f"[파일다운] 다운로드 실패: {fname} → {e}")
    return results


# ── 매뉴얼 미디어 마커 패턴 ──
# cs-agent가 슬랙 답변에 포함하는 마커 형식:
#   [매뉴얼 이미지: https://...]              → 슬랙 image 블록으로 변환
#   [참조: https://... 파일명 p.N]            → 링크 섹션으로 변환
#   📎 매뉴얼 발췌본: https://...pdf          → 파일 다운로드 후 슬랙 파일 업로드
import re as _re
_IMG_MARKER   = _re.compile(r'\[매뉴얼 이미지:\s*(https?://[^\]]+)\]')
_REF_MARKER   = _re.compile(r'\[참조:\s*(https?://\S+)\s*([^\]]*)\]')
_EXCERPT_MARKER = _re.compile(r'📎\s*매뉴얼 발췌본:\s*(https?://\S+)')


def _extract_media(text: str):
    """텍스트에서 미디어 마커 추출 → (정제된 텍스트, 이미지목록, 참조목록, 발췌URL목록)"""
    images   = _IMG_MARKER.findall(text)
    refs     = _REF_MARKER.findall(text)         # [(url, label), ...]
    excerpts = _EXCERPT_MARKER.findall(text)
    clean = _IMG_MARKER.sub('', text)
    clean = _REF_MARKER.sub('', clean)
    clean = _EXCERPT_MARKER.sub('', clean).strip()
    return clean, images, refs, excerpts


def _upload_file_to_slack(channel_id: str, file_url: str, filename: str, title: str) -> bool:
    """URL에서 파일 다운로드 후 Slack files.uploadV2로 채널에 업로드"""
    try:
        resp = urllib.request.urlopen(urllib.request.Request(file_url, method="GET"), timeout=30)
        file_bytes = resp.read()
    except Exception as e:
        log.warning(f"파일 다운로드 실패 ({file_url[:60]}): {e}")
        return False

    try:
        upload_resp = slack_app.client.files_upload_v2(
            channel=channel_id,
            content=file_bytes,
            filename=filename,
            title=title,
        )
        return bool(upload_resp.get("ok"))
    except Exception as e:
        # files_upload_v2 미지원 시 구버전 API 폴백
        try:
            slack_app.client.files_upload(
                channels=channel_id,
                content=file_bytes,
                filename=filename,
                title=title,
            )
            return True
        except Exception as e2:
            log.warning(f"슬랙 파일 업로드 실패: {e2}")
            return False


# ── 대시보드 로그 ──
_DASHBOARD_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "logs")
_dashboard_log_lock = threading.Lock()


def log_to_dashboard(from_: str, to: str, content: str, msg_type: str = "chat"):
    """슬랙봇 메시지를 대시보드 로그(messages_{date}.json)에 직접 기록"""
    os.makedirs(_DASHBOARD_LOG_DIR, exist_ok=True)
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    log_file = os.path.join(_DASHBOARD_LOG_DIR, f"messages_{today}.json")
    kst_time = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")

    with _dashboard_log_lock:
        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            else:
                logs = []
        except (json.JSONDecodeError, IOError):
            logs = []

        max_id = max((m.get("id", 0) for m in logs), default=0)
        logs.append({
            "id": max_id + 1,
            "from": from_,
            "to": to,
            "content": content,
            "type": msg_type,
            "time": kst_time,
        })
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"대시보드 로그 기록 실패: {e}")

from logging.handlers import RotatingFileHandler as _RotatingFH
import atexit

# 콘솔 핸들러 (기존 동작 유지)
logging.basicConfig(
    level=logging.INFO,
    format="[slack-bot] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("slack-bot")

# 전체 로그 → 파일 (RotatingFileHandler, 10MB × 3)
_rfh = _RotatingFH(
    os.path.join(LOG_DIR, "slack-bot.log"),
    maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
_rfh.setLevel(logging.INFO)
_rfh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(_rfh)

# 에러 로그 → 별도 파일 (WARNING 이상)
_fh = logging.FileHandler(os.path.join(LOG_DIR, "slack-bot-error.log"), encoding="utf-8")
_fh.setLevel(logging.WARNING)
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(_fh)

# stderr → 파일 리다이렉트 (크래시 시에도 기록 보존)
_stderr_file = open(os.path.join(LOG_DIR, "slack-bot-stderr.log"), "a", encoding="utf-8")
sys.stderr = _stderr_file

# 미처리 예외 → slack-bot-error.log 기록
def _unhandled_exception_hook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    log.critical("미처리 예외 발생", exc_info=(exc_type, exc_value, exc_tb))

sys.excepthook = _unhandled_exception_hook

# 프로세스 종료 시점 기록
def _log_shutdown():
    log.info("슬랙 봇 프로세스 종료 — %s",
             datetime.now(KST_TZ).strftime("%Y-%m-%d %H:%M:%S KST"))

atexit.register(_log_shutdown)

# ── 설정 ──
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")

# ── agents.json 기반 라우팅 (외부 설정) ──
AGENTS_JSON_PATH = os.path.join(CONFIG_DIR, "agents.json")
AGENT_PORTS: dict[str, int] = {}
CHANNEL_ROUTING: dict[str, str] = {}          # 채널명 → 에이전트ID (정확 매칭)
CHANNEL_PREFIX_ROUTING: dict[str, str] = {}   # prefix → 에이전트ID (startswith 매칭)
CHANNEL_CONFIG: dict[str, dict] = {}          # 채널명 → {mention_required, auto_response, ack_message, context_hint}
DEFAULT_AGENT = "sales-agent"
_routing_lock = threading.Lock()

def _load_agents_routing():
    """agents.json에서 포트·슬랙 라우팅 설정 로드 (재시작 없이 리로드 가능)"""
    global AGENT_PORTS, CHANNEL_ROUTING, CHANNEL_PREFIX_ROUTING, CHANNEL_CONFIG, DEFAULT_AGENT
    try:
        with open(AGENTS_JSON_PATH, "r", encoding="utf-8") as f:
            agents = json.load(f)
    except Exception as e:
        log.error(f"[라우팅] agents.json 로드 실패: {e}")
        return False

    ports: dict[str, int] = {}
    ch_routing: dict[str, str] = {}
    prefix_routing: dict[str, str] = {}
    ch_config: dict[str, dict] = {}

    default_cfg = agents.get("_default", {})

    for agent_id, cfg in agents.items():
        if agent_id.startswith("_") or not isinstance(cfg, dict):
            continue
        # 포트 매핑
        port = cfg.get("port")
        if port:
            ports[agent_id] = port

        # 슬랙 채널 매핑
        channels = cfg.get("slack_channels", [])
        base_mention = cfg.get("mention_required", True)
        base_auto = cfg.get("auto_response", True)
        base_ack = cfg.get("ack_message", True)
        base_hint = cfg.get("context_hint", "")
        overrides = cfg.get("slack_overrides", {})

        for ch in channels:
            ch_routing[ch] = agent_id
            # 채널별 오버라이드 적용
            ov = overrides.get(ch, {})
            ch_config[ch] = {
                "mention_required": ov.get("mention_required", base_mention),
                "auto_response": ov.get("auto_response", base_auto),
                "ack_message": ov.get("ack_message", base_ack),
                "context_hint": ov.get("context_hint", base_hint),
            }

        # prefix 라우팅
        for prefix in cfg.get("slack_prefix", []):
            prefix_routing[prefix] = agent_id

    with _routing_lock:
        AGENT_PORTS = ports
        CHANNEL_ROUTING = ch_routing
        CHANNEL_PREFIX_ROUTING = prefix_routing
        CHANNEL_CONFIG = ch_config

    log.info(f"[라우팅] agents.json 로드 완료: {len(ports)}개 포트, {len(ch_routing)}개 채널, {len(prefix_routing)}개 prefix")
    return True

# 시작 시 로드
_load_agents_routing()
MY_PORT = 5612
_BOOT_TIME = time.time()

# ── CS 세션 JSONL 로깅 ──
_CS_SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "cs-sessions.jsonl")


def _log_cs_session(session_id: str, query: str, answer: str, channel: str = "webchat",
                    user: str = "unknown", question_source: str = "web", status: str = "responded"):
    """CS 세션을 reports/cs-sessions.jsonl에 기록."""
    now = datetime.now(KST_TZ)
    entry = {
        "session_id": session_id,
        "timestamp": now.isoformat(),
        "channel": channel,
        "user": user,
        "question_source": question_source,
        "language": "ko",
        "query": query,
        "response_summary": answer[:200] if answer else "",
        "status": status,
    }
    try:
        with open(_CS_SESSIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"CS 세션 로깅 실패: {e}")

# ── 프로젝트 슬랙 채널 캐시 (TTL 5분) ──
_project_channel_cache: dict[str, dict | None] = {}  # channel_id → project dict or None
_project_channel_ts: dict[str, float] = {}            # channel_id → timestamp
_PROJECT_CACHE_TTL = 300  # 5분


def _is_project_channel(channel_id: str) -> dict | None:
    """channel_id로 MES 프로젝트 매칭. 프로젝트 채널이면 프로젝트 dict 반환, 아니면 None.
    5분 TTL 캐시로 DB 부하 최소화."""
    now = time.time()
    if channel_id in _project_channel_cache:
        if now - _project_channel_ts.get(channel_id, 0) < _PROJECT_CACHE_TTL:
            return _project_channel_cache[channel_id]

    # MES DB에서 조회
    project = None
    try:
        env_path = "C:/MES/backend/.env"
        db_pw = None
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    db_pw = line.strip().split("=", 1)[1]
                    break
        if db_pw:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost", port=55432, user="postgres",
                password=db_pw, dbname="postgres", connect_timeout=5,
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, project_code, name FROM api_project WHERE slack_channel_id = %s LIMIT 1",
                        (channel_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        project = {"id": row[0], "project_code": row[1], "name": row[2]}
            finally:
                conn.close()
    except Exception as e:
        log.warning(f"[프로젝트채널] DB 조회 실패: {e}")

    _project_channel_cache[channel_id] = project
    _project_channel_ts[channel_id] = now
    return project


# 에이전트 이모지
EMOJI_MAP = {
    "MAX": "👑", "nc-manager": "🔍", "db-manager": "📊",
    "cs-agent": "🛠️", "sales-agent": "💰", "design-agent": "📐",
    "manufacturing-agent": "⚙️", "dev-agent": "💻",
    "admin-agent": "📋", "crafter": "🔧",
    "issue-manager": "🚨", "qa-agent": "🔬",
}


def read_token(filename):
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


# ── MES API 헬퍼 ──

def _mes_request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    """MES API 요청 (인증 헤더 포함)"""
    url = f"{MES_API_URL}/api{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_mes_token() -> str | None:
    """MES 서비스 계정 토큰 발급 (캐시 + 자동 갱신)"""
    if not MES_SERVICE_USERNAME or not MES_SERVICE_PASSWORD:
        log.warning("MES 서비스 계정 환경변수 미설정 (MES_SERVICE_USERNAME, MES_SERVICE_PASSWORD)")
        return None
    with _mes_token_lock:
        now = time.time()
        # 만료 1분 전부터 갱신 시도
        if _mes_token_cache["token"] and _mes_token_cache["expires_at"] > now + 60:
            return _mes_token_cache["token"]
        # refresh 토큰으로 갱신 시도
        if _mes_token_cache["refresh"] and _mes_token_cache["expires_at"] > now:
            try:
                resp = _mes_request("POST", "/auth/refresh", {"refresh_token": _mes_token_cache["refresh"]})
                if resp.get("success") and resp.get("data"):
                    data = resp["data"]
                    token = data.get("access_token") or data.get("access")
                    if token:
                        _mes_token_cache["token"] = token
                        _mes_token_cache["expires_at"] = now + data.get("expires_in", 3600)
                        return _mes_token_cache["token"]
            except Exception:
                pass
        # 신규 로그인
        try:
            resp = _mes_request("POST", "/auth/login", {
                "username": MES_SERVICE_USERNAME,
                "password": MES_SERVICE_PASSWORD,
            })
            if resp.get("success") and resp.get("data"):
                data = resp["data"]
                token = data.get("access_token") or data.get("access")
                if token:
                    _mes_token_cache["token"] = token
                    _mes_token_cache["refresh"] = data.get("refresh_token") or data.get("refresh")
                    _mes_token_cache["expires_at"] = now + data.get("expires_in", 3600)
                    log.info("MES 서비스 계정 로그인 성공")
                    return _mes_token_cache["token"]
            log.error(f"MES 로그인 실패: {resp}")
        except Exception as e:
            log.error(f"MES 로그인 오류: {e}")
        return None


# ── MES 사용자/프로젝트 조회 캐시 ──
_mes_user_cache: dict[str, int | None] = {}  # "이메일 또는 이름" → user_id
_mes_project_cache: dict[str, int | None] = {}  # "프로젝트코드" → project_id


def _lookup_mes_user_by_email(email: str, token: str) -> int | None:
    """MES 사용자 이메일 → user_id 조회 (정확한 1:1 매칭)."""
    if not email:
        return None
    cache_key = f"email:{email}"
    if cache_key in _mes_user_cache:
        return _mes_user_cache[cache_key]
    try:
        encoded = urllib.parse.quote(email)
        resp = _mes_request("GET", f"/users?search={encoded}&page_size=5", token=token)
        for item in (resp.get("data") or []):
            if (item.get("email") or "").lower() == email.lower():
                uid = item.get("id")
                _mes_user_cache[cache_key] = uid
                log.info(f"MES 사용자 매칭 (이메일): {email} → id={uid}")
                return uid
    except Exception as e:
        log.warning(f"MES 사용자 이메일 조회 실패 ({email}): {e}")
    _mes_user_cache[cache_key] = None
    return None


def _lookup_mes_user(name: str, token: str) -> int | None:
    """MES 사용자 이름(한글) → user_id 조회. 이메일 매칭 실패 시 이름 폴백."""
    if not name:
        return None
    if name in _mes_user_cache:
        return _mes_user_cache[name]
    try:
        search_term = name[1:] if len(name) >= 2 else name
        encoded = urllib.parse.quote(search_term)
        resp = _mes_request("GET", f"/users?search={encoded}&page_size=10", token=token)
        for item in (resp.get("data") or []):
            full_name = (item.get("last_name") or "") + (item.get("first_name") or "")
            if full_name == name:
                uid = item.get("id")
                _mes_user_cache[name] = uid
                log.info(f"MES 사용자 매칭 (이름): {name} → id={uid}")
                return uid
        log.info(f"MES 사용자 미발견: {name}")
    except Exception as e:
        log.warning(f"MES 사용자 조회 실패 ({name}): {e}")
    _mes_user_cache[name] = None
    return None


def _lookup_project_id(project_code: str, token: str) -> int | None:
    """프로젝트 코드 → project_id 조회. 결과 캐싱."""
    if not project_code:
        return None
    if project_code in _mes_project_cache:
        return _mes_project_cache[project_code]
    try:
        encoded = urllib.parse.quote(project_code)
        resp = _mes_request("GET", f"/production/projects?search={encoded}&page_size=5", token=token)
        for item in (resp.get("data") or []):
            if item.get("project_code") == project_code:
                pid = item.get("id")
                _mes_project_cache[project_code] = pid
                return pid
    except Exception as e:
        log.warning(f"MES 프로젝트 조회 실패 ({project_code}): {e}")
    _mes_project_cache[project_code] = None
    return None


def parse_nc_message(text: str) -> dict | None:
    """
    슬랙 메시지에서 부적합 정보 추출.
    1. 먼저 LLM(Claude API) 파싱 시도
    2. LLM 실패 시 키워드 패턴 파싱으로 폴백
    반환: CreateNonconformanceRequest 형식 dict, 또는 None (파싱 불가)
    """
    # LLM 파싱 시도 (ANTHROPIC_API_KEY 환경변수 설정 시)
    if ANTHROPIC_API_KEY:
        try:
            result = _parse_nc_with_llm(text)
            if result:
                return result
        except Exception as e:
            log.warning(f"LLM 파싱 실패, 키워드 파싱으로 폴백: {e}")
    # 키워드 패턴 파싱
    return _parse_nc_with_keywords(text)


def _parse_nc_with_llm(text: str) -> dict | None:
    """Claude API로 부적합 정보 추출"""
    prompt = f"""다음 슬랙 메시지에서 부적합 보고서 정보를 JSON으로 추출해주세요.

슬랙 메시지:
{text}

추출 결과를 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "title": "부적합 제목 (필수, 없으면 메시지 첫 줄 사용)",
  "nonconformance_type": "타입코드",
  "importance": "중요도코드",
  "description": "상세 설명",
  "part_no": "부품번호 (없으면 null)",
  "unit_no": "유닛번호 (없으면 null)",
  "reporter_name": "보고자 한글이름 (메시지에 언급 없으면 null)",
  "manager_name": "담당자 한글이름 (메시지에 언급 없으면 null)",
  "action_manager_name": "조치담당자 한글이름 (메시지에 언급 없으면 null)",
  "project_code": "프로젝트코드 (예: WTA-001, 없으면 null)"
}}

타입코드 옵션: design_defect(설계결함), order_error(발주오류), receiving_error(수입검사오류),
machining_defect(가공불량), assembly_defect(조립불량), electrical_defect(전장불량),
software_defect(소프트웨어결함), improvement_request(개선요청), loss_damage(분실파손), cost_reduction(원가절감)

중요도코드: low(낮음), medium(보통), high(높음), critical(심각)

메시지가 부적합과 관련이 없으면 null을 반환하세요."""

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    content_text = data["content"][0]["text"].strip()
    if content_text.lower() == "null":
        return None
    # JSON 추출 (마크다운 코드블록 제거)
    match = re.search(r'\{[\s\S]+\}', content_text)
    if not match:
        return None
    parsed = json.loads(match.group())
    # 필수 필드 검증
    if not parsed.get("title"):
        return None
    parsed.setdefault("nonconformance_type", "assembly_defect")
    parsed.setdefault("importance", "medium")
    return parsed


def _parse_nc_with_keywords(text: str) -> dict | None:
    """키워드 패턴으로 부적합 기본 정보 추출"""
    text_lower = text.lower()

    # 부적합 관련 키워드 확인
    nc_keywords = ["불량", "결함", "오류", "파손", "분실", "문제", "부적합", "이슈", "버그", "고장"]
    if not any(k in text for k in nc_keywords):
        return None

    # 제목: 첫 줄 또는 전체 텍스트 첫 50자
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    title = lines[0][:100] if lines else text[:100]

    # 타입 추론
    type_map = [
        (["설계", "도면", "spec", "스펙"], "design_defect"),
        (["발주", "주문", "오더"], "order_error"),
        (["수입검사", "입고검사", "받았", "입고"], "receiving_error"),
        (["가공", "절삭", "선반", "밀링"], "machining_defect"),
        (["조립", "어셈블리", "취부"], "assembly_defect"),
        (["전장", "전기", "배선", "회로"], "electrical_defect"),
        (["소프트웨어", "펌웨어", "sw ", "fw "], "software_defect"),
        (["개선", "요청", "제안"], "improvement_request"),
        (["파손", "분실", "손상"], "loss_damage"),
        (["원가", "비용 절감", "저렴"], "cost_reduction"),
    ]
    nc_type = "assembly_defect"
    for keywords, t in type_map:
        if any(k in text for k in keywords):
            nc_type = t
            break

    # 중요도 추론
    importance = "medium"
    if any(k in text for k in ["긴급", "심각", "critical", "urgent", "즉시"]):
        importance = "critical"
    elif any(k in text for k in ["높음", "high", "중요", "빨리"]):
        importance = "high"
    elif any(k in text for k in ["낮음", "low", "minor", "경미"]):
        importance = "low"

    # 부품번호 패턴 (예: P-12345, 12345-A)
    part_match = re.search(r'\b([A-Z]{1,3}-?\d{4,8}[A-Z]?)\b', text)
    part_no = part_match.group(1) if part_match else None

    return {
        "title": title,
        "nonconformance_type": nc_type,
        "importance": importance,
        "description": text,
        "part_no": part_no,
        "unit_no": None,
        "reporter_name": None,
        "manager_name": None,
        "action_manager_name": None,
        "project_code": None,
    }


def _register_nc_api(nc_data: dict, username: str, channel_name: str) -> dict | None:
    """
    파싱된 nc_data를 MES API로 부적합 보고서 실제 생성.
    성공 시 생성된 NC dict 반환, 실패 시 None.
    """
    token = get_mes_token()
    if not token:
        log.error("MES 토큰 없음 — NC 자동 등록 불가")
        return None

    description = nc_data.get("description") or ""
    description = f"[슬랙 #{channel_name} - {username}]\n{description}"

    KST = timezone(timedelta(hours=9))
    today_str = datetime.now(KST).strftime("%Y-%m-%d")

    # 보고자: 이메일 우선 매칭 → 실패 시 이름 매칭
    reporter_email = nc_data.get("reporter_email")
    reporter_name = nc_data.get("reporter_name") or username
    reporter_id = None
    if reporter_email:
        reporter_id = _lookup_mes_user_by_email(reporter_email, token)
    if not reporter_id:
        reporter_id = _lookup_mes_user(reporter_name, token)

    # 담당자 이름 → user_id 조회
    manager_id = None
    if nc_data.get("manager_name"):
        manager_id = _lookup_mes_user(nc_data["manager_name"], token)

    action_manager_id = None
    if nc_data.get("action_manager_name"):
        action_manager_id = _lookup_mes_user(nc_data["action_manager_name"], token)

    # 프로젝트 코드 → project_id 조회
    project_id = None
    if nc_data.get("project_code"):
        project_id = _lookup_project_id(nc_data["project_code"], token)

    payload = {
        "title": nc_data["title"],
        "nonconformance_type": nc_data.get("nonconformance_type", "assembly_defect"),
        "importance": nc_data.get("importance", "medium"),
        "description": description,
        "start_date": today_str,
    }
    if reporter_id:
        payload["reporter_id"] = reporter_id
    if manager_id:
        payload["manager_id"] = manager_id
    if action_manager_id:
        payload["action_manager_id"] = action_manager_id
    if project_id:
        payload["project_id"] = project_id
    if nc_data.get("part_no"):
        payload["part_no"] = nc_data["part_no"]
    if nc_data.get("unit_no"):
        payload["unit_no"] = nc_data["unit_no"]

    try:
        resp = _mes_request("POST", "/quality/nonconformance", payload, token=token)
        if resp.get("success") and resp.get("data"):
            nc_id = resp["data"].get("id")
            log.info(f"NC 자동 등록 완료: ID={nc_id}, 제목={payload['title'][:40]}")
            return resp["data"]
        log.error(f"NC 생성 응답 실패: {resp}")
    except Exception as e:
        log.error(f"NC 생성 API 오류: {e}\n{traceback.format_exc()}")
    return None


def upload_nc_file(nc_id: int, file_url: str, filename: str, token: str) -> bool:
    """슬랙 파일을 다운로드해 MES NC 첨부파일로 업로드."""
    try:
        # 슬랙 파일 다운로드 (Bot token 인증 필요)
        req = urllib.request.Request(
            file_url,
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            file_data = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")

        # MES API에 multipart/form-data로 업로드
        boundary = "----WTASlackBotBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + file_data + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="nonconformance_id"\r\n\r\n'
            f"{nc_id}\r\n"
            f"--{boundary}--\r\n"
        ).encode()

        upload_req = urllib.request.Request(
            f"{MES_API_URL}/api/quality/nonconformance/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(upload_req, timeout=30) as resp:
            result = json.loads(resp.read())
        if result.get("success"):
            log.info(f"NC 파일 업로드 완료: nc_id={nc_id}, file={filename}")
            return True
        log.error(f"NC 파일 업로드 실패: {result}")
    except Exception as e:
        log.error(f"NC 파일 업로드 오류: {e}")
    return False


# ── 슬랙 파일 → MES 프로젝트 기술자료 자동 업로드 ──
def _find_project_by_slack_channel(channel_id: str) -> dict | None:
    """slack_channel_id로 MES 프로젝트 조회. 없으면 None."""
    try:
        token = get_mes_token()
        if not token:
            return None
        req = urllib.request.Request(
            f"{MES_API_URL}/api/production/projects?page_size=500",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        for p in data.get("data", {}).get("results", []):
            if p.get("slack_channel_id") == channel_id:
                return p
    except Exception as e:
        log.warning(f"[파일→MES] 프로젝트 조회 실패: {e}")
    return None


def _auto_upload_files_to_mes(channel_id: str, channel_name: str, files: list, username: str):
    """슬랙 채널에 업로드된 파일을 MES 프로젝트 기술자료로 자동 저장."""
    project = _find_project_by_slack_channel(channel_id)
    if not project:
        return  # 매칭 프로젝트 없음 — 무시

    project_id = project.get("id")
    project_code = project.get("project_code", "?")
    token = get_mes_token()
    if not token:
        log.warning("[파일→MES] MES 토큰 획득 실패")
        return

    for f in files:
        file_url = f.get("url_private", "")
        filename = f.get("name", "unknown")
        if not file_url:
            continue

        try:
            # 슬랙에서 파일 다운로드 (Bot token 인증)
            dl_req = urllib.request.Request(
                file_url,
                headers={"Authorization": f"Bearer {BOT_TOKEN}"},
            )
            with urllib.request.urlopen(dl_req, timeout=30) as resp:
                file_data = resp.read()

            # MES API로 multipart/form-data 업로드
            boundary = f"----SlackMES{int(time.time()*1000)}"
            body_parts = []
            # 카테고리: specification (사양서) 고정
            body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"category\"\r\n\r\nspecification".encode())
            body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"description\"\r\n\r\n[Slack #{channel_name}] {username} 업로드".encode())
            body_parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n".encode() + file_data
            )
            body_parts.append(f"--{boundary}--\r\n".encode())
            body = b"\r\n".join(body_parts)

            upload_req = urllib.request.Request(
                f"{MES_API_URL}/api/production/projects/{project_id}/technical-files/",
                data=body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            with urllib.request.urlopen(upload_req, timeout=30) as resp:
                result = json.loads(resp.read())

            if result.get("success"):
                log.info(f"[파일→MES] 업로드 성공: {filename} → 프로젝트 {project_code} (id={project_id})")
                # 슬랙에 확인 메시지
                try:
                    slack_app.client.chat_postMessage(
                        channel=channel_id,
                        text=f"📎 `{filename}` → MES 프로젝트 `{project_code}` 기술자료(사양서)에 자동 저장되었습니다.",
                    )
                except Exception:
                    pass
            else:
                log.warning(f"[파일→MES] 업로드 실패: {filename} → {result}")
        except Exception as e:
            log.error(f"[파일→MES] 업로드 오류: {filename} → {e}")


# ── 대기 중인 NC 확인 요청 (message_ts → {nc_data, username, channel_name, file_infos}) ──
_pending_nc: dict = {}
_pending_nc_lock = threading.Lock()

# ── 부적합 채널 !등록 세션 (channel_name → {user_id, username, channel_id, start_time}) ──
_nc_sessions: dict = {}
_nc_sessions_lock = threading.Lock()
NC_SESSION_TIMEOUT = 300  # 5분

# ── NC 모달 등록 후 파일 첨부 세션 (user_id → {nc_id, channel_id, start_time}) ──
_nc_file_sessions: dict = {}
_nc_file_sessions_lock = threading.Lock()
NC_FILE_SESSION_TIMEOUT = 180  # 3분

# ── Ack-first: 처리중 메시지 대기 (channel_id → {ts, agent, request_time, user, question_preview, channel_name}) ──
_pending_ack: dict = {}
_pending_ack_lock = threading.Lock()

# ── 피드백 대기 (channel_id:msg_ts → {agent, channel, question_preview, answer_preview}) ──
_pending_feedback: dict = {}
_pending_feedback_lock = threading.Lock()

# ── 데이터 디렉토리 ──
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def _record_response_time(ack_info: dict, agent: str, answer: str, channel_name: str):
    """응답시간 data/response-times.jsonl 기록"""
    now = time.time()
    elapsed = now - ack_info.get("request_time", now)
    mins, secs = divmod(int(elapsed), 60)
    elapsed_display = f"{mins}분 {secs}초" if mins > 0 else f"{secs}초"
    record = {
        "ts": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S"),
        "channel": channel_name,
        "agent": agent,
        "user": ack_info.get("user", ""),
        "question_preview": ack_info.get("question_preview", ""),
        "request_time": ack_info.get("request_time", 0),
        "response_time": now,
        "elapsed_sec": round(elapsed, 1),
        "elapsed_display": elapsed_display,
    }
    try:
        filepath = os.path.join(DATA_DIR, "response-times.jsonl")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        log.info(f"[응답시간] {agent} #{channel_name}: {elapsed_display}")
    except Exception as e:
        log.warning(f"응답시간 기록 실패: {e}")


def _write_feedback(rating: str, info: dict, ch_id: str, user_id: str):
    """피드백 data/answer-feedback.jsonl 기록 (good → answer-cache.jsonl에도 저장)"""
    record = {
        "ts": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S"),
        "channel": info.get("channel", ch_id),
        "agent": info.get("agent", ""),
        "question_preview": info.get("question_preview", ""),
        "answer_preview": info.get("answer_preview", ""),
        "rating": rating,
        "user": user_id,
    }
    try:
        with open(os.path.join(DATA_DIR, "answer-feedback.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if rating == "good":
            cache = {
                "ts": record["ts"],
                "channel": record["channel"],
                "agent": record["agent"],
                "question": record["question_preview"],
                "answer_preview": record["answer_preview"],
            }
            with open(os.path.join(DATA_DIR, "answer-cache.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(cache, ensure_ascii=False) + "\n")
        log.info(f"[피드백] {rating} ← {user_id} ({info.get('agent', '?')})")
    except Exception as e:
        log.warning(f"피드백 기록 실패: {e}")


def create_nc_from_slack(text: str, username: str, channel_name: str) -> dict | None:
    """
    슬랙 메시지를 파싱해 MES API로 부적합 보고서 생성.
    (하위 호환용 — 확인 없이 즉시 등록. 내부에서 직접 호출 시 사용)
    성공 시 생성된 NC dict 반환, 실패 시 None.
    """
    nc_data = parse_nc_message(text)
    if not nc_data:
        log.info(f"부적합 파싱 불가 (NC 등록 건너뜀): {text[:60]}")
        return None
    return _register_nc_api(nc_data, username, channel_name)


BOT_TOKEN = read_token("slack-token.txt")
APP_TOKEN = read_token("slack-app-token.txt")

# ── MES API 서비스 계정 설정 ──
# 환경변수 또는 config 파일로 관리 (평문 저장 금지)
MES_API_URL = os.environ.get("MES_API_URL", "http://localhost:8100")
MES_SERVICE_USERNAME = os.environ.get("MES_SERVICE_USERNAME", "")
MES_SERVICE_PASSWORD = os.environ.get("MES_SERVICE_PASSWORD", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# cs-agent API 키 (scripts/.env에서 로드)
CS_API_KEY = os.environ.get("CS_API_KEY", "")
_scripts_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_scripts_env_path) and not CS_API_KEY:
    try:
        with open(_scripts_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line.startswith("CS_API_KEY="):
                    CS_API_KEY = _line.split("=", 1)[1]
                    break
    except Exception:
        pass

# ── 웹챗 비동기 폴링 (cs-wta.com → slack-bot → cs-agent) ──
_webchat_tickets: dict[str, dict] = {}  # ticket_id → {status, result, created_at}
_webchat_lock = threading.Lock()
# 스트리밍 세션 추적: request_id → {"query": str, "accum": str}
_webchat_stream_sessions: dict[str, dict] = {}
CS_AGENT_CHAT_PORT = 5602  # mcp-agent-channel (cs-agent) 내부 포트


def _webchat_push_to_hub(content: str, sender: str) -> None:
    """cs-agent → slack-bot 웹챗 마커를 hub /api/chat/push로 전달.

    형식:
      webchat-chunk:{id}:{text}
      webchat-done:{id}
      webchat-error:{id}:{msg}
    """
    # 3조각까지만 split (텍스트에 콜론 허용)
    parts = content.split(":", 2)
    marker = parts[0]
    req_id = parts[1] if len(parts) > 1 else ""
    text = parts[2] if len(parts) > 2 else ""
    if not req_id:
        log.warning(f"[webchat-push] req_id 없음: {content[:80]}")
        return

    if marker == "webchat-chunk":
        # [임시 진단 로깅 - 2026-04-06] webchat-chunk raw content 덤프
        pipe_cnt = text.count("|")
        log.info(f"[webchat-raw] {req_id} chunk({len(text)}b, pipes={pipe_cnt}): {text[:400]!r}")
        payload = {"request_id": req_id, "type": "chunk", "data": text}
        # 스트리밍 텍스트 누적
        if req_id in _webchat_stream_sessions:
            _webchat_stream_sessions[req_id]["accum"] += text
    elif marker == "webchat-done":
        payload = {"request_id": req_id, "type": "done", "data": text}
        # 스트리밍 완료 시 CS 세션 기록 (실제 질문/답변 텍스트 사용)
        sess = _webchat_stream_sessions.pop(req_id, None)
        actual_query = sess["query"] if sess else "(unknown)"
        actual_answer = sess["accum"] if sess and sess["accum"] else text or "(no content)"
        _log_cs_session(
            session_id=f"webchat-stream-{req_id}",
            query=actual_query,
            answer=actual_answer[:500] if actual_answer else "(no content)",
            channel="webchat",
            user="unknown",
            question_source="web",
            status="responded",
        )
    elif marker == "webchat-error":
        payload = {"request_id": req_id, "type": "error", "data": text}
        _webchat_stream_sessions.pop(req_id, None)
    else:
        return

    try:
        req = urllib.request.Request(
            f"http://localhost:{CS_AGENT_CHAT_PORT}/api/chat/push",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": CS_API_KEY},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        if result.get("success"):
            log.info(f"[webchat-push] {marker} {req_id} ({len(text)}b) OK")
        else:
            log.warning(f"[webchat-push] {marker} {req_id} 실패: {result.get('error')}")
    except Exception as e:
        log.error(f"[webchat-push] {marker} {req_id} 예외: {e}")


# ── 슬랙 파이프라인 V2 (progressive edit, 2026-04-05) ──
# Feature flag: SLACK_PIPELINE_V2_CHANNELS (콤마 구분 채널 ID)
_SLACK_PIPE_V2_RAW = os.environ.get("SLACK_PIPELINE_V2_CHANNELS", "").strip()
SLACK_PIPE_V2_CHANNELS: set[str] = {
    c.strip() for c in _SLACK_PIPE_V2_RAW.split(",") if c.strip()
}
SLACK_PIPE_THROTTLE_MS = 800
SLACK_PIPE_BURST_CHARS = 120
SLACK_PIPE_MAX_CHARS = 4000
SLACK_PIPE_SESSION_TTL_SEC = 300  # 5분 GC

_slack_pipe_sessions: dict[str, dict] = {}  # request_id → session
_slack_pipe_lock = threading.Lock()


def _slack_pipe_update(req_id: str, sess: dict, *, force: bool = False) -> None:
    """throttle 규칙에 따라 chat.update 호출."""
    now = time.time()
    last_update = sess.get("last_update_at", 0.0)
    last_size = sess.get("last_update_size", 0)
    curr_size = len(sess["accum"])
    elapsed_ms = (now - last_update) * 1000
    delta_chars = curr_size - last_size
    if not force:
        if elapsed_ms < SLACK_PIPE_THROTTLE_MS and delta_chars < SLACK_PIPE_BURST_CHARS:
            return

    emoji = EMOJI_MAP.get(sess.get("target_agent", "cs-agent"), "🤖")
    text = sess["accum"]
    # 4000자 초과 시 첫 chunk는 본문 편집, 잔여는 thread reply로 분할
    main_text = text
    overflow = ""
    if len(text) > SLACK_PIPE_MAX_CHARS:
        main_text = text[:SLACK_PIPE_MAX_CHARS]
        overflow = text[SLACK_PIPE_MAX_CHARS:]
    display = f"{emoji} {sess['target_agent']}\n{main_text}"
    if not sess.get("done"):
        display += " ▌"  # 커서
    try:
        slack_app.client.chat_update(
            channel=sess["channel_id"], ts=sess["ts"], text=display
        )
        sess["last_update_at"] = now
        sess["last_update_size"] = curr_size
        log.info(
            f"[slack-pipe] update {req_id} ts={sess['ts']} size={curr_size}"
        )
    except Exception as e:
        log.warning(f"[slack-pipe] chat.update 실패 {req_id}: {e}")

    # thread reply overflow
    if overflow and not sess.get("overflow_posted"):
        try:
            slack_app.client.chat_postMessage(
                channel=sess["channel_id"],
                thread_ts=sess["ts"],
                text=f"(이어서)\n{overflow[:SLACK_PIPE_MAX_CHARS]}",
            )
            sess["overflow_posted"] = True
        except Exception as e:
            log.warning(f"[slack-pipe] overflow reply 실패 {req_id}: {e}")


def _slack_pipe_handle(content: str, sender: str) -> None:
    """에이전트 → slack-bot 마커 수신 처리.

    형식:
      slack-chunk:{id}:{text}
      slack-done:{id}
      slack-error:{id}:{reason}
    """
    parts = content.split(":", 2)
    marker = parts[0]
    req_id = parts[1] if len(parts) > 1 else ""
    text = parts[2] if len(parts) > 2 else ""
    if not req_id:
        log.warning(f"[slack-pipe] req_id 없음: {content[:80]}")
        return
    with _slack_pipe_lock:
        sess = _slack_pipe_sessions.get(req_id)
    if not sess:
        log.warning(f"[slack-pipe] unknown req_id: {req_id} (marker={marker})")
        return

    if marker == "slack-chunk":
        sess["accum"] += text
        log.info(f"[slack-pipe] chunk {req_id} (+{len(text)}b, total {len(sess['accum'])}b)")
        _slack_pipe_update(req_id, sess)
    elif marker == "slack-done":
        sess["done"] = True
        _slack_pipe_update(req_id, sess, force=True)
        duration = round(time.time() - sess.get("created_at", time.time()), 1)
        log.info(
            f"[slack-pipe] done {req_id} total={len(sess['accum'])}b duration={duration}s"
        )
    elif marker == "slack-error":
        sess["accum"] = f"⚠️ 오류: {text}"
        sess["done"] = True
        _slack_pipe_update(req_id, sess, force=True)
        log.warning(f"[slack-pipe] error {req_id}: {text[:120]}")


def _slack_pipe_start(
    channel_id: str, target_agent: str, user_query: str, username: str
) -> str | None:
    """멘션 수신 시 세션 시작 + 플레이스홀더 발송 + 에이전트에 slack-req 전달.

    Returns: request_id (실패 시 None)
    """
    import uuid
    req_id = uuid.uuid4().hex[:8]
    emoji = EMOJI_MAP.get(target_agent, "🤖")
    try:
        resp = slack_app.client.chat_postMessage(
            channel=channel_id,
            text=f"⏳ {emoji} 답변 생성 중... ▌",
        )
        ts = resp.get("ts")
    except Exception as e:
        log.error(f"[slack-pipe] 플레이스홀더 발송 실패: {e}")
        return None
    if not ts:
        return None

    with _slack_pipe_lock:
        _slack_pipe_sessions[req_id] = {
            "channel_id": channel_id,
            "ts": ts,
            "accum": "",
            "target_agent": target_agent,
            "username": username,
            "created_at": time.time(),
            "last_update_at": time.time(),
            "last_update_size": 0,
            "done": False,
        }
    send_to_agent(
        target_agent,
        f"slack-req:{req_id}:{channel_id}:{user_query}",
        from_id="slack-bot",
    )
    log.info(f"[slack-pipe] req {req_id} ch={channel_id} agent={target_agent}")
    return req_id


def _slack_pipe_gc_loop() -> None:
    """5분 이상 미완료 세션 정리."""
    while True:
        try:
            time.sleep(60)
            now = time.time()
            stale = []
            with _slack_pipe_lock:
                for rid, s in list(_slack_pipe_sessions.items()):
                    age = now - s.get("created_at", now)
                    if s.get("done") and age > 60:
                        stale.append((rid, s, False))
                    elif not s.get("done") and age > SLACK_PIPE_SESSION_TTL_SEC:
                        stale.append((rid, s, True))
            for rid, s, timed_out in stale:
                if timed_out:
                    try:
                        s["accum"] += "\n\n(⚠️ 응답 미종료 — 자동 종료)"
                        s["done"] = True
                        _slack_pipe_update(rid, s, force=True)
                    except Exception:
                        pass
                    log.warning(f"[slack-pipe] GC timeout {rid}")
                with _slack_pipe_lock:
                    _slack_pipe_sessions.pop(rid, None)
        except Exception as e:
            log.error(f"[slack-pipe] GC loop 예외: {e}")


def _webchat_worker(ticket_id: str, payload: dict):
    """백그라운드 스레드: mcp-agent-channel /api/chat 호출 후 결과 저장"""
    try:
        # 즉시 processing 상태로 전환 (폴링 클라이언트에게 진행 중 알림)
        with _webchat_lock:
            if ticket_id in _webchat_tickets:
                _webchat_tickets[ticket_id]["status"] = "processing"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://localhost:{CS_AGENT_CHAT_PORT}/api/chat",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": CS_API_KEY},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read())
        with _webchat_lock:
            if ticket_id in _webchat_tickets:
                _webchat_tickets[ticket_id]["status"] = "done"
                _webchat_tickets[ticket_id]["result"] = result
        # CS 세션 JSONL 기록
        _log_cs_session(
            session_id=ticket_id,
            query=payload.get("query", ""),
            answer=result.get("answer", result.get("text", ""))[:200] if result.get("success") else "",
            channel="webchat",
            user="unknown",
            question_source="web",
            status="responded" if result.get("success") else "error",
        )
        log.info(f"[webchat] 완료: {ticket_id}")
    except Exception as e:
        log.error(f"[webchat] worker 에러 ({ticket_id}): {e}")
        with _webchat_lock:
            if ticket_id in _webchat_tickets:
                _webchat_tickets[ticket_id]["status"] = "error"
                _webchat_tickets[ticket_id]["result"] = {"success": False, "error": str(e)}


def _cleanup_webchat_tickets():
    """10분 이상 된 웹챗 티켓 정리 (데몬 스레드)"""
    while True:
        time.sleep(60)
        now = time.time()
        with _webchat_lock:
            expired = [k for k, v in _webchat_tickets.items() if now - v["created_at"] > 600]
            for k in expired:
                del _webchat_tickets[k]
        if expired:
            log.info(f"[webchat] 만료 티켓 {len(expired)}건 정리")


# .env에서 MES 서비스 계정 로드 (환경변수 미설정 시)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend", ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line.startswith("MES_SERVICE_USERNAME=") and not MES_SERVICE_USERNAME:
                    MES_SERVICE_USERNAME = _line.split("=", 1)[1]
                elif _line.startswith("MES_SERVICE_PASSWORD=") and not MES_SERVICE_PASSWORD:
                    MES_SERVICE_PASSWORD = _line.split("=", 1)[1]
                elif _line.startswith("ANTHROPIC_API_KEY=") and not ANTHROPIC_API_KEY:
                    ANTHROPIC_API_KEY = _line.split("=", 1)[1]
    except Exception:
        pass

# 서비스 계정 토큰 캐시
_mes_token_cache: dict = {"token": None, "refresh": None, "expires_at": 0}
_mes_token_lock = threading.Lock()

# ── Slack App ──
slack_app = App(token=BOT_TOKEN)

# ── 봇 자신의 User ID (멘션 감지용) ──
try:
    _auth = slack_app.client.auth_test()
    BOT_USER_ID = _auth.get("user_id", "")
    log.info(f"봇 User ID: {BOT_USER_ID}")
except Exception as _e:
    BOT_USER_ID = ""
    log.warning(f"봇 User ID 조회 실패: {_e}")

# ── 채널 ID ↔ 이름 캐시 ──
channel_id_to_name: dict[str, str] = {}
channel_name_to_id: dict[str, str] = {}


def refresh_channel_cache():
    try:
        try:
            resp = slack_app.client.conversations_list(types="public_channel,private_channel", limit=200)
        except Exception:
            # groups:read 권한 없으면 public만 재시도
            resp = slack_app.client.conversations_list(types="public_channel", limit=200)
        for ch in resp["channels"]:
            channel_id_to_name[ch["id"]] = ch["name"]
            channel_name_to_id[ch["name"]] = ch["id"]
        log.info(f"채널 캐시 갱신: {len(channel_id_to_name)}개")
    except Exception as e:
        log.error(f"채널 캐시 갱신 실패: {e}")


# ── P2P 직접 전송 ──
def send_to_agent(target: str, content: str, from_id: str = "slack-bot") -> bool:
    """에이전트 포트로 직접 HTTP POST"""
    port = AGENT_PORTS.get(target)
    if not port:
        log.error(f"알 수 없는 에이전트: {target}")
        return False
    body = json.dumps({"from": from_id, "to": target, "content": content}).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}/message",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                log.info(f"직접 전송 완료 → {target}:{port}")
                return True
    except Exception as e:
        log.warning(f"직접 전송 실패 → {target}:{port} ({e})")
    return False


# ── 부적합 등록 모달 ──

NC_TYPE_OPTIONS = [
    ("설계결함", "design_defect"),
    ("발주오류", "order_error"),
    ("수입검사오류", "receiving_error"),
    ("가공불량", "machining_defect"),
    ("조립불량", "assembly_defect"),
    ("전장불량", "electrical_defect"),
    ("SW결함", "software_defect"),
    ("개선요청", "improvement_request"),
    ("분실파손", "loss_damage"),
    ("원가절감", "cost_reduction"),
]

NC_IMPORTANCE_OPTIONS = [
    ("낮음", "low"),
    ("보통", "medium"),
    ("높음", "high"),
    ("심각", "critical"),
]


NC_TYPE_ACTION_MANAGER = {
    "design_defect": "설계팀",
    "order_error": "구매팀",
    "receiving_error": "품질팀",
    "machining_defect": "가공팀",
    "assembly_defect": "조립팀",
    "electrical_defect": "전장팀",
    "software_defect": "SW팀",
    "improvement_request": "",
    "loss_damage": "",
    "cost_reduction": "",
}


def _build_nc_modal(project_code: str = "", channel_id: str = "", channel_name: str = "", username: str = "") -> dict:
    """부적합 등록 모달 View 구조 생성."""
    type_opts = [{"text": {"type": "plain_text", "text": label}, "value": val} for label, val in NC_TYPE_OPTIONS]
    imp_opts = [{"text": {"type": "plain_text", "text": label}, "value": val} for label, val in NC_IMPORTANCE_OPTIONS]

    blocks = [
        {
            "type": "input", "block_id": "nc_title",
            "label": {"type": "plain_text", "text": "제목"},
            "element": {"type": "plain_text_input", "action_id": "val", "placeholder": {"type": "plain_text", "text": "부적합 제목을 입력하세요"}},
        },
        {
            "type": "input", "block_id": "nc_type",
            "label": {"type": "plain_text", "text": "부적합 유형"},
            "element": {"type": "static_select", "action_id": "val", "options": type_opts,
                         "initial_option": type_opts[4]},  # 조립불량 기본
        },
        {
            "type": "input", "block_id": "nc_importance",
            "label": {"type": "plain_text", "text": "중요도"},
            "element": {"type": "static_select", "action_id": "val", "options": imp_opts,
                         "initial_option": imp_opts[1]},  # 보통 기본
        },
        {
            "type": "input", "block_id": "nc_project",
            "label": {"type": "plain_text", "text": "프로젝트 코드"},
            "element": {"type": "plain_text_input", "action_id": "val",
                         "initial_value": project_code,
                         "placeholder": {"type": "plain_text", "text": "예: KRWTAHPL2501"}},
            "optional": True,
        },
        {
            "type": "input", "block_id": "nc_part",
            "label": {"type": "plain_text", "text": "부품번호"},
            "element": {"type": "plain_text_input", "action_id": "val",
                         "placeholder": {"type": "plain_text", "text": "예: P-12345"}},
            "optional": True,
        },
        {
            "type": "input", "block_id": "nc_desc",
            "label": {"type": "plain_text", "text": "상세 설명"},
            "element": {"type": "plain_text_input", "action_id": "val", "multiline": True,
                         "placeholder": {"type": "plain_text", "text": "부적합 내용을 상세히 기술하세요"}},
        },
        # 담당자: 슬랙 사용자명 자동 표시 (읽기전용 context)
        {
            "type": "context", "block_id": "nc_reporter_info",
            "elements": [{"type": "mrkdwn", "text": f"👤 *보고자*: {username or '(자동 감지)'}"}],
        },
    ]

    # private_metadata에 채널 정보 저장 (submit 시 회신용)
    metadata = json.dumps({"channel_id": channel_id, "channel_name": channel_name, "username": username})

    return {
        "type": "modal",
        "callback_id": "nc_register_modal",
        "title": {"type": "plain_text", "text": "부적합 등록"},
        "submit": {"type": "plain_text", "text": "등록"},
        "close": {"type": "plain_text", "text": "취소"},
        "private_metadata": metadata,
        "blocks": blocks,
    }


@slack_app.action("open_nc_modal")
def handle_open_nc_modal(ack, body, client):
    """'부적합 등록' 버튼 클릭 → 모달 오픈"""
    ack()
    trigger_id = body.get("trigger_id")
    if not trigger_id:
        return

    # 버튼 value에서 프로젝트 코드 + 채널 정보 추출
    action_value = body.get("actions", [{}])[0].get("value", "")
    try:
        val = json.loads(action_value)
    except Exception:
        val = {}

    project_code = val.get("project_code", "")
    channel_id = val.get("channel_id", body.get("channel", {}).get("id", ""))
    channel_name = val.get("channel_name", "")

    # 사용자 이름 조회
    btn_user_id = body.get("user", {}).get("id", "")
    btn_username = ""
    if btn_user_id:
        try:
            u = client.users_info(user=btn_user_id)
            btn_username = u["user"]["real_name"] or u["user"]["name"]
        except Exception:
            btn_username = body.get("user", {}).get("name", "")

    view = _build_nc_modal(project_code, channel_id, channel_name, btn_username)
    try:
        client.views_open(trigger_id=trigger_id, view=view)
    except Exception as e:
        log.error(f"[NC모달] views.open 실패: {e}")


@slack_app.view("nc_register_modal")
def handle_nc_modal_submit(ack, body, client, view):
    """모달 submit → MES 부적합 등록"""
    ack()

    values = view.get("state", {}).get("values", {})
    title = values.get("nc_title", {}).get("val", {}).get("value", "")
    nc_type = values.get("nc_type", {}).get("val", {}).get("selected_option", {}).get("value", "assembly_defect")
    importance = values.get("nc_importance", {}).get("val", {}).get("selected_option", {}).get("value", "medium")
    project_code = values.get("nc_project", {}).get("val", {}).get("value", "") or ""
    part_no = values.get("nc_part", {}).get("val", {}).get("value", "") or ""
    description = values.get("nc_desc", {}).get("val", {}).get("value", "")
    # 사용자 이름 + 이메일 (보고자 = 모달 여는 사람)
    user_id = body.get("user", {}).get("id", "")
    username = body.get("user", {}).get("name", user_id)
    user_email = ""
    try:
        user_info = client.users_info(user=user_id)
        username = user_info["user"]["real_name"] or user_info["user"]["name"]
        user_email = user_info["user"].get("profile", {}).get("email", "")
    except Exception:
        pass

    # 채널 정보 (private_metadata)
    try:
        meta = json.loads(view.get("private_metadata", "{}"))
    except Exception:
        meta = {}
    channel_id = meta.get("channel_id", "")
    channel_name = meta.get("channel_name", "")
    # metadata에 저장된 username이 있으면 사용 (모달 열 때 조회한 이름)
    if meta.get("username"):
        username = meta["username"]

    # 조치담당자: 부적합 유형에 따라 자동 결정
    action_manager_name = NC_TYPE_ACTION_MANAGER.get(nc_type, "")

    # 영문 value → 한글 라벨 매핑 (완료 메시지용)
    nc_type_label = dict((v, k) for k, v in NC_TYPE_OPTIONS).get(nc_type, nc_type)
    importance_label = dict((v, k) for k, v in NC_IMPORTANCE_OPTIONS).get(importance, importance)

    nc_data = {
        "title": title,
        "nonconformance_type": nc_type,
        "importance": importance,
        "description": description,
        "part_no": part_no or None,
        "unit_no": None,
        "reporter_name": username,
        "reporter_email": user_email or None,
        "manager_name": username,  # 담당자 = 보고자 (자동)
        "action_manager_name": action_manager_name or None,
        "project_code": project_code or None,
    }

    def _do_register():
        result = _register_nc_api(nc_data, username, channel_name or "modal")
        if result and channel_id:
            nc_id = result.get("id", "?")
            # 챗로그에 부적합 등록 기록
            _log_chat(channel_id, channel_name or "modal", user_id, username,
                      f"[부적합 등록] NC-{nc_id} | {title} | {nc_type_label} | {importance_label}"
                      f"{f' | 프로젝트:{project_code}' if project_code else ''}"
                      f"{f' | 부품:{part_no}' if part_no else ''}"
                      f" | {description[:200]}")
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    text=(
                        f"✅ 부적합 등록 완료 (NC-{nc_id})\n"
                        f"제목: {title}\n"
                        f"유형: {nc_type_label} | 중요도: {importance_label}\n"
                        f"보고자: {username}"
                        f"{f' | 프로젝트: {project_code}' if project_code else ''}"
                        f"{f' | 부품번호: {part_no}' if part_no else ''}\n"
                        f"내용: {description[:200]}{'…' if len(description) > 200 else ''}\n\n"
                        f"📎 첨부할 사진이나 동영상이 있으신가요?\n"
                        f"3분 이내에 이 채널에 파일을 올려주세요. "
                        f"\"없음\" 또는 \"완료\" 입력 시 종료됩니다."
                    ),
                )
            except Exception as e:
                log.warning(f"[NC모달] 완료 메시지 발송 실패: {e}")
            # 파일 첨부 세션 등록
            with _nc_file_sessions_lock:
                _nc_file_sessions[user_id] = {
                    "nc_id": nc_id,
                    "channel_id": channel_id,
                    "start_time": time.time(),
                    "uploaded": 0,
                }
            log.info(f"[NC모달] 파일 첨부 세션 시작: user={user_id}, nc_id={nc_id}")
        elif channel_id:
            _log_chat(channel_id, channel_name or "modal", user_id, username,
                      f"[부적합 등록 실패] {title} | {nc_type_label} | {importance_label}")
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    text=f"❌ 부적합 등록 실패: {title}\nMES API 오류 — 관리자에게 문의하세요.",
                )
            except Exception:
                pass

    threading.Thread(target=_do_register, daemon=True).start()


# ── NC 확인/취소 액션 핸들러 ──

@slack_app.action("confirm_nc_register")
def handle_confirm_nc(ack, body, client):
    ack()
    msg_ts = body.get("message", {}).get("ts")
    if not msg_ts:
        return
    with _pending_nc_lock:
        pending = _pending_nc.pop(msg_ts, None)
    if not pending:
        try:
            client.chat_update(
                channel=body["channel"]["id"],
                ts=msg_ts,
                text="이미 처리된 요청입니다.",
                blocks=[],
            )
        except Exception:
            pass
        return

    nc_data = pending["nc_data"]
    username = pending["username"]
    channel_name = pending["channel_name"]
    channel_id = pending["channel_id"]
    file_infos = pending.get("file_infos", [])

    nc = _register_nc_api(nc_data, username, channel_name)
    if nc:
        nc_id = nc.get("id", "?")
        nc_title = nc.get("title", nc_data.get("title", ""))[:40]
        # 파일 업로드
        uploaded = 0
        if file_infos:
            token = get_mes_token()
            if token:
                for fi in file_infos:
                    if upload_nc_file(nc_id, fi["url"], fi["name"], token):
                        uploaded += 1
        file_note = f"\n📎 첨부파일 {uploaded}/{len(file_infos)}개 업로드 완료" if file_infos else ""
        try:
            client.chat_update(
                channel=channel_id,
                ts=msg_ts,
                text=f"✅ MES 부적합 등록 완료 (ID: {nc_id})\n제목: {nc_title}{file_note}\n🔗 http://mes-wta.com/quality/nonconformance/{nc_id}",
                blocks=[],
            )
        except Exception as e:
            log.warning(f"NC 등록 완료 메시지 업데이트 실패: {e}")
    else:
        try:
            client.chat_update(
                channel=channel_id,
                ts=msg_ts,
                text="❌ MES 부적합 등록 실패. 로그를 확인해주세요.",
                blocks=[],
            )
        except Exception as e:
            log.warning(f"NC 등록 실패 메시지 업데이트 실패: {e}")


@slack_app.action("cancel_nc_register")
def handle_cancel_nc(ack, body, client):
    ack()
    msg_ts = body.get("message", {}).get("ts")
    if not msg_ts:
        return
    with _pending_nc_lock:
        _pending_nc.pop(msg_ts, None)
    try:
        client.chat_update(
            channel=body["channel"]["id"],
            ts=msg_ts,
            text="🚫 부적합 등록이 취소되었습니다.",
            blocks=[],
        )
    except Exception as e:
        log.warning(f"NC 취소 메시지 업데이트 실패: {e}")


# ── 답변 품질 피드백 핸들러 ──
def _handle_feedback_action(ack, body, client, rating: str):
    ack()
    msg_ts = body.get("message", {}).get("ts", "")
    ch_id = body.get("channel", {}).get("id", "")
    user_id = body.get("user", {}).get("id", "")
    key = f"{ch_id}:{msg_ts}"
    with _pending_feedback_lock:
        info = _pending_feedback.pop(key, {})
    _write_feedback(rating, info, ch_id, user_id)
    # 버튼 제거, 메시지 텍스트 유지
    try:
        label = "👍 감사합니다!" if rating == "good" else "👎 피드백 감사합니다."
        original_blocks = body.get("message", {}).get("blocks", [])
        section = original_blocks[0] if original_blocks else {"type": "section", "text": {"type": "mrkdwn", "text": ""}}
        client.chat_update(
            channel=ch_id,
            ts=msg_ts,
            text=body.get("message", {}).get("text", ""),
            blocks=[section, {"type": "context", "elements": [{"type": "mrkdwn", "text": label}]}],
        )
    except Exception as e:
        log.warning(f"피드백 버튼 제거 실패: {e}")


@slack_app.action("feedback_good")
def handle_feedback_good(ack, body, client):
    _handle_feedback_action(ack, body, client, "good")


@slack_app.action("feedback_bad")
def handle_feedback_bad(ack, body, client):
    _handle_feedback_action(ack, body, client, "bad")


# ── file_shared 이벤트 핸들러 (files.info API) ──
_processed_file_ids: set[str] = set()  # 중복 방지 (message + file_shared 동시 수신)
_processed_file_ids_lock = threading.Lock()

@slack_app.event("file_shared")
def handle_file_shared(event):
    """file_shared 이벤트: files.info로 메타데이터 획득 후 서버에 다운로드.
    message 이벤트(file_share subtype)와 중복 수신 시 한 번만 처리."""
    file_id = event.get("file_id", "")
    if not file_id:
        return

    with _processed_file_ids_lock:
        if file_id in _processed_file_ids:
            return  # message 핸들러에서 이미 처리됨
        _processed_file_ids.add(file_id)
        # 메모리 관리: 1000개 초과 시 절반 제거
        if len(_processed_file_ids) > 1000:
            to_remove = list(_processed_file_ids)[:500]
            for fid in to_remove:
                _processed_file_ids.discard(fid)

    def _process():
        try:
            resp = slack_app.client.files_info(file=file_id)
            fi = resp.get("file", {})
            if not fi:
                return

            channel_ids = fi.get("channels", []) + fi.get("groups", []) + fi.get("ims", [])
            channel_name = "direct"
            if channel_ids:
                ch_id = channel_ids[0]
                channel_name = channel_id_to_name.get(ch_id, ch_id)

            user_id = fi.get("user", "unknown")
            try:
                user_info = slack_app.client.users_info(user=user_id)
                username = user_info["user"]["real_name"] or user_info["user"]["name"]
            except Exception:
                username = user_id

            saved = _download_slack_files([fi], channel_name, username)
            if saved:
                log.info(f"[file_shared] {fi.get('name')} ({fi.get('size', 0)}B) "
                         f"→ #{channel_name} by {username}")
        except Exception as e:
            log.error(f"[file_shared] 처리 실패 (file_id={file_id}): {e}")

    threading.Thread(target=_process, daemon=True).start()


# ── 슬랙 → 에이전트 (Socket Mode) ──
@slack_app.event("message")
def handle_slack_message(event, say):
    if event.get("bot_id"):
        return
    # 파일 공유는 처리, 나머지 subtype은 무시
    subtype = event.get("subtype")
    if subtype and subtype != "file_share":
        return

    user_id = event.get("user", "unknown")
    text = event.get("text", "")
    channel = event.get("channel", "")
    files = event.get("files")

    # ── NC 파일 첨부 세션 처리 ──
    with _nc_file_sessions_lock:
        # 만료 세션 정리
        now = time.time()
        expired_fs = [k for k, s in _nc_file_sessions.items() if now - s["start_time"] > NC_FILE_SESSION_TIMEOUT]
        for k in expired_fs:
            sess = _nc_file_sessions.pop(k)
            log.info(f"[NC파일] 세션 타임아웃 만료: user={k}, nc_id={sess['nc_id']}, 업로드 {sess['uploaded']}개")
            try:
                slack_app.client.chat_postMessage(
                    channel=sess["channel_id"],
                    text=f"⏱️ 파일 첨부 시간이 종료되었습니다. (NC-{sess['nc_id']}, 첨부 {sess['uploaded']}개)",
                )
            except Exception:
                pass
        file_session = _nc_file_sessions.get(user_id)

    if file_session and file_session["channel_id"] == channel:
        # "없음" 또는 "완료" 입력 시 세션 종료
        if text.strip() in ("없음", "완료"):
            with _nc_file_sessions_lock:
                sess = _nc_file_sessions.pop(user_id, file_session)
            log.info(f"[NC파일] 세션 수동 종료: user={user_id}, nc_id={sess['nc_id']}, 업로드 {sess['uploaded']}개")
            try:
                slack_app.client.chat_postMessage(
                    channel=channel,
                    text=f"✅ 파일 첨부 완료 (NC-{sess['nc_id']}, 총 {sess['uploaded']}개 첨부)",
                )
            except Exception:
                pass
            return

        # 파일 첨부 감지
        if files:
            nc_id = file_session["nc_id"]

            def _upload_nc_files():
                token = get_mes_token()
                if not token:
                    log.error("[NC파일] MES 토큰 획득 실패")
                    return
                uploaded = 0
                for fi in files:
                    url = fi.get("url_private") or fi.get("url_private_download", "")
                    name = fi.get("name", "file")
                    if url and upload_nc_file(nc_id, url, name, token):
                        uploaded += 1
                if uploaded > 0:
                    with _nc_file_sessions_lock:
                        if user_id in _nc_file_sessions:
                            _nc_file_sessions[user_id]["uploaded"] += uploaded
                    file_names = [fi.get("name", "file") for fi in files]
                    _log_chat(channel, channel_id_to_name.get(channel, channel), user_id, "system",
                              f"[NC 파일첨부] NC-{nc_id} | {uploaded}개 | {', '.join(file_names)}")
                    try:
                        slack_app.client.chat_postMessage(
                            channel=channel,
                            text=f"📎 {uploaded}개 파일이 NC-{nc_id}에 첨부되었습니다. 추가 파일이 있으면 계속 올려주세요.",
                        )
                    except Exception:
                        pass
                    log.info(f"[NC파일] 업로드 완료: nc_id={nc_id}, {uploaded}개")

            threading.Thread(target=_upload_nc_files, daemon=True).start()
            return

    if not text.strip() and not files:
        return

    # 사용자 이름 조회
    try:
        user_info = slack_app.client.users_info(user=user_id)
        username = user_info["user"]["real_name"] or user_info["user"]["name"]
    except Exception:
        username = user_id

    # 채널 이름 조회
    channel_name = channel_id_to_name.get(channel)
    if not channel_name:
        try:
            ch_info = slack_app.client.conversations_info(channel=channel)
            channel_name = ch_info["channel"]["name"]
            channel_id_to_name[channel] = channel_name
            channel_name_to_id[channel_name] = channel
        except Exception:
            channel_name = channel

    # ── 챗로그 기록 (모든 채널, 모든 메시지) ──
    _log_chat(channel, channel_name, user_id, username, text, files)

    # ── 파일 다운로드 (범용 — uploads/slack/ 경로에 저장) ──
    saved_files: list[dict] = []
    if files:
        # file_shared 이벤트와 중복 방지
        with _processed_file_ids_lock:
            for fi in files:
                fid = fi.get("id", "")
                if fid:
                    _processed_file_ids.add(fid)
        saved_files = _download_slack_files(files, channel_name, username)

    # 멘션 여부 조기 판정 (content 구성 및 필터에서 참조)
    bot_mentioned = BOT_USER_ID and f"<@{BOT_USER_ID}>" in text

    # 파일 정보 문자열 (에이전트 전달용)
    file_info_str = ""
    if saved_files:
        file_lines = [f"  - {sf['name']} ({sf['filetype']}, {sf['size']}B) → {sf['local_path']}" for sf in saved_files]
        file_info_str = "\n[첨부파일]\n" + "\n".join(file_lines)

    # 프로젝트 채널 확인 (CHANNEL_ROUTING보다 우선)
    matched_project = _is_project_channel(channel)
    if matched_project:
        target_agent = "schedule-agent"
        proj_code = matched_project.get("project_code", "?")
        content = f"[슬랙 #{channel_name}] [프로젝트:{proj_code}] {username}: {text}{file_info_str}"
        log.info(f"[수신] #{channel_name} {username}: {text[:80]} → {target_agent} (프로젝트:{proj_code})")
    else:
        prefix_agent = next(
            (agent for prefix, agent in CHANNEL_PREFIX_ROUTING.items() if channel_name.startswith(prefix)),
            None
        )
        target_agent = prefix_agent or CHANNEL_ROUTING.get(channel_name, DEFAULT_AGENT)
        # 채널별 context_hint가 있고 멘션이 없으면 힌트 추가
        ch_cfg = CHANNEL_CONFIG.get(channel_name, {})
        ctx_hint = ch_cfg.get("context_hint", "")
        if ctx_hint and not bot_mentioned:
            content = f"[슬랙 #{channel_name}] {username}: {text}{file_info_str}\n({ctx_hint})"
        else:
            content = f"[슬랙 #{channel_name}] {username}: {text}{file_info_str}"
        log.info(f"[수신] #{channel_name} {username}: {text[:80]} → {target_agent}")
    log_to_dashboard("slack-bot", target_agent, content, "chat")

    # 파일 첨부 감지 → MES 프로젝트 기술자료 자동 저장
    if files:
        threading.Thread(
            target=_auto_upload_files_to_mes,
            args=(channel, channel_name, files, username),
            daemon=True,
        ).start()

    # !부적합 명령어 → 모달 등록 버튼 전송 (모든 채널에서 사용 가능)
    if text.strip() == "!부적합":
        proj_code = matched_project.get("project_code", "") if matched_project else ""
        btn_value = json.dumps({
            "project_code": proj_code,
            "channel_id": channel,
            "channel_name": channel_name,
        })
        try:
            slack_app.client.chat_postMessage(
                channel=channel,
                text="부적합 등록 폼을 열려면 아래 버튼을 클릭하세요.",
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "📋 *부적합 등록*\n아래 버튼을 클릭하여 등록 폼을 작성하세요."},
                    },
                    {
                        "type": "actions",
                        "elements": [{
                            "type": "button",
                            "text": {"type": "plain_text", "text": "⚠️ 부적합 등록"},
                            "style": "danger",
                            "action_id": "open_nc_modal",
                            "value": btn_value,
                        }],
                    },
                ],
            )
        except Exception as e:
            log.error(f"[!부적합] 버튼 전송 실패: {e}")
        return  # !부적합 명령은 에이전트 전달 안 함

    # 부적합 채널: !등록 명령어 또는 활성 세션 메시지만 처리
    if channel_name == "부적합":
        ch_id = channel_name_to_id.get(channel_name, channel)
        now = time.time()

        # 만료 세션 정리
        with _nc_sessions_lock:
            expired = [k for k, s in _nc_sessions.items() if now - s["start_time"] > NC_SESSION_TIMEOUT]
            for k in expired:
                log.info(f"[부적합] 세션 타임아웃 만료: {k}")
            for k in expired:
                del _nc_sessions[k]

        # 활성 세션 중인 사용자 메시지 → nc-manager로 계속 전달
        with _nc_sessions_lock:
            session = _nc_sessions.get(user_id)

        if session:
            nc_content = (
                f"[슬랙 #부적합 세션 추가 메시지] 요청자: {username}\n"
                f"{text}"
            )
            send_to_agent("nc-manager", nc_content, from_id="slack-bot")
            log.info(f"[부적합] 세션 메시지 → nc-manager: {username}: {text[:60]}")
            return

        # 세션 없는 일반 메시지는 무시
        if text.strip() != "!등록":
            log.info(f"[부적합] 일반 메시지 무시: {text[:60]}")
            return

        # !등록 명령: 세션 시작 + 최근 대화 수집 → nc-manager 전달
        def _request_nc_confirm():
            if not ch_id:
                log.warning(f"채널 ID 없음: #{channel_name}")
                return
            try:
                # 세션 등록
                with _nc_sessions_lock:
                    _nc_sessions[user_id] = {
                        "username": username,
                        "channel_id": ch_id,
                        "channel_name": channel_name,
                        "start_time": time.time(),
                    }

                # 최근 대화 10개 수집 (동영상, 사진, 메시지 모두 포함)
                history = slack_app.client.conversations_history(channel=ch_id, limit=10)
                messages = history.get("messages", [])

                history_lines = []
                for msg in reversed(messages):
                    msg_user = msg.get("user", "")
                    if msg_user:
                        try:
                            u = slack_app.client.users_info(user=msg_user)
                            msg_username = u["user"]["real_name"] or u["user"]["name"]
                        except Exception:
                            msg_username = msg_user
                    else:
                        msg_username = msg.get("bot_id", "봇")
                    msg_text = msg.get("text", "")
                    files = msg.get("files", [])
                    file_note = ""
                    if files:
                        file_names = [f.get("name", "파일") for f in files]
                        file_note = f" [첨부: {', '.join(file_names)}]"
                    history_lines.append(f"{msg_username}: {msg_text}{file_note}")

                history_summary = "\n".join(history_lines)
                nc_content = (
                    f"[슬랙 #부적합 !등록 요청] 요청자: {username}\n"
                    f"최근 대화 {len(messages)}개:\n"
                    f"{history_summary}\n\n"
                    f"위 내용을 분석하여 신규 부적합 건을 식별하고, "
                    f"슬랙 #부적합 채널에 '이 건에 대해 등록하시겠습니까?' 확인 질문을 보내주세요. "
                    f"추가 정보가 필요하면 슬랙으로 질문하세요. 사용자가 추가 입력하면 계속 전달됩니다. "
                    f"등록 완료 또는 취소 시 반드시 '[세션종료]' 키워드를 응답에 포함해 주세요. "
                    f"슬랙 회신: slack:#부적합 [내용]"
                )
                send_to_agent("nc-manager", nc_content, from_id="slack-bot")
                log.info(f"[부적합] !등록 → nc-manager 전달 ({len(messages)}개 메시지), 세션 시작")

                slack_app.client.chat_postMessage(
                    channel=ch_id,
                    text="⏳ nc-manager가 대화 내용을 분석 중입니다. 추가 정보가 필요하면 이 채널에 바로 입력하세요. (5분 내 미응답 시 자동 종료)",
                )
            except Exception as e:
                log.error(f"[부적합] !등록 처리 실패: {e}\n{traceback.format_exc()}")

        threading.Thread(target=_request_nc_confirm, daemon=True).start()
        return  # 부적합 채널은 에이전트 전송 없이 종료

    # 프로젝트 채널: ! 명령어만 에이전트 전달, 일반 메시지는 챗로그만 기록
    if matched_project and not text.strip().startswith("!"):
        log.info(f"[챗로그] #{channel_name} {username}: {text[:80]} (프로젝트 채널 — 로깅만)")
        return

    # @멘션 전용: CHANNEL_CONFIG의 mention_required 설정 기반
    # 부적합 채널은 위에서 이미 처리됨 (자체 흐름)
    ch_mention_cfg = CHANNEL_CONFIG.get(channel_name, {})
    mention_required = ch_mention_cfg.get("mention_required", True)
    if not bot_mentioned and mention_required:
        log.info(f"[챗로그] #{channel_name} {username}: {text[:80]} (멘션 없음 — 로깅만)")
        return

    # 슬랙 파이프라인 V2: feature flag on인 채널은 progressive edit 경로로 전환
    ch_id_for_ack = channel_name_to_id.get(channel_name, channel)
    if ch_id_for_ack in SLACK_PIPE_V2_CHANNELS and channel_name != "부적합":
        # content에는 이미 [슬랙 #ch username] 헤더 포함 → 원본 text 전달
        req_id = _slack_pipe_start(
            channel_id=ch_id_for_ack,
            target_agent=target_agent,
            user_query=text,
            username=username,
        )
        if req_id:
            return

    # 레거시 Ack-first: 즉시 처리중 메시지 발송 (ack_message=false인 채널 제외)
    ch_ack_cfg = CHANNEL_CONFIG.get(channel_name, {})
    if ch_ack_cfg.get("ack_message", True):
        if ch_id_for_ack:
            try:
                ack_resp = slack_app.client.chat_postMessage(
                    channel=ch_id_for_ack,
                    text="확인했습니다, 처리 중입니다 ⏳",
                )
                ack_ts = ack_resp.get("ts")
                if ack_ts:
                    with _pending_ack_lock:
                        _pending_ack[ch_id_for_ack] = {
                            "ts": ack_ts,
                            "agent": target_agent,
                            "request_time": time.time(),
                            "user": username,
                            "question_preview": text[:50],
                            "channel_name": channel_name,
                        }
            except Exception as e:
                log.warning(f"Ack 메시지 발송 실패: {e}")

    # 에이전트 포트로 직접 전송
    send_to_agent(target_agent, content, from_id="slack-bot")


# ── 에이전트 → 슬랙 (포트 5612 HTTP 서버) ──
class AgentMessageHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 기본 로그 억제

    def do_OPTIONS(self):
        """CORS preflight 처리"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            self._json({"agent_id": "slack-bot", "online": True})
        elif self.path == "/routing":
            # 현재 라우팅 설정 조회
            self._json({
                "channel_routing": CHANNEL_ROUTING,
                "prefix_routing": CHANNEL_PREFIX_ROUTING,
                "channel_config": CHANNEL_CONFIG,
                "default_agent": DEFAULT_AGENT,
            })
        elif self.path == "/reload-routing":
            # agents.json 리로드
            ok = _load_agents_routing()
            self._json({"ok": ok, "channels": len(CHANNEL_ROUTING), "prefixes": len(CHANNEL_PREFIX_ROUTING)})
        elif self.path.startswith("/api/webchat/result/"):
            self._handle_webchat_result()
        else:
            self.send_response(404)
            self.end_headers()

    def _check_api_key(self) -> bool:
        """API 키 검증. 실패 시 401 응답 전송."""
        if not CS_API_KEY:
            return True  # 키 미설정 시 인증 스킵
        api_key = self.headers.get("X-API-Key", "")
        if api_key != CS_API_KEY:
            self._cors_json({"error": "Invalid API key"}, status=401)
            return False
        return True

    def _handle_webchat_result(self):
        """GET /api/webchat/result/{ticket_id} — 폴링 결과 조회"""
        if not self._check_api_key():
            return
        ticket_id = self.path.rsplit("/", 1)[-1]
        with _webchat_lock:
            ticket = _webchat_tickets.get(ticket_id)
        if not ticket:
            self._cors_json({"error": "Ticket not found"}, status=404)
        elif ticket["status"] == "pending":
            self._cors_json({"status": "pending", "ticket_id": ticket_id})
        else:
            result = ticket["result"]
            status = ticket["status"]
            with _webchat_lock:
                _webchat_tickets.pop(ticket_id, None)
            self._cors_json({"status": status, "ticket_id": ticket_id, "result": result})

    def _handle_webchat_query(self):
        """POST /api/webchat/query — 웹챗 질의 접수 (비동기)"""
        if not self._check_api_key():
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._cors_json({"error": "Invalid JSON"}, status=400)
            return
        query = (data.get("query") or "").strip()
        if not query:
            self._cors_json({"error": "query is required"}, status=400)
            return
        ticket_id = f"wc-{int(time.time() * 1000)}-{os.urandom(4).hex()}"
        with _webchat_lock:
            _webchat_tickets[ticket_id] = {
                "status": "pending",
                "result": None,
                "created_at": time.time(),
            }
        payload = {"query": query, "language": data.get("language", "ko")}
        if data.get("equipment_id"):
            payload["equipment_id"] = data["equipment_id"]
        if data.get("error_code"):
            payload["error_code"] = data["error_code"]
        if data.get("message_history"):
            payload["message_history"] = data["message_history"]
        threading.Thread(target=_webchat_worker, args=(ticket_id, payload), daemon=True).start()
        log.info(f"[webchat] 티켓 생성: {ticket_id} - {query[:60]}")
        self._cors_json({"status": "accepted", "ticket_id": ticket_id})

    def _handle_chat(self):
        """POST /api/chat — cs-agent 직접 호출 (동기, 60초 타임아웃)"""
        if not self._check_api_key():
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._cors_json({"error": "Invalid JSON"}, status=400)
            return
        query = (data.get("query") or "").strip()
        if not query:
            self._cors_json({"error": "query is required"}, status=400)
            return

        payload = {"query": query, "language": data.get("language", "ko")}
        if data.get("equipment_id"):
            payload["equipment_id"] = data["equipment_id"]
        if data.get("error_code"):
            payload["error_code"] = data["error_code"]
        if data.get("message_history"):
            payload["message_history"] = data["message_history"]

        log.info(f"[api/chat] 요청: {query[:60]}")
        try:
            req = urllib.request.Request(
                f"http://localhost:{CS_AGENT_CHAT_PORT}/api/chat",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "X-API-Key": CS_API_KEY},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
            log.info(f"[api/chat] 응답 완료: {query[:40]}")
            self._cors_json(result)
        except urllib.error.URLError as e:
            log.error(f"[api/chat] cs-agent 연결 실패: {e}")
            self._cors_json({"error": "CS agent unavailable", "response": "현재 AI 상담 서비스에 연결할 수 없습니다."}, status=502)
        except Exception as e:
            log.error(f"[api/chat] 에러: {e}")
            self._cors_json({"error": str(e), "response": "처리 중 오류가 발생했습니다."}, status=500)

    def _handle_chat_stream_DIRECT_CLAUDE(self):
        """(비활성) Claude API 직접 호출 방식. 재전환 시 _handle_chat_stream으로 이름 교체."""
        if not self._check_api_key():
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._cors_json({"error": "Invalid JSON"}, status=400)
            return
        query = (data.get("query") or "").strip()
        if not query:
            self._cors_json({"error": "query is required"}, status=400)
            return

        import uuid
        request_id = uuid.uuid4().hex[:8]
        log.info(f"[chat/stream-direct] init: {request_id} - {query[:60]}")

        # SSE 응답 헤더
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.close_connection = True

        def emit(event: str, payload: dict) -> bool:
            try:
                line = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                self.wfile.write(line)
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError):
                return False

        # cs_rag 지연 import (slack-bot 기동 시점 의존성 회피)
        try:
            import sys as _sys
            _scripts_dir = os.path.dirname(os.path.abspath(__file__))
            if _scripts_dir not in _sys.path:
                _sys.path.insert(0, _scripts_dir)
            from cs_rag import search_and_build_context, stream_claude_answer
        except Exception as e:
            log.exception("[chat/stream-direct] cs_rag import 실패")
            emit("error", {"code": "IMPORT", "message": f"module load failed: {e}"})
            emit("done", {"data": ""})
            return

        # 1) 검색 진행 알림
        if not emit("progress", {"message": "자료 검색 중..."}):
            return

        # 2) 벡터 검색 + 컨텍스트 (실패 시 fallback)
        try:
            ctx_result = search_and_build_context(query, top_k=8)
        except Exception as e:
            log.exception("[chat/stream-direct] search error")
            ctx_result = {
                "context": "(검색 불가 — 일반 지식으로 답변)",
                "fallback": True,
                "fallback_reason": str(e)[:200],
            }
        if ctx_result.get("fallback"):
            log.warning(f"[chat/stream-direct] RAG fallback: {ctx_result.get('fallback_reason','')}")
            emit("progress", {"message": "답변 생성 중 (검색 제한)..."})
        else:
            emit("progress", {"message": "답변 생성 중..."})

        # 3) Claude 스트리밍
        try:
            meta = {}
            for ev, payload in stream_claude_answer(query, ctx_result["context"]):
                if ev == "chunk":
                    if not emit("chunk", {"data": payload, "content": payload}):
                        log.info(f"[chat/stream-direct] 클라이언트 연결 종료: {request_id}")
                        return
                elif ev == "done":
                    meta = payload
                elif ev == "error":
                    emit("error", {"code": "CLAUDE", "message": str(payload)})
                    break
            emit("meta", {
                "model": meta.get("model", ""),
                "sources": [],
                "input_tokens": meta.get("input_tokens", 0),
                "output_tokens": meta.get("output_tokens", 0),
            })
            emit("done", {"data": ""})
            log.info(
                f"[chat/stream-direct] 완료: {request_id} "
                f"({meta.get('input_tokens',0)}in+{meta.get('output_tokens',0)}out, "
                f"{meta.get('time_sec',0)}s, fallback={ctx_result.get('fallback',False)})"
            )
        except Exception as e:
            log.exception("[chat/stream-direct] stream error")
            emit("error", {"code": "STREAM", "message": str(e)[:200]})
            emit("done", {"data": ""})

    def _handle_chat_stream(self):
        """POST /api/chat/stream — hub 경유 SSE 프록시 (롤백: 2026-04-05)."""
        if not self._check_api_key():
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._cors_json({"error": "Invalid JSON"}, status=400)
            return
        query = (data.get("query") or "").strip()
        if not query:
            self._cors_json({"error": "query is required"}, status=400)
            return

        # request_id 생성 (slack-bot 측)
        import uuid
        request_id = uuid.uuid4().hex[:8]

        # hub에 init 요청
        payload = {
            "request_id": request_id,
            "query": query,
            "language": data.get("language", "ko"),
        }
        if data.get("equipment_id"):
            payload["equipment_id"] = data["equipment_id"]
        if data.get("error_code"):
            payload["error_code"] = data["error_code"]
        if data.get("message_history"):
            payload["message_history"] = data["message_history"]

        log.info(f"[api/chat/stream] init: {request_id} - {query[:60]}")
        try:
            init_req = urllib.request.Request(
                f"http://localhost:{CS_AGENT_CHAT_PORT}/api/chat/init",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "X-API-Key": CS_API_KEY},
                method="POST",
            )
            with urllib.request.urlopen(init_req, timeout=5) as resp:
                init_result = json.loads(resp.read())
            if not init_result.get("success"):
                self._cors_json({"error": init_result.get("error", "init failed")}, status=502)
                return
        except Exception as e:
            log.error(f"[api/chat/stream] init 실패: {e}")
            self._cors_json({"error": "CS agent unavailable"}, status=502)
            return

        # cs-agent에게 webchat-req 마커로 요청 발송 (신규 producer 파이프라인, 2026-04-05)
        # 이미지 첨부 지원 (2026-04-06): image_urls 배열을 마커 두번째 줄 `images:` 로 첨부
        try:
            webchat_req = f"webchat-req:{request_id}:{query}"
            # 스트리밍 세션 추적 시작 (질문 텍스트 저장)
            _webchat_stream_sessions[request_id] = {"query": query, "accum": ""}
            image_urls = data.get("image_urls") or []
            if isinstance(image_urls, list) and image_urls:
                # 문자열만 필터 + S3 버킷 URL만 허용 (SSRF 방지)
                safe_urls = [
                    u for u in image_urls
                    if isinstance(u, str)
                    and u.startswith("https://cs-chat-uploads.s3.ap-northeast-2.amazonaws.com/")
                ]
                if safe_urls:
                    webchat_req += "\nimages:" + ",".join(safe_urls)
                    log.info(f"[api/chat/stream] images 첨부: {request_id} ({len(safe_urls)}장)")
            ok = send_to_agent("cs-agent", webchat_req, from_id="slack-bot")
            if ok:
                log.info(f"[api/chat/stream] webchat-req 전송 → cs-agent: {request_id}")
            else:
                log.warning(f"[api/chat/stream] webchat-req 전송 실패: {request_id}")
        except Exception as _e:
            log.error(f"[api/chat/stream] webchat-req 예외 {request_id}: {_e}")

        # SSE 응답 헤더 전송
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        # Connection: close — Python stdlib은 chunked encoding 미지원, 연결 종료로 스트림 끝 신호
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.close_connection = True

        # hub SSE 스트림 프록시
        stream_url = f"http://localhost:{CS_AGENT_CHAT_PORT}/api/chat/stream?request_id={request_id}"
        try:
            stream_req = urllib.request.Request(
                stream_url,
                headers={"X-API-Key": CS_API_KEY, "Accept": "text/event-stream"},
                method="GET",
            )
            with urllib.request.urlopen(stream_req, timeout=125) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        log.info(f"[api/chat/stream] 클라이언트 연결 종료: {request_id}")
                        break
            log.info(f"[api/chat/stream] 완료: {request_id}")
        except Exception as e:
            log.error(f"[api/chat/stream] 프록시 에러 {request_id}: {e}")
            try:
                self.wfile.write(f"event: error\ndata: {json.dumps({'data': str(e)})}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass

    def do_POST(self):
        if self.path == "/api/chat":
            self._handle_chat()
            return
        if self.path == "/api/chat/stream" or self.path == "/api/chat-stream":
            self._handle_chat_stream()
            return
        if self.path == "/api/webchat/query":
            self._handle_webchat_query()
            return

        if self.path != "/message":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            msg = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        content: str = msg.get("content", "")
        sender: str = msg.get("from", "unknown")

        # 상태점검 자동응답
        if content.strip() in ("상태점검", "상태 보고", "상태점검 — 현재 상태 보고해주세요", "health", "status"):
            self._handle_health_check(sender)
            return

        # 슬랙 파이프라인 V2 마커 파싱 — 에이전트 → slack-bot progressive edit (2026-04-05)
        # 형식: slack-chunk:{id}:{delta}  |  slack-done:{id}  |  slack-error:{id}:{reason}
        if content.startswith(("slack-chunk:", "slack-done:", "slack-error:")):
            try:
                _slack_pipe_handle(content, sender)
            except Exception as _e:
                log.error(f"[slack-pipe] handle 예외: {_e}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        # 웹챗 producer 마커 파싱 — cs-agent → slack-bot → hub queue (2026-04-05 신규)
        # 형식: webchat-chunk:{req_id}:{text}  |  webchat-done:{req_id}  |  webchat-error:{req_id}:{msg}
        if content.startswith(("webchat-chunk:", "webchat-done:", "webchat-error:")):
            try:
                _webchat_push_to_hub(content, sender)
            except Exception as _e:
                log.error(f"[webchat-push] 실패: {_e}")
            # ack 반환
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        # "slack:#채널명 내용" 형식 파싱
        if content.startswith("slack:#"):
            parts = content.split(" ", 1)
            ch_name = parts[0].replace("slack:#", "")
            actual_content = parts[1] if len(parts) > 1 else ""

            # DM 채널(D로 시작) 또는 채널 ID(C로 시작)는 직접 사용
            if ch_name.startswith(("D", "C")) and len(ch_name) > 8 and ch_name.isalnum():
                ch_id = ch_name
            else:
                if ch_name not in channel_name_to_id:
                    refresh_channel_cache()
                ch_id = channel_name_to_id.get(ch_name)
            if ch_id and actual_content:
                try:
                    emoji = EMOJI_MAP.get(sender, "🤖")
                    # 미디어 마커 추출 (이미지, 참조링크, 발췌 PDF)
                    clean_content, media_images, media_refs, media_excerpts = _extract_media(actual_content)
                    msg_text = f"{emoji} {sender}: {clean_content}"

                    feedback_blocks = [
                        {"type": "section", "text": {"type": "mrkdwn", "text": msg_text}},
                    ]

                    # 이미지 블록 추가 (최대 3개)
                    for img_url in media_images[:3]:
                        feedback_blocks.append({
                            "type": "image",
                            "image_url": img_url.strip(),
                            "alt_text": "매뉴얼 이미지",
                        })

                    # 참조 링크 블록 추가
                    if media_refs:
                        ref_lines = []
                        for ref_url, ref_label in media_refs[:5]:
                            label = ref_label.strip() or "매뉴얼 참조"
                            ref_lines.append(f"📄 <{ref_url.strip()}|{label}>")
                        feedback_blocks.append({
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "\n".join(ref_lines)},
                        })

                    # 피드백 버튼 비활성화 (2026-04-02 부서장 요청)
                    # feedback_blocks.append({
                    #     "type": "actions",
                    #     "elements": [
                    #         {"type": "button", "text": {"type": "plain_text", "text": "👍 도움됨"},
                    #          "action_id": "feedback_good", "value": "good"},
                    #         {"type": "button", "text": {"type": "plain_text", "text": "👎 아쉬움"},
                    #          "action_id": "feedback_bad", "value": "bad"},
                    #     ],
                    # })
                    # Ack 대기 중이면 update, 아니면 새 메시지
                    with _pending_ack_lock:
                        ack_info = _pending_ack.pop(ch_id, None)
                    if ack_info:
                        slack_app.client.chat_update(
                            channel=ch_id,
                            ts=ack_info["ts"],
                            text=msg_text,
                            blocks=feedback_blocks,
                        )
                        msg_ts = ack_info["ts"]
                        _record_response_time(ack_info, sender, actual_content, ch_name)
                    else:
                        resp = slack_app.client.chat_postMessage(
                            channel=ch_id,
                            text=msg_text,
                            blocks=feedback_blocks,
                        )
                        msg_ts = resp.get("ts", "")
                    # 피드백 대기 등록
                    if msg_ts:
                        with _pending_feedback_lock:
                            _pending_feedback[f"{ch_id}:{msg_ts}"] = {
                                "agent": sender,
                                "channel": ch_name,
                                "question_preview": ack_info.get("question_preview", "") if ack_info else "",
                                "answer_preview": actual_content[:200],
                            }
                    log.info(f"[슬랙 발신] #{ch_name} ← {sender}: {clean_content[:60]}")
                    log_to_dashboard(sender, f"slack:#{ch_name}", clean_content, "chat")

                    # 부적합 세션 종료: nc-manager 응답에 [세션종료] 포함 시
                    if ch_name == "부적합" and "[세션종료]" in actual_content:
                        with _nc_sessions_lock:
                            closed = list(_nc_sessions.keys())
                            _nc_sessions.clear()
                        log.info(f"[부적합] 세션 종료 (nc-manager 신호): {closed}")

                    # 발췌 PDF 파일 업로드 (별도 파일로 전송)
                    for excerpt_url in media_excerpts[:2]:
                        excerpt_url = excerpt_url.strip()
                        fname = excerpt_url.split("/")[-1].split("?")[0] or "manual_excerpt.pdf"
                        threading.Thread(
                            target=_upload_file_to_slack,
                            args=(ch_id, excerpt_url, fname, f"📎 매뉴얼 발췌본 — {fname}"),
                            daemon=True,
                        ).start()
                except Exception as e:
                    log.error(f"슬랙 발신 실패: {e}\n{traceback.format_exc()}")
            else:
                log.warning(f"채널 ID 없음: #{ch_name}")
        else:
            log.info(f"[수신] {sender}: {content[:80]} (슬랙 발신 형식 아님 — 무시)")

        self._json({"ok": True})

    def _handle_health_check(self, sender: str):
        """상태점검 메시지에 자동 응답"""
        uptime_sec = int(time.time() - _BOOT_TIME)
        h, rem = divmod(uptime_sec, 3600)
        m, s = divmod(rem, 60)
        uptime_str = f"{h}h {m}m {s}s"

        # Socket Mode 연결 상태 확인
        socket_ok = slack_app.client is not None
        try:
            auth = slack_app.client.auth_test()
            slack_connected = auth.get("ok", False)
        except Exception:
            slack_connected = False

        status_msg = (
            f"slack-bot 상태 보고\n"
            f"- Slack 연결: {'정상' if slack_connected else '끊김'}\n"
            f"- Socket Mode: {'활성' if socket_ok else '비활성'}\n"
            f"- 가동시간: {uptime_str}\n"
            f"- HTTP 포트: {MY_PORT}"
        )

        # sender에게 응답
        try:
            hub_url = "http://localhost:5600"
            payload = json.dumps({"to": sender, "message": status_msg}).encode("utf-8")
            req = urllib.request.Request(
                f"{hub_url}/api/send",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception as e:
            log.warning(f"상태점검 응답 전송 실패: {e}")

        self._json({"ok": True})

    def _json(self, data: dict):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def start_p2p_server():
    """포트 5612 HTTP 서버 (에이전트 메시지 수신)"""
    server = ThreadingHTTPServer(("0.0.0.0", MY_PORT), AgentMessageHandler)
    log.info(f"P2P HTTP 서버 시작 (포트 {MY_PORT})")
    # slack-pipe GC 스레드 기동
    threading.Thread(target=_slack_pipe_gc_loop, daemon=True, name="slack-pipe-gc").start()
    if SLACK_PIPE_V2_CHANNELS:
        log.info(f"[slack-pipe] V2 활성 채널: {sorted(SLACK_PIPE_V2_CHANNELS)}")
    server.serve_forever()


# ── PID 파일 ──
PID_FILE = os.path.join(LOG_DIR, "slack-bot.pid")


def kill_existing():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            result = subprocess.run(
                ["taskkill", "/PID", str(old_pid), "/F"],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                log.info(f"이전 프로세스 종료: PID {old_pid}")
                time.sleep(1)
        except (ValueError, OSError, Exception):
            pass


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


# ── 메인 ──
if __name__ == "__main__":
    kill_existing()
    write_pid()

    log.info("WTA 슬랙 봇 프로세스 시작 — PID %d — %s",
             os.getpid(), datetime.now(KST_TZ).strftime("%Y-%m-%d %H:%M:%S KST"))
    log.info("WTA 슬랙 봇 시작 (P2P 직접 통신)...")

    # 채널 캐시 초기화
    refresh_channel_cache()

    # 포트 5612 P2P HTTP 서버 (백그라운드)
    p2p_thread = threading.Thread(target=start_p2p_server, daemon=True)
    p2p_thread.start()

    # 웹챗 티켓 정리 스레드
    threading.Thread(target=_cleanup_webchat_tickets, daemon=True).start()

    # Socket Mode (Slack 수신) — 자동 재시작 with 지수 백오프
    BACKOFF_STEPS = [5, 10, 30, 60]
    consecutive_failures = 0

    while True:
        try:
            log.info("Socket Mode 연결 시작... (시도 #%d)", consecutive_failures + 1)
            handler = SocketModeHandler(slack_app, APP_TOKEN)
            handler.start()
        except KeyboardInterrupt:
            log.info("슬랙 봇 종료 (KeyboardInterrupt)")
            break
        except Exception:
            consecutive_failures += 1
            tb = traceback.format_exc()
            log.error("Socket Mode 크래시 (연속 실패 %d회):\n%s", consecutive_failures, tb)

            # 크래시 로그 파일에도 기록
            crash_log = os.path.join(LOG_DIR, "slack-bot-crash.log")
            try:
                KST = timezone(timedelta(hours=9))
                ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
                with open(crash_log, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"[{ts}] 연속 실패 #{consecutive_failures}\n")
                    f.write(tb)
            except Exception:
                pass

            delay = BACKOFF_STEPS[min(consecutive_failures - 1, len(BACKOFF_STEPS) - 1)]
            log.info("재연결 대기 %d초...", delay)
            time.sleep(delay)
        else:
            # handler.start()가 정상 종료한 경우 — 재연결 시도
            log.info("Socket Mode handler 정상 종료 감지, 재연결 시도")
            consecutive_failures = 0
            time.sleep(5)
