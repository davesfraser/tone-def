from tonedef.retriever import search_by_descriptor, search_by_hardware

print("=== Hardware search (unchanged) ===")
for r in search_by_hardware("Dallas Arbiter Fuzz Face", n_results=3):
    print(f"  {r['component_name']:25s} ({r['category']}) dist={r['distance']:.3f}")

print()
print("=== Descriptor search (stratified) ===")
for desc in [
    "bright clean jangly chime with tremolo and spring reverb, low gain",
    "high gain scooped metal rhythm, tight low end, fizzy top end",
]:
    print(f"Query: {desc[:60]}")
    results = search_by_descriptor(desc)
    for r in results:
        print(f"  {r['component_name']:25s} ({r['category']}) dist={r['distance']:.3f}")
    print()
