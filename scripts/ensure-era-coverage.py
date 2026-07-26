#!/usr/bin/env python3
"""Ensure every legitimate franchise/era pool can field PG, SG, SF, PF, and C.

The source is the audited Basketball Reference CSV mirror used by the player-data
audit. A decade is offered only when the franchise lineage recorded games in it.
New records and decade tags are derived solely from those franchise-season rows.
"""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = Path("/tmp/nba-stats/Player Per Game.csv")
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
DECADES = {"70s": (1970, 1979), "80s": (1980, 1989), "90s": (1990, 1999), "00s": (2000, 2009), "10s": (2010, 2019)}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_module("audit_player_data", ROOT / "scripts" / "audit-player-data.py")
expand = load_module("expand_player_data", ROOT / "scripts" / "expand-player-data.py")


def matching(candidates):
    """Return a unique player-name assignment for all five positions."""
    assigned = {}

    def place(position, seen):
        options = sorted((name for name, positions in candidates.items() if position in positions),
                         key=lambda name: (-len(candidates[name]), name))
        for name in options:
            if name in seen:
                continue
            seen.add(name)
            if name not in assigned or place(assigned[name], seen):
                assigned[name] = position
                return True
        return False

    if not all(place(position, set()) for position in POSITIONS):
        return None
    return {position: name for name, position in assigned.items()}


def decade_for_year(year):
    return next((tag for tag, (start, end) in DECADES.items() if start <= year <= end), None)


def lineage_rows(rows, team):
    return [row for row in rows if row["team"] in audit.LINEAGE[team]]


def supported_tags(rows, team):
    return sorted({tag for row in lineage_rows(rows, team) if (tag := decade_for_year(row["seasonEndYear"] - 1))},
                  key=lambda tag: list(DECADES).index(tag))


def ensure_position(player, position):
    if position in player["positions"]:
        return
    if len(player["positions"]) < 3:
        player["positions"].append(position)
    else:
        player["positions"] = [player["positions"][0], player["positions"][1], position]


def next_index(players, team):
    indices = []
    for player in players:
        if player["teamId"] != team:
            continue
        match = re.search(r"-(\d+)$", player["id"])
        if match:
            indices.append(int(match.group(1)))
    return max(indices, default=0) + 1


def source_pool(by_name, team, start, end):
    pool = {}
    for rows in by_name.values():
        relevant = [row for row in lineage_rows(rows, team) if start <= row["seasonEndYear"] - 1 <= end]
        if not relevant:
            continue
        name = relevant[0]["name"]
        pool[name] = {position for row in relevant for position in row["positions"] if position in POSITIONS}
    return pool


def add_or_update_player(players, references, by_name, team, era, name, required_position):
    key = audit.norm(name)
    rows = by_name[key]
    existing = next((player for player in players if player["teamId"] == team and audit.norm(player["name"]) == key), None)
    if existing:
        ensure_position(existing, required_position)
        if era != "current":
            existing["decadeTags"] = supported_tags(rows, team)
        return existing, False

    if era == "current":
        relevant = [row for row in lineage_rows(rows, team) if row["seasonEndYear"] == 2026 and required_position in row["positions"]]
    else:
        start, end = DECADES[era]
        relevant = [row for row in lineage_rows(rows, team) if start <= row["seasonEndYear"] - 1 <= end and required_position in row["positions"]]
    selected = max(relevant, key=lambda row: (expand.score(row), row["minutes"], row["games"], row["seasonEndYear"]))
    player = expand.make_player("current" if era == "current" else "all-time", team, selected, rows, next_index(players, team))
    ensure_position(player, required_position)
    if era != "current":
        player["decadeTags"] = supported_tags(rows, team)
    players.append(player)
    references.append(expand.reference_row(player, rows))
    return player, True


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing audited source dataset: {SOURCE}")
    by_name, years = audit.parse_csv_dataset(SOURCE)
    current = json.loads((DATA / "current-players.json").read_text())
    alltime = json.loads((DATA / "all-time-players.json").read_text())
    reference_data = json.loads((DATA / "player-season-reference.json").read_text())
    references = reference_data["players"]
    reference_by_id = {row["playerId"]: row for row in references}
    additions = 0

    # Refresh decade tags from actual seasons with the selected franchise lineage.
    for player in alltime:
        reference = reference_by_id.get(player["id"], {})
        player["decadeTags"] = supported_tags(reference.get("seasons", []), player["teamId"])

    # Current pools: all 30 active franchises must field a complete lineup.
    for team, codes in audit.LINEAGE.items():
        candidates = source_pool(by_name, team, 2025, 2025)
        lineup = matching(candidates)
        if not lineup:
            raise RuntimeError(f"Source has no complete current lineup for {team}")
        for position, name in lineup.items():
            _, added = add_or_update_player(current, references, by_name, team, "current", name, position)
            additions += added

    legitimate = {}
    for era, (start, end) in DECADES.items():
        legitimate[era] = []
        for team in audit.LINEAGE:
            candidates = source_pool(by_name, team, start, end)
            if not candidates:
                continue
            lineup = matching(candidates)
            if not lineup:
                raise RuntimeError(f"Source has no complete {team}/{era} lineup")
            legitimate[era].append(team)
            for position, name in lineup.items():
                _, added = add_or_update_player(alltime, references, by_name, team, era, name, position)
                additions += added

    reference_data["players"] = references
    reference_data["downloadedSeasonEndYears"] = years
    reference_data["generated"] = "2026-07-26"
    (DATA / "current-players.json").write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
    (DATA / "all-time-players.json").write_text(json.dumps(alltime, indent=2, ensure_ascii=False) + "\n")
    (DATA / "player-season-reference.json").write_text(json.dumps(reference_data, indent=2, ensure_ascii=False) + "\n")
    version = json.loads((DATA / "data-version.json").read_text())
    version["datasetVersion"] = "era-coverage-v1"
    version["lastUpdated"] = "2026-07-26"
    version["supportedDraftErasByTeam"] = {team: [era for era in DECADES if team in legitimate[era]] for team in audit.LINEAGE}
    (DATA / "data-version.json").write_text(json.dumps(version, indent=2) + "\n")
    print(json.dumps({"current": len(current), "allTime": len(alltime), "added": additions,
                      "legitimatePairs": sum(map(len, legitimate.values())), "byEra": legitimate}, indent=2))


if __name__ == "__main__":
    main()
