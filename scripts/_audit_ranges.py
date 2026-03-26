"""Audit component_schema.json for parameters with values outside [0, 1]."""

import json
from pathlib import Path

schema = json.loads(Path("data/processed/component_schema.json").read_text("utf-8"))

outliers = []
for comp_name, comp in schema.items():
    for p in comp.get("parameters", []):
        stats = p.get("stats", {})
        mx = stats.get("max", 0)
        mn = stats.get("min", 0)
        dv = p.get("default_value", 0)
        if mx > 1.0 or mn < 0.0 or dv > 1.0 or dv < 0.0:
            outliers.append((comp_name, p["param_id"], p["param_name"], dv, mn, mx))

print(f"Parameters with values outside [0, 1]: {len(outliers)}")
print()
header = f"{'Component':<30} {'Param':<10} {'Name':<20} {'Default':>10} {'Min':>10} {'Max':>10}"
print(header)
print("-" * len(header))
for comp, pid, pname, dv, mn, mx in sorted(outliers):
    print(f"{comp:<30} {pid:<10} {pname:<20} {dv:>10.1f} {mn:>10.1f} {mx:>10.1f}")
