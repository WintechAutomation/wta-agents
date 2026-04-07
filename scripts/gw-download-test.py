"""gw-download-test.py — 그룹웨어 CS 이력 첨부파일 다운로드 테스트.

게시물 1건(ID 26474)에서 첨부파일 다운로드 가능 여부 확인.

Usage:
  py scripts/gw-download-test.py
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads", "gw_test")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 크레덴셜 로드
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.gw")
GW_USER = ""
GW_PASS = ""
GW_BASE_URL = ""
with open(ENV_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("GW_USER="):
            GW_USER = line.split("=", 1)[1]
        elif line.startswith("GW_PASS="):
            GW_PASS = line.split("=", 1)[1]
        elif line.startswith("GW_BASE_URL="):
            GW_BASE_URL = line.split("=", 1)[1]

TEST_DOC_ID = "26474"
DOC_URL = f"{GW_BASE_URL}/app/works/applet/110/doc/{TEST_DOC_ID}/navigate"


def main():
    print(f"테스트 게시물: {DOC_URL}")
    print(f"다운로드 경로: {DOWNLOAD_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # 1. 로그인 페이지 접근
        print("\n[1] 그룹웨어 접속...")
        page.goto(GW_BASE_URL, timeout=30000)
        time.sleep(2)

        # 현재 URL 확인 (로그인 리다이렉트 여부)
        current_url = page.url
        print(f"    현재 URL: {current_url}")

        # 스크린샷
        page.screenshot(path=os.path.join(DOWNLOAD_DIR, "01_initial.png"))

        # 2. 로그인
        print("\n[2] 로그인 시도...")
        # 로그인 폼 찾기
        login_selectors = [
            'input[name="username"]',
            'input[name="userId"]',
            'input[name="id"]',
            'input[type="text"][name*="user"]',
            'input[type="text"][name*="id"]',
            '#userId',
            '#username',
            '#id',
        ]
        pw_selectors = [
            'input[name="password"]',
            'input[name="userPw"]',
            'input[name="passwd"]',
            'input[type="password"]',
            '#password',
            '#userPw',
        ]

        user_input = None
        for sel in login_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    user_input = el
                    print(f"    사용자 입력 필드: {sel}")
                    break
            except Exception:
                continue

        pw_input = None
        for sel in pw_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    pw_input = el
                    print(f"    비밀번호 입력 필드: {sel}")
                    break
            except Exception:
                continue

        if not user_input or not pw_input:
            # iframe 안에 있을 수 있음
            print("    메인 페이지에서 로그인 폼 없음. iframe 확인...")
            frames = page.frames
            print(f"    프레임 수: {len(frames)}")
            for frame in frames:
                print(f"    - {frame.url[:80]}")
                for sel in login_selectors:
                    try:
                        el = frame.query_selector(sel)
                        if el:
                            user_input = el
                            pw_input = frame.query_selector('input[type="password"]')
                            print(f"    iframe에서 로그인 폼 발견!")
                            page = frame  # frame으로 전환
                            break
                    except Exception:
                        continue
                if user_input:
                    break

        if not user_input:
            # 페이지 HTML 일부 출력하여 디버깅
            html = page.content()[:3000]
            print(f"    로그인 폼을 찾을 수 없음. 페이지 HTML (처음 3000자):")
            print(html)
            page.screenshot(path=os.path.join(DOWNLOAD_DIR, "02_no_login_form.png"))
            browser.close()
            return

        user_input.fill(GW_USER)
        pw_input.fill(GW_PASS)
        page.screenshot(path=os.path.join(DOWNLOAD_DIR, "02_login_filled.png"))

        # 로그인 버튼 클릭
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("로그인")',
            'a:has-text("로그인")',
            '.login-btn',
            '#loginBtn',
        ]
        for sel in submit_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    print(f"    로그인 버튼: {sel}")
                    btn.click()
                    break
            except Exception:
                continue

        time.sleep(3)
        page.screenshot(path=os.path.join(DOWNLOAD_DIR, "03_after_login.png"))
        print(f"    로그인 후 URL: {page.url}")

        # 3. 게시물 페이지 이동
        print(f"\n[3] 게시물 페이지 이동: ID {TEST_DOC_ID}")
        page.goto(DOC_URL, timeout=30000)
        time.sleep(3)
        print(f"    현재 URL: {page.url}")
        page.screenshot(path=os.path.join(DOWNLOAD_DIR, "04_doc_page.png"))

        # 4. 첨부파일 탐색
        print("\n[4] 첨부파일 탐색...")
        # 일반적인 첨부파일 선택자
        attach_selectors = [
            'a[href*="download"]',
            'a[href*="attach"]',
            'a[href*="file"]',
            '.attach a',
            '.attachment a',
            '.file-list a',
            '[class*="attach"] a',
            '[class*="file"] a',
        ]

        found_links = []
        for sel in attach_selectors:
            try:
                links = page.query_selector_all(sel)
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()
                    if href and text:
                        found_links.append({"selector": sel, "href": href, "text": text})
            except Exception:
                continue

        if found_links:
            print(f"    첨부파일 링크 {len(found_links)}개 발견:")
            for fl in found_links[:10]:
                print(f"      [{fl['selector']}] {fl['text']} → {fl['href'][:80]}")
        else:
            print("    첨부파일 링크 없음. 페이지 내 모든 링크 확인...")
            all_links = page.query_selector_all("a")
            for link in all_links[:30]:
                href = link.get_attribute("href") or ""
                text = link.inner_text().strip()[:50]
                if href:
                    print(f"      {text} → {href[:80]}")

        # 5. 다운로드 시도 (첫 번째 첨부파일)
        if found_links:
            print(f"\n[5] 다운로드 시도: {found_links[0]['text']}")
            with page.expect_download(timeout=30000) as download_info:
                page.click(f"a[href='{found_links[0]['href']}']")
            download = download_info.value
            save_path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
            download.save_as(save_path)
            file_size = os.path.getsize(save_path)
            print(f"    다운로드 완료: {download.suggested_filename} ({file_size/1024:.0f} KB)")
        else:
            print("\n[5] 다운로드할 첨부파일 없음")

        # 최종 스크린샷
        page.screenshot(path=os.path.join(DOWNLOAD_DIR, "05_final.png"))
        browser.close()

    print("\n완료. 스크린샷 확인: " + DOWNLOAD_DIR)


if __name__ == "__main__":
    main()
