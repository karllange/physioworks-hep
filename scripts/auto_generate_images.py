"""Generate a clinic illustration for every exercise listed in docs/asset_gaps.md."""

import argparse
import base64
import io
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GAPS_PATH = ROOT / "docs" / "asset_gaps.md"
OUT_DIR = Path(r"G:\My Drive\PhysioWorks HEP Images\raw_grok_outputs")
DELAY_SECONDS = 10
TIMEOUT_SECONDS = 180

PROMPT = (
    "Clinical line illustration for a physical therapy home exercise program. One adult figure, "
    "navy blue line art on a solid white #FFFFFF background. High contrast, no text, no labels, "
    "no arrows, no watermark. Square composition, simple anatomy. Show the start position and the "
    "finish position as two separate frames side by side within the same image. "
    "The exercise is: {exercise_name}"
)

PROVIDERS = {
    "openai": {
        "url": "https://api.openai.com/v1/images/generations",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_IMAGE_MODEL",
        "default_model": "dall-e-3",
        "extra": {"size": "1024x1024", "quality": "standard"},
    },
    # xAI rejects the size and quality fields.
    "xai": {
        "url": "https://api.x.ai/v1/images/generations",
        "key_env": "XAI_API_KEY",
        "model_env": "XAI_IMAGE_MODEL",
        "default_model": "grok-2-image",
        "extra": {},
    },
}

HEADING = re.compile(r"^##\s+(\S+)\s+[—–-]\s+(.+?)\s*$")


def parse_gaps(path):
    exercises = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if match:
            exercises.append((match.group(1), match.group(2)))
    return exercises


def generate(provider, api_key, model, exercise_name):
    config = PROVIDERS[provider]
    payload = {
        "model": model,
        "prompt": PROMPT.format(exercise_name=exercise_name),
        "n": 1,
        **config["extra"],
    }
    response = requests.post(
        config["url"],
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
    item = response.json()["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    image = requests.get(item["url"], timeout=TIMEOUT_SECONDS)
    image.raise_for_status()
    return image.content


def save_png(data, path):
    with Image.open(io.BytesIO(data)) as image:
        image.save(path, format="PNG")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=PROVIDERS, default=None,
                        help="Defaults to IMAGE_PROVIDER from .env, then openai.")
    parser.add_argument("--limit", type=int, default=None, help="Stop after this many API calls.")
    parser.add_argument("--force", action="store_true", help="Regenerate images that already exist.")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")

    load_dotenv(ROOT / ".env")
    provider = args.provider or os.getenv("IMAGE_PROVIDER", "openai").lower()
    if provider not in PROVIDERS:
        print(f"Unknown provider '{provider}'. Use one of: {', '.join(PROVIDERS)}")
        return 2
    config = PROVIDERS[provider]
    api_key = os.getenv(config["key_env"])
    if not api_key:
        print(f"Missing {config['key_env']} in .env")
        return 2
    model = os.getenv(config["model_env"], config["default_model"])

    if not OUT_DIR.parent.exists():
        print(f"Output drive not found: {OUT_DIR.parent}")
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    exercises = parse_gaps(GAPS_PATH)
    todo = [(eid, name) for eid, name in exercises
            if args.force or not (OUT_DIR / f"{eid}.png").exists()]
    skipped = len(exercises) - len(todo)
    if args.limit is not None:
        todo = todo[:args.limit]

    print(f"Provider: {provider} ({model})")
    print(f"Missing exercises in gaps file: {len(exercises)}")
    print(f"Already generated (skipped):    {skipped}")
    print(f"To generate this run:           {len(todo)}")
    print(f"Output folder: {OUT_DIR}")
    print("")

    succeeded, failed = 0, []
    for index, (exercise_id, name) in enumerate(todo, start=1):
        label = f"[{index}/{len(todo)}] {exercise_id} — {name}"
        try:
            data = generate(provider, api_key, model, name)
            save_png(data, OUT_DIR / f"{exercise_id}.png")
            succeeded += 1
            print(f"OK    {label}")
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as error:
            failed.append(exercise_id)
            print(f"FAIL  {label}: {error}")
        if index < len(todo):
            time.sleep(DELAY_SECONDS)

    print("")
    print(f"Succeeded: {succeeded}")
    print(f"Failed:    {len(failed)}")
    for exercise_id in failed:
        print(f"  {exercise_id}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
