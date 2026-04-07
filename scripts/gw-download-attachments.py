"""gw-download-attachments.py — 그룹웨어 CS 첨부파일 일괄 다운로드 + cs-wta.com 업로드.

CSV에서 첨부파일 있는 건을 추출, 그룹웨어에서 다운로드, cs-wta.com API로 업로드.
cs-wta.com API가 AWS S3 저장 + 메타데이터 관리를 자동 처리.

Usage:
  py scripts/gw-download-attachments.py --limit 5                    # 해외 5건 테스트
  py scripts/gw-download-attachments.py                               # 해외 전체
  py scripts/gw-download-attachments.py --domestic --limit 5         # 국내 5건 테스트
  py scripts/gw-download-attachments.py --domestic                    # 국내 전체
  py scripts/gw-download-attachments.py --dry-run                     # 미리보기
"""

import argparse
import csv
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import psycopg2
import requests
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "data", "cs_attachments")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 해외/국내 설정
PROFILES = {
    "overseas": {
        "csv": os.path.join(BASE_DIR, "data", "uploads", "C_S 이력관리 해외_20260329.csv"),
        "applet": 110,
        "label": "해외",
    },
    "domestic": {
        "csv": os.path.join(BASE_DIR, "data", "uploads", "C_S 이력관리_20260329.csv"),
        "applet": 22,
        "label": "국내",
    },
}

# 크레덴셜
ENV_GW = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.gw")
GW_USER = ""
GW_PASS = ""
GW_BASE_URL = ""
with open(ENV_GW, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("GW_USER="):
            GW_USER = line.split("=", 1)[1]
        elif line.startswith("GW_PASS="):
            GW_PASS = line.split("=", 1)[1]
        elif line.startswith("GW_BASE_URL="):
            GW_BASE_URL = line.split("=", 1)[1]

# cs-wta.com API
CS_WTA_API = "https://cs-wta.com/api/v1"

# DB (cs_history 매칭용)
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}


def get_mime(filename):
    """파일 확장자 → MIME 타입."""
    ext = os.path.splitext(filename)[1].lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
        ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".wmv": "video/x-ms-wmv", ".mkv": "video/x-matroska",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")


def upload_to_cswta(cs_history_id, file_data, filename, attach_type="symptom"):
    """cs-wta.com API로 첨부파일 업로드. S3 저장 + 메타데이터 자동 처리."""
    url = f"{CS_WTA_API}/cs/{cs_history_id}/attachments"
    mime = get_mime(filename)
    files = {"file": (filename, file_data, mime)}
    data = {"type": attach_type}
    resp = requests.post(url, files=files, data=data, timeout=120)
    if resp.status_code in (200, 201):
        result = resp.json()
        return result
    print(f"    cs-wta.com 업로드 실패: {resp.status_code} {resp.text[:200]}")
    return None


def safe_filename(name):
    """파일명에서 위험 문자 제거."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def load_csv_attachments(csv_path):
    """CSV에서 첨부파일 있는 건 추출."""
    results = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            attach = row.get("사진 및 파일첨부", "").strip()
            if attach:
                results.append({
                    "csv_id": row["*ID"],
                    "title": row.get("C/S 제목", ""),
                    "attachment_names": attach,
                })
    return results


def main():
    parser = argparse.ArgumentParser(description="그룹웨어 CS 첨부파일 다운로드")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    parser.add_argument("--dry-run", action="store_true", help="미리보기만")
    parser.add_argument("--domestic", action="store_true", help="국내 CS (applet 22)")
    args = parser.parse_args()

    profile = PROFILES["domestic"] if args.domestic else PROFILES["overseas"]
    applet_id = profile["applet"]
    print(f"[{profile['label']}] Applet {applet_id}")

    # 1. CSV 로드
    items = load_csv_attachments(profile["csv"])
    print(f"CSV 첨부파일 건수: {len(items)}건")
    if args.limit > 0:
        items = items[:args.limit]
        print(f"처리 대상: {len(items)}건 (--limit {args.limit})")

    if args.dry_run:
        for item in items:
            print(f"  ID {item['csv_id']}: {item['attachment_names'][:60]}")
        return

    # 2. DB 연결
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True

    # 3. Playwright 로그인 + 다운로드
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # 로그인
        print("\n[로그인]")
        page.goto(GW_BASE_URL, timeout=30000)
        time.sleep(2)

        user_input = page.query_selector('input[name="username"]')
        pw_input = page.query_selector('input[type="password"]')
        if user_input and pw_input:
            user_input.fill(GW_USER)
            pw_input.fill(GW_PASS)
            login_btn = page.query_selector('a:has-text("로그인")')
            if login_btn:
                login_btn.click()
            time.sleep(3)
            print(f"  로그인 완료: {page.url}")
        else:
            print("  로그인 폼 없음!")
            browser.close()
            return

        # 4. 각 게시물 처리
        success = 0
        fail = 0
        skip = 0
        total_files = 0
        total_bytes = 0

        for idx, item in enumerate(items):
            csv_id = item["csv_id"]
            print(f"\n[{idx + 1}/{len(items)}] ID {csv_id}: {item['title'][:40]}")

            # DB에서 cs_history 확인
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM csagent.cs_history WHERE csv_source_id = %s",
                (int(csv_id),),
            )
            db_row = cur.fetchone()
            if not db_row:
                print(f"  DB 매칭 없음 (csv_source_id={csv_id})")
                fail += 1
                continue

            cs_history_id = db_row[0]

            # cs-wta.com API로 이미 첨부파일 있는지 확인
            try:
                check_resp = requests.get(
                    f"{CS_WTA_API}/cs/{cs_history_id}/attachments", timeout=30
                )
                if check_resp.status_code == 200:
                    existing = check_resp.json()
                    existing_count = len(existing.get("symptom", [])) + len(existing.get("result", []))
                    if existing_count > 0:
                        print(f"  이미 첨부파일 있음 ({existing_count}개), 스킵")
                        skip += 1
                        continue
            except Exception as e:
                print(f"  첨부파일 확인 실패: {e} (계속 진행)")

            # 게시물 페이지 이동
            doc_url = f"{GW_BASE_URL}/app/works/applet/{applet_id}/doc/{csv_id}/navigate"
            try:
                page.goto(doc_url, timeout=30000)
                time.sleep(2)
            except Exception as e:
                print(f"  페이지 접근 실패: {e}")
                fail += 1
                continue

            # 첨부파일 링크 찾기
            download_links = page.query_selector_all('a[href*="download"]')
            if not download_links:
                print(f"  첨부파일 링크 없음")
                fail += 1
                continue

            # 중복 제거 (href 기준), 파일명 추출
            seen_hrefs = set()
            unique_links = []
            for link in download_links:
                href = link.get_attribute("href") or ""
                text = link.inner_text().strip()
                # "다운로드" 텍스트만 있는 링크는 파일명 링크와 중복이므로 제외
                if href and href not in seen_hrefs and text != "다운로드":
                    seen_hrefs.add(href)
                    # 텍스트가 없으면 href에서 파일명 추론
                    if not text:
                        text = href.split("/")[-1]
                    unique_links.append({"href": href, "text": text})

            print(f"  첨부파일 {len(unique_links)}개 발견")

            # 브라우저 쿠키 추출 → requests 세션으로 직접 다운로드
            cookies = context.cookies()
            session = requests.Session()
            for ck in cookies:
                session.cookies.set(ck["name"], ck["value"], domain=ck.get("domain", ""))

            # 다운로드 + cs-wta.com API 업로드
            uploaded_files = []
            for dl in unique_links:
                href = dl["href"]
                # 파일명: 링크의 title 속성 또는 텍스트에서 추출
                link_el = page.query_selector(f'a[href="{href}"]')
                title_attr = link_el.get_attribute("title") if link_el else ""
                filename = safe_filename(title_attr or dl["text"])
                if not filename or filename == href.split("/")[-1]:
                    # attachment_names에서 추출 시도
                    names = [n.strip() for n in item["attachment_names"].split(",")]
                    idx_in_list = unique_links.index(dl)
                    if idx_in_list < len(names):
                        filename = safe_filename(names[idx_in_list])

                print(f"    다운로드: {filename}")

                try:
                    download_url = f"{GW_BASE_URL}{href}"
                    resp = session.get(download_url, timeout=120, stream=True)
                    if resp.status_code != 200:
                        print(f"      HTTP {resp.status_code}")
                        continue

                    # Content-Disposition에서 파일명 추출
                    cd = resp.headers.get("Content-Disposition", "")
                    if "filename=" in cd:
                        import urllib.parse
                        if "filename*=" in cd:
                            # RFC 5987
                            part = cd.split("filename*=")[1].split(";")[0].strip()
                            if "''" in part:
                                filename = urllib.parse.unquote(part.split("''", 1)[1])
                        elif 'filename="' in cd:
                            filename = cd.split('filename="')[1].split('"')[0]
                        filename = safe_filename(filename)

                    file_data = resp.content
                    file_size = len(file_data)

                    # 로컬 저장
                    local_dir = os.path.join(DOWNLOAD_DIR, str(csv_id))
                    os.makedirs(local_dir, exist_ok=True)
                    local_path = os.path.join(local_dir, filename)
                    with open(local_path, "wb") as f:
                        f.write(file_data)
                    print(f"      저장: {filename} ({file_size / 1024:.0f} KB)")

                    # cs-wta.com API로 업로드 (S3 저장 자동 처리)
                    result = upload_to_cswta(cs_history_id, file_data, filename)
                    if result:
                        uploaded_files.append(result)
                        total_files += 1
                        total_bytes += file_size
                        print(f"      업로드: 성공 → {result.get('url', '')[:60]}")
                    else:
                        print(f"      업로드: 실패")

                except Exception as e:
                    print(f"      다운로드 실패: {e}")

            # 결과 집계
            if uploaded_files:
                print(f"  완료: {len(uploaded_files)}개 업로드 (cs_history_id={cs_history_id})")
                success += 1
            else:
                fail += 1

        browser.close()
    conn.close()

    # 용량 포맷
    if total_bytes >= 1073741824:
        size_str = f"{total_bytes / 1073741824:.1f} GB"
    else:
        size_str = f"{total_bytes / 1048576:.0f} MB"

    print(f"\n{'=' * 50}")
    print(f"[{profile['label']}] 완료")
    print(f"성공: {success}건, 실패: {fail}건, 스킵: {skip}건")
    print(f"총 파일: {total_files}개, 총 용량: {size_str}")
    print(f"로컬 저장: {DOWNLOAD_DIR}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
