#!/usr/bin/env python3
"""Push a phone notification (via ntfy) whenever a Piazza class has new activity.

Piazza has no official API; this uses the unofficial `piazza-api` package,
which logs in with your normal email/password.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from piazza_api import Piazza

EMAIL = os.environ["PIAZZA_EMAIL"]
PASSWORD = os.environ["PIAZZA_PASSWORD"]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]  # long random string = your private channel
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
INTERVAL = int(os.environ.get("POLL_SECONDS", "1800"))
FEED_LIMIT = int(os.environ.get("FEED_LIMIT", "50"))
# Optional: comma-separated class network ids to watch. Default: all enrolled.
ONLY = {x.strip() for x in os.environ.get("PIAZZA_NETWORK_IDS", "").split(",") if x.strip()}
# Quiet hours: no polling from QUIET_START to QUIET_END (24h clock, in TIMEZONE).
# Anything posted overnight is caught by the first check after QUIET_END.
QUIET_START = int(os.environ.get("QUIET_START", "23"))
QUIET_END = int(os.environ.get("QUIET_END", "6"))
TZ = ZoneInfo(os.environ["TIMEZONE"]) if os.environ.get("TIMEZONE") else None
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return None


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE_FILE)


def notify(title, message, url):
    r = requests.post(
        f"{NTFY_SERVER}/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Click": url, "Tags": "books"},
        timeout=15,
    )
    r.raise_for_status()


def login():
    p = Piazza()
    p.user_login(email=EMAIL, password=PASSWORD)
    return p


def check(p, state, first_run):
    for cls in p.get_user_classes():
        nid = cls["nid"]
        if ONLY and nid not in ONLY:
            continue
        label = cls.get("num") or cls.get("name") or nid
        feed = p.network(nid).get_feed(limit=FEED_LIMIT, offset=0).get("feed", [])
        seen = state.setdefault(nid, {})
        for item in feed:
            pid, modified = item["id"], item.get("modified", "")
            old = seen.get(pid)
            if old == modified:
                continue
            seen[pid] = modified
            if first_run:
                continue  # seed state silently so you don't get a flood
            kind = "New post" if old is None else "Updated"
            subject = item.get("subject", "(no subject)")
            url = f"https://piazza.com/class/{nid}/post/{item.get('nr', pid)}"
            notify(f"{label}: {kind}", f"@{item.get('nr', '?')} {subject}", url)
            print(f"notified: {label} {kind} @{item.get('nr')} {subject}", flush=True)


def in_quiet_hours():
    h = datetime.now(TZ).hour
    if QUIET_START == QUIET_END:
        return False
    if QUIET_START < QUIET_END:
        return QUIET_START <= h < QUIET_END
    return h >= QUIET_START or h < QUIET_END  # wraps past midnight


def seconds_until_quiet_end():
    now = datetime.now(TZ)
    end = now.replace(hour=QUIET_END, minute=0, second=0, microsecond=0)
    if end <= now:
        end += timedelta(days=1)
    return max(60, int((end - now).total_seconds()))


def main():
    state = load_state()
    first_run = state is None
    state = state or {}
    if os.environ.get("ONCE"):  # single check then exit (for cron / GitHub Actions)
        if in_quiet_hours():
            print("quiet hours, skipping", flush=True)
            return
        check(login(), state, first_run)
        save_state(state)
        return
    p = login()
    while True:
        if in_quiet_hours():
            wait = seconds_until_quiet_end()
            print(f"quiet hours, sleeping {wait}s", flush=True)
            time.sleep(wait)
            p = login()  # session may have expired overnight
            continue
        try:
            check(p, state, first_run)
            save_state(state)
            first_run = False
        except Exception as e:  # network hiccup / expired session: re-login next loop
            print(f"error: {e}", file=sys.stderr, flush=True)
            try:
                p = login()
            except Exception as e2:
                print(f"login failed: {e2}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
