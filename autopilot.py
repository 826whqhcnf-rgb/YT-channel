#!/usr/bin/env python3
"""
Autopilot: hands-off content machine.

  python autopilot.py                 # make + post videos using config.json autopilot settings
  python autopilot.py --count 3       # make + post 3 now, then stop
  python autopilot.py --loop          # keep going forever on a schedule
  python autopilot.py --mode finance  # long-form finance instead of reddit stories

It reads an "autopilot" block in config.json:
  "autopilot": {
    "count": 3,                 # videos per run
    "mode": "reddit",           # reddit | finance
    "upload": ["youtube"],      # where to post (e.g. ["youtube","tiktok"]) or [] to just save
    "every_hours": 24,          # with --loop, wait this long between runs
    "stop_after_runs": 0        # 0 = unlimited
  }

Posting still needs your one-time credential setup (UPLOAD_SETUP.md). The first
YouTube post will pause for the one-time browser authorization; after that it's
fully unattended.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

CONFIG = "config.json"


def load_config():
    if not os.path.exists(CONFIG):
        print("No config.json — run: python setup.py")
        sys.exit(1)
    with open(CONFIG) as f:
        return json.load(f)


def one_run(cfg, mode, count, uploads):
    """Generate + (optionally) post `count` videos. Returns (ok, failed)."""
    from src.pipeline import run
    from run import pick_topics

    # turn the requested upload targets on in cfg
    cfg.setdefault("upload", {})
    cfg["upload"]["youtube"] = "youtube" in uploads
    cfg["upload"]["tiktok"] = "tiktok" in uploads

    topics_file = "data/finance_topics.txt" if mode == "finance" else "data/topics.txt"
    # reddit mode pulls fresh stories regardless of topic; finance uses the seed list
    topics = pick_topics(count, topics_file)

    ok = failed = 0
    for i, topic in enumerate(topics, 1):
        label = f"[{i}/{count}]"
        print(f"\n========== autopilot {label} ({mode}) ==========")
        try:
            out = run(topic, cfg, mode=mode)
            if out:
                ok += 1
                print(f"autopilot {label} ✅ {out}")
            else:
                failed += 1
                print(f"autopilot {label} ⚠️ nothing produced")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"autopilot {label} ❌ {e}")
    return ok, failed


def main():
    p = argparse.ArgumentParser(description="Hands-off video autopilot")
    p.add_argument("--count", type=int, help="Videos per run (overrides config)")
    p.add_argument("--mode", choices=["reddit", "finance"], help="Content mode (overrides config)")
    p.add_argument("--loop", action="store_true", help="Keep running on a schedule")
    p.add_argument("--upload", help="Override upload targets, e.g. youtube or youtube,tiktok or none")
    args = p.parse_args()

    cfg = load_config()
    ap = cfg.get("autopilot", {})

    mode = args.mode or ap.get("mode", "reddit")
    count = args.count or ap.get("count", 3)
    if args.upload is not None:
        uploads = [] if args.upload.lower() in ("none", "") else \
                  [s.strip() for s in args.upload.split(",") if s.strip()]
    else:
        uploads = ap.get("upload", [])
    every_hours = ap.get("every_hours", 24)
    stop_after = ap.get("stop_after_runs", 0)

    where = ", ".join(uploads) if uploads else "save only (no posting)"
    print(f"🤖 Autopilot: {count} {mode} video(s) per run → {where}")
    if args.loop:
        print(f"   Looping every {every_hours}h" +
              (f", stopping after {stop_after} runs." if stop_after else ", forever (Ctrl+C to stop)."))

    runs = 0
    while True:
        runs += 1
        print(f"\n##### RUN {runs} @ {datetime.now():%Y-%m-%d %H:%M} #####")
        ok, failed = one_run(cfg, mode, count, uploads)
        print(f"\n##### RUN {runs} done: {ok} ok, {failed} failed #####")

        if not args.loop:
            break
        if stop_after and runs >= stop_after:
            print("Reached stop_after_runs — stopping.")
            break
        wake = datetime.now().timestamp() + every_hours * 3600
        print(f"😴 Sleeping until {datetime.fromtimestamp(wake):%Y-%m-%d %H:%M}...")
        try:
            time.sleep(every_hours * 3600)
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break


if __name__ == "__main__":
    main()
