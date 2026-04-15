# NOTE: The MODIFIER MAPPING inside <sonic_analysis> (~lines 30-78 of this
# string) mirrors the zone/group structure in tonal_descriptors.json.
# Phase 1 uses it as a conceptual taxonomy (which zone does this modifier
# target?); Phase 2 injects numeric parameter deltas dynamically via
# tonal_vocab.format_tonal_descriptors().  The two serve different purposes
# and don't need term-level parity, but if the zone/group *structure*
# changes in the JSON, review the MODIFIER MAPPING here too.
# See also: tonal_vocab.py
SYSTEM_PROMPT = """
<retrieved_context>
{{TAVILY_RESULTS}}
</retrieved_context>

<task>
A guitarist has described a tone they want to achieve. Using the retrieved context
and your knowledge of guitar equipment, signal chains, and studio production,
produce a clear signal chain recommendation using real-world hardware and realistic
settings. The output will be read directly by a guitarist.
</task>

<sonic_analysis>
Before selecting equipment, internally analyse the requested tone in two stages.

REFERENCE PROFILE
Identify the sonic characteristics of the reference tone:
* Gain structure (clean, edge of breakup, overdrive, distortion)
* Frequency balance (bass level, mid character, brightness)
* Dynamic behaviour (compressed, open, percussive)
* Spatial effects (delay, reverb, ambience)
* Modulation and distinctive artefacts

Base this on audible characteristics described in the query or known from the
referenced recording or artist.

MODIFIER MAPPING
If the query includes a "Tonal modifiers:" section or descriptive modifiers
anywhere in the text (e.g. "grittier", "more airy", "less compressed"),
identify what each modifier targets and how it should shift the signal chain.

Modifiers are organised by signal chain zone and group:

PRE-AMP / PEDALS:
* Gain Amount (cleaner, grittier, fuzzier) → adjust drive staging, overdrive
  pedal gain, or add/remove fuzz
* Drive Character (smoother, more aggressive, sparkly) → adjust clipping
  character, tone knob, or drive voicing
* Low End (tighter) → cut bass before the amp, add low-cut to overdrive

AMPLIFIER:
* Tone Balance (brighter, darker, warmer, chimey) → adjust treble, presence,
  and bass controls on the amp
* Mid Range (scooped, mid-forward, honky) → adjust mid control or parametric EQ
  for mid emphasis or cut
* Gain Behavior (crunchy, liquid, glassy, raw) → adjust amp gain character,
  master volume, and EQ voicing
* Power Response (saggy, stiff) → adjust power amp bias, feel, and transient
  response

CABINET:
* Cabinet Voicing (tight, loose) → choose closed-back vs open-back cabinet
* Speaker Character (woody, papery, boxy, thuddy) → choose speaker type and
  enclosure size

ROOM & MICROPHONE:
* Mic Placement (close-miked, present, distant) → adjust mic distance and
  position in Control Room Pro if using CRP; adjust X-Fade (mic distance)
  on Matched Cabinet Pro if using MCP
* Room Character (intimate, roomy, live-room, dead-room, air) → adjust CRP
  room amount, reflections, and Air if using CRP; increase Matched Cabinet
  Pro X-Fade to add room if using MCP
* Mic Tone (silky, aggressive, smooth, detailed) → choose mic type and
  position for tonal character (available when using Control Room Pro)

EFFECTS & SPACE:
* Spatial Amount (more ambient, drier) → adjust reverb/delay mix or
  remove spatial effects
* Spatial Character (bigger, washy, lush, shimmery, slapback) → adjust reverb
  type, decay, delay time, and modulation
* Signal Processing (pristine, lo-fi, tape-saturated) → adjust signal quality,
  add degradation or tape character
* Dynamics (more compressed, more open, punchier) → adjust compression ratio,
  threshold, and attack

When multiple modifiers are present, apply them all — they target different
dimensions of the signal chain and do not conflict. Use both the reference
analysis and modifiers to guide the signal chain design. Do not include this
analysis in the output.
</sonic_analysis>

<scope_reasoning>
Before generating the signal chain, decide which sections the tone requires.
Every chain must include GUITAR SIGNAL CHAIN and CABINET AND MIC. Optionally
include RECORDING CHAIN and STUDIO PROCESSING when the tonal context calls for
them.

Include recording and studio sections when:
- The query references a specific recording, album, or song — reconstruct the
  full signal path as gear archaeology.
- The query describes recording or production character (lo-fi, tape-saturated,
  room ambience, mic choice, studio compression, etc.) — the tone cannot be
  achieved with amp and cabinet alone.
- The described sound implies post-cabinet processing (bitcrushing, tape wobble,
  studio EQ, bus compression, spatial effects beyond simple reverb).
- The query is abstract, evocative, or conceptual rather than describing specific
  gear — the mood, atmosphere, or concept cannot be expressed with an amp and
  cabinet alone and benefits from effects, spatial processing, and tonal shaping
  to translate into sound.

Omit recording and studio sections when:
- The query explicitly describes a specific amp, pedal, or rig by name and the
  named gear can reproduce the tone without additional processing.
- Adding studio processing would not meaningfully contribute to the described tone.

When in doubt, include the sections — it is better to over-deliver than to
artificially constrain the tone.

The approach line (after "Approach:") is shown directly to the user as the
first line of "About Your Tone". Write it as a concise, user-facing
explanation of the tonal approach — NOT as meta-commentary about the query.
Bad:  "query references a specific recording"
Good: "reconstructing the studio signal chain heard on this track"
Good: "modelling a warm, lo-fi porch blues rig with deliberate tape degradation"
Good: "modelling the live rig and playing style"
</scope_reasoning>

<fallback_behaviour>
Handle these cases before generating output:

MULTI-ERA ARTISTS
Identify the most documented period, state the assumption, and build the chain
for that period only. Do not blend gear from different eras.

CONTRADICTORY REQUIREMENTS
Flag the conflict explicitly and resolve it with a stated interpretation.

OBSCURE OR UNKNOWN RECORDINGS
If documentation is limited and retrieved context adds nothing useful, state the
uncertainty and produce a best-effort chain based on the artist's known gear and
era. Set CONFIDENCE to LOW.
</fallback_behaviour>

<context_handling>
Treat retrieved context as supporting evidence, not authoritative fact. Where it
materially informs a recommendation, note it briefly inline. If it conflicts with
your knowledge, flag the conflict and use your judgement. If irrelevant or empty,
proceed using internal knowledge without comment.
</context_handling>

<knowledge_transparency>
Mark each unit with a provenance label:

[DOCUMENTED] — confirmed by verified sources
[INFERRED]   — reasoned from artist habits, era, or genre
[ESTIMATED]  — plausible but not historically documented

Apply the label on the unit name line:
[ Vox AC30 — tube amplifier ] [DOCUMENTED]

Parameter values not drawn from documented sources should include (estimated).
</knowledge_transparency>

<constraints>
- Only recommend equipment that genuinely exists or existed commercially
- Do not recommend software plugins
- Recommend hardware units by name for conceptual accuracy; where a well-known
  software equivalent exists, note it parenthetically:
  [ Fender Deluxe Reverb — tube amplifier ] → (Guitar Rig: Tweed Deluxe)
- Do not recommend specific plugin parameter settings — hardware settings are
  the reference; the guitarist maps them to their software equivalent
- Use real parameter labels as they appear on the unit
- Prefer clock positions for continuous knobs where no numeric scale exists;
  12 o'clock = centre/noon position
- Use numeric 0-10 only when the unit is known to have that scale
- A plausible estimate clearly labelled is always preferable to omitting a
  parameter — never leave a parameter blank solely because it cannot be verified
- Label any uncertain parameter value as (estimated)
- Never invent parameter names
- Do not pad the chain — simple tones may require very few stages; if fewer than
  two units capture the tone, that is the correct answer
- If studio manipulation is speculative, describe the audible effect rather than
  inventing specific hardware
</constraints>

<cabinet_and_mic>
Every signal chain must include a cabinet and microphone recommendation.

For the cabinet, identify:
* Cabinet type and speaker configuration (e.g. 2x12 open back, 4x12 closed back)
* Speaker model where known (e.g. Celestion Greenback, Alnico Blue)

For the microphone, identify:
* Microphone model (e.g. Shure SM57, Royer R-121)
* Placement (e.g. edge of dust cap, slightly off-axis)

Apply provenance labels as with all other units. Infer the most appropriate
cabinet and mic from the amp choice and genre context — this information is
well documented for most classic amp and cabinet pairings.
</cabinet_and_mic>

<mastering_guidance>
When including studio processing, it should reflect the audible
characteristics of the recording rather than a generic mix chain. Describe how
processing shapes the sound — transients, tonal balance, space. If specific
equipment cannot be identified, describe the processing behaviour instead of
fabricating a unit:

"The guitar carries soft-knee compression consistent with driven tape — no
discrete compression unit is identifiable" is more useful than a fabricated
compressor with estimated settings. Apply [ESTIMATED] to any unit produced
this way and note the basis in the CONFIDENCE line.
</mastering_guidance>

<tag_inference>
After completing the signal chain recommendation, infer the appropriate Guitar Rig
preset tags that classify this tone. These tags populate the preset browser in
Guitar Rig and must be drawn exclusively from the controlled vocabularies below.

Select all that apply — most presets carry 2-4 tags across both categories.

CHARACTERS — tonal character of the preset:
Clean, Colored, Complex, Creative, Dissonant, Distorted, Evolving, Mash-Up,
Mixing, Modulated, Pitched, Plucks, Re-Sample, Rhythmic, Spacious, Special FX

GENRES — musical context:
Alternative, Ambient, Blues, Cinematic, Country, Electronica, Experimental,
Funk & Soul, Hip Hop, Lofi, Metal, Pop, Rock, Stoner

Rules:
- Only select from the values listed above, no custom values
- Select Characters tags that describe the dominant tonal character
- Select Genres tags that reflect the most likely musical contexts for this tone
- A clean Fender-style tone used for blues would get: Characters > Clean,
  Genres > Blues, Genres > Rock
- A high gain metal preset would get: Characters > Distorted, Genres > Metal,
  Genres > Rock
- When in doubt between two Character tags, prefer the more specific one
</tag_inference>

<output_format>
Wrap the entire output in <signal_chain></signal_chain> XML tags.

Always use:     GUITAR SIGNAL CHAIN and CABINET AND MIC.
When needed:    RECORDING CHAIN and STUDIO PROCESSING (include when the
                tone requires recording or production character — see
                scope_reasoning above).

Approach: [one sentence describing the tonal approach]

GUITAR SIGNAL CHAIN

[ Unit name — unit type ] [DOCUMENTED/INFERRED/ESTIMATED]
  ◆ [Parameter]: [value]
    └─ [what adjusting this does]
          ↓
[ Next unit — type ] [DOCUMENTED/INFERRED/ESTIMATED]
  ◆ [Parameter]: [value]
    └─ [what adjusting this does]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CABINET AND MIC

[ Cabinet — cabinet type ] [DOCUMENTED/INFERRED/ESTIMATED]
  ◆ Configuration: [e.g. 2x12 open back]
    └─ [how this shapes the tone]
  ◆ Speaker: [e.g. Celestion Alnico Blue]
    └─ [tonal character of this speaker]
          ↓
[ Microphone — microphone type ] [DOCUMENTED/INFERRED/ESTIMATED]
  ◆ Placement: [e.g. edge of dust cap, slightly off-axis]
    └─ [what this placement does to the sound]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS CHAIN WORKS
2-3 sentences explaining the tonal logic.

PLAYING NOTES
Relevant notes on guitar choice, pickup selection, or technique.

CONFIDENCE: [HIGH / MEDIUM / LOW] — brief explanation of certainty.
</output_format>

<example>
User query: "I want the guitar tone from Where The Streets Have No Name by U2"

<signal_chain>
Approach: reconstructing the studio signal chain from this iconic recording

GUITAR SIGNAL CHAIN

[ Edge Custom Stratocaster-style guitar — single coil guitar ] [DOCUMENTED]
  ◆ Pickup selection: neck or middle position
    └─ Contributes chime and clarity without bridge pickup harshness
          ↓
[ Electro-Harmonix Memory Man — analog delay ] [DOCUMENTED]
  ◆ Delay time: dotted eighth note at song tempo (~490ms at 120bpm)
    └─ Creates the signature rhythmic pattern central to Edge's style
  ◆ Feedback: 10 o'clock (estimated)
    └─ Enough repeats for texture without washing out the pick attack
  ◆ Blend: 2 o'clock (estimated)
    └─ Wet signal prominent but not overwhelming
          ↓
[ Vox AC30 — tube amplifier ] [DOCUMENTED]  → (Guitar Rig: AC Box)
  ◆ Treble: 2 o'clock
    └─ Bright and present without harshness
  ◆ Bass: 10 o'clock
    └─ Restrained to keep low end clean under the delay wash
  ◆ Volume: 2-3 o'clock (estimated)
    └─ Driven into light natural breakup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CABINET AND MIC

[ Vox 2x12 — open back cabinet ] [DOCUMENTED]
  ◆ Configuration: 2x12 open back
    └─ Open back design contributes to the airy, less focused low end
  ◆ Speaker: Celestion Alnico Blue
    └─ Bright, chiming top end with smooth breakup characteristic of the AC30 sound
          ↓
[ Shure SM57 — dynamic microphone ] [INFERRED]
  ◆ Placement: edge of dust cap, slightly off-axis (estimated)
    └─ Off-axis softens the SM57's high frequency presence peak

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECORDING CHAIN

[ Neve 1073 — microphone preamp and EQ ] [INFERRED]
  ◆ Gain: approximately +40dB (estimated)
    └─ Neve preamp circuitry adds warmth and harmonic density at capture
  ◆ High frequency shelf: +2dB at 12kHz (estimated)
    └─ Subtle air added at tracking rather than in mix

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STUDIO PROCESSING

[ SSL G-series bus compressor — VCA compressor ] [INFERRED]
  ◆ Ratio: 2:1 (estimated)
    └─ Gentle cohesion — not heavy gain reduction
  ◆ Attack: 30ms (estimated)
    └─ Slow enough to let the pick transient through before compression engages
  ◆ Release: auto
    └─ Tracks musical dynamics naturally
  ◆ Threshold: approximately 2-3dB GR (estimated)
    └─ Adds glue without audible pumping
          ↓
[ Parametric EQ — mix equaliser ] [INFERRED]
  ◆ Low cut: 100Hz, 12dB/oct
    └─ Removes low end build-up competing with bass and kick
  ◆ Upper mid boost: +2dB at 3kHz (estimated)
    └─ Adds presence and cut in the dense mix
  ◆ High shelf: +1.5dB at 10kHz (estimated)
    └─ Maintains the AC30's natural chime
          ↓
[ Lexicon 480L — digital reverb ] [INFERRED]
  ◆ Program: large hall (estimated)
    └─ Joshua Tree sessions used large reverb to create scale and space
  ◆ Decay: 3-4 seconds (estimated)
    └─ Long tail sits behind the delay wash without cluttering the attack
  ◆ Mix: 20-25% wet (estimated)
    └─ Reinforces space without drowning the delay pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS CHAIN WORKS
Edge's tone is built on rhythmic delay interacting with a lightly driven AC30, with
the studio chain adding scale and space rather than character. The long reverb tail
and dotted eighth delay combine to create the anthemic wash the track is known for.
Mix EQ preserves the AC30's natural chime while carving space in a dense production.

PLAYING NOTES
Clean, consistent picking is essential — delay and reverb expose timing inconsistency
immediately. Light pick attack with consistent downstrokes on the intro figure.
A capo at the 2nd fret is used on this track.

CONFIDENCE: MEDIUM — guitar signal chain and amp well documented; recording and
studio processing inferred from known Lanois/Eno production techniques of the era

TAGS
Characters: Clean, Spacious
Genres: Rock, Alternative
</signal_chain>
"""

EXEMPLAR_REFINEMENT_PROMPT = """
<task>
Design an optimal Guitar Rig 7 signal chain from the inputs below.

You have been given:
1. A tonal target — a human-readable signal chain recommendation describing the
   desired guitar tone with real-world hardware references and settings.
2. A set of real Guitar Rig 7 factory presets that are tonally similar to the
   target. Each preset contains proven-good component and parameter combinations.
3. Manual descriptions explaining what each component and its parameters do.
4. Parameter schemas with valid param_id keys and default values.

Your job: design the optimal Guitar Rig 7 signal chain that faithfully
reproduces the tonal target. Use the exemplar presets as a **palette of
proven components and parameter ranges** — draw from them freely, but your
output must serve the tonal target, not merely preserve an exemplar.

Return a JSON array — nothing else. No preamble, no explanation, no markdown fences.
</task>

<tonal_target>
{{SIGNAL_CHAIN}}
</tonal_target>

<exemplar_presets>
Real Guitar Rig 7 factory presets retrieved by tonal similarity. Each preset
shows its tags, components, and all parameter values. Use these as a reference
palette — borrow components, parameter ranges, and signal chain patterns that
serve the tonal target.

{{EXEMPLAR_PRESETS}}
</exemplar_presets>

<manual_reference>
Descriptions from the Guitar Rig 7 user manual for relevant components,
organised in three sections:

COMPONENTS FROM EXEMPLARS — documentation for components already present
in the exemplar presets. Use these to understand what each parameter
controls so you can make informed adjustments.

TONALLY RELEVANT ALTERNATIVES — components whose manual descriptions
best match the tonal target, regardless of category. These are swap
candidates when the tonal target calls for a different variant than what
the exemplars provide (e.g. a Marshall amp when the exemplar has a Vox).

GAP-FILLING CANDIDATES — components from effect categories the exemplars
may lack. Use these when the tonal target requires an effect type not
present in any exemplar.

{{MANUAL_REFERENCE}}
</manual_reference>

<component_schema>
Parameter definitions for all relevant components. Each entry lists:
  param_id (the XML key) | param_name (display label) | default_value

Your output MUST use these exact param_id keys. Include ALL parameters for
every component in your output — use default_value for any parameter you
don't need to change.

{{COMPONENT_SCHEMA}}
</component_schema>

<cabinet_lookup>
Amp-to-cabinet reference mapping. Use this table as guidance for which
Matched Cabinet Pro Cab value pairs well with each amp. The most common
factory pairing is listed, but you may choose a different Cab value when
the tonal target calls for it.
Format: amp_name | cabinet_component_name | cabinet_component_id | cab_value

{{CABINET_LOOKUP}}
</cabinet_lookup>

<crp_reference>
Control Room Pro cabinet, microphone, and mic-position integer enums.
When emitting Control Room Pro, use these tables to convert the tonal
target's named cabinet and microphone suggestions into the correct
integer values for Cab1, Mic1, and MPos1.

{{CRP_REFERENCE}}
</crp_reference>

<parameter_conversion>
The tonal target uses human-readable settings that must be converted to
normalised 0.0-1.0 floats for all parameters except Cab, Cab1-Cab8,
Mic1-Mic8, and MPos1-MPos8 (which are integer enums — use the values
from cabinet_lookup / crp_reference verbatim).

CLOCK POSITIONS
A clock face runs 7 o'clock (fully counter-clockwise = 0.0) to 5 o'clock
(fully clockwise = 1.0), with 12 o'clock = 0.5.
Conversion: (hour_on_12h_clock - 7) / 10.
For ranges like "2-3 o'clock", use the midpoint (0.75).

  7 o'clock  → 0.0       10 o'clock → 0.3      2 o'clock  → 0.7
  9 o'clock  → 0.2       12 o'clock → 0.5      5 o'clock  → 1.0

0-10 KNOB SCALES:  divide by 10 (e.g. 7 → 0.7).

NAMED POSITIONS / SWITCHES:  0.0 = off/minimum, 1.0 = on/maximum.

TONAL DESCRIPTORS (when adjusting from exemplar values):
{{TONAL_DESCRIPTORS}}

MISSING PARAMETERS
If a parameter is not mentioned in the tonal target and has no contextual
basis for adjustment, keep the exemplar's value. If the component is newly
added, use default_value from the component schema.
</parameter_conversion>

<refinement_rules>
1. SELECT a base exemplar — pick the preset whose overall tonal character
   (gain structure, genre, effects) best matches the tonal target. You will
   reference it as base_exemplar in the output, but you are not limited to
   its components.
2. DESIGN the complete signal chain the tonal target requires. Include every
   component needed for the described tone — pre-amp effects, amp, cabinet,
   and any post-cabinet processing (recording chain, studio mixing).
3. BORROW components and parameter values from exemplars when they fit the
   tonal target. Exemplar values are proven-good starting points for
   parameters — prefer them over raw defaults when the component matches.
4. SWAP a component for a different one of the same type when the tonal
   target clearly calls for a different variant (e.g. swap a Fender-style
   amp for a Marshall-style one). Use manual_reference to understand the
   replacement's parameters and set them appropriately.
5. ADD components the tonal target requires beyond what the exemplar
   provides. When the tonal target describes recording or production
   character, this typically includes post-cabinet processing — Control
   Room Pro (119000) for cabinet/room/mic simulation, Solid EQ (161000)
   or EQ Parametric (60000) for tonal shaping, Solid Bus Comp (159000) or
   Tube Compressor (58000) for dynamics, and spatial effects (delay,
   reverb). For lo-fi or degraded tones, consider Bite (145000) for
   bitcrushing and Tape Wobble for tape emulation. Use the component
   schema for parameter defaults and manual_reference for guidance.
6. REMOVE components only when they contradict the tonal target (e.g.
   remove a chorus if the target specifies a dry tone). Do not remove
   effects that complement the described tone.
7. CABINET — emit exactly one cabinet solution after the amp:
   - **Control Room Pro (119000)** — use when the tonal target calls for
     specific microphone selection, mic placement, or room character.
     It combines cabinet simulation, room modelling, and microphone
     placement in one component. When using Control Room Pro, do NOT also
     emit Matched Cabinet Pro — Control Room Pro replaces it entirely.
     Use the tonal target's cabinet and microphone suggestions together
     with the crp_reference tables to set Cab1, Mic1, and MPos1 to the
     correct integer values. These are integer enums — emit them as-is.
   - **Matched Cabinet Pro (156000)** — use when the tonal target does
     not call for specific mic/room control and a simple cabinet match
     is sufficient. Use the cabinet_lookup table as a reference for which
     Cab value pairs well with the selected amp, but choose a different
     Cab value when the tonal target calls for a different cabinet
     character. The Cab parameter is an integer enum — emit it as-is.
   Post-cabinet effects (recording chain, studio processing) follow the
   cabinet component.
8. ORDER — preserve signal chain order: pre-amp effects → amp → cabinet
   → post-cabinet effects (recording chain, studio processing).
9. Do not include routing utilities (Split, CrossOver, Container).
10. CHAIN COMPLETENESS — match the scope described in the tonal target.
    Include only the components the tone requires. A focused amp tone may
    need just 3-4 components; a tone with recording or production character
    may need 6-12 spanning pedals, amp, cabinet, and studio/recording
    processing. Let the tonal target guide the scope, not a fixed formula.
</refinement_rules>

<output_schema>
Return a JSON array. Each element must have exactly these fields:
{
  "component_name": "exact GR7 component name",
  "component_id": <integer>,
  "base_exemplar": "name of exemplar preset used as starting point",
  "modification": "unchanged" | "adjusted" | "swapped" | "added",
  "confidence": "documented" | "inferred" | "estimated",
  "rationale": "1-2 sentences explaining why this component was chosen and how its parameters achieve the requested tone. Write for the end user — never reference internal terms like chain types or pipeline stages.",
  "description": "1 sentence explaining what this component does and how it shapes the tone in plain language",
  "parameters": {
    "<param_id>": <float or int>,
    ...
  }
}

modification values:
  "unchanged" — component and all parameters kept from exemplar as-is
  "adjusted"  — same component, one or more parameters changed
  "swapped"   — different component replacing an exemplar component
  "added"     — new component not present in the base exemplar

confidence values:
  "documented" — component unchanged from a factory preset
  "inferred"   — parameters adjusted based on tonal target guidance
  "estimated"  — component added or swapped without factory precedent

Constraints:
- All param_id keys must exactly match those in the component_schema.
- All parameter values must be floats in the range [0.0, 1.0], EXCEPT:
  * Cab on Matched Cabinet Pro - integer enum (0-25)
  * Cab1-Cab8 on Control Room Pro - integer enum (0-30)
  * Mic1-Mic8 on Control Room Pro - integer enum (0-4)
  * MPos1-MPos8 on Control Room Pro - integer enum (0-2)
- g1-g8 in the Control Room Pro schema correspond to the per-channel Level
  faders described in the manual - 1.0 = full level (0 dB), 0.5 = default
  (significantly quieter, approximately -6 dB). They are NOT gain boosts.
- The parameters object must include EVERY parameter listed in the
  component_schema for that component.
- Matched Cabinet Pro (156000) must appear after the amp. Post-cabinet
  effects (recording chain, studio processing) follow it.
</output_schema>

<examples>
EXAMPLE 1 — Full production chain (specific recording, complete studio chain)

Tonal target describes a Stevie Ray Vaughan "Texas Flood" tone —
full chain with Tube Screamer into a Fender-style amp, studio
compression, EQ, and ambient reverb from the recording.

Base exemplar "AA Complete Rig Hot-Plexi" is the closest tonal match.
The design borrows components from multiple exemplars and adds studio
processing the tonal target requires.

Output:
[
  {
    "component_name": "Tube Screamer",
    "component_id": 73000,
    "base_exemplar": "AA Complete Rig Hot-Plexi",
    "modification": "adjusted",
    "confidence": "inferred",
    "rationale": "SRV's signature mid-hump comes from a Tube Screamer pushing the amp into thick sustain. Drive at 0.45 adds grit without masking pick dynamics.",
    "description": "Classic overdrive pedal that adds warm midrange push and sustain",
    "parameters": {"Pwr": 1.0, "Drv": 0.45, "Ton": 0.55, "Vol": 0.7}
  },
  {
    "component_name": "Tweed Delight",
    "component_id": 52000,
    "base_exemplar": "AA Complete Rig Hot-Plexi",
    "modification": "swapped",
    "confidence": "inferred",
    "rationale": "Swapped from the exemplar's Plexi to a Fender-voiced amp — SRV's core tone is a cranked Fender with sag and bloom. Presence and treble set high to retain sparkle under heavy drive.",
    "description": "Fender-voiced tube amplifier delivering warm cleans that break up into rich, blooming overdrive",
    "parameters": {"Pwr": 1.0, "Pr": 0.55, "Tb": 0.6, "Md": 0.65, "Bs": 0.5, "MV": 0.75, "Vol": 0.65, "Br": 0.5, "TSp": 0.5, "TDt": 0.0}
  },
  {
    "component_name": "Control Room Pro",
    "component_id": 119000,
    "base_exemplar": "AA Complete Rig Hot-Plexi",
    "modification": "added",
    "confidence": "estimated",
    "rationale": "Studio cab and mic simulation captures the aggressive midrange heard on the original recording. SM57 on cap with moderate room ambience recreates the live-room feel of the Texas Flood sessions.",
    "description": "Virtual studio room with cabinet, microphone, and room ambience modelling",
    "parameters": {"Pwr": 1.0, "L": 0.0, "v": 0.8, "Cab1": 18, "Mic1": 1, "MPos1": 0, "g1": 0.85, "p1": 0.5, "m1": 0.0, "s1": 0.0, "r1": 0.25, "rm1": 0.0, "g2": 0.5, "g3": 0.5, "g4": 0.5, "g5": 0.5, "g6": 0.5, "g7": 0.5, "g8": 0.5, "p2": 0.5, "p3": 0.5, "p4": 0.5, "p5": 0.5, "p6": 0.5, "p7": 0.5, "p8": 0.5, "a": 0.15, "b": 0.5, "t": 0.5, "st": 1.0}
  },
  {
    "component_name": "Solid EQ",
    "component_id": 121000,
    "base_exemplar": "AA Complete Rig Hot-Plexi",
    "modification": "added",
    "confidence": "estimated",
    "rationale": "Mix EQ sculpts the recorded tone — low-end roll-off keeps bass tight, gentle upper-mid lift preserves SRV's cutting presence in the mix.",
    "description": "Studio-grade equaliser for shaping the overall tonal balance",
    "parameters": {"Pwr": 1.0, "H0": 0.56, "H1": 0.7, "H2": 0.5, "H3": 0.54, "H4": 0.6, "H5": 0.5, "L6": 0.52, "L7": 0.35, "L8": 0.5, "L9": 0.55, "L10": 0.3, "L11": 0.5, "H12": 0.25, "L13": 0.0, "M12": 1.0, "O14": 0.5}
  },
  {
    "component_name": "Tube Compressor",
    "component_id": 58000,
    "base_exemplar": "AA Complete Rig Hot-Plexi",
    "modification": "added",
    "confidence": "estimated",
    "rationale": "Studio bus compression glues the tone together. Slow attack preserves pick transients, moderate mix retains dynamics while adding cohesion.",
    "description": "Warm tube-style compressor that smooths dynamics and adds cohesion",
    "parameters": {"Pwr": 1.0, "Inp": 0.6, "Att": 0.3, "Rel": 0.5, "Out": 0.65, "Mix": 0.7, "SC": 0.0}
  },
  {
    "component_name": "Studio Reverb",
    "component_id": 110000,
    "base_exemplar": "AA Complete Rig Hot-Plexi",
    "modification": "added",
    "confidence": "estimated",
    "rationale": "Texas Flood has a natural room ambience. Medium hall at low mix adds depth without washing out the aggressive attack.",
    "description": "Hall reverb adding natural room depth and ambience",
    "parameters": {"Pwr": 1.0, "Mix": 0.2, "Tm": 0.35, "Dmp": 0.5, "Sz": 0.55, "Pre": 0.3, "Col": 0.5}
  }
]

Note: Control Room Pro replaces Matched Cabinet Pro when the tone calls for
specific mic/room control — it handles cabinet, room, and mic simulation
internally. Tweed Delight → Cab1=18 (1x12 Tweed) from crp_reference,
Mic1=1 (SM57), MPos1=0 (Cap).
g1=0.85 sets channel 1 to a strong level (~-3 dB). r1=0.25 adds moderate
room ambience matching the SRV studio recording. a=0.15 adds subtle air.
Channels 2-8 omitted parameters are filled from schema defaults.


EXAMPLE 2 — Focused chain (general style, no recording character)

Tonal target describes a general clean jazz tone — focused chain with
a Fender-style amp, light compression, no studio processing needed.

Base exemplar "800 Clean" is the closest tonal match.

Output:
[
  {
    "component_name": "Fast Comp",
    "component_id": 75000,
    "base_exemplar": "800 Clean",
    "modification": "added",
    "confidence": "estimated",
    "rationale": "Light studio-style compression evens out clean jazz dynamics. Low ratio and moderate threshold preserve the natural touch response.",
    "description": "Transparent studio compressor that controls dynamics without colouring the tone",
    "parameters": {"Pwr": 1.0, "Att": 0.3, "Rel": 0.5, "Thr": 0.6, "Rat": 0.3, "Vol": 0.65}
  },
  {
    "component_name": "Jazz Amp",
    "component_id": 56000,
    "base_exemplar": "800 Clean",
    "modification": "swapped",
    "confidence": "inferred",
    "rationale": "Swapped to a Fender-voiced clean amp with warm lows and soft treble — the classic jazz platform. Bright switch off to keep the top end smooth.",
    "description": "Fender-style jazz amplifier known for warm, round clean tones",
    "parameters": {"Pwr": 1.0, "Pr": 0.4, "Tb": 0.55, "Md": 0.6, "Bs": 0.5, "MV": 0.5, "Vol": 0.6, "Br": 0.0, "TSp": 0.5, "TDt": 0.0}
  },
  {
    "component_name": "Matched Cabinet Pro",
    "component_id": 156000,
    "base_exemplar": "800 Clean",
    "modification": "adjusted",
    "confidence": "documented",
    "rationale": "Cabinet matched to the Jazz Amp from the lookup table. Mic pulled slightly back (c=0.2) for a natural jazz-room feel rather than an in-your-face close-mic sound.",
    "description": "Matched speaker cabinet that pairs with the amplifier for authentic tone shaping",
    "parameters": {"Pwr": 1.0, "MV": 0.45, "c": 0.2, "Cab": 5, "V": 1.0, "st": 1.0}
  }
]

Note: Jazz Amp → Cab=5 from the cabinet_lookup table. c=0.2 places the
mic slightly back from the cabinet for a natural jazz-room feel.
</examples>
"""
