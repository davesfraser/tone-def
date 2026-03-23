# ToneDef

A chat-based tool for building guitar tone using your existing amp simulation
software. Describe the sound you want in plain language - ToneDef identifies
the likely signal chain, explains the reasoning, and maps the result to
components in your software.

---

## The problem it solves

Amp simulation software has become genuinely good. The gap is not the tools -
it is knowing what to load and how to configure it. Finding a John Mayer clean
tone means knowing he played a Dumble through specific pedals with particular
settings, then knowing which component in your software is the closest
equivalent, then knowing where to start with the knobs.

ToneDef is the knowledge layer that sits above your simulation software. It
does not replace Guitar Rig or a neural amp modeller - it tells you what to
load into them and why.

---

## What it does

- Takes a natural language tone description ("I want a warm edge-of-breakup
  blues tone like early Bonamassa but grittier")
- Identifies the likely real-world signal chain with provenance labels -
  distinguishing between documented gear, inferred choices, and plausible
  estimates
- Maps hardware to software equivalents where known
- Handles modifier queries ("grittier", "more compressed", "warmer") by
  reasoning about which part of the chain to adjust and how
- Retrieves supporting evidence via web search to validate recommendations

### What it does not do

ToneDef is not a tone replication tool. When you ask about a specific
recording, it performs gear archaeology - an informed reconstruction of what
was likely used and why it sounds the way it does. The output is reference
material and a starting point, not a recipe that will produce an identical
result. The gap between a documented signal chain and the sound of a specific
recording involves room acoustics, tape response, vintage component variation,
and a specific engineer's decisions on a specific day - none of which are
recoverable from gear documentation alone.

---

## Current state (v0.1)

- Natural language tone query via Streamlit interface
- Web retrieval via Tavily to validate and enrich recommendations
- Structured signal chain output with provenance labelling
  (DOCUMENTED / INFERRED / ESTIMATED per unit)
- Software mapping hints for Guitar Rig equivalents
- Modifier query support ("grittier", "more ambient", etc.)
- Fallback handling for multi-era artists, obscure recordings, and
  contradictory requirements

---

## Roadmap

### v0.2 - Guitar Rig preset output
Single-turn preset generation. The natural language chain recommendation is
accompanied by a valid Guitar Rig XML preset the user can load directly.
Requires schema discovery from parsed presets and a hardware-to-software
component mapping layer.

### v0.3 - Grounded and validated output
ChromaDB-backed retrieval of Guitar Rig parameter documentation, chunked by
component. Every component name in the generated preset is validated against
the indexed documentation before output. An LLM fallback handles unmapped
hardware references. Target: near-zero preset load failures.

v0.3 is the target release.

### v0.4 - Chat-based iterative refinement with conversation state and modification loop

...is planned but not committed.

---

## Tech stack

| Layer | Technology |
|---|---|
| Interface | Streamlit |
| LLM | Anthropic Claude (claude-sonnet-4-6) |
| Web retrieval | Tavily |
| Vector store (V3) | ChromaDB |
| Package management | uv |
| Linting | Ruff |

---

## Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/tonedef.git
cd tonedef

# Install dependencies
uv sync

# Set environment variables
cp .env.example .env
# Add your ANTHROPIC_API_KEY and TAVILY_API_KEY to .env

# Run the app
uv run streamlit run app.py
```

---

## Usage

Describe the tone you want in plain language. Queries can reference:

- A guitarist's general sound: `"I want a warm Stevie Ray Vaughan tone"`
- A specific recording: `"What gear was likely used on Comfortably Numb"`
- A modified reference: `"John Mayer Gravity live tone but grittier and
  more compressed"`
- A genre or era: `"Late 70s hard rock rhythm tone"`

The output identifies the signal chain with confidence labelling, notes
where recommendations are documented fact versus informed inference, and
suggests Guitar Rig equivalents where known.

---

## Prompt engineering notes

The system prompt is the core technical artifact of V1 and is worth
understanding if you are evaluating the project or contributing.

**Two-stage sonic analysis** - Before selecting equipment, the model builds
a reference profile of the target tone's gain structure, frequency balance,
dynamic behaviour, and spatial characteristics. If the query includes
descriptive modifiers, a second modifier mapping stage translates them into
specific chain adjustments before any equipment is selected. This is what
allows "grittier" to mean something precise rather than something generic.

**Provenance taxonomy** - Every unit in the chain is labelled DOCUMENTED,
INFERRED, or ESTIMATED. Individual parameter values are additionally marked
(estimated) where they are not drawn from a verified source. This
distinguishes between "BB King used a Lab Series L5" (documented) and "the
volume was probably around 3 o'clock" (estimated) rather than presenting
both with equal confidence.

**Gear archaeology framing** - FULL_PRODUCTION queries (specific recordings)
are explicitly framed as reference and education rather than replication.
The mastering guidance section instructs the model to describe audible
processing behaviour when specific studio equipment cannot be identified,
rather than fabricating a plausible-looking chain.

**Fallback handling** - Explicit cases for multi-era artists (build for the
most documented period only), contradictory requirements (flag and resolve
with a stated interpretation), and obscure recordings (best-effort with LOW
confidence).

---

## Project status

Active development. v0.1 complete. v0.2 in progress.

---
