"""Attach unused drawings to catalog cards and record exercises that still have no image."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CATALOG_PATH = ROOT / "exercises.json"
GAPS_PATH = ROOT / "docs" / "asset_gaps.md"

STRENGTH = {"sets": 2, "reps": 20, "hold_sec": 2, "frequency": "Daily (7x/wk)"}
STRETCH = {"sets": 2, "reps": 1, "hold_sec": 30, "frequency": "Daily (7x/wk)"}

# Keyword must appear in the unused filename. Longer phrases are checked first.
MISSING_KEYWORDS = {
    "lumbar-204": ["dead-bug", "deadbug"],
    "cerv-304": ["scapular-retraction", "scapular-depression", "scap-retraction"],
    "shld-402": ["external-rotation", "band-er", "towel-roll"],
    "shld-403": ["sleeper"],
    "shld-404": ["serratus", "wall-slide"],
    "shld-405": ["wand"],
    "elbow-101": ["wrist-extensor", "extensor-stretch"],
    "elbow-102": ["eccentric-wrist", "wrist-extension"],
    "elbow-103": ["pronation", "supination", "hammer"],
    "hand-101": ["tendon-glid", "tendon-glide"],
    "hand-102": ["web-space", "first-web"],
    "hand-103": ["putty"],
    "ankle-101": ["gastroc", "gastrocnemius", "calf"],
    "ankle-102": ["soleus"],
    "ankle-103": ["4-way-ankle", "four-way-ankle", "ankle-alphabet"],
    "ankle-104": ["heel-raise", "heel-raises"],
    "balance-101": ["single-leg-stance", "single-leg-stand"],
    "balance-102": ["tandem", "romberg"],
    "balance-103": ["airex", "weight-shift", "lateral-weight"],
}

# Older files that repeat a movement already linked to a newer drawing.
DUPLICATE_GROUPS = {
    "007-sidelying-hip-abduction",
    "010-supine-straight-leg-raises",
    "011-supine-quad-set",
    "012-supine-heel-slide",
    "014-clamshell",
    "025-seated-long-arc-quad",
    "037-standing-terminal-knee-extension-with-resistance",
    "041-side-plank-on-knees",
    "060-seated-upper-trapezius-stretch",
    "072-cervical-retraction",
    "088-supine-single-knee-to-chest-stretch",
    "089-prone-press-up",
    "091-supine-pelvic-tilt",
    "093-half-kneeling-hip-flexor-stretch",
    "099-seated-superior-patellar-glide",
    "117-supine-march",
}

NEW_EXERCISES = [
    ("001-supine-lower-trunk-rotation", "lumbar-supine-lower-trunk-rotation-01", "Supine Lower Trunk Rotation", "lumbar", "stretch", True, [
        "Lie on your back with the knees bent and the feet flat",
        "Slowly roll both knees to one side while the shoulders stay down",
        "Return to the middle and repeat to the other side",
    ]),
    ("017-prone-press-up-on-elbows", "lumbar-prone-press-up-on-elbows-01", "Prone Press-Up on Elbows", "lumbar", "stretch", True, [
        "Lie face down and prop on your elbows under the shoulders",
        "Let the low back sag gently while the hips stay on the table",
        "Hold the comfortable extension, then rest back down",
    ]),
    ("020-side-plank-on-elbow", "core-side-plank-on-elbow-01", "Side Plank on Elbow", "core", "strength", True, [
        "Lie on your side and prop on the elbow under the shoulder",
        "Lift the hips so the body makes a straight line",
        "Keep the neck long and do not let the hips roll forward",
    ]),
    ("021-standing-lumbar-extension", "lumbar-standing-lumbar-extension-01", "Standing Lumbar Extension", "lumbar", "stretch", True, [
        "Stand tall with the feet about hip width",
        "Place the hands on the hips and gently arch the low back",
        "Return upright without forcing the motion",
    ]),
    ("033-child-s-pose-stretch", "lumbar-childs-pose-stretch-01", "Child's Pose Stretch", "lumbar", "stretch", True, [
        "Kneel and sit the hips back toward the heels",
        "Reach the arms forward and let the chest sink toward the floor",
        "Breathe and keep the stretch comfortable through the back",
    ]),
    ("038-supine-piriformis-stretch-with-foot-on-ground", "hip-supine-piriformis-stretch-foot-on-ground-01", "Supine Piriformis Stretch with Foot on Ground", "hip", "stretch", True, [
        "Lie on your back and cross one ankle over the opposite thigh",
        "Keep the foot of the supporting leg on the ground",
        "Draw the thigh in until a stretch is felt deep in the buttock",
    ]),
    ("039-mountain-climbers-slow", "core-mountain-climbers-slow-01", "Mountain Climbers, Slow", "core", "strength", True, [
        "Start in a plank with the hands under the shoulders",
        "Step one knee toward the chest, then switch legs slowly",
        "Keep the hips level and do not bounce",
    ]),
    ("040-standing-diagonal-chops-with-medicine-ball", "core-standing-diagonal-chops-medicine-ball-01", "Standing Diagonal Chops with Medicine Ball", "core", "strength", False, [
        "Stand with a soft knee bend and hold the ball at one shoulder",
        "Chop the ball diagonally down across the body",
        "Control the return and keep the trunk from collapsing",
    ]),
    ("042-plank-on-knees", "core-plank-on-knees-01", "Plank on Knees", "core", "strength", True, [
        "Prop on the forearms with the knees on the floor",
        "Make a straight line from the head to the knees",
        "Brace the stomach and do not let the low back sag",
    ]),
    ("055-bent-knee-fallouts", "hip-bent-knee-fallouts-01", "Bent Knee Fallouts", "hip", "strength", True, [
        "Lie on your back with the knees bent and the feet together",
        "Let one knee fall out to the side while the pelvis stays still",
        "Bring the knee back to the middle with control",
    ]),
    ("062-supine-transversus-abdominis-bracing-hands-on-stomach", "core-supine-transversus-abdominis-bracing-01", "Supine Transversus Abdominis Bracing", "core", "strength", True, [
        "Lie on your back with the knees bent and the hands on the lower stomach",
        "Gently draw the belly in without holding your breath",
        "Keep the ribs down and the low back quiet",
    ]),
    ("069-sidelying-tfl-stretch", "hip-sidelying-tfl-stretch-01", "Sidelying TFL Stretch", "hip", "stretch", True, [
        "Lie on your side with the bottom leg straight",
        "Let the top leg drop behind you until the outer hip stretches",
        "Keep the pelvis stacked and do not twist the low back",
    ]),
    ("084-standing-egypt-nerve-glide", "elbow-standing-egypt-nerve-glide-01", "Standing Ulnar Nerve Glide", "elbow_wrist", "strength", True, [
        "Stand tall and make the 'OK' sign with the thumb and index finger",
        "Bring the hand toward the face, then turn it out like a mask",
        "Move only as far as a gentle nerve glide, not a strong stretch",
    ]),
    ("090-standard-plank", "core-standard-plank-01", "Standard Plank", "core", "strength", True, [
        "Prop on the forearms and toes with the body in one line",
        "Brace the stomach and squeeze the glutes",
        "Do not let the hips pike up or the low back sag",
    ]),
    ("092-seated-lumbar-extension", "lumbar-seated-lumbar-extension-01", "Seated Lumbar Extension", "lumbar", "stretch", True, [
        "Sit tall at the front of a chair with the feet supported",
        "Gently arch the low back and lift the chest",
        "Return upright without forcing the motion",
    ]),
    ("100-supine-isometric-hamstring-set", "knee-supine-isometric-hamstring-set-01", "Supine Isometric Hamstring Set", "knee", "strength", True, [
        "Lie on your back with the knee slightly bent",
        "Press the heel down as if you are trying to bend the knee",
        "Hold the hamstring contraction, then relax",
    ]),
    ("108-thomas-stretch-on-table", "hip-thomas-stretch-on-table-01", "Thomas Stretch on Table", "hip", "stretch", True, [
        "Sit at the edge of the table and roll back while hugging one knee",
        "Let the other thigh hang off the table",
        "Keep the low back flat and feel the stretch in the front of the hanging hip",
    ]),
    ("112-modified-side-plank-with-hip-abduction", "core-modified-side-plank-hip-abduction-01", "Modified Side Plank with Hip Abduction", "core", "strength", True, [
        "Set up in a side plank from the knees",
        "Lift the top leg a few inches without rolling the trunk",
        "Lower the leg with control and keep the hips lifted",
    ]),
    ("113-half-kneeling-diagonal-chops-with-medicine-ball", "core-half-kneeling-diagonal-chops-medicine-ball-01", "Half-Kneeling Diagonal Chops with Medicine Ball", "core", "strength", False, [
        "Half kneel with the front knee over the ankle",
        "Chop the ball from the high side down across the body",
        "Stay tall and do not let the front knee cave in",
    ]),
    ("114-bird-dog-on-foam-roll", "core-bird-dog-on-foam-roll-01", "Bird Dog on Foam Roll", "core", "strength", False, [
        "Rest the shins or hands on the roll as directed and find a tall spine",
        "Reach the opposite arm and leg until they are level with the trunk",
        "Move slowly and do not let the low back sag",
    ]),
    ("115-half-kneeling-diagonal-lift-with-resistance-opposite-forward-leg", "core-half-kneeling-diagonal-lift-01", "Half-Kneeling Diagonal Lift with Resistance", "core", "strength", False, [
        "Half kneel with the band starting low on the side of the back leg",
        "Lift the hands diagonally up across the body",
        "Keep the ribs stacked and the front knee over the foot",
    ]),
    ("119-swiss-ball-march", "core-swiss-ball-march-01", "Swiss Ball March", "core", "strength", False, [
        "Lie on your back with the heels on the ball and the hips lifted",
        "March one foot, then the other, without dropping the hips",
        "Keep the ribs down and the motion slow",
    ]),
    ("120-full-superman-on-table", "lumbar-full-superman-on-table-01", "Full Superman on Table", "lumbar", "strength", True, [
        "Lie face down with the arms reaching overhead",
        "Lift the arms, chest, and legs a few inches off the table",
        "Lower slowly and do not crank the neck back",
    ]),
    ("121-single-leg-bridge-with-leg-supported", "hip-single-leg-bridge-leg-supported-01", "Single-Leg Bridge with Leg Supported", "hip", "strength", True, [
        "Lie on your back with one foot on the floor and the other leg supported",
        "Lift the hips by pushing through the standing heel",
        "Keep the pelvis level and lower with control",
    ]),
    ("123-standing-sidebends", "lumbar-standing-sidebends-01", "Standing Sidebends", "lumbar", "stretch", True, [
        "Stand tall with the arms at the sides",
        "Slide one hand down the thigh as the trunk bends sideways",
        "Return to the middle and repeat to the other side",
    ]),
    ("143-prone-knee-extension-hang", "knee-prone-knee-extension-hang-01", "Prone Knee Extension Hang", "knee", "stretch", True, [
        "Lie face down with the knee just past the edge of the table",
        "Let the lower leg hang so the knee straightens with gravity",
        "Stay relaxed and do not force the knee down",
    ]),
    ("146-gentle-levator-scapulae-stretch", "cerv-gentle-levator-scapulae-stretch-01", "Gentle Levator Scapulae Stretch", "cervical", "stretch", True, [
        "Sit tall and look down toward the opposite armpit",
        "Use a light hand pressure only if it stays comfortable",
        "Keep the stretch in the back of the neck, not the shoulder joint",
    ]),
    ("147-seated-cervical-rotation-arom", "cerv-seated-cervical-rotation-arom-01", "Seated Cervical Rotation AROM", "cervical", "strength", True, [
        "Sit tall and look over one shoulder as far as is comfortable",
        "Return to the middle, then turn to the other side",
        "Move slowly and keep the shoulders relaxed",
    ]),
    ("148-seated-cervical-extension-arom", "cerv-seated-cervical-extension-arom-01", "Seated Cervical Extension AROM", "cervical", "strength", True, [
        "Sit tall and look up only as far as the neck stays comfortable",
        "Return to a neutral chin position",
        "Do not force the head backward",
    ]),
    ("149-seated-cervical-flexion-arom", "cerv-seated-cervical-flexion-arom-01", "Seated Cervical Flexion AROM", "cervical", "strength", True, [
        "Sit tall and nod the chin toward the chest",
        "Return to neutral without jutting the chin forward",
        "Keep the motion slow and pain free",
    ]),
    ("150-seated-cervical-sidebending-arom", "cerv-seated-cervical-sidebending-arom-01", "Seated Cervical Sidebending AROM", "cervical", "strength", True, [
        "Sit tall and tilt one ear toward the same shoulder",
        "Return to the middle, then tilt to the other side",
        "Keep the shoulders down and do not rotate the head",
    ]),
]


def group_key(stem):
    return re.sub(r"-(start|finish)$", "", stem)


def photo_pair(files):
    ordered = sorted(files, key=lambda path: (0 if path.stem.endswith("-start") else 1 if path.stem.endswith("-finish") else 2, path.name))
    rels = [f"assets/{path.name}" for path in ordered[:2]]
    if len(rels) == 1:
        return [rels[0], rels[0]]
    return rels


def asset_groups():
    groups = {}
    for path in ASSETS.glob("*.webp"):
        groups.setdefault(group_key(path.stem), []).append(path)
    return groups


def referenced_photos(catalog):
    return {photo for exercise in catalog for photo in exercise.get("photos") or []}


def unattached_groups(catalog, groups):
    used = referenced_photos(catalog)
    free = {}
    for key, files in groups.items():
        if not any(f"assets/{path.name}" in used for path in files):
            free[key] = files
    return free


def match_missing(catalog, free):
    resolved = []
    claimed = set()
    by_id = {exercise["id"]: exercise for exercise in catalog}
    for exercise_id, keywords in MISSING_KEYWORDS.items():
        exercise = by_id.get(exercise_id)
        if exercise is None:
            continue
        if exercise.get("photos") and not any("placehold.co" in photo for photo in exercise["photos"]):
            continue
        ranked = sorted(keywords, key=len, reverse=True)
        hit = None
        for key in sorted(free):
            if key in claimed:
                continue
            slug = re.sub(r"^\d+-", "", key)
            if any(word in slug for word in ranked):
                hit = key
                break
        if not hit:
            continue
        exercise["photos"] = photo_pair(free[hit])
        claimed.add(hit)
        resolved.append((exercise, hit))
    return resolved, claimed


def add_exercises(catalog, free, claimed):
    existing_ids = {exercise["id"] for exercise in catalog}
    added = []
    for group, exercise_id, name, category, movement, starter, cues in NEW_EXERCISES:
        if group not in free or group in claimed or group in DUPLICATE_GROUPS:
            continue
        if exercise_id in existing_ids:
            raise SystemExit(f"Duplicate id {exercise_id}")
        entry = {
            "id": exercise_id,
            "name": name,
            "category": category,
            "type": movement,
            "starter": starter,
            "default_dosing": dict(STRETCH if movement == "stretch" else STRENGTH),
            "cues": cues,
            "photos": photo_pair(free[group]),
            "video_url": "",
        }
        catalog.append(entry)
        existing_ids.add(exercise_id)
        claimed.add(group)
        added.append(entry)
    return added


def still_missing(catalog):
    gaps = []
    for exercise in catalog:
        photos = exercise.get("photos") or []
        if not photos or any("placehold.co" in photo for photo in photos):
            gaps.append(exercise)
    return gaps


def grok_prompt(exercise):
    name = exercise["name"]
    return (
        f"Clinical line illustration of {name} for a physical therapy home program. "
        "One adult figure, navy blue line art on a solid white #FFFFFF background, "
        "high contrast so it prints clearly in black and white. No text, no labels, "
        "no watermark, square 800 by 800 composition, simple anatomy, and a clear joint position. "
        f"Show the start position and the finish or hold position of {name} as two separate frames."
    )


def write_gaps(gaps):
    GAPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Exercises still missing a drawing",
        "",
        "These catalog cards have no clinic illustration. Each prompt matches the white-background line drawings already in `assets/`.",
        "",
    ]
    if not gaps:
        lines.append("No remaining gaps.")
    for exercise in gaps:
        lines.extend([
            f"## {exercise['id']} — {exercise['name']}",
            "",
            f"- Category: {exercise.get('category', '')}",
            f"- Type: {exercise.get('type', '')}",
            "",
            "Suggested Grok prompt:",
            "",
            "```",
            grok_prompt(exercise),
            "```",
            "",
        ])
    GAPS_PATH.write_text("\n".join(lines), encoding="utf-8")


def print_summary(resolved, added, catalog, gaps):
    print("")
    print("Catalog reconciliation summary")
    print(f"{'Item':<42} {'Count':>7}")
    print(f"{'-' * 42} {'-' * 7}")
    print(f"{'Missing cards resolved':<42} {len(resolved):>7}")
    print(f"{'New exercises added to the catalog':<42} {len(added):>7}")
    print(f"{'Total active exercises in exercises.json':<42} {len(catalog):>7}")
    print(f"{'Remaining true gaps in docs/asset_gaps.md':<42} {len(gaps):>7}")
    if resolved:
        print("")
        print("Resolved cards")
        for exercise, group in resolved:
            print(f"  {exercise['id']}  {exercise['name']}  <- {group}")
    if added:
        print("")
        print("Added exercises")
        for exercise in added:
            print(f"  {exercise['id']}  {exercise['name']}")
    if gaps:
        print("")
        print("Remaining gaps")
        for exercise in gaps:
            print(f"  {exercise['id']}  {exercise['name']}")


def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    groups = asset_groups()
    free = unattached_groups(catalog, groups)
    resolved, claimed = match_missing(catalog, free)
    added = add_exercises(catalog, free, claimed)
    gaps = still_missing(catalog)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_gaps(gaps)
    print_summary(resolved, added, catalog, gaps)


if __name__ == "__main__":
    main()
