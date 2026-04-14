#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WTA 밥먹기 메뉴 추천 시스템
- 매일 오전 10시 실행
- 날씨 + 요일 패턴 기반 추천
- 슬랙 #밥먹기 채널 발송
- 직원 응답 수집 후 정리본 발송

사용법:
  py menu_recommender.py recommend   # 추천 메시지 발송
  py menu_recommender.py collect     # 응답 수집 및 정리본 발송 (오후 12시쯤)
"""
import sys
import io
import json
import urllib.request
import datetime
import random
import os
from pathlib import Path

# Windows 콘솔 UTF-8 출력
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
MENU_DATA_FILE = BASE_DIR / "menu_data.json"
MENU_HISTORY_FILE = BASE_DIR / "menu_history.json"

# 슬랙 토큰
SLACK_TOKEN_FILE = Path("C:/MES/wta-agents/config/slack-token.txt")
CHANNEL = "밥먹기"

# MCP agent-channel send-alert
SEND_ALERT = Path("C:/MES/wta-agents/scripts/send-alert.py")


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_korean_event(date_obj: datetime.date) -> str:
    """한국 날짜별 주요 이벤트 반환"""
    events = {
        (1, 1): "신정",
        (3, 1): "삼일절",
        (4, 5): "한식의 날🍜",  # 청명절, 한식문화의 날
        (5, 5): "어린이날🎈",
        (5, 15): "스승의 날👨‍🏫",
        (6, 6): "현충일🇰🇷",
        (8, 15): "광복절🇰🇷",
        (9, 16): "추석🌙",
        (10, 3): "개천절🇰🇷",
        (10, 9): "한글날📝",
        (12, 25): "크리스마스🎄",
    }
    return events.get((date_obj.month, date_obj.day), "")


def get_weather():
    """wttr.in API로 창원 날씨 조회. 실패 시 기본값 반환."""
    try:
        url = "https://wttr.in/Changwon?format=j1"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        cur = data["current_condition"][0]
        desc = cur["weatherDesc"][0]["value"]
        temp_c = int(cur["temp_C"])
        feels_c = int(cur["FeelsLikeC"])

        # 체감 온도 기반 분류
        if feels_c <= 5:
            category = "cold"
            emoji = "🥶"
            comment = f"기온 {temp_c}°C, 꽤 춥네요"
        elif feels_c <= 13:
            category = "cool"
            emoji = "🧥"
            comment = f"기온 {temp_c}°C, 선선한 날씨"
        elif feels_c <= 22:
            category = "warm"
            emoji = "☀️"
            comment = f"기온 {temp_c}°C, 따뜻한 날씨"
        else:
            category = "hot"
            emoji = "🌡️"
            comment = f"기온 {temp_c}°C, 더운 날씨"

        # 비/흐림 감지
        rain_keywords = ["Rain", "Drizzle", "Shower", "Thunder", "Snow", "Sleet"]
        is_rain = any(k in desc for k in rain_keywords)
        cloud_keywords = ["Cloudy", "Overcast", "Fog", "Mist"]
        is_cloudy = any(k in desc for k in cloud_keywords)

        weather_note = ""
        if is_rain:
            weather_note = "☔ 비 오는 날"
        elif is_cloudy:
            weather_note = "☁️ 흐린 날"
        else:
            weather_note = f"{emoji} {desc}"

        return {
            "temp": temp_c,
            "feels": feels_c,
            "desc": desc,
            "category": category,
            "comment": comment,
            "note": weather_note,
            "is_rain": is_rain,
        }
    except Exception as e:
        print(f"[경고] 날씨 조회 실패: {e}", file=sys.stderr)
        return {
            "temp": 15, "feels": 15, "desc": "Unknown",
            "category": "cool", "comment": "기온 정보 없음",
            "note": "날씨 정보 없음", "is_rain": False
        }


def get_recent_restaurants(days: int = 5) -> list[str]:
    """최근 N일 '실제 선택된' 식당 목록 (중복 방지용, decided 상태만)"""
    history = load_json(MENU_HISTORY_FILE, [])
    recent = history[-days:] if len(history) >= days else history
    # decided 상태만 반영 (recommended는 무시, pending도 무시)
    return [r["restaurant"] for r in recent if r.get("status") == "decided" and r["restaurant"] != "미정"]


def recommend_restaurants(weekday: str, weather: dict, top_n: int = 3) -> tuple[list[str], dict]:
    """요일 + 날씨 가중치로 식당 추천. (추천 목록, 근거 dict) 반환"""
    data = load_json(MENU_DATA_FILE, {"restaurants": {}})
    restaurants = data.get("restaurants", {})
    recent = get_recent_restaurants(4)
    yesterday_list = get_recent_restaurants(1)
    yesterday = yesterday_list[0] if yesterday_list else ""

    scores = {}
    details = {}  # 각 식당별 점수 상세 정보
    for name, info in restaurants.items():
        wd_w = info.get("weekday_weight", {}).get(weekday, 1)
        wt_w = info.get("weather_weight", {}).get(weather["category"], 1)
        # 최근 나온 식당 페널티 (어제 먹었으면 특히 강함)
        if name == yesterday:
            penalty = 0.1
        elif name in recent:
            penalty = 0.3
        else:
            penalty = 1.0

        score = wd_w * wt_w * penalty
        scores[name] = score
        details[name] = {
            "weekday_weight": wd_w,
            "weather_weight": wt_w,
            "penalty": penalty,
            "final_score": score
        }

    # 점수 정렬 + 약간의 랜덤성 (동점 구분)
    sorted_rests = sorted(scores.items(), key=lambda x: x[1] + random.uniform(0, 0.1), reverse=True)
    picks = [r[0] for r in sorted_rests[:top_n]]

    return picks, {
        "picks": picks,
        "yesterday": yesterday,  # 실제 선택된 메뉴만 (decided 상태)
        "details": details,
        "score_summary": {name: score for name, score in sorted_rests[:top_n]}
    }


def build_recommend_message(weekday: str, weather: dict, today: datetime.date, reason: dict) -> str:
    """추천 메시지 조립 (근거 포함)"""
    picks = reason.get("picks", [])
    yesterday = reason.get("yesterday", "")
    details = reason.get("details", {})

    # 이벤트 확인
    event = get_korean_event(today)
    event_msg = f"{event} " if event else ""

    # 추천 근거 조립
    reason_lines = []
    if event:
        reason_lines.append(f"📅 오늘은 {event}")
    if yesterday:
        reason_lines.append(f"🔄 어제({yesterday}) 드셨으니 다른 식당 추천")
    reason_lines.append(f"🌤️ {weather['note']} ({weather['comment']})")
    reason_text = " + ".join(reason_lines)

    # 추천 식당 (메달 이모지 + 점수 표시)
    medal = ["1️⃣", "2️⃣", "3️⃣"]
    pick_lines = []
    for i, p in enumerate(picks):
        detail = details.get(p, {})
        score = detail.get("final_score", 0)
        pick_lines.append(f"{medal[i]} *{p}* (점수: {score:.2f})")

    data = load_json(MENU_DATA_FILE, {})
    members = data.get("members", [])
    member_lines = "\n".join(f"{m}>" for m in members)

    msg = (
        f"🍽️ *오늘 점심 뭐 드실건가요?*\n\n"
        f"💡 AI 추천 근거:\n"
        f"{reason_text}\n\n"
        f"📊 추천 메뉴:\n"
        f"{chr(10).join(pick_lines)}\n\n"
        f"아래 형식으로 답해주세요 👇\n"
        f"{member_lines}"
    )
    return msg


def slack_post(message: str) -> bool:
    """슬랙 채널에 직접 발송 (slack_sdk)"""
    if not SLACK_TOKEN_FILE.exists():
        print(f"[오류] 슬랙 토큰 없음: {SLACK_TOKEN_FILE}", file=sys.stderr)
        return False
    token = SLACK_TOKEN_FILE.read_text(encoding="utf-8").strip().splitlines()[0]
    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)
        resp = client.chat_postMessage(channel=CHANNEL, text=message)
        return resp["ok"]
    except ImportError:
        # slack_sdk 없으면 HTTP 직접 호출
        import urllib.parse
        payload = json.dumps({"channel": CHANNEL, "text": message}).encode()
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {token}",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"[오류] 슬랙 발송 실패: {e}", file=sys.stderr)
        return False


def save_history(date_str: str, restaurant: str, weekday: str, status: str = "recommended"):
    """추천 이력 저장 (status: recommended/decided/pending)"""
    history = load_json(MENU_HISTORY_FILE, [])
    # 같은 날 중복 저장 방지
    if history and history[-1].get("date") == date_str:
        history[-1]["restaurant"] = restaurant
        history[-1]["status"] = status
    else:
        history.append({"date": date_str, "restaurant": restaurant, "weekday": weekday, "status": status})
    # 최근 60일만 보관
    save_json(MENU_HISTORY_FILE, history[-60:])


def cmd_recommend():
    """오전 10시 추천 메시지 발송"""
    today = datetime.date.today()
    weekday = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]

    # 주말 처리: 토요일(5), 일요일(6) 건너뛰기
    if today.weekday() >= 5:
        print(f"[{today}({weekday})] 주말 — 추천 생략")
        save_history(str(today), "미정", weekday, status="pending")
        return

    weather = get_weather()
    picks, reason = recommend_restaurants(weekday, weather)

    event = get_korean_event(today)
    print(f"[{today}({weekday})] {event if event else '일반날'}")
    print(f"날씨: {weather['note']} ({weather['comment']})")
    print(f"어제: {reason.get('yesterday', '(첫날)')}")
    print(f"추천: {picks}")

    msg = build_recommend_message(weekday, weather, today, reason)
    ok = slack_post(msg)
    print(f"슬랙 발송: {'성공' if ok else '실패'}")

    if ok:
        save_history(str(today), picks[0], weekday, status="recommended")


def cmd_collect():
    """응답 수집 후 정리본 발송 + 히스토리 업데이트 (slack_history로 최근 메시지 파싱)"""
    if not SLACK_TOKEN_FILE.exists():
        print("[오류] 슬랙 토큰 없음", file=sys.stderr)
        return

    token = SLACK_TOKEN_FILE.read_text(encoding="utf-8").strip().splitlines()[0]
    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)

        # 채널 ID 조회
        resp = client.conversations_list(types="public_channel,private_channel", limit=200)
        ch_id = None
        for ch in resp.get("channels", []):
            if ch["name"] == CHANNEL:
                ch_id = ch["id"]
                break
        if not ch_id:
            print(f"[오류] #{CHANNEL} 채널 없음", file=sys.stderr)
            return

        # 오늘 메시지 조회 (최근 50개)
        history = client.conversations_history(channel=ch_id, limit=50)
        messages = history.get("messages", [])

        # 직원 이름 목록
        data = load_json(MENU_DATA_FILE, {})
        members = data.get("members", [])

        # 최신 응답 파싱 (이름> 메뉴 형식)
        import re
        member_orders: dict[str, str] = {}
        for msg in messages:
            if msg.get("bot_id") or msg.get("subtype") == "bot_message":
                continue
            text = msg.get("text", "")
            # 여러 줄 파싱
            for line in text.split("\n"):
                m = re.match(r"^([가-힣]{2,4})>\s*(.*)$", line.strip())
                if m:
                    name, order = m.group(1), m.group(2).strip()
                    if name in members and order:
                        member_orders[name] = order

        if not member_orders:
            print("[정보] 응답 없음 — 정리본 발송 생략")
            return

        # 정리본 메시지
        lines = []
        for name in members:
            order = member_orders.get(name, "미응답")
            lines.append(f"{name}> {order}")

        summary = "📋 *점심 주문 정리*\n\n" + "\n".join(lines)
        ok = slack_post(summary)
        print(f"정리본 발송: {'성공' if ok else '실패'}")

        # 히스토리 업데이트: 실제 선택된 메뉴 기록
        today = datetime.date.today()
        history_data = load_json(MENU_HISTORY_FILE, [])
        if history_data and history_data[-1].get("date") == str(today):
            # 오늘 항목이 있으면, 첫 응답자의 선택을 대표로 저장
            first_order = list(member_orders.values())[0] if member_orders else "미정"
            history_data[-1]["restaurant"] = first_order
            history_data[-1]["status"] = "decided"
            history_data[-1]["responded_count"] = len(member_orders)
            save_json(MENU_HISTORY_FILE, history_data)
            print(f"히스토리 업데이트: {first_order} (결정됨, {len(member_orders)}명 응답)")

    except Exception as e:
        print(f"[오류] 응답 수집 실패: {e}", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recommend"
    if cmd == "recommend":
        cmd_recommend()
    elif cmd == "collect":
        cmd_collect()
    else:
        print(f"알 수 없는 명령: {cmd}")
        print("사용법: py menu_recommender.py [recommend|collect]")
