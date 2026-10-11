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


def read_docx(path):
    import zipfile
    from xml.etree import ElementTree

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter(f"{ns}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{ns}t")).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def read_document(path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print(f"Skipping {path.name}: install pypdf to read PDF files.")
            return ""
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text(extraction_mode="layout") or page.extract_text() or "")
        return "\n\f\n".join(pages)
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
    if re.search(r"shoulder|rotator|cuff|scapula|labrum", text):
        return "Shoulder"
    if re.search(r"\bhip\b|groin", text):
        return "Hip"
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
    if re.search(r"balance|single[- ]leg stance|weight shift|tandem", text):
        return "balance"
    if re.search(r"plank|dead bug|bird dog|\bchop\b|abdominal", text):
        return "core"
    if re.search(r"wrist|forearm|elbow", text):
        return "elbow_wrist"
    if re.search(r"hand|grip|fist", text):
        return "hand"
    if region == "Hip" or re.search(r"\bhip\b|glute|clamshell", text):
        return "hip"
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


ALIAS_RULES = [
    (r"\bquad sets?\b", "knee-101"),
    (r"\bstraight leg raises?\b|\bslrs?\b", "knee-102"),
    (r"\bterminal knee extensions?\b|\btkes?\b", "knee-104"),
    (r"\bheel slides?\b", "knee-105"),
    (r"\blong arc quads?\b|\blaqs?\b", "knee-106"),
    (r"\bclamshells?\b", "hip-101"),
    (r"\bglute bridges?\b|(?<![\w-])bridges?\b", "hip-102"),
    (r"\bside[- ]lying (?:hip )?abduction\b", "hip-103"),
    (r"\bcalf raises?\b|\bheel raises?\b", "ankle-104"),
    (r"\bpendulums?\b", "standing-pendulum"),
    (r"\bchin tucks?\b", "cerv-301"),
    (r"\bsit to stands?\b", "knee-squat-01"),
    (r"\bstep ups?\b", "knee-forward-step-up-01"),
    (r"\bprone hangs?\b", "knee-prone-knee-extension-hang-01"),
    (r"\bhamstring stretches?\b", "knee-seated-hamstring-stretch-01"),
    (r"\bsingle[- ]leg stance\b|\bsls\b", "balance-101"),
    (r"\bside planks?\b", "core-102"),
    (r"(?<!side )planks?\b", "core-standard-plank-01"),
    (r"\bbird dogs?\b", "lumbar-203"),
    (r"\bdead bugs?\b", "lumbar-204"),
]


def stem_token(word):
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def stem_tokens(value):
    return {stem_token(word) for word in tokens(value)}


def alias_match(name, catalog):
    for pattern, exercise_id in ALIAS_RULES:
        if re.search(pattern, name, re.I):
            found = next((exercise for exercise in catalog if exercise.get("id") == exercise_id), None)
            if found:
                return found
    return None


def match_exercise(name, catalog):
    aliased = alias_match(name, catalog)
    if aliased:
        return aliased
    query = stem_tokens(name)
    if len(query) < 2:
        return None
    best = None
    best_score = 0
    for exercise in catalog:
        candidate = stem_tokens(exercise.get("name", ""))
        if not candidate:
            continue
        if query == candidate:
            return exercise
        overlap = query & candidate
        if len(overlap) < 2:
            continue
        score = len(overlap) / max(len(query), len(candidate))
        if query <= candidate or candidate <= query:
            if abs(len(query) - len(candidate)) <= 1:
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


def new_entry(parsed, region, exercise_id, starter=True):
    name = parsed["name"]
    stretch = bool(re.search(r"stretch", name, re.I))
    cues = cue_list(parsed["cues"]) if parsed["cues"] else default_cues(name)
    return {
        "id": exercise_id,
        "name": name,
        "category": category_for(region, name),
        "type": "stretch" if stretch else "strength",
        "starter": starter,
        "default_dosing": dosing_for(parsed, name),
        "cues": cues,
        "photos": list(PLACEHOLDERS),
        "video_url": "",
        "image_status": "pending_asset",
    }


def link_exercises(parsed_doc, catalog, starter=True):
    region = region_for(parsed_doc["title"], " ".join(phase["label"] for phase in parsed_doc["phases"]))
    added = []
    matched = 0
    for phase in parsed_doc["phases"]:
        ids = []
        doses = {}
        for exercise in phase["exercises"]:
            match = match_exercise(exercise["name"], catalog)
            if match:
                exercise_id = match["id"]
                matched += 1
            else:
                entry = new_entry(exercise, region, unique_slug(exercise["name"], catalog), starter=starter)
                catalog.append(entry)
                exercise_id = entry["id"]
                added.append(entry)
            if exercise_id in ids:
                continue
            ids.append(exercise_id)
            doses[exercise_id] = dosing_for(exercise, exercise["name"])
        phase["exercise_ids"] = ids
        phase["exercise_doses"] = doses
    parsed_doc["matched_count"] = matched
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


SKIP_FILES = {
    "how_to_navigate_your_protocol.pdf",
    "rotator-cuff-repair-small-medium.md",
    "rotator_cuff_phase_2.txt",
    "rotator_cuff_phase_3.txt",
}
HEADER_RE = re.compile(
    r"^\s*(?P<title>(?!(?:to|continue)\b).+?)\s+(?:Prot(?:o)?col\s+)?Phase\s+(?P<number>\d+)\s*$",
    re.I,
)
WEEKS_LABEL_RE = re.compile(r"\d+\s*[-–]\s*\d+\s*(?:weeks|months)", re.I)
PROGRAM_DOSE_RE = re.compile(
    r"(\d+)(?:\s*[-–]\s*\d+)?\s*sets?\s+of\s+(\d+)(?:\s*[-–]\s*\d+)?\s*reps",
    re.I,
)
ITEM_RE = re.compile(r"^(?:[a-z]|[ivx]{1,4})[.)]\s*(.+)$", re.I)
SKIP_ITEM_RE = re.compile(
    r"mobiliz|\bmanual technique\b|\bmobs\b|\biastm\b|\bcupping\b|\bscar\b|tissue work|\bmodalit|\boverpressure\b|glide of|oscillation",
    re.I,
)
GAP_PROMPT = (
    "Clinical line illustration of {name} for a physical therapy home program. "
    "One adult figure, navy blue line art on a solid white #FFFFFF background, high contrast so it prints clearly in black and white. "
    "No text, no labels, no watermark, square 800 by 800 composition, simple anatomy, and a clear joint position. "
    "Show the start position and the finish or hold position of {name} as two separate frames."
)


def display_name(value):
    text = re.sub(r"\s+", " ", value).strip(" .:-")
    text = re.sub(r"\b(er)\b", "External Rotation", text, flags=re.I)
    text = re.sub(r"\b(ir)\b", "Internal Rotation", text, flags=re.I)
    text = re.sub(r"\bslr\b", "Straight Leg Raise", text, flags=re.I)
    text = re.sub(r"\btkes?\b", "Terminal Knee Extension", text, flags=re.I)
    text = re.sub(r"\bsaq\b", "Short Arc Quad", text, flags=re.I)
    text = re.sub(r"\blaq\b", "Long Arc Quad", text, flags=re.I)
    text = re.sub(r"\bsls\b", "Single Leg Stance", text, flags=re.I)
    text = re.sub(r"\brdl\b", "Romanian Deadlift", text, flags=re.I)
    text = re.sub(r"\bhs\b", "Hamstring", text, flags=re.I)
    text = re.sub(r"\bdf\b", "Dorsiflexion", text, flags=re.I)
    words = []
    for word in text.split():
        if word.isupper() and len(word) <= 4:
            words.append(word)
        elif re.match(r"^[A-Z0-9][A-Za-z0-9/+'-]*$", word):
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def tidy_piece(value):
    text = value.replace("½", "1/2")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(optional|with nmes|nmes|using hips only)\b", " ", text, flags=re.I)
    text = re.sub(r"\d+\s*sec(?:ond)?s?\s*hold", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .:-")
    return text


def hold_from_text(value):
    match = re.search(r"(\d+)\s*sec", value or "", re.I)
    return int(match.group(1)) if match else None


def split_gap(line):
    stripped = line.rstrip()
    gaps = [match for match in re.finditer(r"\s{3,}", stripped) if match.start() > 0]
    if not gaps:
        if len(line) - len(line.lstrip(" ")) >= 28:
            return "", stripped.strip()
        return stripped.strip(), ""
    gap = gaps[-1]
    return stripped[:gap.start()].strip(), stripped[gap.end():].strip()


def column_segments(block):
    segments = []
    for raw in block.splitlines():
        if not raw.strip():
            continue
        left, right = split_gap(raw)
        for part in (left, right):
            if not part:
                continue
            pieces = re.split(r"\s+(?=(?:[a-z]|[ivx]{1,4}|\d+)[.)]\s*)", part, flags=re.I)
            segments.extend(piece.strip() for piece in pieces if piece.strip())
    return segments


def join_wrapped(lines):
    joined = []
    for raw in lines:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or line.lower() in {"precautions", "criteria to pass", "purpose", "typical time frame"}:
            continue
        if joined and (line[0].islower() or line[0] in ")]"):
            joined[-1] = f"{joined[-1]} {line}"
        else:
            joined.append(line)
    return joined


def exercise_pieces(body):
    body = re.sub(r"\s+", " ", body).strip()
    if re.match(r"continue\b", body, re.I):
        return []
    prefix, separator, rest = body.partition(":")
    if separator and SKIP_ITEM_RE.search(prefix):
        return []
    source = rest.strip() if separator and len(prefix.strip()) <= 42 else body
    source = tidy_piece(source)
    if SKIP_ITEM_RE.search(source) and not separator:
        return []
    pieces = []
    for chunk in re.split(r"\s*(?:>|,|;|&)\s*", source):
        name = chunk.strip(" .:-")
        if not name or re.match(r"^(reset|into|full|and|or|per discretion)$", name, re.I):
            continue
        if re.search(r"mobiliz|\bmanual\b|\bmobs\b|\biastm\b|\bcupping\b|\bscar\b|\bglide\b|oscillation", name, re.I):
            continue
        if name.count("(") != name.count(")"):
            continue
        if re.match(r"^(so|do|and|or|per|with|than|avoid|monitor|into|reset)\b", name, re.I):
            continue
        if len(stem_tokens(name)) < 2 and not alias_match(name, [{"id": rule[1], "name": name} for rule in ALIAS_RULES]):
            continue
        pieces.append(name)
    return pieces


def exercises_from_block(block, dose):
    found = []
    seen = set()
    for segment in column_segments(block):
        item = ITEM_RE.match(segment)
        body = item.group(1) if item else ""
        if not body or re.match(r"^\d+[.)]", segment):
            continue
        for name in exercise_pieces(body):
            if len(name.split()) > 8:
                continue
            key = stem_tokens(name)
            if not key or frozenset(key) in seen:
                continue
            seen.add(frozenset(key))
            hold = hold_from_text(body)
            found.append({
                "name": display_name(name),
                "sets": dose["sets"],
                "reps": dose["reps"],
                "hold_sec": hold if hold is not None else dose["hold_sec"],
                "frequency": dose["frequency"],
                "cues": "",
            })
    return found


def sentence_join(lines):
    parts = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if parts and parts[-1][-1] not in ".!?":
            parts[-1] += "."
        parts.append(text)
    return " ".join(parts)


def programming_dose(considerations):
    match = PROGRAM_DOSE_RE.search(considerations or "")
    if not match:
        return {"sets": 2, "reps": 10, "hold_sec": 2, "frequency": "Daily (7x/wk)"}, ""
    note = re.sub(r"\s+", " ", match.group(0)).strip()
    return {"sets": int(match.group(1)), "reps": int(match.group(2)), "hold_sec": 2, "frequency": "Daily (7x/wk)"}, note


def parse_criteria_page(page):
    header = None
    for line in page.splitlines():
        match = HEADER_RE.match(line.rstrip())
        if match:
            header = match
            break
    if not header:
        return None
    title = re.sub(r"\s+", " ", header.group("title")).strip()
    title = re.sub(r"\s+prot(?:o)?col$", "", title, flags=re.I).strip()
    criteria_at = re.search(r"criteria to pass", page, re.I)
    priority_at = re.search(r"priority list\s*&\s*suggested exercises", page, re.I)
    special_at = re.search(r"special considerations", page, re.I)
    if not criteria_at or not priority_at:
        return None
    meta_block = page[:criteria_at.start()]
    left_lines = []
    right_lines = []
    for line in meta_block.splitlines():
        if not line.strip() or HEADER_RE.match(line.rstrip()):
            continue
        left, right = split_gap(line)
        if left and left.lower() not in {"purpose", "precautions"}:
            left_lines.append(left)
        if right and right.lower() not in {"purpose", "precautions"}:
            right_lines.append(right)
    purpose = ""
    weeks = ""
    for line in join_wrapped(left_lines):
        if re.search(r"\bphase\s+\d+\s*$", line, re.I):
            continue
        weeks_match = WEEKS_LABEL_RE.search(line)
        if weeks_match and len(line) <= 24:
            weeks = re.sub(r"\s+", " ", weeks_match.group(0)).strip()
            weeks = weeks[:1].upper() + weeks[1:]
        elif line.lower() not in {"purpose", "typical time frame"} and len(line) <= 36:
            if not re.match(r"^(avoid|no\b|nwb|wbat|ttwb|pwb|monitor)\b", line, re.I):
                purpose = purpose or line
    criteria_left = []
    criteria_right = []
    for line in page[criteria_at.end():priority_at.start()].splitlines():
        left, right = split_gap(line)
        if left:
            criteria_left.append(left)
        if right:
            criteria_right.append(right)
    criteria = sentence_join(join_wrapped(criteria_left + criteria_right))
    exercise_block = page[priority_at.end():special_at.start()] if special_at else page[priority_at.end():]
    considerations = page[special_at.end():] if special_at else ""
    considerations = re.split(r"subscribe to our exercise library|©", considerations, flags=re.I)[0]
    dose, dose_note = programming_dose(considerations)
    precautions = sentence_join(join_wrapped(right_lines))
    if dose_note:
        precautions = f"{precautions} Dosing: {dose_note}.".strip()
    return {
        "title": title,
        "number": int(header.group("number")),
        "purpose": purpose,
        "weeks": weeks,
        "label": " ".join(part for part in (purpose, weeks) if part),
        "precautions": precautions,
        "criteria": criteria,
        "exercises": exercises_from_block(exercise_block, dose),
    }


def source_from_text(text):
    named = re.search(r"\bDr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", text)
    if named and not re.search(r"surgeon", named.group(0), re.I):
        return named.group(0).replace("Dr ", "Dr. ")
    if re.search(r"performance doc", text, re.I):
        return "The Performance Doc"
    copyright_match = re.search(r"©\s*\d{4}\s+(.+)$", text, re.M)
    if copyright_match:
        return re.sub(r"\s+", " ", copyright_match.group(1)).strip()
    return ""


def parse_criteria_document(text):
    pages = []
    for page in re.split(r"\f", text):
        parsed = parse_criteria_page(page)
        if parsed and parsed["exercises"]:
            pages.append(parsed)
    if not pages:
        return None
    title = pages[0]["title"]
    phases = []
    for page in pages:
        phases.append({
            "number": page["number"],
            "label": page["label"],
            "weeks": page["weeks"],
            "purpose": page["purpose"],
            "precautions": page["precautions"],
            "criteria": page["criteria"],
            "exercises": page["exercises"],
        })
    return {
        "title": title,
        "source": source_from_text(text),
        "criteria_based": True,
        "phases": phases,
    }


def criteria_entries(parsed_doc):
    key = slugify(base_title(parsed_doc["title"]))[:48]
    entries = []
    for phase in parsed_doc["phases"]:
        purpose = phase.get("purpose") or ""
        title = f"{parsed_doc['title']} (Phase {phase['number']}"
        title += f": {purpose})" if purpose else ")"
        entries.append({
            "id": f"{key}-phase-{phase['number']}",
            "type": "surgeon",
            "source": parsed_doc.get("source") or "",
            "protocol_title": title,
            "phase": phase.get("weeks") or phase.get("label") or "",
            "region": region_for(parsed_doc["title"], phase.get("label", "")),
            "exercise_ids": phase.get("exercise_ids", []),
            "exercise_doses": phase.get("exercise_doses", {}),
            "criteria": phase.get("criteria", ""),
            "precautions": phase.get("precautions", ""),
        })
    return entries


def append_asset_gaps(entries):
    path = ROOT / "docs" / "asset_gaps.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Exercises still missing a drawing\n"
    additions = []
    for entry in entries:
        if f"## {entry['id']} " in existing:
            continue
        additions.append(
            "\n".join([
                f"## {entry['id']} — {entry['name']}",
                "",
                f"- Category: {entry['category']}",
                f"- Type: {entry['type']}",
                "",
                "Suggested Grok prompt:",
                "",
                "```",
                GAP_PROMPT.format(name=entry["name"]),
                "```",
                "",
            ])
        )
    if not additions:
        return 0
    if not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing.rstrip() + "\n\n" + "\n".join(additions), encoding="utf-8")
    return len(additions)


def staging_files():
    if not STAGING.exists():
        return []
    files = []
    for path in sorted(STAGING.iterdir()):
        if not path.is_file():
            continue
        if path.name.lower() in SKIP_FILES or path.name.startswith("_"):
            continue
        if path.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
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
        if not text.strip():
            continue
        if "Criteria to Pass" in text:
            parsed = parse_criteria_document(text)
            if parsed:
                documents.append(parsed)
            else:
                print(f"No phases parsed from {path.name}")
        else:
            documents.append(parse_document(text))
    added = []
    fresh = []
    matched = 0
    for document in documents:
        starter = not document.get("criteria_based")
        added.extend(link_exercises(document, catalog, starter=starter))
        matched += document.get("matched_count", 0)
        if document.get("criteria_based"):
            fresh.extend(criteria_entries(document))
        else:
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
    gap_count = append_asset_gaps(added)
    print("")
    print("Protocol ingestion summary")
    print(f"{'Protocol':<52} {'Phases':>7}")
    print(f"{'-' * 52} {'-' * 7}")
    by_title = {}
    for entry in fresh:
        title = re.sub(r"\s*\(Phase\s+\d+.*$", "", entry["protocol_title"])
        by_title[title] = by_title.get(title, 0) + 1
    for title, count in by_title.items():
        print(f"{title[:52]:<52} {count:>7}")
    print(f"{'-' * 52} {'-' * 7}")
    print(f"{'Ingested protocols':<52} {len(by_title):>7}")
    print(f"{'Total phases':<52} {len(fresh):>7}")
    print(f"{'Exercises matched to existing assets':<52} {matched:>7}")
    print(f"{'New exercises pending in docs/asset_gaps.md':<52} {gap_count:>7}")
    print(f"{'Registry entries':<52} {len(registry):>7}")
    print(f"{'Total exercises in exercises.json':<52} {len(catalog):>7}")
    for entry in fresh:
        print(f"  {entry['id']}  {entry['protocol_title']}  [{', '.join(entry['exercise_ids'])}]")
    for entry in added:
        print(f"  new  {entry['id']}  {entry['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(ingest(sys.argv[1:]))
