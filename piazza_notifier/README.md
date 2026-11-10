# Piazza → phone notifications

Polls your enrolled Piazza classes and pushes a notification to your phone
(via [ntfy](https://ntfy.sh)) for every new or updated post. Tapping the
notification opens the post.

## Setup
1. Install the **ntfy** app (iOS/Android) and subscribe to a long random topic name.
2. `cd piazza_notifier && pip install -r requirements.txt`
3. `cp .env.example .env`, fill it in, then:
   ```
   set -a; . ./.env; set +a
   python notifier.py
   ```
The first run records current posts silently; only later changes notify you.

## Running 24/7
Needs an always-on machine (Raspberry Pi, VPS, home server). Example systemd/`nohup`/Docker all work; or `tmux` + the command above.

## Notes
- Piazza has no official API. `piazza-api` is unofficial and logs in with your password, so keep `.env` private (it's git-ignored). If you use Google/SSO login, set a Piazza password first.
- Latency is up to `POLL_SECONDS` (default 1800s = 30 min).
- Anyone who knows your topic name can read notifications; use a long random one (or self-host ntfy).

## Quiet hours
By default it pauses from 23:00 to 06:00 (`QUIET_START`/`QUIET_END`, in `TIMEZONE`,
an IANA name like `Asia/Kolkata`). Set `TIMEZONE` or it uses the machine's clock.
Posts made overnight are sent as notifications at the first check after 06:00.
