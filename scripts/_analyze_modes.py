"""Analyze mode value distributions across all component parameters."""

import json
from collections import Counter

from tonedef.ngrr_parser import extract_xml2, parse_non_fix_components
from tonedef.paths import DATA_EXTERNAL, DATA_PROCESSED

preset_dir = DATA_EXTERNAL / "presets"
preset_files = sorted(preset_dir.glob("*.ngrr"))

all_values: dict[str, dict[str, list[float]]] = {}
for path in preset_files:
    xml2 = extract_xml2(path)
    if xml2 is None:
        continue
    for comp in parse_non_fix_components(xml2):
        name = comp["component_name"]
        if name not in all_values:
            all_values[name] = {}
        for param in comp["parameters"]:
            pid = param["param_id"]
            if pid not in all_values[name]:
                all_values[name][pid] = []
            all_values[name][pid].append(param["value"])

# Categorise all params by mode strength
strong = []  # mode >= 50%
moderate = []  # 25-49%
weak = []  # < 25%
total_params = 0

for comp_name, params in all_values.items():
    for pid, vals in params.items():
        total_params += 1
        counter = Counter(vals)
        total = len(vals)
        mode_val, mode_count = counter.most_common(1)[0]
        mode_pct = mode_count / total * 100
        unique = len(counter)

        entry = (comp_name, pid, total, unique, mode_val, mode_pct)
        if mode_pct >= 50:
            strong.append(entry)
        elif mode_pct >= 25:
            moderate.append(entry)
        else:
            weak.append(entry)

print(f"Total params across all components: {total_params}")
print(f"  Strong mode (>=50%): {len(strong)} ({len(strong) / total_params * 100:.0f}%)")
print(f"  Moderate mode (25-49%): {len(moderate)} ({len(moderate) / total_params * 100:.0f}%)")
print(f"  Weak mode (<25%): {len(weak)} ({len(weak) / total_params * 100:.0f}%)")
print()

# Compare: current default_value vs mode for Solid EQ
schema_path = DATA_PROCESSED / "component_schema.json"
with open(schema_path) as f:
    schema = json.load(f)

print("=== Solid EQ: current default_value vs mode vs median ===")
eq_params = schema["Solid EQ"]["parameters"]
for p in eq_params:
    pid = p["param_id"]
    vals = all_values.get("Solid EQ", {}).get(pid, [])
    if not vals:
        continue
    counter = Counter(vals)
    mode_val, mode_count = counter.most_common(1)[0]
    mode_pct = mode_count / len(vals) * 100
    med = p.get("stats", {}).get("median", "?")
    dv = p["default_value"]
    print(f"  {pid:>5}: default={dv:>8} | mode={mode_val:>8} ({mode_pct:.0f}%) | median={med}")

# Show the weakest mode params (all unique / near-unique)
print()
print("=== Weakest mode params (near-unique) - sample ===")
weak_sorted = sorted(weak, key=lambda x: x[5])
for comp, pid, total, unique, mval, mpct in weak_sorted[:15]:
    print(f"  {comp:>25}.{pid:<12} total={total:>4} unique={unique:>4} mode={mval} ({mpct:.0f}%)")
