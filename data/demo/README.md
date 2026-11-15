# Bajaur synthetic planning sandbox

`bajaur-v1.json` is the generated dataset and complete record of input values. All entries are fictional. The district label describes the demonstration's focus. Schematic positions have no geographic meaning. No population estimates, operational facility names, observed travel times, or individual records are used.

The generator uses Python's seeded random generator with seed `2026`. Its fixed 4 × 6 graph layout contains 24 clusters, 5 existing sites, 8 eligible candidate zones, and 38 bidirectional links. Entity values are integer weekly visits, weekly-equivalent PKR, or minutes. The disconnected test fixture lives outside this demo folder.

Regenerate with `uv run python scripts/seed.py` and check consistency with `uv run python scripts/seed.py --check`. The hash is SHA-256 over UTF-8 compact JSON with lexically sorted keys, excluding the `sha256` field. Nodes, communities and sites sort by ID. Edges sort by endpoints and direction after sorting the two endpoints of bidirectional links. Provenance sorts by canonical JSON. Assumptions retain their displayed order.

The default scenario uses PKR 300,000 per modeled week, at most two new units, a 45-minute threshold, 100% demand, 0% equity floor, and coverage-first policy. Mohmand and Khyber remain future expansion districts.
