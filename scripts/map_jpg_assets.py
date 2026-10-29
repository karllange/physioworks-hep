import json
import os
import re
EXERCISES_FILE = "exercises.json"
ASSETS_DIR = "assets"
with open(EXERCISES_FILE, "r") as f:
    exercises = json.load(f)
# Collect all jpg files in assets/
jpg_files = [f for f in os.listdir(ASSETS_DIR) if f.lower().endswith(".jpg")]
mapped_pairs = 0
mapped_singles = 0
for ex in exercises:
    ex_name = ex.get("name", "").lower()
    # Normalize exercise name into alphanumeric tokens
    tokens = [t for t in re.split(r'[^a-z0-9]+', ex_name) if len(t) > 2]
    
    # Identify matching start/finish or single frames
    start_img = None
    finish_img = None
    single_img = None
    
    for fname in jpg_files:
        fn_clean = re.sub(r'^\d+-', '', fname.lower())
        fn_clean_no_ext = os.path.splitext(fn_clean)[0]
        
        # Check token overlap
        matches = sum(1 for t in tokens if t in fn_clean_no_ext)
        if matches >= min(2, len(tokens)):
            if "-start" in fn_clean_no_ext:
                start_img = f"assets/{fname}"
            elif "-finish" in fn_clean_no_ext:
                finish_img = f"assets/{fname}"
            else:
                single_img = f"assets/{fname}"
    current_photos = ex.get("photos", [])
    
    # Check if current photos exist on disk
    has_valid_photo = any(os.path.exists(p) for p in current_photos)
    if not has_valid_photo:
        if start_img and finish_img:
            ex["photos"] = [start_img, finish_img]
            mapped_pairs += 1
        elif single_img:
            ex["photos"] = [single_img]
            mapped_singles += 1
with open(EXERCISES_FILE, "w") as f:
    json.dump(exercises, f, indent=2)
print(f"Updated {mapped_pairs} exercises with dual Start/Finish pairs.")
print(f"Updated {mapped_singles} exercises with single photo assets.")
