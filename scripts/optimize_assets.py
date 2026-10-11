"""Convert raw clinic drawings to print-safe WebP files and point the catalog at them."""

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw_grok_outputs"
OUTPUT_DIR = ROOT / "assets"
CATALOG_PATH = ROOT / "exercises.json"
CANVAS_SIZE = 800
WEBP_QUALITY = 85
SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def ensure_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow is not installed. Installing it now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])


ensure_pillow()
from PIL import Image  # noqa: E402


def kebab_stem(value):
    text = Path(value).stem.lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def name_slug(name):
    return kebab_stem(name.replace("°", " "))


def group_key(stem):
    return re.sub(r"-(start|finish)$", "", stem)


def group_slug(key):
    return re.sub(r"^\d+-", "", key)


def leading_number(key):
    match = re.match(r"^(\d+)-", key)
    return int(match.group(1)) if match else -1


def extract_archives():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for archive in sorted(RAW_DIR.rglob("*.zip")):
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                if info.is_dir():
                    continue
                suffix = Path(info.filename).suffix.lower()
                if suffix not in SOURCE_SUFFIXES:
                    continue
                destination = RAW_DIR / Path(info.filename)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and destination.stat().st_size == info.file_size:
                    continue
                destination.write_bytes(bundle.read(info))
                print(f"Extracted {destination.relative_to(RAW_DIR).as_posix()}")


def source_images():
    extract_archives()
    files = [
        path for path in RAW_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    ]
    files.sort(key=lambda path: ("corrected" in path.as_posix().lower(), path.as_posix().lower()))
    chosen = {}
    for path in files:
        chosen[kebab_stem(path.name)] = path
    return [chosen[key] for key in sorted(chosen)]


def render_square(source):
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
        flattened = Image.new("RGB", image.size, (255, 255, 255))
        flattened.paste(image, mask=image.getchannel("A"))
        canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255))
        offset = ((CANVAS_SIZE - flattened.width) // 2, (CANVAS_SIZE - flattened.height) // 2)
        canvas.paste(flattened, offset)
        return canvas


def process_images():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    processed = []
    for source in source_images():
        destination = OUTPUT_DIR / f"{kebab_stem(source.name)}.webp"
        try:
            canvas = render_square(source)
            canvas.save(destination, "WEBP", quality=WEBP_QUALITY, method=6)
        except Exception as error:
            print(f"Skipped {source.name}: {error}")
            continue
        processed.append(destination)
        print(f"Wrote {destination.relative_to(ROOT).as_posix()}")
    return processed


def image_groups(processed):
    groups = {}
    for path in processed:
        key = group_key(path.stem)
        groups.setdefault(key, []).append(path)
    for files in groups.values():
        files.sort(key=lambda path: (0 if path.stem.endswith("-start") else 1 if path.stem.endswith("-finish") else 2, path.name))
    return groups


def photo_list(files):
    rels = [f"assets/{path.name}" for path in files]
    if len(rels) == 1:
        return [rels[0], rels[0]]
    return rels[:2]


def existing_group_key(exercise):
    for photo in exercise.get("photos") or []:
        name = Path(str(photo)).name
        if name.lower().startswith("http"):
            continue
        return group_key(kebab_stem(name))
    return ""


def choose_group(exercise, groups):
    wanted = name_slug(exercise.get("name") or "")
    named = [key for key in groups if group_slug(key) == wanted]
    if named:
        return max(named, key=leading_number)
    current = existing_group_key(exercise)
    if current in groups:
        return current
    return ""


def reconcile_catalog(processed):
    groups = image_groups(processed)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    matched = []
    missing = []
    used = set()
    for exercise in catalog:
        key = choose_group(exercise, groups)
        if not key:
            missing.append(exercise)
            continue
        exercise["photos"] = photo_list(groups[key])
        used.add(key)
        matched.append((exercise, exercise["photos"]))
    referenced = {photo for exercise in catalog for photo in exercise.get("photos") or []}
    orphans = [
        path for path in processed
        if f"assets/{path.name}" not in referenced
    ]
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return catalog, matched, missing, orphans, len(groups)


def print_report(processed, catalog, matched, missing, orphans, group_count):
    print("")
    print("Asset optimization report")
    print(f"Total images processed: {len(processed)}")
    print(f"Image groups: {group_count}")
    print(f"Catalog entries: {len(catalog)}")
    print(f"Total catalog entries matched: {len(matched)}")
    for exercise, photos in matched:
        print(f"  {exercise['id']}  {exercise['name']}")
        for photo in photos:
            print(f"    {photo}")
    print(f"Missing exercises still needing assets: {len(missing)}")
    for exercise in missing:
        print(f"  {exercise['id']}  {exercise['name']}")
    print(f"Orphaned images: {len(orphans)}")
    for path in orphans:
        print(f"  assets/{path.name}")


def main():
    processed = process_images()
    catalog, matched, missing, orphans, group_count = reconcile_catalog(processed)
    print_report(processed, catalog, matched, missing, orphans, group_count)


if __name__ == "__main__":
    main()
