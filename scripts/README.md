# Data scripts

- `python validate-data.py` validates all checked-in JSON, provenance, season rollovers, semantic duplicates, rating bounds/consistency, and reference agreement; critical errors exit non-zero.
- `python audit-player-data.py` produces reports without mutating production data. Add `--apply` to archive inputs and apply only supported factual changes.
- `python generate-ratings.py INPUT OUTPUT --config config/rating-weights.json --overrides config/manual-rating-overrides.json --report report.json` creates ratings from documented position/season normalization. Every manual override requires a source and reason.
- `build-prototype-data.py` is retained only for historical prototype development. Do not run it over audited production data; it contains synthetic placeholder logic.
