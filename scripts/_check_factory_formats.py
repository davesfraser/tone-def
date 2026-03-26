"""Check how factory presets format non-0-1 parameters."""

import re
from pathlib import Path

from tonedef.ngrr_builder import extract_signal_chain

# VC 76 in Basic Tweedman
raw = extract_signal_chain("data/external/presets/Basic Tweedman.ngrr")
xml = raw.decode("utf-8", errors="replace")
for m in re.finditer(r'id="(R1|VUMode)"[^>]*value="([^"]+)"', xml):
    print(f"Basic Tweedman - VC 76 {m.group(1)}: {m.group(2)}")

# Find a preset with Flair
for p in Path("data/external/presets").glob("*.ngrr"):
    raw = extract_signal_chain(str(p))
    xml = raw.decode("utf-8", errors="replace")
    if "Flair" in xml:
        for m in re.finditer(r'id="(pitch|chord|mode)"[^>]*value="([^"]+)"', xml):
            print(f"{p.stem} - Flair {m.group(1)}: {m.group(2)}")
        break

# Find Maximizer
for p in Path("data/external/presets").glob("*.ngrr"):
    raw = extract_signal_chain(str(p))
    xml = raw.decode("utf-8", errors="replace")
    if "Maximizer" in xml:
        for m in re.finditer(r'id="(M|T|C)"[^>]*value="([^"]+)"', xml):
            print(f"{p.stem} - Maximizer {m.group(1)}: {m.group(2)}")
        break
