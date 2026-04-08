"""특정 메일 전체 내용 조회"""
import imaplib
import email
import os
import json
import base64
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv("C:/MES/wta-agents/.env")

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", 143))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")


def decode_modified_utf7(s):
    try:
        res = []
        i = 0
        while i < len(s):
            if s[i] == '&':
                j = s.index('-', i + 1)
                encoded = s[i+1:j]
                if encoded == '':
                    res.append('&')
                else:
                    encoded = encoded.replace(',', '/')
                    padding = len(encoded) % 4
                    if padding:
                        encoded += '=' * (4 - padding)
                    decoded = base64.b64decode(encoded).decode('utf-16-be')
                    res.append(decoded)
                i = j + 1
            else:
                res.append(s[i])
                i += 1
        return ''.join(res)
    except Exception:
        return s


def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def get_full_body(msg):
    """전체 본문 반환 (text/plain 우선, 없으면 text/html)"""
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            if ct == "text/plain":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    plain += part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    pass
            elif ct == "text/html" and not plain:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html += part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
            if msg.get_content_type() == "text/plain":
                plain = body
            else:
                html = body
        except Exception:
            pass
    return plain if plain else html


results = []

try:
    mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASSWORD)

    # 검색 폴더: 광학기술센터 raw + Inbox
    search_folders = ["&rRHVWa4wwiDBPNEw-", "Inbox"]

    for folder in search_folders:
        try:
            status, count = mail.select(f'"{folder}"', readonly=True)
            if status != "OK":
                status, count = mail.select(folder, readonly=True)
            if status != "OK":
                print(f"[WARN] 폴더 선택 실패: {folder}")
                continue

            total = int(count[0])
            print(f"[INFO] 폴더 '{decode_modified_utf7(folder)}' 총 {total}건 검색 중...")

            # 최근 200건 헤더 스캔
            status2, all_data = mail.uid("SEARCH", None, "ALL")
            if status2 != "OK" or not all_data[0]:
                continue

            all_ids = all_data[0].split()
            recent_ids = all_ids[-200:] if len(all_ids) > 200 else all_ids

            for uid in recent_ids:
                s, hdr_data = mail.uid("FETCH", uid, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if s != "OK":
                    continue
                hdr_raw = hdr_data[0][1]
                hdr_msg = email.message_from_bytes(hdr_raw)
                subj = decode_str(hdr_msg.get("Subject", ""))
                from_ = decode_str(hdr_msg.get("From", ""))
                date_ = hdr_msg.get("Date", "")

                # 제목에 "팔레트" 또는 "도트" 포함, 발신자 jwsuh
                if ("팔레트" in subj or "도트" in subj or "pallet" in subj.lower()) and "jwsuh" in from_:
                    print(f"  -> 매칭: {subj} / {date_}")
                    # 전체 본문 가져오기
                    s2, msg_data = mail.uid("FETCH", uid, "(RFC822)")
                    if s2 != "OK":
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    body = get_full_body(msg)
                    results.append({
                        "folder": decode_modified_utf7(folder),
                        "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                        "subject": decode_str(msg.get("Subject", "")),
                        "from": decode_str(msg.get("From", "")),
                        "to": decode_str(msg.get("To", "")),
                        "cc": decode_str(msg.get("Cc", "")),
                        "date": msg.get("Date", ""),
                        "body": body
                    })

        except Exception as e:
            import traceback
            print(f"[ERR] {folder}: {e}")
            traceback.print_exc()

    mail.logout()

except Exception as e:
    import traceback
    print(f"[ERR] IMAP: {e}")
    traceback.print_exc()

out_path = "C:/MES/wta-agents/workspaces/admin-agent/specific_mail_result.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n[DONE] {len(results)}건 찾음")
for r in results:
    print(f"\n{'='*60}")
    print(f"폴더: {r['folder']}")
    print(f"날짜: {r['date']}")
    print(f"발신: {r['from']}")
    print(f"수신: {r['to']}")
    print(f"참조: {r['cc']}")
    print(f"제목: {r['subject']}")
    print(f"\n[본문]\n{r['body']}")
