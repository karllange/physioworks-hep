"""Map pending protocol placeholders onto catalog cards that already have drawings."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "exercises.json"
REGISTRY_PATH = ROOT / "protocols.json"
GAPS_PATH = ROOT / "docs" / "asset_gaps.md"
ASSETS = ROOT / "assets"

EQUIPMENT = {
    "wand", "cane", "stick", "dowel", "pvc", "pipe", "band", "tubing", "theraband",
    "elastic", "loop", "trx", "dumbbell", "db", "kettlebell", "kb", "cable",
    "weighted", "loaded", "assisted", "green", "yellow", "red", "blue", "black",
}
CONSTRAINT_RE = re.compile(
    r"(\d+\s*(?:deg(?:rees)?|°)?\s*(?:-|–|to)\s*\d+\s*(?:deg(?:rees)?|°)?"
    r"|[<>]\s*\d+\s*(?:deg(?:rees)?|°)?"
    r"|\d+\s*(?:deg(?:rees)?|°)"
    r"|with\s+\d+\s*(?:lb|lbs|pounds?)"
    r"|with\s+(?:a\s+)?(?:green|yellow|red|blue|black)\s+band)",
    re.I,
)

# Longer, more specific patterns first. These are the same movement, not a nearby one.
EXPLICIT = [
    (r"\b(?:quad sets?|isometric quadriceps(?: contraction)?)\b", "knee-101"),
    (r"\bslr\b.*\babduction\b|\babduction\b.*\bslr\b|\bside lying (?:hip )?abduction\b|\bsidelying abduction\b", "hip-103"),
    (r"\bslr\b.*\badduction\b|\badduction\b.*\bslr\b|\bside lying hip adduction\b|\bsidelying hip adduction\b", "hip-sidelying-hip-adduction-01"),
    (r"\bslr\b.*\bextension\b|\bextension\b.*\bslr\b|\bprone hip extension\b", "hip-prone-hip-extension-01"),
    (r"\b(?:straight leg raises?|slrs?)\b", "knee-102"),
    (r"\b(?:terminal knee extensions?|tkes?)\b", "knee-104"),
    (r"\bheel slides?\b", "knee-105"),
    (r"\b(?:extension prop|heel prop|foot on ottoman|prone hangs?|passive extension|low load long duration(?: knee extension)?)\b", "knee-prone-knee-extension-hang-01"),
    (r"\bsuperior patellar\b|\bpatellar (?:mobilization|glides?)\b.*\bsuperior\b", "knee-103"),
    (r"\binferior patellar\b|\bpatellar (?:mobilization|glides?)\b.*\binferior\b", "knee-seated-inferior-patellar-glide-01"),
    (r"\bclamshells?\b.*\b(?:band|resistance|loop)\b|\b(?:band|resistance|loop)\b.*\bclamshells?\b", "hip-clamshell-with-resistance-01"),
    (r"\bclamshells?\b", "hip-101"),
    (r"\b(?:glute bridges?|hip thrusters?|hip thrusts?|supine bridges?)\b", "hip-102"),
    (r"\bdead ?bugs?\b", "lumbar-204"),
    (r"\bbird ?dogs?\b", "lumbar-203"),
    (r"\b(?:posterior )?pelvic tilts?\b", "lumbar-205"),
    (r"\bside plank\b.*\belbow\b|\belbow\b.*\bside plank\b", "core-side-plank-on-elbow-01"),
    (r"\bside planks?\b", "core-102"),
    (r"\bplanks?\b", "core-standard-plank-01"),
    (r"\b(?:chin tucks?|cervical retraction)\b", "cerv-301"),
    (r"\bupper trapezius stretch\b", "cerv-302"),
    (r"\blevator scapulae stretch\b", "cerv-303"),
    (r"\bscap(?:ular)? (?:retraction|depression|setting)\b|\bscap retraction\b", "cerv-304"),
    (r"\b(?:wand|cane|stick|dowel|pvc(?: pipe)?)\b", "shld-405"),
    (r"\bweighted flexion in supine\b", "shld-405"),
    (r"\bscapular plane external rotation\b|\bside lying external rotation\b|\bexternal rotation at 0\b|\bneutral er\b", "shld-402"),
    (r"\bsleeper stretch\b", "shld-403"),
    (r"\bserratus\b.*\bwall slide\b|\bwall slide\b.*\bserratus\b", "shld-404"),
    (r"\bhorizontal abduction\b", "shld-401"),
    (r"\bgastroc(?:nemius)?\b", "ankle-101"),
    (r"\bsoleus\b", "ankle-102"),
    (r"\b(?:4|four) way ankle\b", "ankle-103"),
    (r"\b(?:heel raises?|calf raises?|deficit calf|ankle pf|resisted isotonic pf)\b", "ankle-104"),
    (r"\b(?:single leg stance|stork stance|sls)\b", "balance-101"),
    (r"\btandem (?:stance|romberg)\b", "balance-102"),
    (r"^weight shifting$", "balance-103"),
    (r"\bta setting\b|\btransversus abdominis bracing\b|\btransverse abdominis drawing in\b", "core-supine-transversus-abdominis-bracing-01"),
    (r"\bbent knee fall ?outs?\b", "hip-bent-knee-fallouts-01"),
    (r"\b(?:hip )?adductor squeeze\b", "hip-supine-hip-adduction-isometric-with-ball-01"),
    (r"\bstep ups?\b", "knee-forward-step-up-01"),
    (r"\bmini squats?\b", "knee-mini-squat-with-counter-support-01"),
    (r"\b(?:air squat|goblet squat|trx squat|trx assisted squats|(?<!sl )(?<!lateral )(?<!split )squat progression|(?<!lateral )squat variations)\b", "knee-squat-01"),
    (r"\b(?:long arc quads?|laqs?|leg extensions?)\b", "knee-106"),
    (r"\b(?:half kneeling hip flexor|couch stretch|hip flexor stretch)\b", "hip-104"),
    (r"\blateral lunges?\b", "knee-lateral-lunge-with-slider-01"),
    (r"\b(?:reverse lunges?|lunge progression|lunge matrix)\b", "knee-lunge-matrix-01"),
    (r"\b(?:reverse slider lunge|lunge on slider|slider lunge)\b", "knee-lunge-on-slider-01"),
    (r"\bprone press up on elbows\b|\bprone on elbows\b", "lumbar-prone-press-up-on-elbows-01"),
    (r"\bprone press ups?\b", "lumbar-201"),
    (r"\bstanding lumbar extension\b", "lumbar-standing-lumbar-extension-01"),
    (r"\bsingle knee to chest\b", "lumbar-hooklying-single-knee-to-chest-stretch-01"),
    (r"\bdouble knee to chest\b", "lumbar-202"),
    (r"\bfigure 4\b|\bpiriformis stretch\b", "hip-105"),
    (r"\blateral band walks?\b|\blbw skaters\b", "hip-side-stepping-with-resistance-at-ankles-01"),
    (r"\bside stepping\b", "hip-side-stepping-with-resistance-at-ankles-01"),
    (r"\bopen book\b", "thor-101"),
    (r"\bthoracic extension\b", "thor-102"),
    (r"\bthread the needle\b", "thor-103"),
    (r"\bhamstring stretch\b", "knee-seated-hamstring-stretch-01"),
    (r"\bisometric hamstring set\b|\bhamstring sets?\b", "knee-supine-isometric-hamstring-set-01"),
    (r"\bputty\b", "hand-103"),
    (r"\btendon glid", "hand-101"),
    (r"\bfirst web space\b", "hand-102"),
    (r"\bwrist extensor stretch\b", "elbow-101"),
    (r"\beccentric wrist extension\b", "elbow-102"),
    (r"\bpronation and supination\b", "elbow-103"),
    (r"\bchilds pose\b|\bchild s pose\b", "lumbar-childs-pose-stretch-01"),
    (r"\bsuperman\b", "lumbar-full-superman-on-table-01"),
    (r"\bmountain climbers?\b", "core-mountain-climbers-slow-01"),
    (r"\blower trunk rotation\b", "lumbar-supine-lower-trunk-rotation-01"),
    (r"\bmodified thomas\b", "hip-modified-thomas-stretch-01"),
    (r"\bthomas stretch\b", "hip-thomas-stretch-on-table-01"),
    (r"\bgluteal sets?\b", "hip-supine-gluteal-sets-01"),
    (r"\bseated lumbar extension\b", "lumbar-seated-lumbar-extension-01"),
    (r"\bstanding sidebends?\b", "lumbar-standing-sidebends-01"),
]


def normalize(value):
    text = str(value or "").lower().replace("°", " deg ")
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = text.replace("½", " half ")
    text = re.sub(r"\b1\s*/\s*2\b", " half ", text)
    text = re.sub(r"side[- ]?lying", "side lying", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def constraint_note(value):
    found = CONSTRAINT_RE.findall(str(value or ""))
    notes = []
    for piece in found:
        cleaned = re.sub(r"\s+", " ", piece).strip()
        if cleaned and cleaned not in notes:
            notes.append(cleaned)
    return "; ".join(notes)


def tokens(value):
    return [word for word in normalize(value).split() if word]


def content_tokens(value):
    return [word for word in tokens(value) if word not in EQUIPMENT]


def has_drawing(entry):
    if entry.get("image_status") != "pending_asset":
        return True
    for photo in entry.get("photos") or []:
        path = ROOT / str(photo)
        if path.suffix.lower() == ".webp" and path.is_file():
            return True
    return False


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def explicit_match(name, canonical_ids):
    text = normalize(name)
    for pattern, exercise_id in EXPLICIT:
        if exercise_id in canonical_ids and re.search(pattern, text):
            return exercise_id
    return ""


def exact_match(name, canonical):
    query = content_tokens(name)
    if len(query) < 2:
        return ""
    for entry in canonical:
        candidate = content_tokens(entry["name"])
        if query == candidate:
            return entry["id"]
    return ""


def choose_target(placeholder, canonical, canonical_ids):
    explicit = explicit_match(placeholder["name"], canonical_ids)
    if explicit:
        return explicit
    return exact_match(placeholder["name"], canonical)


def add_alias(entry, alias):
    aliases = entry.setdefault("aliases", [])
    if alias and alias not in aliases and alias != entry.get("name"):
        aliases.append(alias)


def merge_dose(doses, old_id, new_id, note):
    if not isinstance(doses, dict):
        return
    incoming = dict(doses.pop(old_id, {}) or {})
    if note:
        prior = incoming.get("instruction", "")
        incoming["instruction"] = f"{prior}; {note}".strip("; ") if prior else note
    current = doses.get(new_id)
    if not current:
        if incoming:
            doses[new_id] = incoming
        return
    if note and note not in str(current.get("instruction", "")):
        prior = current.get("instruction", "")
        current["instruction"] = f"{prior}; {note}".strip("; ") if prior else note


def remap_id_list(ids, old_id, new_id):
    remapped = []
    changed = 0
    for exercise_id in ids:
        if exercise_id == old_id:
            changed += 1
            exercise_id = new_id
        if exercise_id not in remapped:
            remapped.append(exercise_id)
    return remapped, changed


def remap_protocols(protocols, mapping, notes):
    slots = 0
    for entry in protocols:
        ids = entry.get("exercise_ids")
        if isinstance(ids, list):
            updated = []
            for exercise_id in ids:
                target = mapping.get(exercise_id, exercise_id)
                if target != exercise_id:
                    slots += 1
                    merge_dose(entry.get("exercise_doses"), exercise_id, target, notes.get(exercise_id, ""))
                if target not in updated:
                    updated.append(target)
            entry["exercise_ids"] = updated
        for saved in entry.get("saved_exercises") or []:
            if isinstance(saved, dict) and saved.get("id") in mapping:
                saved["id"] = mapping[saved["id"]]
                slots += 1
    return slots


def remove_gap_sections(text, removed_ids):
    if not removed_ids:
        return text, 0
    pattern = re.compile(r"^## (.+?) —", re.M)
    matches = list(pattern.finditer(text))
    if not matches:
        return text, 0
    kept = []
    removed = 0
    prefix_end = matches[0].start()
    kept.append(text[:prefix_end])
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_id = match.group(1).strip()
        if section_id in removed_ids:
            removed += 1
            continue
        kept.append(text[match.start():end])
    body = "".join(kept).rstrip() + "\n"
    return body, removed


def remaining_gap_count(text):
    return len(re.findall(r"^## .+", text, re.M))


def active_drawing_slots(protocols, canonical_ids):
    total = 0
    for entry in protocols:
        total += sum(1 for exercise_id in entry.get("exercise_ids") or [] if exercise_id in canonical_ids)
    return total


def unresolved_ids(protocols, catalog_ids):
    missing = []
    for entry in protocols:
        for exercise_id in entry.get("exercise_ids") or []:
            if exercise_id not in catalog_ids:
                missing.append((entry.get("id", ""), exercise_id))
    return missing


def reconcile():
    catalog = load_json(CATALOG_PATH)
    protocols = load_json(REGISTRY_PATH)
    gaps = GAPS_PATH.read_text(encoding="utf-8") if GAPS_PATH.exists() else ""

    canonical = [entry for entry in catalog if has_drawing(entry)]
    placeholders = [entry for entry in catalog if not has_drawing(entry)]
    canonical_ids = {entry["id"] for entry in canonical}
    by_id = {entry["id"]: entry for entry in canonical}

    mapping = {}
    notes = {}
    pairs = []
    for placeholder in placeholders:
        target = choose_target(placeholder, canonical, canonical_ids)
        if not target or target == placeholder["id"]:
            continue
        mapping[placeholder["id"]] = target
        notes[placeholder["id"]] = constraint_note(placeholder["name"])
        pairs.append((placeholder, by_id[target]))

    for placeholder, target in pairs:
        add_alias(target, placeholder["name"])

    slots = remap_protocols(protocols, mapping, notes)
    removed_ids = set(mapping)
    catalog = [entry for entry in catalog if entry["id"] not in removed_ids]
    gaps, gaps_removed = remove_gap_sections(gaps, removed_ids)

    dump_json(CATALOG_PATH, catalog)
    dump_json(REGISTRY_PATH, protocols)
    if GAPS_PATH.exists():
        GAPS_PATH.write_text(gaps, encoding="utf-8")

    catalog_ids = {entry["id"] for entry in catalog}
    canonical_now = {entry["id"] for entry in catalog if has_drawing(entry)}
    missing = unresolved_ids(protocols, catalog_ids)
    print("")
    print("Exercise alias reconciliation")
    print(f"{'Placeholder':<44} {'Canonical':<28}")
    print(f"{'-' * 44} {'-' * 28}")
    for placeholder, target in pairs:
        print(f"{placeholder['name'][:44]:<44} {target['id']:<28}")
    print(f"{'-' * 44} {'-' * 28}")
    print(f"{'Placeholder exercises consolidated':<52} {len(pairs):>7}")
    print(f"{'Total active exercises remaining':<52} {len(catalog):>7}")
    print(f"{'Protocol slots that now have active drawings':<52} {active_drawing_slots(protocols, canonical_now):>7}")
    print(f"{'Protocol slots remapped in this run':<52} {slots:>7}")
    print(f"{'Net remaining gaps in docs/asset_gaps.md':<52} {remaining_gap_count(gaps):>7}")
    print(f"{'Gap sections removed':<52} {gaps_removed:>7}")
    still_pending = [entry for entry in catalog if not has_drawing(entry)]
    print(f"{'Unresolved protocol exercise ids':<52} {len(missing):>7}")
    print(f"{'Exercises that still lack images':<52} {len(still_pending):>7}")
    for protocol_id, exercise_id in missing[:20]:
        print(f"  missing {protocol_id} -> {exercise_id}")
    print("")
    print("Still lacking an image")
    for entry in still_pending:
        print(f"  {entry['id']} — {entry['name']}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(reconcile())
