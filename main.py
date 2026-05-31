#!/usr/bin/env python3
"""
Faceless YouTube/TikTok channel — command-line entry point.

Examples:
  # Generate a video from a topic (renders MP4s into ./output)
  python main.py --topic "strangest deep sea creatures"

  # Use a hand-edited script instead of generating one
  python main.py --topic "deep sea" --script output/.../script.json

  # Generate the script JSON only (so you can edit before rendering)
  python main.py --topic "ancient inventions" --script-only

  # Enable uploads from the CLI (overrides config.yaml)
  python main.py --topic "black holes" --upload youtube,tiktok
"""

from __future__ import annotations

import argparse
import sys

import yaml
from dotenv import load_dotenv


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Faceless Top-10 video generator")
    p.add_argument("--topic", required=True, help="Video topic, e.g. 'haunted places'")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--script", help="Path to an existing script.json to render")
    p.add_argument("--script-only", action="store_true", help="Only generate script.json")
    p.add_argument("--upload", help="Comma list: youtube,tiktok (overrides config)")
    args = p.parse_args()

    cfg = load_config(args.config)

    if args.upload is not None:
        wanted = {s.strip() for s in args.upload.split(",") if s.strip()}
        cfg["upload"]["youtube"]["enabled"] = "youtube" in wanted
        cfg["upload"]["tiktok"]["enabled"] = "tiktok" in wanted

    if args.script_only:
        from src import script_generator

        script = script_generator.generate(
            args.topic,
            num_items=cfg["content"]["num_items"],
            words_per_item=cfg["content"]["words_per_item"],
        )
        out = "script.json"
        with open(out, "w", encoding="utf-8") as f:
            f.write(script.to_json())
        print(f"Wrote {out} — edit it, then: python main.py --topic '{args.topic}' --script {out}")
        return 0

    from src import pipeline

    result = pipeline.run(cfg, args.topic, script_path=args.script)
    print("\n=== Done ===")
    print(f"Output folder: {result['out_dir']}")
    for orient, path in result["videos"].items():
        print(f"  {orient:9s} -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
