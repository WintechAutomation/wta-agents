"""광학기술센터 관련 최근 수신 메일 조회"""
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
    """IMAP Modified UTF-7 폴더명 디코딩"""
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


def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            pass
    return body


results = []

try:
    mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASSWORD)

    # 1) 폴더 목록 디코딩
    status, folders = mail.list()
    optic_folder_raw = None
    print("[INFO] 디코딩된 폴더 목록:")
    for f in folders:
        raw = f.decode("ascii", errors="replace")
        # 폴더명 추출 (마지막 "." 이후)
        parts = raw.split('"." ')
        folder_raw = parts[-1].strip().strip('"') if len(parts) > 1 else raw
        folder_decoded = decode_modified_utf7(folder_raw)
        print(f"  {folder_decoded}  (raw: {folder_raw})")
        if "광학" in folder_decoded or "optic" in folder_decoded.lower():
            optic_folder_raw = folder_raw
            print(f"  *** 광학기술센터 폴더 발견: {folder_decoded} ***")

    print(f"\n[INFO] 광학 폴더 raw: {optic_folder_raw}")

    # 2) 검색 폴더 순서: 광학 폴더 → Inbox
    search_folders = []
    if optic_folder_raw:
        search_folders.append(optic_folder_raw)
    search_folders.append("Inbox")
    search_folders.append("INBOX")

    seen_folders = set()
    for folder in search_folders:
        if folder in seen_folders:
            continue
        seen_folders.add(folder)

        try:
            status, count = mail.select(f'"{folder}"', readonly=True)
            if status != "OK":
                status, count = mail.select(folder, readonly=True)
            if status != "OK":
                print(f"[WARN] 폴더 선택 실패: {folder}")
                continue

            total = int(count[0])
            print(f"\n[INFO] 폴더 '{folder}' 총 {total}건")

            # 최근 100건 가져와서 수동 필터 (UID 기반)
            status2, all_data = mail.uid("SEARCH", None, "ALL")
            if status2 != "OK" or not all_data[0]:
                continue

            all_ids = all_data[0].split()
            recent_ids = all_ids[-100:] if len(all_ids) > 100 else all_ids
            matched_ids = []

            for uid in recent_ids:
                s, hdr_data = mail.uid("FETCH", uid, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if s != "OK":
                    continue
                hdr_raw = hdr_data[0][1]
                hdr_msg = email.message_from_bytes(hdr_raw)
                subj = decode_str(hdr_msg.get("Subject", ""))
                from_ = decode_str(hdr_msg.get("From", ""))
                if "광학" in subj or "광학" in from_:
                    matched_ids.append(uid)

            print(f"[INFO] 광학기술센터 관련: {len(matched_ids)}건")

            # 최근 5건
            for uid in list(reversed(matched_ids))[:5]:
                s, msg_data = mail.uid("FETCH", uid, "(RFC822)")
                if s != "OK":
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = decode_str(msg.get("Subject", ""))
                from_ = decode_str(msg.get("From", ""))
                date_ = msg.get("Date", "")
                body = get_body(msg)
                results.append({
                    "folder": decode_modified_utf7(folder),
                    "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "subject": subject,
                    "from": from_,
                    "date": date_,
                    "body_preview": body[:2000]
                })

        except Exception as e:
            import traceback
            print(f"[ERR] {folder} 처리 오류: {e}")
            traceback.print_exc()

    mail.logout()

except Exception as e:
    import traceback
    print(f"[ERR] IMAP 연결 오류: {e}")
    traceback.print_exc()
    results = [{"error": str(e)}]

# 결과 저장
out_path = "C:/MES/wta-agents/workspaces/admin-agent/optic_mail_result.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n[DONE] 총 {len(results)}건")
for r in results:
    if "error" in r:
        print(f"ERROR: {r['error']}")
        continue
    print(f"\n{'='*60}")
    print(f"폴더 : {r.get('folder','')}")
    print(f"날짜 : {r.get('date','')}")
    print(f"발신 : {r.get('from','')}")
    print(f"제목 : {r.get('subject','')}")
    print(f"내용 :\n{r.get('body_preview','')[:800]}")
