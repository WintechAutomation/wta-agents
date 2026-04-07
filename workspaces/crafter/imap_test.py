"""IMAP 접속 테스트 — .env에서 설정 읽기"""
import imaplib
import email
from email.header import decode_header
import os

# .env 로드
env = {}
with open("C:/MES/wta-agents/.env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

host = env.get("IMAP_HOST", "")
user = env.get("IMAP_USER", "")
pw = env.get("IMAP_PASSWORD", "")

print(f"Host: {host}")
print(f"User: {user}")
print(f"Password: {'*' * len(pw)}")

try:
    # SSL 접속
    print("\n[1] IMAP SSL 접속 시도...")
    mail = imaplib.IMAP4_SSL(host, 993, timeout=10)
    print(f"    접속 성공: {mail.welcome.decode()[:80]}")

    # 로그인
    print("[2] 로그인 시도...")
    mail.login(user, pw)
    print("    로그인 성공!")

    # 메일함 목록
    print("[3] 메일함 목록:")
    status, folders = mail.list()
    for f in folders[:10]:
        print(f"    {f.decode()}")

    # INBOX 선택
    print("\n[4] INBOX 선택...")
    status, data = mail.select("INBOX", readonly=True)
    msg_count = int(data[0])
    print(f"    INBOX 메일 수: {msg_count}")

    # 최근 2건 제목 읽기
    print("\n[5] 최근 메일 2건:")
    if msg_count > 0:
        start = max(1, msg_count - 1)
        status, data = mail.fetch(f"{start}:{msg_count}", "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
        for i in range(0, len(data), 2):
            if data[i] is None:
                continue
            raw = data[i][1]
            msg = email.message_from_bytes(raw)
            # 제목 디코딩
            subject_raw = msg.get("Subject", "")
            decoded_parts = decode_header(subject_raw)
            subject = ""
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    subject += part.decode(charset or "utf-8", errors="replace")
                else:
                    subject += part
            from_raw = msg.get("From", "")
            date_raw = msg.get("Date", "")
            print(f"    [{date_raw[:20]}] {from_raw[:30]} | {subject[:60]}")

    # UNSEEN 확인
    print("\n[6] 읽지 않은 메일 수:")
    status, data = mail.search(None, "UNSEEN")
    unseen_ids = data[0].split()
    print(f"    UNSEEN: {len(unseen_ids)}건")

    mail.close()
    mail.logout()
    print("\n접속 테스트 완료!")

except Exception as e:
    print(f"\n에러: {e}")
