"""Read staged protocol text and update exercises.json plus protocols.json."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "protocols"
CATALOG_PATH = ROOT / "exercises.json"
REGISTRY_PATH = ROOT / "protocols.json"

STOPWORDS = {"a", "an", "the", "and", "with", "of", "on", "at", "to", "for", "in", "or"}
DOSE_KEYS = {"sets", "reps", "rep", "hold", "frequency", "freq", "cues", "cue", "instructions", "precautions", "precaution"}
PHASE_RE = re.compile(r"^(?:#{1,6}\s*)?phase\s+(\d+)\s*[:.-]\s*(.+?)\s*$", re.I)
PHASE_WEEKS_RE = re.compile(r"^(?:#{1,6}\s*)?phase\s*:\s*(.+)$", re.I)
WEEKS_RE = re.compile(r"weeks?\s+\d+\s*[-–]\s*\d+", re.I)
TITLE_RE = re.compile(r"^(?:#\s+|(?:protocol(?:\s+name)?)\s*[:.-]\s+)(.+)$", re.I)
EXERCISE_RE = re.compile(r"^(?:#{2,6}\s+|\d+[.)]\s+|[-*]\s+)(.+?)\s*$")
PRECAUTION_RE = re.compile(r"^(?:#{0,6}\s*)?(?:precautions?|restrictions?)\s*[:.-]\s*(.+)$", re.I)
FIELD_RE = re.compile(r"^(?:[-*]\s*)?(sets?|reps?|hold|frequency|freq|cues?|instructions?)\s*[:.-]\s*(.+)$", re.I)
BULLET_DOSE_RE = re.compile(
    r"^[-*]\s*(?P<name>[^:]+):\s*(?P<sets>\d+)\s*sets?,\s*(?P<reps>\d+)\s*reps?,\s*(?P<hold>\d+)\s*s(?:ec(?:onds?)?)?\s*hold,\s*(?P<freq>[^.]+)\.(?:\s*(?P<cues>.*))?$",
    re.I,
)
INLINE_RE = re.compile(
    r"^(?P<name>.+?)\s*(?:—|–|\|)\s*(?P<sets>\d+)\s*sets?\s*[x×]\s*(?P<reps>\d+)\s*reps?(?P<rest>.*)$",
    re.I,
)
PHYSICIAN_PREFIX_RE = re.compile(
    r"^(?:(?:dr\.?\s+)?carson\b(?:\s*[-–:]\s*|\s+)|dr\.?\s+[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*)?\s*[-–:]\s*)",
    re.I,
)
PHASE_IN_TITLE_RE = re.compile(r"\s*\(phase\s+(\d+)\)\s*", re.I)

STRENGTH = {"sets": 2, "reps": 20, "hold_sec": 2, "frequency": "Daily (7x/wk)"}
STRETCH = {"sets": 2, "reps": 1, "hold_sec": 30, "frequency": "Daily (7x/wk)"}
PLACEHOLDERS = [
    "https://placehold.co/300x200/e2e8f0/1e293b?text=Start",
    "https://placehold.co/300x200/cbd5e1/1e293b?text=Finish",
]


def read_document(path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print(f"Skipping {path.name}: install pypdf to read PDF files.")
            return ""
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return ""


def slugify(value):
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "exercise"


def tokens(value):
    words = re.findall(r"[a-z0-9]+", value.lower())
    return {word for word in words if word not in STOPWORDS and len(word) > 1}


def strip_physician_prefix(title):
    text = (title or "").strip()
    previous = None
    while text and text != previous:
        previous = text
        text = PHYSICIAN_PREFIX_RE.sub("", text).strip()
    return re.sub(r"\s+", " ", text).strip(" -")


def weeks_label(text):
    match = WEEKS_RE.search(text or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(0)).strip().title()


def phase_number_in(title):
    match = PHASE_IN_TITLE_RE.search(title or "")
    return int(match.group(1)) if match else None


def base_title(title):
    text = strip_physician_prefix(title)
    text = PHASE_IN_TITLE_RE.sub(" ", text)
    text = re.sub(r"\s+phase\s+\d+\s*$", "", text, flags=re.I)
    head = re.split(r"\s+[-–]\s+", text, maxsplit=1)[0].strip()
    return re.sub(r"\s+", " ", head or text).strip(" -")


def protocol_key(title):
    if re.search(r"rotator\s+cuff", title, re.I):
        return "rc-repair"
    return slugify(base_title(title))[:48]


def region_for(title, phase_text):
    text = f"{title} {phase_text}".lower()
    if re.search(r"ankle|foot|achilles", text):
        return "Foot/Ankle"
    if re.search(r"knee|acl|tka|patella|meniscus", text):
        return "Knee"
    if re.search(r"lumbar|cervical|thoracic|spine|neck|back", text):
        return "Spine"
    if re.search(r"shoulder|rotator|cuff|scapula", text):
        return "Shoulder"
    return "General"


def category_for(region, name):
    text = f"{region} {name}".lower()
    if "foot/ankle" in region.lower() or re.search(r"ankle|heel|calf|gastroc|soleus", text):
        return "ankle"
    if region == "Knee" or re.search(r"\bknee\b|quad|patella", text):
        return "knee"
    if region == "Spine" or re.search(r"lumbar|cervical|thoracic|neck", text):
        if re.search(r"cervical|neck", text):
            return "cervical"
        if re.search(r"thoracic", text):
            return "thoracic"
        return "lumbar"
    if re.search(r"wrist|forearm|elbow", text):
        return "elbow_wrist"
    if re.search(r"hand|grip|fist", text):
        return "hand"
    if region == "Shoulder" or re.search(r"shoulder|scapula|rotator", text):
        return "shoulder"
    return "shoulder"


def parse_hold(value):
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def normalize_frequency(value):
    text = re.sub(r"\s+", " ", (value or "").strip())
    lowered = text.lower()
    if lowered in {"daily", "daily (7x/wk)", "7x/wk", "every day"}:
        return "Daily (7x/wk)"
    return text


def cue_list(value):
    parts = [part.strip(" -") for part in re.split(r"(?<=[.!?])\s+|;\s+", value or "") if part.strip(" -")]
    return parts[:3] or ["Move only through a comfortable range.", "Keep the motion slow.", "Stop if pain increases."]


def default_cues(name):
    return [
        f"Set up for {name} in a comfortable position",
        "Move slowly and stay within the range allowed for this phase",
        "Stop if pain increases and return to the start position",
    ]


def blank_exercise():
    return {"name": "", "sets": None, "reps": None, "hold_sec": None, "frequency": "", "cues": ""}


def flush_exercise(phase, current):
    if phase and current and current["name"]:
        phase["exercises"].append(current)


def open_phase(phases, number, label):
    phase = {
        "number": number,
        "label": label,
        "weeks": weeks_label(label),
        "precautions": "",
        "exercises": [],
    }
    phases.append(phase)
    return phase


def parse_document(text):
    title = ""
    phases = []
    phase = None
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().rstrip(":") == "exercises":
            continue
        if not title:
            titled = TITLE_RE.match(line)
            if titled and not PHASE_RE.match(line) and not PHASE_WEEKS_RE.match(line):
                title = strip_physician_prefix(titled.group(1).strip())
                continue
        phase_match = PHASE_RE.match(line)
        if phase_match:
            flush_exercise(phase, current)
            current = None
            phase = open_phase(phases, int(phase_match.group(1)), phase_match.group(2).strip())
            continue
        weeks_match = PHASE_WEEKS_RE.match(line)
        if weeks_match and re.match(r"^phase\s*:", line, re.I):
            flush_exercise(phase, current)
            current = None
            label = weeks_match.group(1).strip()
            number = phase_number_in(title) or (len(phases) + 1)
            phase = open_phase(phases, number, label)
            continue
        if phase is None:
            continue
        precaution = PRECAUTION_RE.match(line)
        if precaution:
            flush_exercise(phase, current)
            current = None
            extra = precaution.group(1).strip()
            phase["precautions"] = f"{phase['precautions']} {extra}".strip()
            continue
        bullet = BULLET_DOSE_RE.match(line)
        if bullet:
            flush_exercise(phase, current)
            current = blank_exercise()
            current.update({
                "name": bullet.group("name").strip(),
                "sets": int(bullet.group("sets")),
                "reps": int(bullet.group("reps")),
                "hold_sec": int(bullet.group("hold")),
                "frequency": normalize_frequency(bullet.group("freq")),
                "cues": (bullet.group("cues") or "").strip(),
            })
            flush_exercise(phase, current)
            current = None
            continue
        field = FIELD_RE.match(line)
        if field and current:
            key = field.group(1).lower()
            value = field.group(2).strip()
            if key.startswith("set"):
                number = re.search(r"\d+", value)
                current["sets"] = int(number.group(0)) if number else current["sets"]
            elif key.startswith("rep"):
                number = re.search(r"\d+", value)
                current["reps"] = int(number.group(0)) if number else current["reps"]
            elif key == "hold":
                current["hold_sec"] = parse_hold(value)
            elif key in {"frequency", "freq"}:
                current["frequency"] = normalize_frequency(value)
            else:
                current["cues"] = f"{current['cues']} {value}".strip()
            continue
        inline = INLINE_RE.match(line)
        if inline and tokens(inline.group("name")) and not any(word in tokens(inline.group("name")) for word in DOSE_KEYS):
            flush_exercise(phase, current)
            rest = inline.group("rest") or ""
            hold_match = re.search(r"hold\s+(\d+)", rest, re.I)
            frequency = ""
            freq_match = re.search(r"(daily(?:\s*\(7x/wk\))?|\d+\s*[-–]?\s*\d*\s*x\s*/?\s*day|\d+x/day)", rest, re.I)
            if freq_match:
                frequency = normalize_frequency(freq_match.group(1))
            current = blank_exercise()
            current.update({
                "name": inline.group("name").strip(" -"),
                "sets": int(inline.group("sets")),
                "reps": int(inline.group("reps")),
                "hold_sec": parse_hold(hold_match.group(0) if hold_match else ""),
                "frequency": frequency,
            })
            continue
        exercise = EXERCISE_RE.match(line)
        if exercise:
            name = exercise.group(1).strip()
            if tokens(name) & DOSE_KEYS or name.lower().startswith("precaution"):
                continue
            flush_exercise(phase, current)
            current = blank_exercise()
            current["name"] = name
    if phase:
        flush_exercise(phase, current)
    if not title:
        title = "Untitled Protocol"
    return {"title": strip_physician_prefix(title), "phases": [item for item in phases if item["exercises"]]}


def match_exercise(name, catalog):
    query = tokens(name)
    if len(query) < 2:
        return None
    best = None
    best_score = 0
    for exercise in catalog:
        candidate = tokens(exercise.get("name", ""))
        if not candidate:
            continue
        if query == candidate:
            return exercise
        overlap = query & candidate
        if len(overlap) < 2:
            continue
        score = len(overlap) / max(len(query), len(candidate))
        if query <= candidate or candidate <= query:
            score += 0.25
        if score > best_score:
            best_score = score
            best = exercise
    if best and best_score >= 0.7:
        return best
    return None


def dosing_for(parsed, name):
    stretch = bool(re.search(r"stretch", name, re.I))
    base = dict(STRETCH if stretch else STRENGTH)
    if parsed["sets"] is not None:
        base["sets"] = parsed["sets"]
    if parsed["reps"] is not None:
        base["reps"] = parsed["reps"]
    if parsed["hold_sec"] is not None:
        base["hold_sec"] = parsed["hold_sec"]
    if parsed["frequency"]:
        base["frequency"] = parsed["frequency"]
    return base


def unique_slug(name, catalog):
    base = slugify(name)
    taken = {exercise["id"] for exercise in catalog}
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def new_entry(parsed, region, exercise_id):
    name = parsed["name"]
    stretch = bool(re.search(r"stretch", name, re.I))
    cues = cue_list(parsed["cues"]) if parsed["cues"] else default_cues(name)
    return {
        "id": exercise_id,
        "name": name,
        "category": category_for(region, name),
        "type": "stretch" if stretch else "strength",
        "starter": True,
        "default_dosing": dosing_for(parsed, name),
        "cues": cues,
        "photos": list(PLACEHOLDERS),
        "video_url": "",
        "image_status": "pending_asset",
    }


def link_exercises(parsed_doc, catalog):
    region = region_for(parsed_doc["title"], " ".join(phase["label"] for phase in parsed_doc["phases"]))
    added = []
    for phase in parsed_doc["phases"]:
        ids = []
        doses = {}
        for exercise in phase["exercises"]:
            match = match_exercise(exercise["name"], catalog)
            if match:
                exercise_id = match["id"]
            else:
                entry = new_entry(exercise, region, unique_slug(exercise["name"], catalog))
                catalog.append(entry)
                exercise_id = entry["id"]
                added.append(entry)
            ids.append(exercise_id)
            doses[exercise_id] = dosing_for(exercise, exercise["name"])
        phase["exercise_ids"] = ids
        phase["exercise_doses"] = doses
    return added


def registry_entries(parsed_doc):
    key = protocol_key(parsed_doc["title"])
    short = base_title(parsed_doc["title"])
    entries = []
    for phase in parsed_doc["phases"]:
        weeks = phase["weeks"] or phase["label"]
        entries.append({
            "id": f"{key}-phase-{phase['number']}",
            "type": "standard",
            "protocol_title": f"{short} (Phase {phase['number']})",
            "phase": weeks,
            "region": region_for(parsed_doc["title"], phase["label"]),
            "exercise_ids": phase["exercise_ids"],
            "exercise_doses": phase.get("exercise_doses", {}),
            "precautions": strip_physician_prefix(phase["precautions"]),
        })
    return entries


def load_registry():
    if not REGISTRY_PATH.exists():
        return []
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return [data]
    return list(data)


def migrate_entry(entry):
    if entry.get("type") == "surgeon":
        return dict(entry)
    raw_id = str(entry.get("id", ""))
    if re.search(r"carson", raw_id, re.I):
        return None
    item = dict(entry)
    if not item.get("type"):
        item["type"] = "standard"
    for field in ("protocol_title", "precautions", "phase"):
        value = item.get(field)
        if isinstance(value, str):
            item[field] = strip_physician_prefix(value)
    return item


def staging_files():
    if not STAGING.exists():
        return []
    files = []
    for path in sorted(STAGING.iterdir()):
        if not path.is_file():
            continue
        if path.name == REGISTRY_PATH.name:
            continue
        if path.suffix.lower() in {".txt", ".md", ".pdf"}:
            files.append(path)
    return files


def resolve_inputs(argv):
    if not argv:
        return staging_files()
    paths = []
    for arg in argv:
        path = Path(arg)
        if not path.is_absolute():
            path = ROOT / path
        paths.append(path)
    return paths


def ingest(argv):
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    documents = []
    for path in resolve_inputs(argv):
        if not path.is_file():
            print(f"Skipping missing file {path}")
            continue
        text = read_document(path)
        if text.strip():
            documents.append(parse_document(text))
    added = []
    fresh = []
    for document in documents:
        added.extend(link_exercises(document, catalog))
        fresh.extend(registry_entries(document))
    fresh_ids = {entry["id"] for entry in fresh}
    registry = []
    for entry in load_registry():
        migrated = migrate_entry(entry)
        if migrated and migrated["id"] not in fresh_ids:
            registry.append(migrated)
    registry.extend(fresh)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("")
    print("Protocol ingestion summary")
    print(f"{'Item':<42} {'Count':>7}")
    print(f"{'-' * 42} {'-' * 7}")
    print(f"{'Documents read':<42} {len(documents):>7}")
    print(f"{'New exercises appended':<42} {len(added):>7}")
    print(f"{'Protocol phases written':<42} {len(fresh):>7}")
    print(f"{'Registry entries':<42} {len(registry):>7}")
    print(f"{'Total exercises in exercises.json':<42} {len(catalog):>7}")
    for entry in fresh:
        print(f"  {entry['id']}  {entry['protocol_title']}  [{', '.join(entry['exercise_ids'])}]")
    for entry in added:
        print(f"  new  {entry['id']}  {entry['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(ingest(sys.argv[1:]))
