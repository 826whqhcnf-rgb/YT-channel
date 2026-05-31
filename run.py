#!/usr/bin/env python3
"""
Make a short-form video.

  python run.py --topic "top 10 strangest deep sea creatures"
  python run.py --random
  python run.py --topic "haunted places" --script-only
  python run.py --topic "haunted places" --upload youtube,tiktok
"""
import argparse, json, os, random, sys

CONFIG = "config.json"

def load_config():
    if not os.path.exists(CONFIG):
        print("No config.json found. Run: python setup.py")
        sys.exit(1)
    with open(CONFIG) as f:
        return json.load(f)

def random_topic():
    path = "data/topics.txt"
    if os.path.exists(path):
        lines = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
        if lines:
            return random.choice(lines)
    return "strangest deep sea creatures"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topic", help="Video topic")
    p.add_argument("--random", action="store_true", help="Pick a random topic")
    p.add_argument("--script-only", action="store_true", help="Only write the script, no video")
    p.add_argument("--script", help="Path to existing script.json to use instead of generating")
    p.add_argument("--upload", help="youtube, tiktok, or youtube,tiktok")
    args = p.parse_args()

    cfg = load_config()

    topic = args.topic
    if not topic or args.random:
        topic = random_topic()
        print(f"Topic: {topic}")

    if args.upload:
        wanted = {s.strip() for s in args.upload.split(",")}
        cfg["upload"]["youtube"] = "youtube" in wanted
        cfg["upload"]["tiktok"] = "tiktok" in wanted

    from src.pipeline import run
    run(topic, cfg, script_path=args.script, script_only=args.script_only)

if __name__ == "__main__":
    main()
