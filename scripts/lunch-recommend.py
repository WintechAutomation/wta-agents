"""Weekday 10:00 lunch menu recommendation for #밥먹기 Slack channel.
Reads lunch-menu.md, picks random restaurants and menus, posts to Slack."""

import os
import re
import random
import sys

sys.stdout.reconfigure(encoding='utf-8')

from slack_sdk import WebClient

MENU_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "workspaces", "sales-agent", "lunch-menu.md")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "config", "slack-token.txt")
CHANNEL_NAME = "밥먹기"
BUDGET = 9000


def parse_restaurants(filepath):
    """Parse lunch-menu.md and extract restaurant menus."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    restaurants = []
    # Split by "### " headers under "식당 메뉴판"
    menu_section = content.split("## 식당 메뉴판")
    if len(menu_section) < 2:
        return restaurants

    parts = re.split(r"### (.+)", menu_section[1])
    i = 1
    while i < len(parts):
        name = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        menus = []
        for m in re.finditer(r"\| (.+?) \| ([\d,]+)원", body):
            menu_name = m.group(1).strip()
            price = int(m.group(2).replace(",", ""))
            menus.append({"name": menu_name, "price": price})
        if menus:
            restaurants.append({"name": name, "menus": menus})
        i += 2

    return restaurants


def pick_recommendations(restaurants, count=3):
    """Pick random restaurant+menu combinations."""
    candidates = []
    for r in restaurants:
        for m in r["menus"]:
            candidates.append({
                "restaurant": r["name"],
                "menu": m["name"],
                "price": m["price"],
                "over": max(0, m["price"] - BUDGET),
            })

    if not candidates:
        return []

    return random.sample(candidates, min(count, len(candidates)))


def format_message(picks):
    """Format Slack message."""
    lines = ["🍽️ *오늘의 점심 추천 메뉴*\n"]
    for i, p in enumerate(picks, 1):
        price_str = f"{p['price']:,}원"
        over_str = f" (식대 초과 +{p['over']:,}원)" if p['over'] > 0 else " (식대 내)"
        lines.append(f"*{i}. {p['restaurant']}* — {p['menu']} {price_str}{over_str}")

    lines.append(f"\n💰 식대 기준: {BUDGET:,}원")
    lines.append("맛있는 점심 되세요! 🙂")
    return "\n".join(lines)


def find_channel(client, name):
    """Find channel ID by name."""
    result = client.conversations_list(types="public_channel,private_channel", limit=500)
    for ch in result["channels"]:
        if ch["name"] == name:
            return ch["id"]
    return None


def main():
    if not os.path.exists(MENU_FILE):
        print(f"Menu file not found: {MENU_FILE}")
        return

    restaurants = parse_restaurants(MENU_FILE)
    if not restaurants:
        print("No restaurants found in menu file")
        return

    picks = pick_recommendations(restaurants, count=3)
    message = format_message(picks)
    print(message)

    # Send to Slack
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()

    client = WebClient(token=token)
    ch_id = find_channel(client, CHANNEL_NAME)
    if not ch_id:
        print(f"Channel #{CHANNEL_NAME} not found")
        return

    client.chat_postMessage(channel=ch_id, text=message, mrkdwn=True)
    print(f"\nPosted to #{CHANNEL_NAME}")


if __name__ == "__main__":
    main()
