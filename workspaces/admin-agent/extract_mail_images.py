"""메일 첨부 이미지 추출 — uid 121, 광학기술센터 폴더"""
import imaplib
import email
import os
import base64
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv("C:/MES/wta-agents/.env")

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", 143))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

SAVE_DIR = "C:/MES/wta-agents/workspaces/admin-agent"
FOLDER_RAW = "&rRHVWa4wwiDBPNEw-"
TARGET_UID = "121"

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

saved_files = []

try:
    mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASSWORD)

    status, count = mail.select(f'"{FOLDER_RAW}"', readonly=True)
    if status != "OK":
        print(f"[ERR] 폴더 선택 실패")
        exit(1)

    print(f"[INFO] UID {TARGET_UID} 메일 전체 가져오기...")
    status, msg_data = mail.uid("FETCH", TARGET_UID.encode(), "(RFC822)")
    if status != "OK":
        print("[ERR] 메일 가져오기 실패")
        exit(1)

    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)

    print(f"[INFO] 제목: {decode_str(msg.get('Subject', ''))}")
    print(f"[INFO] 전체 파트 수: {sum(1 for _ in msg.walk())}")
    print()

    idx = 0
    for part in msg.walk():
        content_type = part.get_content_type()
        content_disp = str(part.get("Content-Disposition", ""))
        content_id = part.get("Content-ID", "")

        # 파일명 결정
        filename = part.get_filename()
        if filename:
            filename = decode_str(filename)

        # 이미지 파트 처리 (첨부 or 인라인)
        is_image = content_type.startswith("image/")
        is_attachment = "attachment" in content_disp
        is_inline = "inline" in content_disp or (content_id and is_image)

        print(f"  Part: {content_type} | disp={content_disp[:50]} | cid={content_id} | filename={filename}")

        if is_image or (is_attachment and content_type.startswith("image/")):
            idx += 1
            # 파일명 생성
            if not filename:
                ext = content_type.split("/")[-1]
                # content-id에서 이름 추출
                if content_id:
                    cid_clean = content_id.strip("<>").split("@")[0].replace(" ", "_")
                    filename = f"img_{idx:02d}_{cid_clean}.{ext}"
                else:
                    filename = f"img_{idx:02d}.{ext}"

            # 번호 prefix 붙여서 중복 방지
            base, ext_part = os.path.splitext(filename)
            safe_name = f"mail_img_{idx:02d}_{base}{ext_part}"
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._-").strip()
            if not safe_name:
                safe_name = f"mail_img_{idx:02d}.{content_type.split('/')[-1]}"

            save_path = os.path.join(SAVE_DIR, safe_name)
            payload = part.get_payload(decode=True)
            if payload:
                with open(save_path, "wb") as f:
                    f.write(payload)
                size = len(payload)
                saved_files.append(save_path)
                print(f"  -> 저장: {safe_name} ({size:,} bytes)")
            else:
                print(f"  -> 페이로드 없음: {filename}")

    mail.logout()

except Exception as e:
    import traceback
    print(f"[ERR] {e}")
    traceback.print_exc()

print(f"\n[DONE] 총 {len(saved_files)}개 이미지 저장:")
for p in saved_files:
    print(f"  {p}")
