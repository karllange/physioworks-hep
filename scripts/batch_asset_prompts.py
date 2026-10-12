"""Rank unillustrated exercises and write 20-item Grok prompt batches."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "exercises.json"
REGISTRY_PATH = ROOT / "protocols.json"
OUT_DIR = ROOT / "docs" / "asset_batches"
BATCH_SIZE = 20

STYLE = (
    "PT line illustration, clean navy blue vector linework (#1A365D) on a pure solid "
    "white background (#FFFFFF). Minimal anatomical shading, clear motion arrows if "
    "depicting movement, no background scenery, no gym equipment clutter unless specified, "
    "no text labels, square 1:1 aspect ratio, high contrast optimized for black-and-white "
    "laser printing."
)

# First match wins. High-frequency names that would otherwise land in the wrong family
# are pinned here.
PINNED = {
    "lsd-progression": "closed",
    "loaded-lsd": "closed",
    "shuttle-press-variations": "isolation",
    "dl-extension": "isolation",
    "sl-extension": "isolation",
    "sl-machine": "isolation",
    "sl-holds": "isolation",
    "shuttle-press": "isolation",
    "sl-shuttle-press": "isolation",
    "sidelying-shuttle-press": "isolation",
    "double-leg-shuttle-press": "isolation",
    "eccentric-shuttle-press": "isolation",
    "wall-slides": "isolation",
    "wall-sits": "closed",
    "wall-sit-progression": "closed",
    "double-leg-wall-sit-progression-on": "closed",
    "nu-step": "gait",
    "nu-step-and-bike": "gait",
    "bike-no-recumbent-bike": "gait",
    "hamstring-and-slantboard": "isolation",
    "standing-hamstring-curl": "isolation",
    "hamstring-curls": "isolation",
    "hamstring-curls-progression": "isolation",
    "hamstring-ball-curls": "isolation",
    "prone-hamstring-curls": "isolation",
    "hurdle-progression": "plyo",
    "cable-decels": "plyo",
    "ladder-decels": "plyo",
    "split-squat-progression": "closed",
    "kb-swings": "closed",
    "rotational-deadlifts": "closed",
    "db-rdls": "closed",
    "hip-hike-holds": "gait",
    "hip-hike-reps": "gait",
    "hip-hikes": "gait",
    "anti-rotation-and-balance-training": "spine",
    "pallof-press": "spine",
    "cable-column-rotation": "spine",
    "cervical-prom-stretching": "spine",
    "quadruped-rock-backs": "spine",
    "cat-camel": "spine",
    "modified-curl-up-mcgill": "spine",
    "seated-lumbar-flexion": "spine",
    "rolling-patterns": "spine",
    "behind-the-back-stretch-rope": "shoulder",
    "cross-symmetry-walk-outs": "shoulder",
    "1-2-kneeling-halos": "shoulder",
    "tall-kneeling-halos": "shoulder",
    "kb-pass-through": "shoulder",
    "ball-squeezes": "shoulder",
    "elevated-ice": "program",
    "add-weight": "program",
    "increase-distance": "program",
    "add-more-load-to-functional-movements": "program",
    "4-exercises-performed-in-succession": "program",
    "compound-exercise-at": "program",
    "incorporate-more-compound-movements": "program",
    "focus-on-problem-areas": "program",
    "gross-movements": "program",
    "intro-to-functional-movements": "program",
    "tissue-work-to": "program",
    "light-isotonics": "program",
    "more-aggressive-prom": "program",
    "aggressive-prom-stretching-to-achieve": "shoulder",
    "abduction-beginning-at-2-weeks": "shoulder",
    "arm-hangs-outside-of-the-sling": "shoulder",
    "cross-train-rather-than-just-running": "program",
    "out-of-boot": "gait",
    "initiate-wb-with-crutches-in-the-boot": "gait",
    "progress-to-sled": "closed",
    "double-leg": "closed",
    "flexion-on-step": "isolation",
    "active-knee": "isolation",
    "exxentric-squat": "closed",
    "exxentric-machine": "shoulder",
}

RULES = [
    ("plyo", r"hop|jump|plyo|agility|shuffle|cutting|pro-agility|snap-down|sprint|jog|hurdle|medicine-ball-drop|depth-jump|star-drill|reactive|mini-hop|decel"),
    ("foot", r"ankle|toe-|heel-walk|toe-walk|baps|short-foot|tib-bar|towel-scrunch|foot-intrinsic|great-toe|inv-isometric|dorsiflex|weighted-toe|toe/|heel walk|toe walk|toe curl|toe lift|toe raise|toe spread"),
    ("closed", r"squat|split|bulgarian|step-down|step down|lunge|rdl|deadlift|romanian|wall-sit|wall sit|kickstand|cossack|slant|lsd|sled|farmer|carry|suitcase"),
    ("isolation", r"hamstring|nordic|leg-press|shuttle|machine-extension|short-arc|leg-curl|knee-flexion|knee-bend|quad|physioball-knee|kicking-into|hip-extension|4-way-hip|copenhagen|hyperextension|knee-circle|tibial-rotation|saq|standing-knee|hip-flexion|wall-slide|leg press"),
    ("shoulder", r"pendulum|scaption|rotator|external-rotation|internal-rotation|row|pulldown|pull-down|push-up|pushup|ckc|y-t|sleeper|band-resisted|trx|d2|pnf|rhythmic|scapular|shoulder|ube|doorway|biceps|triceps|chest-press|bench|lat-|press|flexion-progression|unweighted-flex|isometric|abduction|sling"),
    ("gait", r"gait|walk|treadmill|crutch|weight-shift|feet-together|marching|tandem|balance|get-up|boot|bike|nu-step"),
    ("spine", r"lumbar|cat-camel|curl-up|pallof|quadruped-rock|cervical|anti-rotation"),
    ("elbow", r"elbow|wrist|pronat|supinat"),
    ("hip", r"hip|kneeling|halo|runner|stretch|prone-lying|circumduction|stool|90-90|90/90"),
]

THEMES = [
    (
        "closed",
        "lower_chain",
        "High-Frequency Closed-Chain Lower Extremity",
        "Squats, split squats, step-downs, lunges, and Romanian deadlifts.",
    ),
    (
        "isolation",
        "isolation",
        "Knee and Hip Isolation / Open-Chain",
        "Leg-press and shuttle variants, hamstring curls, and extension holds.",
    ),
    (
        "foot",
        "foot_ankle",
        "Foot, Ankle and Calf Progression",
        "Intrinsic foot work, heel and toe walks, and loaded dorsiflexion.",
    ),
    (
        "plyo",
        "return_to_sport",
        "Return-to-Sport, Plyometrics and Agility",
        "Hops, cuts, ladder drills, and change-of-direction work.",
    ),
    (
        "shoulder",
        "shoulder",
        "Shoulder and Upper Extremity Mechanics",
        "Rotation, rows, pull-downs, and closed-chain shoulder work.",
    ),
    (
        "gait",
        "gait_balance",
        "Gait, Balance and Weight Shift",
        "Walking progressions, carries, and stance drills.",
    ),
    (
        "spine",
        "spine_core",
        "Spine and Core Control",
        "Lumbar mobility, bracing, and anti-rotation.",
    ),
    (
        "elbow",
        "elbow_wrist",
        "Elbow, Wrist and Hand",
        "Elbow and wrist range that is still missing a drawing.",
    ),
    (
        "hip",
        "hip_mobility",
        "Hip Mobility",
        "Hip range and kneeling patterns that are not a squat or a curl.",
    ),
    (
        "program",
        "programming_notes",
        "Programming Notes",
        "Phase instructions that were stored as exercise cards. Draw the concrete action, not a text slide.",
    ),
]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value):
    text = str(value or "").lower().replace("°", " deg ")
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9\s/-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def phase_counts(protocols):
    counts = Counter()
    for protocol in protocols:
        seen = set()
        for exercise_id in protocol.get("exercise_ids") or []:
            if exercise_id in seen:
                continue
            seen.add(exercise_id)
            counts[exercise_id] += 1
    return counts


def classify(entry):
    exercise_id = entry["id"]
    if exercise_id in PINNED:
        return PINNED[exercise_id]
    haystack = normalize(f"{exercise_id} {entry.get('name', '')}")
    category = entry.get("category") or ""
    for theme, pattern in RULES:
        if theme == "shoulder" and category in {"hip", "knee", "ankle", "lumbar", "core"}:
            continue
        if re.search(pattern, haystack):
            return theme
    category = entry.get("category") or ""
    if category in {"shoulder", "cervical"}:
        return "shoulder"
    if category in {"ankle"}:
        return "foot"
    if category in {"elbow_wrist", "hand"}:
        return "elbow"
    if category in {"lumbar", "thoracic", "core"}:
        return "spine"
    if category == "hip":
        return "hip"
    if category in {"knee", "balance"}:
        return "gait"
    return "program"


CUE_PATTERNS = [
    (r"lateral squat", "Stand with the feet wider than the hips and both knees soft.", "Shift the hips toward one side, bending that knee while the other leg stays long, then return to center.", "none"),
    (r"split squat|bulgarian", "Stand in a staggered stance, front heel down and back knee slightly bent.", "Lower straight down until the back knee nears the floor, then press through the front heel to stand.", "a low bench only if the back foot is elevated"),
    (r"single-leg squat|sl squat|kickstand", "Stand on one leg with the other toe lightly touching behind for balance.", "Sit the hips back and down on the stance leg, knee tracking over the toes, then stand tall.", "none"),
    (r"squat|wall sit", "Stand with the feet about shoulder width and the arms reaching forward.", "Sit the hips down and back as if toward a chair, keeping the heels down, then drive up to stand.", "none"),
    (r"cossack", "Stand in a wide stance with the toes turned slightly out.", "Shift onto one bent leg while the other leg stays straight, then return to the tall stance.", "a suspension strap only if the title names TRX"),
    (r"step-down|step down|slantboard step|lsd", "Stand on a low step with one heel hanging off the edge and the other foot free.", "Lower the free heel toward the floor by bending the stance knee, then press back up without the pelvis dropping.", "one aerobic step"),
    (r"romanian|deadlift|\brdls?\b|hip hinge|kb swing|kettlebell swing", "Stand tall holding a light weight in front of the thighs, knees soft.", "Hinge the hips back with a flat spine until the weight reaches about knee height, then stand by driving the hips forward.", "one kettlebell or dumbbell"),
    (r"sled", "Stand facing a low sled with the arms straight and the hips hinged slightly.", "Drive the sled forward with short steps, then show the return or pull path with the hips still hinged.", "a low sled"),
    (r"farmer|suitcase|carry", "Stand tall with a weight in one or both hands, shoulders level.", "Walk forward three steps without leaning, then pause in the tall stance.", "one dumbbell"),
    (r"nordic", "Kneel tall with the ankles held, hips extended, and the body in one line.", "Lower the trunk forward from the knees as far as the hamstrings allow, then pull back to tall kneeling.", "a pad under the knees"),
    (r"slantboard", "Stand on a slanted board with the knees soft and the hips tall.", "Hinge forward from the hips until the hamstrings stretch, then return to tall.", "a slant board"),
    (r"hamstring|leg curl", "Lie prone or stand with the knee straight and the hip quiet.", "Bend the knee, bringing the heel toward the buttock, then lower with control.", "a physioball or light cuff only if the title names one"),
    (r"leg press|shuttle", "Sit or lie with both feet on a platform and the knees bent about 90 degrees.", "Press the platform away until the knees are nearly straight without locking, then return.", "a leg-press or shuttle carriage"),
    (r"machine extension|short arc|\bquad\b|\b(dl|sl) extension\b|\bsl machine\b|\bsl holds\b", "Sit tall with the knee bent and the thigh supported.", "Straighten the knee, or hold it straight, then lower with control. One frame shows both legs and the other shows one leg when the title says SL.", "a seated knee-extension machine"),
    (r"wall slide", "Lie on the back with the foot resting on a wall and the knee bent.", "Slide the heel up the wall to straighten the knee, then slide back down.", "none"),
    (r"knee bend|knee flexion|physioball knee", "Sit at the edge of a table with the thigh supported and the knee bent a little.", "Bend the knee further, drawing the heel back under the table, then return.", "a physioball only if the title names one"),
    (r"prone quad stretch", "Lie prone with both knees straight.", "Bend one knee and draw the heel toward the buttock until the front of the thigh stretches, then lower.", "none"),
    (r"hip extension|quadruped hip", "Start on hands and knees, or prone, with the knee bent about 90 degrees.", "Lift the thigh back until the hip opens without arching the low back, then lower.", "a bench only if the title names one"),
    (r"hip flexion|knee to chest", "Stand or sit tall with the hip starting near neutral.", "Lift the thigh toward the chest, keeping the trunk still, then lower.", "none"),
    (r"copenhagen|adduction|abd/add|abduction and adduction", "Lie on the side with the top leg supported and the lower leg free.", "Lift the lower leg toward the top leg, then lower with control.", "a bench"),
    (r"4 way hip|four way hip", "Stand tall holding a stable surface, the moving leg starting under the hip.", "Move the leg forward, then show a second frame out to the side, keeping the pelvis level.", "a cable or band"),
    (r"hip hike", "Stand on a step on one leg, the other foot hanging free and the pelvis level.", "Lift the free side of the pelvis toward the ribs, then lower it just below level.", "one step"),
    (r"heel raise|toe walk|heel walk|calf", "Stand tall with the knees straight and the weight over the midfoot.", "Rise onto the forefoot, or walk on the heels or toes, keeping the hips level.", "none"),
    (r"dorsiflex|ankle circle|ankle pump", "Sit with the knee straight enough to see the ankle and the foot relaxed.", "Pull the toes toward the shin, or circle the ankle, then return to the resting foot.", "none"),
    (r"baps|wobble", "Sit or stand with the foot centered on a round balance board.", "Tip the board forward and back under the foot, keeping the knee quiet.", "a BAPS board"),
    (r"short foot|towel scrunch|toe curl|toe spread|toe lift|great toe|intrinsic|inv isometric", "Sit with the foot flat and the toes long.", "Draw the ball of the foot toward the heel, or curl and spread the toes, without gripping the whole leg.", "a towel only for the scrunch"),
    (r"tib bar|toe raise", "Stand or sit with the heels down and the toes free.", "Lift the toes and forefoot toward the shins, then lower.", "a light tib bar only if the title names one"),
    (r"hop|jump|plyo|snap down", "Stand tall on both feet with the knees soft and the arms ready.", "Dip a little, then leave the floor and land softly with the knees bent over the toes.", "a low box only if the title names a box or depth jump"),
    (r"hurdle", "Stand beside a low hurdle with the stance knee soft.", "Hop or step laterally over the hurdle and stick the landing on the far foot.", "one low hurdle"),
    (r"ladder|shuffle|cutting|agility|cone|pro agility", "Start in an athletic stance beside a cone or ladder square.", "Change direction or step through the pattern and finish in a balanced athletic stance.", "cones or one agility ladder"),
    (r"star drill|balance reach", "Stand on one leg with the hands on the hips.", "Reach the free leg or hand toward one direction, then return to the single-leg stance.", "none"),
    (r"jog|sprint", "Show a side view mid-stride with the trunk tall.", "Show the next stride with the opposite arm and leg forward, foot landing under the hip.", "none"),
    (r"external rotation|internal rotation|\ber\b", "Sit or stand with the elbow bent 90 degrees and tucked at the side.", "Rotate the forearm out or in while the elbow stays against the ribs.", "a light band"),
    (r"pendulum", "Hinge at the hips and let one arm hang.", "Swing the arm gently forward and back like a pendulum, then show the return.", "none"),
    (r"scaption|full can|flexion", "Stand tall with the arm at the side, thumb up.", "Raise the arm in the scapular plane to about shoulder height, then lower.", "none"),
    (r"row|pull-down|pulldown|face pull", "Sit or hinge with the arm reaching forward.", "Pull the elbow back toward the hip, squeezing the shoulder blade, then return the arm long.", "a band or cable"),
    (r"push-up|pushup|ckc", "Hold a high plank with the hands under the shoulders.", "Bend the elbows to lower the chest a short way, then press back to the plank. Add a small plus at the top if the title says plus.", "none"),
    (r"press", "Stand or sit tall with the elbows bent and the hands near the shoulders.", "Press the hands overhead until the elbows are nearly straight, then lower.", "light dumbbells"),
    (r"y/?t|i y|wall tap", "Stand facing a wall with the arms long.", "Slide or lift the arms into a Y, then show a T, keeping the ribs down.", "none"),
    (r"isometric|doorway|rhythmic", "Stand in a doorway or against a wall with the elbow bent.", "Gently press the arm into the wall without the body moving, then relax.", "a doorway"),
    (r"halo|pass through", "Stand tall holding a light weight at the chest.", "Circle the weight slowly around the head, finishing with it back at the chest.", "one light kettlebell"),
    (r"gait|walk|treadmill|crutch|boot", "Stand tall at the start of a step, heel ready to strike.", "Finish mid-stride with the opposite heel down and the trunk upright.", "crutches or a boot only if the title names them"),
    (r"weight shift|feet together|tandem|march", "Stand with the feet in the stance named by the title.", "Shift the weight or take a march step and finish balanced without the trunk leaning.", "a foam pad only if the title names foam"),
    (r"cat-camel|cat camel", "Start on hands and knees with the spine long.", "Round the back toward the ceiling, then show the reverse arch with the gaze slightly lifted.", "none"),
    (r"curl-up|mcgill", "Lie on the back with one knee bent and the hands under the low back.", "Lift the head and shoulders a short way off the floor, then lower.", "none"),
    (r"lumbar flexion|rock back", "Start on hands and knees or sitting tall.", "Rock the hips toward the heels or bend forward from the hips, then return upright.", "none"),
    (r"pallof|anti-rotation|cable column", "Stand sideways to a band held at the chest with the elbows bent.", "Press the hands straight out and resist the twist, then bring them back to the chest.", "a band"),
    (r"wrist|elbow|pronat|supinat", "Sit with the forearm supported and the wrist or elbow in the start position.", "Move through the named range, then return to the supported start.", "none"),
    (r"hip 90|90/90|runner|world|kneeling hip|couch", "Kneel or sit in the setup the title names, with the pelvis neutral.", "Shift forward or rotate into the stretch and hold the end range.", "none"),
    (r"ice|elevat", "Lie on the back with the leg supported above the heart.", "Rest with the limb elevated. No ice-bag label.", "a pillow or wedge"),
    (r"knee circle", "Sit with the thigh supported and the knee slightly bent.", "Draw a small slow circle with the heel, then reverse the circle.", "none"),
    (r"tibial rotation", "Sit with the knee bent and the foot on a slider or the floor.", "Rotate the shin inward, then outward, keeping the thigh still.", "a slider only if the title names one"),
    (r"hyperextension", "Lie prone with the arms at the sides.", "Lift the chest and thighs slightly off the table, then lower.", "none"),
    (r"active knee", "Sit with the foot on the floor and the knee bent.", "Straighten the knee as far as comfortable, then bend it back.", "none"),
    (r"medicine ball|weighted ball", "Stand tall holding a light ball at the chest.", "Drop, catch, or tap the ball at shoulder height and finish in a tall stance.", "one light ball"),
    (r"rotator cuff|band resisted ext|\bd2\b|pnf", "Stand with the elbow bent or the arm at the side.", "Move the arm through the named rotation or diagonal, then return.", "a light band"),
    (r"ball squeeze", "Hold a small ball in the hand at the side.", "Squeeze the ball, then relax the hand.", "a small ball"),
    (r"arm hang|sling", "Stand tall with the arm resting out to the side of the body.", "Let the arm hang relaxed, slightly away from the sling position.", "none"),
    (r"shoulder tap", "Hold a plank with the hands under the shoulders.", "Tap the opposite shoulder with one hand, then return the hand to the floor.", "none"),
    (r"trx y|\by t\b|end range", "Stand or hinge with the arms long toward the floor.", "Lift the arms into a Y, then show a T, keeping the ribs down.", "a suspension strap only if the title names TRX"),
    (r"ube|arm bike", "Sit tall at an arm crank with both hands on the handles.", "Turn the crank forward through a half circle, then show the hands at the opposite point.", "an arm bike"),
    (r"shoulder circle", "Stand tall with the arms at the sides.", "Circle the shoulders backward, then show the arms back at the sides.", "none"),
    (r"unweighted flex|standing flex", "Stand tall with the arm at the side.", "Raise the arm forward to shoulder height, then lower it.", "none"),
    (r"nu-step|bike", "Sit tall on a bike or seated stepper with the feet on the pedals.", "Show one pedal down and the other up, trunk still.", "a bike or seated stepper"),
    (r"get up|floor", "Start half-kneeling after rising from the floor.", "Finish standing tall with the feet under the hips.", "none"),
    (r"cable decel", "Stand facing a cable held in one hand at shoulder height.", "Slow the arm as it moves across the body, then stop in a tall athletic stance.", "a cable handle"),
    (r"ankle weight", "Sit with a small cuff around the ankle and the foot relaxed.", "Lift the forefoot toward the shin, then lower.", "one ankle cuff"),
    (r"cervical|neck", "Sit tall with the head stacked over the shoulders.", "Gently tilt or turn the head, then return to center.", "none"),
    (r"rolling", "Lie on the back with the knees bent.", "Roll onto the side, leading with the knees and shoulder together.", "none"),
    (r"hooklying|abd/add|abd add", "Lie on the back with the knees bent and the feet flat.", "Press the knees apart, then draw them together.", "none"),
    (r"prone lying", "Lie face down with the arms resting beside the body.", "Stay relaxed with the forehead supported and the legs long.", "none"),
    (r"rotation", "Sit or stand tall with the moving limb in neutral.", "Rotate the limb through the named direction, then return to neutral.", "a stool only if the title names one"),
    (r"double leg", "Stand on both feet with the hips back slightly.", "Sit into a small two-leg squat, then return to standing.", "none"),
    (r"succession|compound|functional movement|gross movement|problem area|isotonics|tissue|cross train|increase distance|aggressive prom", "Stand in a tall ready posture.", "Move one large joint through a slow pain-free arc and finish back at the start. This card is a phase note, so keep the figure simple.", "none"),
    (r"aarom|physioball", "Lie on the back with the heel resting on a physioball.", "Roll the ball away to straighten the hip and knee, then roll it back.", "a physioball"),
    (r"hip circle", "Stand tall holding a stable surface.", "Circle the free hip slowly, then return the foot under the hip.", "none"),
    (r"abduction", "Stand tall with the arm at the side.", "Lift the arm out to the side a short way, thumb up, then lower.", "none"),
    (r"behind the back|rope", "Stand tall holding a strap behind the back, one hand low and one hand high.", "Gently walk the hands toward each other, then relax.", "a strap"),
    (r"bench", "Lie on a bench with the elbows bent and the hands above the chest.", "Press the hands toward the ceiling, then lower the elbows with control.", "a bench and light weights"),
    (r"exxentric|flywheel", "Stand tall holding the handles of a flywheel machine.", "Pull or squat against the wheel, then return to the start under control.", "a flywheel machine"),
    (r"add weight|more load|loaded", "Stand in the exercise setup holding no weight.", "Show the same posture with one light dumbbell added.", "one dumbbell"),
]


def cues_for(entry):
    text = normalize(f"{entry['id']} {entry.get('name', '')}")
    text = re.sub(r"[-/]", " ", text)
    text = re.sub(r"\s+", " ", text)
    for pattern, start, finish, equipment in CUE_PATTERNS:
        if re.search(pattern.replace("-", " "), text):
            return start, finish, equipment
    title = entry.get("name") or entry["id"]
    return (
        f"Set up for {title} with the joints stacked and the moving limb at the beginning of the range.",
        f"Move through {title} and hold the end position. A single motion arrow shows the direction of travel.",
        "none",
    )


def prompt_for(entry, phases):
    start, finish, equipment = cues_for(entry)
    lines = [
        STYLE,
        "",
        f"Movement: {entry['name']}.",
        f"Start: {start}",
        f"Finish: {finish}",
    ]
    if equipment and equipment != "none":
        lines.append(f"Equipment: include only {equipment}.")
    else:
        lines.append("Equipment: body weight only. No extra gym equipment.")
    lines.append("Two frames may share the square if both positions stay readable. No words in the image.")
    return "\n".join(lines), start, finish


def chunk(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)] or []


def assign_files(groups):
    files = []
    overflow = []
    primary = {theme for theme, *_rest in THEMES[:5]}
    for theme, slug, title, blurb in THEMES:
        items = groups.get(theme, [])
        parts = chunk(items, BATCH_SIZE)
        if not parts:
            continue
        if theme in primary:
            files.append((slug, title, blurb, parts[0], False))
            overflow.extend((slug, title, blurb, part) for part in parts[1:])
        else:
            overflow.extend((slug, title, blurb, part) for part in parts)
    numbered = []
    for index, (slug, title, blurb, part, _continued) in enumerate(files, start=1):
        numbered.append((f"batch_{index:02d}_{slug}.md", title, blurb, part))
    next_index = len(numbered) + 1
    for slug, title, blurb, part in overflow:
        numbered.append((f"batch_{next_index:02d}_{slug}.md", title, blurb, part))
        next_index += 1
    return numbered


def render_batch(title, blurb, exercises, counts):
    lines = [
        f"# {title}",
        "",
        blurb,
        "",
        "Ranked by how many protocol phases include the exercise. Each prompt is ready to paste into Grok.",
        "",
    ]
    for index, entry in enumerate(exercises, start=1):
        phases = counts[entry["id"]]
        prompt, start, finish = prompt_for(entry, phases)
        lines.extend([
            f"## {index}. {entry['name']}",
            "",
            f"- Exercise ID: `{entry['id']}`",
            f"- Protocol phases: {phases}",
            f"- Category: {entry.get('category') or 'unassigned'}",
            f"- Start: {start}",
            f"- Finish: {finish}",
            "",
            "```",
            prompt,
            "```",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def print_top(ranked, counts, limit=15):
    print("")
    print(f"{'Rank':<6}{'Phases':>8}  {'Exercise ID':<52} Title")
    print(f"{'-' * 6}{'-' * 8}  {'-' * 52} {'-' * 28}")
    for index, entry in enumerate(ranked[:limit], start=1):
        print(f"{index:<6}{counts[entry['id']]:>8}  {entry['id']:<52} {entry['name']}")


def main():
    catalog = load_json(CATALOG_PATH)
    protocols = load_json(REGISTRY_PATH)
    counts = phase_counts(protocols)
    pending = [entry for entry in catalog if entry.get("image_status") == "pending_asset"]
    pending.sort(key=lambda entry: (-counts[entry["id"]], entry["name"].lower(), entry["id"]))

    groups = {theme: [] for theme, *_rest in THEMES}
    for entry in pending:
        theme = classify(entry)
        groups.setdefault(theme, []).append(entry)

    files = assign_files(groups)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written_ids = []
    for filename, title, blurb, exercises in files:
        path = OUT_DIR / filename
        path.write_text(render_batch(title, blurb, exercises, counts), encoding="utf-8")
        written_ids.extend(entry["id"] for entry in exercises)
        print(f"{filename:<36} {len(exercises):>3}  {title}")

    missing = [entry["id"] for entry in pending if entry["id"] not in set(written_ids)]
    duplicate = len(written_ids) - len(set(written_ids))
    print_top(pending, counts)
    print("")
    print(f"{'Pending exercises':<40} {len(pending):>6}")
    print(f"{'Prompt cards written':<40} {len(written_ids):>6}")
    print(f"{'Batch files':<40} {len(files):>6}")
    print(f"{'Unassigned':<40} {len(missing):>6}")
    print(f"{'Duplicates':<40} {duplicate:>6}")
    if missing:
        for exercise_id in missing:
            print(f"  missing {exercise_id}")
    return 1 if missing or duplicate or len(pending) != 266 else 0


if __name__ == "__main__":
    raise SystemExit(main())
