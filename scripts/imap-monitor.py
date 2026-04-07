"""IMAP 메일 모니터 — 신규입사자 안내 메일 감지 및 MAX 보고

다우오피스 IMAP(gw.wta.kr:143)에서 UNSEEN 메일을 확인하고,
관리팀(민지원 mjwon@wta.kr) 발신 신규입사자 안내 메일을 파싱하여
MAX에게 보고한다.

APScheduler 등록: 5분 간격 실행
"""

import imaplib
import email
import re
import json
import sys
import os
import urllib.request
from email.header import decode_header
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
MCP_URL = "http://localhost:5600/send"  # agent-channel MCP
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
STATE_FILE = os.path.join(LOG_DIR, "imap-monitor-state.json")


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
            print(f"[INFO] MAX 전송 완료: {str(result)[:100]}")
    except Exception as e:
        print(f"[ERROR] MAX 전송 실패: {e}")


def load_state() -> dict:
    """이전 처리 상태 로드 (마지막 처리 UID 등)."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_uid": 0, "processed_ids": []}


def save_state(state: dict):
    """처리 상태 저장."""
    # processed_ids는 최근 200건만 유지
    if len(state.get("processed_ids", [])) > 200:
        state["processed_ids"] = state["processed_ids"][-200:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_new_employee_mail(from_addr: str, subject: str) -> bool:
    """신규입사자 안내 메일인지 판단."""
    from_lower = from_addr.lower()
    subject_lower = subject.lower()

    # 발신자 패턴: 관리팀 민지원
    sender_match = "mjwon@wta.kr" in from_lower

    # 제목 패턴
    keywords = ["신규입사", "입사자", "계정 생성", "계정생성", "신입사원", "입사 안내", "입사안내"]
    subject_match = any(kw in subject_lower for kw in keywords)

    return sender_match or subject_match


def extract_body(msg: email.message.Message) -> str:
    """메일 본문 추출 (text/plain 우선, text/html fallback)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
                break
            elif ctype == "text/html" and not body:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace")
                # HTML 태그 제거 (간단)
                body = re.sub(r"<[^>]+>", " ", html)
                body = re.sub(r"\s+", " ", body).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body


def parse_new_employee(subject: str, body: str) -> dict | None:
    """메일 본문에서 신규입사자 정보 파싱."""
    info = {
        "name": None,
        "department": None,
        "email": None,
        "start_date": None,
        "raw_subject": subject,
    }

    text = subject + " " + body

    # 이름 추출 (이름: xxx, 성명: xxx, 신규입사자: xxx)
    name_patterns = [
        r"(?:이름|성명|입사자)\s*[:\-]\s*([가-힣]{2,4})",
        r"([가-힣]{2,4})\s*(?:님|씨)?\s*(?:입사|합류)",
    ]
    for pat in name_patterns:
        m = re.search(pat, text)
        if m:
            info["name"] = m.group(1)
            break

    # 부서 추출
    dept_patterns = [
        r"(?:부서|소속|팀)\s*[:\-]\s*([가-힣a-zA-Z0-9]+(?:팀|부|실|센터)?)",
        r"([가-힣]+(?:팀|부|실))\s*(?:배치|소속|근무)",
    ]
    for pat in dept_patterns:
        m = re.search(pat, text)
        if m:
            info["department"] = m.group(1)
            break

    # 이메일 추출
    email_pat = r"[\w.+-]+@wta\.kr"
    emails = re.findall(email_pat, text)
    # mjwon(발신자) 제외
    for em in emails:
        if em.lower() != "mjwon@wta.kr":
            info["email"] = em
            break

    # 입사일 추출
    date_patterns = [
        r"(?:입사일|입사\s*일자|시작일)\s*[:\-]\s*(\d{4}[-./]\d{1,2}[-./]\d{1,2})",
        r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})\s*(?:입사|합류|시작)",
    ]
    for pat in date_patterns:
        m = re.search(pat, text)
        if m:
            info["start_date"] = m.group(1).replace("/", "-").replace(".", "-")
            break

    # 최소 이름이라도 있어야 유효
    if info["name"] or info["email"]:
        return info
    return None


def _scan_folder(mail, folder_name: str, folder_label: str, processed: set) -> list:
    """단일 폴더의 UNSEEN 메일 스캔 후 신규입사 메일 목록 반환."""
    new_employees = []

    try:
        # 특수문자(괄호, 쉼표) 포함 폴더명은 따옴표로 감싸기
        quoted = f'"{folder_name}"'
        status, data = mail.select(quoted, readonly=False)
        if status != "OK":
            print(f"[WARN] {folder_label} 폴더 선택 실패")
            return []
        msg_count = int(data[0])
    except Exception as e:
        print(f"[WARN] {folder_label} 폴더 접근 실패: {e}")
        return []

    # UNSEEN 메일 검색
    status, data = mail.search(None, "UNSEEN")
    if status != "OK" or not data[0]:
        print(f"[INFO] {folder_label}: 읽지 않은 메일 없음 (전체 {msg_count}건)")
        mail.close()
        return []

    unseen_ids = data[0].split()
    print(f"[INFO] {folder_label}: UNSEEN {len(unseen_ids)}건 (전체 {msg_count}건)")

    for msg_id in unseen_ids:
        # 폴더별로 고유한 키 생성 (폴더명:메일ID)
        msg_id_str = f"{folder_label}:{msg_id.decode()}"

        if msg_id_str in processed:
            continue

        # 헤더만 먼저 조회 (효율)
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

        # 신규입사 메일 판별
        if not is_new_employee_mail(from_addr, subject):
            continue

        print(f"[MATCH] [{folder_label}] 신규입사 메일 감지: {subject[:50]}")

        # 본문 전체 조회
        status, full_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK" or not full_data[0]:
            continue

        full_msg = email.message_from_bytes(full_data[0][1])
        body = extract_body(full_msg)

        # 파싱
        emp_info = parse_new_employee(subject, body)
        if emp_info:
            emp_info["mail_date"] = date_str[:30]
            emp_info["mail_from"] = from_addr[:50]
            emp_info["folder"] = folder_label
            new_employees.append(emp_info)

        # RFC822 fetch로 SEEN 처리됨
        processed.add(msg_id_str)

    mail.close()
    return new_employees


# 스캔 대상 폴더 목록 (IMAP Modified UTF-7 인코딩명, 표시명)
SCAN_FOLDERS = [
    ("INBOX", "INBOX"),
    ("&x3jArA-", "인사"),
    ("&swDUXMd0wKw-", "대표이사"),
    ("&xgHFxcd8vPg-", "영업일본"),
    ("&xgHFxckRrW0-", "영업중국"),
    ("&xgHFxcnAxtA-", "영업지원"),
    ("&xgHFxc0drQQ-", "영업총괄"),
    ("&0rnVyA-", "특허"),
    ("&0rnVyA-(&1gTC4A-, &ycDG0MCsxcU-)", "특허(현신,지원사업)"),
    ("&1IjJyK34uPk-", "품질그룹"),
    ("&rL25rA-", "경리"),
]


def check_mail():
    """IMAP 접속 -> 복수 폴더 UNSEEN 확인 -> 신규입사 메일 처리."""
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
    print(f"[{now}] IMAP 모니터 시작 - {host}:{port}")

    try:
        mail = imaplib.IMAP4(host, port)
        mail.login(user, pw)

        all_new_employees = []
        total_unseen = 0

        for folder_imap, folder_label in SCAN_FOLDERS:
            employees = _scan_folder(mail, folder_imap, folder_label, processed)
            all_new_employees.extend(employees)

        # MAX에게 보고
        if all_new_employees:
            for emp in all_new_employees:
                parts = [
                    "[IMAP 모니터] 신규입사자 메일 감지!",
                    f"- 폴더: {emp.get('folder', '')}",
                    f"- 이름: {emp.get('name', '미확인')}",
                    f"- 부서: {emp.get('department', '미확인')}",
                    f"- 이메일: {emp.get('email', '미확인')}",
                    f"- 입사일: {emp.get('start_date', '미확인')}",
                    f"- 메일제목: {emp.get('raw_subject', '')[:60]}",
                    f"- 발신: {emp.get('mail_from', '')}",
                    f"- 수신일: {emp.get('mail_date', '')}",
                ]
                report = "\n".join(parts)
                print(report)
                send_to_max(report)
        else:
            print(f"[INFO] 신규입사 메일 없음")

        # 상태 저장
        state["processed_ids"] = list(processed)
        state["last_check"] = now
        save_state(state)

        mail.logout()
        print(f"[{now}] IMAP 모니터 완료")

    except Exception as e:
        print(f"[ERROR] IMAP 처리 실패: {type(e).__name__}: {e}")


if __name__ == "__main__":
    check_mail()
