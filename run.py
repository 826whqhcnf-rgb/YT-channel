#!/usr/bin/env python3
"""
Make short-form story videos.

  python run.py --topic "AITA for ruining my sister's wedding"
  python run.py --random
  python run.py --batch 5                 # make 5 videos from random topics
  python run.py --topic "..." --script-only
  python run.py --topic "..." --upload youtube,tiktok
"""
import argparse, json, os, random, sys

CONFIG = "config.json"


def load_config():
    if not os.path.exists(CONFIG):
        print("No config.json found. Run: python setup.py")
        sys.exit(1)
    with open(CONFIG) as f:
        return json.load(f)


def all_topics():
    path = "data/topics.txt"
    if os.path.exists(path):
        lines = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
        if lines:
            return lines
    return ["strangest deep sea creatures"]


def random_topic():
    return random.choice(all_topics())


def pick_topics(count):
    """Return `count` distinct random topics (repeats only if not enough)."""
    pool = all_topics()
    random.shuffle(pool)
    if count <= len(pool):
        return pool[:count]
    return [random.choice(pool) for _ in range(count)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topic", help="Video topic / story prompt")
    p.add_argument("--random", action="store_true", help="Pick a random topic")
    p.add_argument("--batch", type=int, default=1, metavar="N",
                   help="Make N videos from random topics (a backlog)")
    p.add_argument("--script-only", action="store_true", help="Only write the script, no video")
    p.add_argument("--script", help="Path to existing script.json to use instead of generating")
    p.add_argument("--upload", help="youtube, tiktok, or youtube,tiktok")
    p.add_argument("--reset-stories", action="store_true",
                   help="Clear the list of already-used Reddit posts")
    args = p.parse_args()

    if args.reset_stories:
        used = os.path.join("data", "used_reddit.txt")
        if os.path.exists(used):
            os.remove(used)
            print("Cleared used-stories list — Reddit posts can be reused now.")
        else:
            print("No used-stories list to clear.")
        return

    cfg = load_config()

    if args.upload:
        wanted = {s.strip() for s in args.upload.split(",")}
        cfg["upload"]["youtube"] = "youtube" in wanted
        cfg["upload"]["tiktok"] = "tiktok" in wanted

    from src.pipeline import run

    # --- Batch mode ---
    if args.batch > 1:
        topics = pick_topics(args.batch)
        print(f"=== Batch: making {len(topics)} videos ===")
        results = []
        for i, topic in enumerate(topics, 1):
            print(f"\n----- [{i}/{len(topics)}] {topic} -----")
            try:
                out = run(topic, cfg, script_only=args.script_only)
                results.append((topic, out if out else "script written"))
            except Exception as e:
                print(f"[batch] '{topic}' failed: {e}")
                results.append((topic, "FAILED"))
        print("\n=== Batch complete ===")
        for topic, status in results:
            print(f"  {topic[:45]:45s} -> {status}")
        return

    # --- Single video ---
    topic = args.topic
    if not topic or args.random:
        topic = random_topic()
        print(f"Topic: {topic}")
    run(topic, cfg, script_path=args.script, script_only=args.script_only)


if __name__ == "__main__":
    main()
