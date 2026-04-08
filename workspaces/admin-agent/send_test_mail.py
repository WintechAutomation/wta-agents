"""테스트 메일 발송 — SMTP gw.wta.kr:465 SSL"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from dotenv import load_dotenv

load_dotenv("C:/MES/wta-agents/.env")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_SSL  = os.getenv("SMTP_SSL", "true").lower() == "true"
FROM_ADDR = os.getenv("IMAP_USER")
PASSWORD  = os.getenv("IMAP_PASSWORD")
TO_ADDR   = "hjcho@wta.kr"

print(f"[INFO] SMTP: {SMTP_HOST}:{SMTP_PORT} SSL={SMTP_SSL}")
print(f"[INFO] From: {FROM_ADDR} → To: {TO_ADDR}")

msg = MIMEMultipart("alternative")
msg["Subject"] = Header("[WTA AI] 테스트 메일", "utf-8")
msg["From"]    = FROM_ADDR
msg["To"]      = TO_ADDR

body = (
    "WTA AI팀 MAX에서 발송한 테스트 메일입니다. "
    "정상 수신 확인 부탁드립니다.\n"
    "(발송시각: 2026-04-08 22:57 KST)"
)
msg.attach(MIMEText(body, "plain", "utf-8"))

try:
    if SMTP_SSL:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.starttls()

    server.login(FROM_ADDR, PASSWORD)
    server.sendmail(FROM_ADDR, [TO_ADDR], msg.as_bytes())
    server.quit()
    print("[DONE] 메일 발송 성공")
except Exception as e:
    import traceback
    print(f"[ERR] 발송 실패: {e}")
    traceback.print_exc()
