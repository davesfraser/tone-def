"""Quick check that Cab values in regenerated presets are integers."""

import re

from tonedef.ngrr_builder import extract_signal_chain
from tonedef.paths import GR7_PRESETS_DIR

names = [
    "tweedman_cab15_expected",
    "lead800_cab10_expected",
    "acbox_cab00_expected",
    "chicago_cab18_expected",
    "tweedman_cab00_acbox",
    "lead800_cab00",
]
for n in names:
    raw = extract_signal_chain(str(GR7_PRESETS_DIR / "cab_with_amp" / f"{n}.ngrr"))
    xml = raw.decode("utf-8", errors="replace")
    m = re.search(r'id="Cab"[^>]*value="([^"]+)"', xml)
    cab_val = m.group(1) if m else "NOT FOUND"
    print(f"{n}: Cab={cab_val}")
