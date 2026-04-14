"""IMAP 부서장 메일함 모니터 — 5분마다 새 메일 감지 및 MAX 보고

부서장(hjcho@wta.kr) IMAP 메일함에서 UNSEEN 메일을 확인하고,
발신자, 제목, 수신시각을 포함하여 MAX에게 보고한다.

APScheduler 등록: 5분 간격 실행
"""

import imaplib
import email
import json
import sys
import os
import urllib.request
from email.header import decode_header
from datetime import datetime, timezone, timedelta
import io

# UTF-8 출력 인코딩 설정 (Windows에서 한글 처리)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

KST = timezone(timedelta(hours=9))
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
MCP_URL = "http://localhost:5600/send"  # agent-channel MCP
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
STATE_FILE = os.path.join(LOG_DIR, "imap-boss-state.json")


def load_env() -> dict:
    """Read .env file and return key-value dict."""
    env = {}
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    except Exception as e:
        print(f"[ERROR] .env 로드 실패: {e}")
    return env


def decode_mime_header(raw: str) -> str:
    """Decode MIME encoded header (RFC 2047)."""
    if not raw:
        return ""
    parts = decode_header(raw)
    result = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result


def send_to_max(message: str):
    """MAX에게 agent-channel MCP를 통해 메시지 전송."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "send_message",
            "arguments": {"to": "MAX", "message": message}
        },
        "id": 1
    }).encode("utf-8")

    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"[INFO] MAX 전송 완료")
    except Exception as e:
        print(f"[ERROR] MAX 전송 실패: {e}")


def load_state() -> dict:
    """이전 처리 상태 로드 (처리 메일 ID 목록)."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed_ids": [], "initialized": False}


def save_state(state: dict):
    """처리 상태 저장."""
    # processed_ids는 최근 500건만 유지 (장기 스토리지)
    if len(state.get("processed_ids", [])) > 500:
        state["processed_ids"] = state["processed_ids"][-500:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_email_date(date_str: str) -> str:
    """RFC 2822 날짜를 KST '2026-04-14 15:30' 형식으로 변환."""
    if not date_str:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        # UTC → KST 변환
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        kst_dt = dt.astimezone(KST)
        return kst_dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return date_str[:30]


def check_boss_mail():
    """부서장 IMAP 접속 -> INBOX UNSEEN 메일 확인 -> MAX에 보고."""
    env = load_env()
    host = env.get("IMAP_HOST", "gw.wta.kr")
    port = int(env.get("IMAP_PORT", "143"))
    user = env.get("IMAP_USER", "")
    pw = env.get("IMAP_PASSWORD", "")

    if not user or not pw:
        print("[ERROR] IMAP 인증 정보 없음")
        return

    state = load_state()
    processed = set(state.get("processed_ids", []))

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 부서장 메일 모니터 시작 - {host}:{port}")

    try:
        # IMAP4 연결 (비SSL)
        mail = imaplib.IMAP4(host, port)
        mail.login(user, pw)

        # INBOX 선택
        status, data = mail.select("INBOX", readonly=False)
        if status != "OK":
            print("[WARN] INBOX 선택 실패")
            return

        msg_count = int(data[0])
        print(f"[INFO] INBOX 총 {msg_count}건")

        # UNSEEN 메일 검색
        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            print(f"[INFO] 읽지 않은 새 메일 없음")
            mail.close()
            mail.logout()
            return

        unseen_ids = data[0].split()
        print(f"[INFO] UNSEEN 메일 {len(unseen_ids)}건 감지")

        new_mails = []

        for msg_id in unseen_ids:
            msg_id_str = msg_id.decode()

            if msg_id_str in processed:
                print(f"[DEBUG] 이미 처리한 메일: {msg_id_str}")
                continue

            # 메일 헤더 조회
            status, header_data = mail.fetch(
                msg_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])"
            )
            if status != "OK" or not header_data[0]:
                continue

            raw_header = header_data[0][1]
            header_msg = email.message_from_bytes(raw_header)

            from_addr = decode_mime_header(header_msg.get("From", ""))
            subject = decode_mime_header(header_msg.get("Subject", ""))
            date_str = header_msg.get("Date", "")
            msg_id_raw = header_msg.get("Message-ID", "")

            # KST 시각으로 변환
            received_time = parse_email_date(date_str)

            print(f"[MATCH] 새 메일: {from_addr[:30]} | {subject[:50]} | {received_time}")

            new_mails.append({
                "from": from_addr,
                "subject": subject,
                "date": received_time,
                "msg_id": msg_id_raw,
            })

            # RFC822 fetch로 상태 업데이트 (선택)
            processed.add(msg_id_str)

        # MAX에게 보고
        if new_mails:
            for mail_info in new_mails:
                parts = [
                    "[부서장 메일함] 새 메일 도착",
                    f"- 발신: {mail_info['from']}",
                    f"- 제목: {mail_info['subject']}",
                    f"- 수신시각: {mail_info['date']} KST",
                ]
                report = "\n".join(parts)
                print(report)
                send_to_max(report)

        # 상태 저장
        state["processed_ids"] = list(processed)
        state["last_check"] = now
        save_state(state)

        mail.close()
        mail.logout()
        print(f"[{now}] 부서장 메일 모니터 완료")

    except Exception as e:
        print(f"[ERROR] IMAP 처리 실패: {type(e).__name__}: {e}")


if __name__ == "__main__":
    check_boss_mail()
