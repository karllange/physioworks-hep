"""Watch an intake folder and publish new exercise drawings as 800x800 WebP files.

Drop .png, .jpg, .jpeg, or .webp files into raw_grok_outputs/ (or pass --intake
for a Google Drive synced folder). A filename that matches an exercise id is
attached to that card. A generic name such as grok_output_1.png is applied to
the next still-pending exercise in docs/asset_batches/batch_01_priority.md.

When a scan activates at least one exercise, the script commits those files and
pushes origin main. Pass --no-git to process without publishing.
"""

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "exercises.json"
GAPS_PATH = ROOT / "docs" / "asset_gaps.md"
PRIORITY_PATH = ROOT / "docs" / "asset_batches" / "batch_01_priority.md"
DEFAULT_INTAKE = ROOT / "raw_grok_outputs"
ASSETS = ROOT / "assets"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TEMP_DOWNLOAD_PATTERNS = ("*.tmp", "*.crdownload", "*.~*")
STABLE_SECONDS = 1.0
COMMIT_MESSAGE = "feat(assets): ingest and optimize new exercise diagrams from grok batch"
GENERIC_RE = re.compile(
    r"^(?:grok[_-]?output|output|image|img|untitled|screenshot|download|dsc|img)[_-]?\d+$",
    re.I,
)


def slugify(value):
    text = str(value or "").lower().strip().replace("_", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def priority_ids(path):
    if not Path(path).exists():
        return []
    return re.findall(r"Exercise ID: `([^`]+)`", Path(path).read_text(encoding="utf-8"))


def remove_gap_sections(text, removed_ids):
    if not removed_ids:
        return text, 0
    pattern = re.compile(r"^## (.+?) —", re.M)
    matches = list(pattern.finditer(text))
    if not matches:
        return text, 0
    kept = [text[:matches[0].start()]]
    removed = 0
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if match.group(1).strip() in removed_ids:
            removed += 1
            continue
        kept.append(text[match.start():end])
    return "".join(kept).rstrip() + "\n", removed


def index_catalog(catalog):
    by_id = {}
    by_slug = {}
    for entry in catalog:
        exercise_id = entry.get("id")
        if not exercise_id:
            continue
        by_id[exercise_id] = entry
        by_slug[slugify(exercise_id)] = exercise_id
        by_slug.setdefault(slugify(entry.get("name")), exercise_id)
    return by_id, by_slug


def is_generic(stem):
    slug = slugify(stem)
    if GENERIC_RE.match(slug):
        return True
    return bool(re.fullmatch(r"\d+", slug))


def match_exercise(stem, by_slug, pending_queue):
    slug = slugify(stem)
    if is_generic(stem):
        return pending_queue.pop(0) if pending_queue else ""
    if slug in by_slug:
        return by_slug[slug]
    for known, exercise_id in by_slug.items():
        if known and (slug == known or slug.endswith("-" + known) or known.endswith("-" + slug)):
            return exercise_id
    return ""


def is_temp_download(path):
    name = Path(path).name
    return any(fnmatch.fnmatch(name, pattern) for pattern in TEMP_DOWNLOAD_PATTERNS)


def is_html_redirect(path):
    try:
        header = Path(path).read_bytes()[:512]
    except OSError:
        return False
    text = header.decode("utf-8", errors="ignore")
    lowered = text.lstrip("\ufeff \t\r\n").lower()
    return (
        lowered.startswith("<!doctype")
        or lowered.startswith("<html")
        or "accounts.google.com" in lowered
    )


def to_square_webp(source, destination):
    try:
        with Image.open(source) as image:
            frame = image.convert("RGBA")
            width, height = frame.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            cropped = frame.crop((left, top, left + side, top + side))
            resized = cropped.resize((800, 800), Image.Resampling.LANCZOS)
            background = Image.new("RGB", (800, 800), "white")
            background.paste(resized, mask=resized.getchannel("A"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            background.save(destination, "WEBP", quality=85, method=6)
    except (UnidentifiedImageError, OSError, IOError):
        print(f"Corrupt or incomplete file detected: {Path(source).name}. Waiting for full write or skipping.")
        return False
    return True


def activate(entry, relative_url):
    entry["image_status"] = "active"
    entry["image_url"] = relative_url
    entry["photos"] = [relative_url, relative_url]


def stable_files(folder):
    found = []
    for path in sorted(Path(folder).iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if is_temp_download(path):
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if is_html_redirect(path):
            print(f"Skipping non-image/HTML redirect file: {path.name}")
            continue
        try:
            first = path.stat().st_size
        except OSError:
            continue
        time.sleep(STABLE_SECONDS)
        try:
            still_there = path.exists() and path.stat().st_size == first and first > 0
        except OSError:
            still_there = False
        if still_there:
            found.append(path)
    return found


def git_sync(paths):
    relative = [str(Path(path).resolve().relative_to(ROOT)) for path in paths if Path(path).exists()]
    if not relative:
        return
    subprocess.run(["git", "add", "--", *relative], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", COMMIT_MESSAGE, "--", *relative], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)


def process_batch(intake, catalog_path, gaps_path, priority_path, publish):
    intake = Path(intake)
    intake.mkdir(parents=True, exist_ok=True)
    (intake / "processed").mkdir(exist_ok=True)
    files = stable_files(intake)
    if not files:
        print("No new images.")
        return 0

    catalog = load_json(catalog_path)
    by_id, by_slug = index_catalog(catalog)
    pending = [
        exercise_id for exercise_id in priority_ids(priority_path)
        if by_id.get(exercise_id, {}).get("image_status") == "pending_asset"
    ]
    gaps = Path(gaps_path).read_text(encoding="utf-8") if Path(gaps_path).exists() else ""
    activated = []
    written = []

    for source in files:
        exercise_id = match_exercise(source.stem, by_slug, pending)
        entry = by_id.get(exercise_id)
        if not entry:
            print(f"skip {source.name}: no exercise match")
            continue
        destination = ASSETS / f"{exercise_id}.webp"
        if not to_square_webp(source, destination):
            continue
        relative = f"assets/{exercise_id}.webp"
        activate(entry, relative)
        gaps, _removed = remove_gap_sections(gaps, {exercise_id})
        shutil.move(str(source), str(intake / "processed" / source.name))
        activated.append(exercise_id)
        written.append(destination)
        print(f"active {exercise_id} <- {source.name}")

    if not activated:
        print("Newly activated exercises: 0")
        return 0

    dump_json(catalog_path, catalog)
    if Path(gaps_path).exists() or gaps.strip():
        Path(gaps_path).write_text(gaps, encoding="utf-8")
    print(f"Newly activated exercises: {len(activated)}")
    if publish:
        git_sync([catalog_path, gaps_path, *written])
        print("Pushed to origin main.")
    return len(activated)


def self_test():
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        intake = root / "in"
        intake.mkdir()
        catalog_path = root / "exercises.json"
        gaps_path = root / "gaps.md"
        priority_path = root / "priority.md"
        catalog = [
            {
                "id": "hamstring-curls-progression",
                "name": "Hamstring Curls Progression",
                "image_status": "pending_asset",
                "photos": ["https://placehold.co/300x200"],
            },
            {
                "id": "split-squat",
                "name": "Split Squat",
                "image_status": "pending_asset",
                "photos": ["https://placehold.co/300x200"],
            },
        ]
        dump_json(catalog_path, catalog)
        gaps_path.write_text(
            "# Gaps\n\n## hamstring-curls-progression — Hamstring Curls Progression\n\nbody\n\n## other — Other\n\nkeep\n",
            encoding="utf-8",
        )
        priority_path.write_text("Exercise ID: `hamstring-curls-progression`\n", encoding="utf-8")
        Image.new("RGB", (120, 40), (210, 45, 59)).save(intake / "grok_output_1.png")
        (intake / "login.jpg").write_text(
            "<!doctype html><html><base href=\"https://accounts.google.com\">",
            encoding="utf-8",
        )
        (intake / "partial.png.crdownload").write_bytes(b"still downloading")
        (intake / "notes.~tmp").write_bytes(b"editor swap")
        (intake / "split-squat.png").write_bytes(b"not a real image")
        original_assets = ASSETS
        test_assets = root / "assets"
        globals()["ASSETS"] = test_assets
        try:
            count = process_batch(intake, catalog_path, gaps_path, priority_path, publish=False)
        finally:
            globals()["ASSETS"] = original_assets
        updated = load_json(catalog_path)
        hamstring = updated[0]
        split_squat = updated[1]
        webp = test_assets / "hamstring-curls-progression.webp"
        with Image.open(webp) as image:
            size = image.size
        gaps = gaps_path.read_text(encoding="utf-8")
        ok = (
            count == 1
            and hamstring["image_status"] == "active"
            and hamstring["image_url"] == "assets/hamstring-curls-progression.webp"
            and split_squat["image_status"] == "pending_asset"
            and not (test_assets / "split-squat.webp").exists()
            and (intake / "login.jpg").exists()
            and (intake / "partial.png.crdownload").exists()
            and size == (800, 800)
            and "hamstring-curls-progression" not in gaps
            and "## other — Other" in gaps
        )
        print("self-test", "ok" if ok else "failed", size)
        return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="Ingest new Grok exercise drawings into assets/.")
    parser.add_argument("--intake", default=str(DEFAULT_INTAKE), help="Folder to watch. Defaults to raw_grok_outputs/.")
    parser.add_argument("--catalog", default=str(CATALOG_PATH))
    parser.add_argument("--gaps", default=str(GAPS_PATH))
    parser.add_argument("--priority", default=str(PRIORITY_PATH))
    parser.add_argument("--once", action="store_true", help="Process the current files and exit.")
    parser.add_argument("--no-git", action="store_true", help="Do not commit or push.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    intake = Path(args.intake)
    print(f"Watching {intake}")
    while True:
        process_batch(intake, args.catalog, args.gaps, args.priority, publish=not args.no_git)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
