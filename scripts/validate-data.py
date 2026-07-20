#!/usr/bin/env python3
"""Fail-fast validation for production NBA data and audit metadata."""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
errors, warnings = [], []
POSITIONS = {"PG", "SG", "SF", "PF", "C"}
ATTRS = ["offense", "defense", "shooting", "playmaking", "rebounding", "athleticism"]
WEIGHTS = {"offense": .28, "defense": .20, "shooting": .15, "playmaking": .15, "rebounding": .12, "athleticism": .10}
SEASON_RE = re.compile(r"^(\d{4})-(\d{2})$")


def load(name):
    try: return json.loads((DATA / name).read_text())
    except Exception as exc: errors.append(f"{name}: invalid JSON ({exc})"); return []


def normalized_name(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", value)


teams = load("teams.json")
current = load("current-players.json")
alltime = load("all-time-players.json")
version = load("data-version.json")
reference = load("player-season-reference.json")
team_required = {"id", "name", "city", "conference", "division", "baseOverall", "baseOffense", "baseDefense", "pace", "active", "theme"}
player_required = {"id", "name", "teamId", "era", "season", "positions", "overall", *ATTRS, "ratingMethod", "ratingConfidence", "active", "playingStatus", "careerStartYear", "careerEndYear", "factVerification"}
team_ids = []

for team in teams:
    missing = team_required - team.keys()
    if missing: errors.append(f"Team {team.get('id', '?')} missing {sorted(missing)}")
    team_ids.append(team.get("id"))
    if team.get("conference") not in {"East", "West"}: errors.append(f"{team.get('id')} invalid conference")
    for key in ["baseOverall", "baseOffense", "baseDefense", "pace"]:
        if not isinstance(team.get(key), int) or not 40 <= team[key] <= 105: errors.append(f"{team.get('id')}.{key} invalid")
if len(team_ids) != len(set(team_ids)): errors.append("Duplicate team IDs")
if sum(t.get("active") is True for t in teams) != 30: errors.append("There must be exactly 30 active teams")

ref_by_id = {r.get("playerId"): r for r in reference.get("players", [])} if isinstance(reference, dict) else {}
player_ids = []; semantic = defaultdict(list)
for filename, records, era in (("current-players.json", current, "current"), ("all-time-players.json", alltime, "all-time")):
    for player in records:
        pid = player.get("id", "?"); player_ids.append(pid)
        missing = player_required - player.keys()
        if missing: errors.append(f"{pid} missing {sorted(missing)}")
        name = str(player.get("name", "")).strip()
        if not name: errors.append(f"{pid} empty name")
        semantic[(filename, normalized_name(name), player.get("teamId"))].append(pid)
        if player.get("teamId") not in team_ids: errors.append(f"{pid} unknown team")
        if player.get("era") != era: errors.append(f"{pid} is in wrong file or has invalid era")
        match = SEASON_RE.match(str(player.get("season", "")))
        if not match: errors.append(f"{pid} invalid season format")
        elif (int(match.group(1)) + 1) % 100 != int(match.group(2)): errors.append(f"{pid} invalid season rollover")
        if era == "current" and player.get("season") != version.get("currentSeasonLabel"): errors.append(f"{pid} current season mismatch")
        positions = player.get("positions")
        if not isinstance(positions, list) or not positions or not set(positions) <= POSITIONS or len(positions) != len(set(positions)) or len(positions) > 3: errors.append(f"{pid} invalid positions")
        if isinstance(positions, list) and len(positions) == 3: warnings.append(f"{pid} has 3 eligible positions; manually verify")
        if isinstance(positions, list) and positions and set(positions) <= POSITIONS:
            order = {'PG': 0, 'SG': 1, 'SF': 2, 'PF': 3, 'C': 4}
            if max(order[p] for p in positions) - min(order[p] for p in positions) > 1: warnings.append(f"{pid} has a non-adjacent position combination; manually verify")
        for key in ["overall", *ATTRS]:
            if not isinstance(player.get(key), int) or not 40 <= player[key] <= 99: errors.append(f"{pid}.{key} invalid")
        if all(isinstance(player.get(k), int) for k in ATTRS) and isinstance(player.get("overall"), int):
            expected = round(sum(player[k] * WEIGHTS[k] for k in ATTRS))
            if abs(player["overall"] - expected) > 8: warnings.append(f"{pid} overall differs from weighted attributes by {abs(player['overall'] - expected)}")
        start, end = player.get("careerStartYear"), player.get("careerEndYear")
        if start is not None and (not isinstance(start, int) or not 1946 <= start <= 2026): errors.append(f"{pid} invalid careerStartYear")
        if end is not None and (not isinstance(end, int) or not 1947 <= end <= 2026): errors.append(f"{pid} invalid careerEndYear")
        if isinstance(start, int) and isinstance(end, int) and end <= start: errors.append(f"{pid} invalid career range")
        status = player.get("factVerification", {}).get("status")
        if status not in {"verified-secondary", "manual-review-required"}: errors.append(f"{pid} invalid fact verification status")
        if status == "manual-review-required": warnings.append(f"{pid} requires factual manual review")
        selected = ref_by_id.get(pid, {}).get("selectedSeason")
        if status == "verified-secondary":
            if not selected: errors.append(f"{pid} verified without season reference")
            elif selected.get("season") != player.get("season"): errors.append(f"{pid} season disagrees with reference")

if len(player_ids) != len(set(player_ids)): errors.append("Duplicate player IDs")
for key, ids in semantic.items():
    if len(ids) > 1: errors.append(f"Semantic duplicate in {key[0]}: {ids}")

for team in team_ids:
    for era, records in (("current", current), ("all-time", alltime)):
        covered = {pos for player in records if player.get("teamId") == team and player.get("active") for pos in player.get("positions", [])}
        missing = POSITIONS - covered
        if missing: warnings.append(f"{team} {era} lacks verified positional coverage: {sorted(missing)}")

for era, records in (("current", current), ("all-time", alltime)):
    values = [p["overall"] for p in records]
    if max(values) - min(values) < 8: warnings.append(f"{era} overall distribution is suspiciously narrow")
    counts = Counter(values)
    if counts.most_common(1)[0][1] > len(values) * .20: warnings.append(f"{era} overall distribution has excessive clustering")

for item in warnings: print("WARNING:", item)
for item in errors: print("ERROR:", item)
print(f"Validated {len(teams)} teams and {len(current) + len(alltime)} players: {len(errors)} errors, {len(warnings)} warnings")
sys.exit(1 if errors else 0)
